"""Notifications: time announcements, bug SLA checks."""

import subprocess

from .base import Concern
from .config import DispatcherConfig
from .coral import CoralPoker
from .helpers import board_send, db, log


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
