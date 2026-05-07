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


class TimeAnnouncer(Concern):
    interval = 30

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg
        from datetime import datetime as dt

        self.last_hour = dt.now().hour

    def tick(self, now: int) -> None:
        from datetime import datetime as dt

        d = dt.now()
        if d.minute != 0 or d.hour == self.last_hour:
            return
        self.last_hour = d.hour
        ts = d.strftime("%Y-%m-%d %H:%M")

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
