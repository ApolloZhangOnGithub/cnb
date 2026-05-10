"""Notifications: inbox nudging, time announcements, bug SLA checks, queued message flushing."""

import subprocess

from .base import Concern
from .config import DispatcherConfig
from .coral import CoralPoker
from .helpers import board_send, db, get_dev_sessions, is_claude_running, log, tmux, tmux_ok, tmux_send


class InboxNudger(Concern):
    interval = 5

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg

    def nudge_if_unread(self, name: str) -> None:
        if not self.cfg.board_db.exists():
            return
        try:
            unread = db(self.cfg).scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,)) or 0
        except Exception:
            return
        if unread <= 0:
            return

        sess = f"{self.cfg.prefix}-{name}"
        if not tmux_ok("has-session", "-t", sess) or not is_claude_running(sess):
            return

        log(f"INBOX: {name} has {unread} unread -> nudging")
        tmux_send(sess, f"./board --as {name} inbox")

    def tick(self, now: int) -> None:
        for name in get_dev_sessions(self.cfg):
            self.nudge_if_unread(name)


class ManagerCloseoutEscalator(Concern):
    """Escalate manager sessions that keep reading reports without closing out."""

    interval = 15
    STUCK_TICKS = 3
    COOLDOWN = 300

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.streaks: dict[str, int] = {}
        self.last_escalation: dict[str, int] = {}

    @staticmethod
    def _is_manager_session(name: str) -> bool:
        return name == "lead" or "manager" in name

    def _count(self, sql: str, params: tuple[str, ...]) -> int:
        value = db(self.cfg).scalar(sql, params) or 0
        return int(value)

    def _is_closeout_stall(self, name: str) -> bool:
        unread = self._count("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,))
        own_open = self._count(
            "SELECT COUNT(*) FROM tasks WHERE session=? AND status IN ('active', 'pending')",
            (name,),
        )
        other_open = self._count(
            "SELECT COUNT(*) FROM tasks WHERE session!=? AND status IN ('active', 'pending')",
            (name,),
        )
        return unread > 0 and own_open > 0 and other_open == 0

    def _escalate(self, name: str) -> None:
        board_send(
            self.cfg,
            name,
            "closeout escalation：所有执行子任务看起来已收口，但你的管理任务仍 active 且 inbox 未读。"
            "请立即汇总执行同学报告、说明剩余风险，随后 ack inbox 并 task done；"
            "如果不能收口，请明确发消息给 device-supervisor 说明 blocker。",
        )
        log(f"CLOSEOUT escalation sent to {name}")

    def tick(self, now: int) -> None:
        if not self.cfg.board_db.exists():
            return

        for name in get_dev_sessions(self.cfg):
            if not self._is_manager_session(name):
                continue
            sess = f"{self.cfg.prefix}-{name}"
            if not tmux_ok("has-session", "-t", sess) or not is_claude_running(sess):
                self.streaks.pop(name, None)
                continue

            try:
                stalled = self._is_closeout_stall(name)
            except Exception:
                self.streaks.pop(name, None)
                continue
            if not stalled:
                self.streaks.pop(name, None)
                continue

            streak = self.streaks.get(name, 0) + 1
            self.streaks[name] = streak
            if streak < self.STUCK_TICKS:
                continue
            if (now - self.last_escalation.get(name, 0)) < self.COOLDOWN:
                continue

            self._escalate(name)
            self.last_escalation[name] = now


class TimeAnnouncer(Concern):
    interval = 30

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg
        from datetime import datetime as dt

        self.last_hour = dt.now().hour

    def _already_sent(self, hour_ts: str) -> bool:
        """Check DB for a clock message already sent this hour (prevents duplicate announcements)."""
        try:
            count = db(self.cfg).scalar(
                "SELECT COUNT(*) FROM messages WHERE sender='dispatcher' AND body LIKE '%[Clock]%' AND ts LIKE ?",
                (f"{hour_ts}%",),
            )
            return bool(count)
        except Exception:
            return False

    def tick(self, now: int) -> None:
        from datetime import datetime as dt

        d = dt.now()
        if d.minute != 0 or d.hour == self.last_hour:
            return
        self.last_hour = d.hour
        ts = d.strftime("%Y-%m-%d %H:%M")

        if self._already_sent(ts):
            log(f"Hourly announcement: {d.hour}:00 (already sent, skipping)")
            return

        if d.hour == 9:
            board_send(
                self.cfg,
                "All",
                f"[Clock] {ts} ({d.strftime('%A')}) — 新一天。检查 KR 列表，确认优先级。",
            )
            log("Daily announcement sent")
        else:
            board_send(self.cfg, "All", f"[Clock] 现在是 {ts}。")
            log(f"Hourly announcement: {d.hour}:00")


class QueuedMessageFlusher(Concern):
    """Detect queued messages in idle agent panes and send Enter to flush them.

    When nudge injects a command while Claude Code is busy, it gets queued.
    The pane shows 'queued message' and waits for Enter. This concern
    auto-flushes that queue when the agent becomes idle.
    """

    interval = 5
    COOLDOWN = 30

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.last_flush: dict[str, int] = {}

    def tick(self, now: int) -> None:
        for name in get_dev_sessions(self.cfg):
            sess = f"{self.cfg.prefix}-{name}"
            if not tmux_ok("has-session", "-t", sess) or not is_claude_running(sess):
                continue
            if (now - self.last_flush.get(name, 0)) < self.COOLDOWN:
                continue

            content = tmux("capture-pane", "-t", sess, "-p") or ""
            if "queued message" not in content.lower():
                continue

            lines = content.splitlines()[-5:]
            has_empty_prompt = any(line.rstrip() == "❯" for line in lines)
            if not has_empty_prompt:
                continue

            log(f"{name}: flushing queued message")
            subprocess.run(["tmux", "send-keys", "-t", sess, "Enter"], capture_output=True, timeout=5)
            self.last_flush[name] = now


class BugSLAChecker(Concern):
    interval = 600

    def __init__(self, cfg: DispatcherConfig, poker: CoralPoker) -> None:
        super().__init__()
        self.cfg = cfg
        self.poker = poker

    def tick(self, now: int) -> None:
        try:
            r = subprocess.run(
                [self.cfg.board_sh, "bug", "overdue"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            overdue = r.stdout.strip()
        except Exception:
            return
        if overdue and "No overdue" not in overdue:
            log(f"Bug SLA alert: {overdue}")
            self.poker.poke(f"[Dispatcher] Bug SLA 超时: {overdue}")
