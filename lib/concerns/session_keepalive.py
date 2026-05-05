"""SessionKeepAlive — detect dead dev sessions."""

from lib.common import is_suspended

from .base import Concern
from .config import DispatcherConfig
from .helpers import get_dev_sessions, is_claude_running, log, tmux_ok


class SessionKeepAlive(Concern):
    interval = 5

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg

    def tick(self, now: int) -> None:
        for name in get_dev_sessions(self.cfg):
            if is_suspended(name, self.cfg.suspended_file):
                continue
            sess = f"{self.cfg.prefix}-{name}"
            if tmux_ok("has-session", "-t", sess) and not is_claude_running(sess):
                log(f"{name}: agent exited, NOT restarting (idle policy)")
