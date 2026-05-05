"""IdleKiller — kill sessions idle >30min."""

from .base import Concern
from .config import DispatcherConfig
from .coral_manager import CoralManager
from .helpers import board_send, get_dev_sessions, is_claude_running, log, tmux, tmux_ok
from .idle_detector import IdleDetector


class IdleKiller(Concern):
    interval = 5
    THRESHOLD = 1800

    def __init__(self, cfg: DispatcherConfig, idle: IdleDetector, coral: CoralManager) -> None:
        super().__init__()
        self.cfg = cfg
        self.idle = idle
        self.coral = coral
        self.idle_since: dict[str, int] = {}

    def tick(self, now: int) -> None:
        for name in get_dev_sessions(self.cfg):
            sess = f"{self.cfg.prefix}-{name}"
            if not tmux_ok("has-session", "-t", sess) or not is_claude_running(sess):
                self.idle_since.pop(name, None)
                continue

            if name not in self.coral.boot_times:
                self.coral.record_boot(name)
            if self.coral.in_grace_period(name, now):
                continue

            if self.idle.is_idle(sess):
                since = self.idle_since.setdefault(name, now)
                if (now - since) >= self.THRESHOLD:
                    log(f"{name}: idle {now - since}s (>30min), killing session")
                    tmux("kill-session", "-t", sess)
                    self.idle_since.pop(name, None)
                    board_send(self.cfg, "All", f"[Dispatcher] {name} 闲置超过 30 分钟，已终止。")
            else:
                self.idle_since.pop(name, None)
