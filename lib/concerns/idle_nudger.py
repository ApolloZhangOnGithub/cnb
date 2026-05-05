"""IdleNudger — nudge idle sessions to continue working."""

from lib.common import is_suspended

from .base import Concern
from .config import DispatcherConfig
from .helpers import get_dev_sessions, is_claude_running, log, tmux_ok, tmux_send
from .idle_detector import IdleDetector


class IdleNudger(Concern):
    interval = 5
    COOLDOWN = 300

    def __init__(self, cfg: DispatcherConfig, idle: IdleDetector) -> None:
        super().__init__()
        self.cfg = cfg
        self.idle = idle
        self.last_nudge: dict[str, int] = {}

    def tick(self, now: int) -> None:
        for name in get_dev_sessions(self.cfg):
            if is_suspended(name, self.cfg.suspended_file):
                continue
            sess = f"{self.cfg.prefix}-{name}"
            if not tmux_ok("has-session", "-t", sess) or not is_claude_running(sess):
                continue
            if not self.idle.is_idle(sess):
                continue
            if (now - self.last_nudge.get(name, 0)) < self.COOLDOWN:
                continue

            log(f"{name}: idle, nudging autonomous loop")
            tmux_send(
                sess,
                f"继续工作。检查你的 OKR ({self.cfg.okr_dir}/{name}.md)，推进你的活跃 KR。自己决定优先级。",
            )
            self.last_nudge[name] = now
