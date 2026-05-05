"""HealthChecker — periodic status report + team idle detection."""

import time

from lib.common import date_to_epoch, is_suspended

from .base import Concern
from .config import DispatcherConfig
from .coral_manager import CoralManager
from .coral_poker import CoralPoker
from .helpers import board_send, db, get_dev_sessions, is_claude_running, log, tmux_ok


class HealthChecker(Concern):
    INITIAL = 600
    MAX = 3600
    IDLE_THRESHOLD = 1800

    def __init__(self, cfg: DispatcherConfig, poker: CoralPoker, coral: CoralManager) -> None:
        super().__init__()
        self.cfg = cfg
        self.interval = self.INITIAL
        self.poker = poker
        self.coral = coral
        self.last_idle_alert: int = 0

    def tick(self, now: int) -> None:
        parts = []
        for name in get_dev_sessions(self.cfg):
            on = "on" if tmux_ok("has-session", "-t", f"{self.cfg.prefix}-{name}") else "off"
            parts.append(f"{name}:{on}")
        status = " ".join(parts)

        log(f"Health check (interval:{self.interval}s): {status}")
        self.poker.poke(f"[Dispatcher] 健康巡检 {time.strftime('%H:%M:%S')}: {status}")
        self.interval = min(self.interval * 2, self.MAX)
        self._check_team_idle(now)

    def _check_team_idle(self, now: int) -> None:
        if not self.cfg.board_db.exists():
            return
        idle_list: list[str] = []
        total = 0
        d = db(self.cfg)

        for name in get_dev_sessions(self.cfg):
            if is_suspended(name, self.cfg.suspended_file):
                continue
            sess = f"{self.cfg.prefix}-{name}"
            if not tmux_ok("has-session", "-t", sess) or not is_claude_running(sess):
                continue
            if self.coral.in_grace_period(name, now):
                continue

            total += 1
            try:
                updated = d.scalar("SELECT updated_at FROM sessions WHERE name=?", (name,)) or ""
            except Exception:
                continue
            if updated:
                age = now - date_to_epoch(updated)
                if age > self.IDLE_THRESHOLD:
                    idle_list.append(f"{name}({age}s)")

        if idle_list and len(idle_list) == total and (now - self.last_idle_alert) > 3600:
            log(f"All sessions idle: {' '.join(idle_list)}")
            board_send(
                self.cfg,
                "lead",
                f"[Dispatcher] 全员空闲超过 {self.IDLE_THRESHOLD // 60} 分钟:{' '.join(idle_list)}。可能需要分配工作。",
            )
            self.last_idle_alert = now
