"""CoralManager — ensure dispatcher Claude session is running."""

import time

from lib.common import is_suspended

from .base import Concern
from .config import DispatcherConfig
from .helpers import is_claude_running, log, tmux, tmux_send


class CoralManager(Concern):
    interval = 5
    BOOT_WAIT = 8
    BOOT_GRACE = 120

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.boot_times: dict[str, int] = {}

    def record_boot(self, name: str) -> None:
        self.boot_times[name] = int(time.time())

    def in_grace_period(self, name: str, now: int) -> bool:
        bt = self.boot_times.get(name)
        return bt is not None and (now - bt) < self.BOOT_GRACE

    def tick(self, now: int) -> None:
        dev_alive = any(is_claude_running(f"{self.cfg.prefix}-{s}") for s in self.cfg.dev_sessions)
        if dev_alive and not is_suspended("dispatcher", self.cfg.suspended_file):
            self._ensure()

    def _ensure(self) -> None:
        if is_claude_running(self.cfg.coral_sess):
            return
        log("Starting Coral...")
        tmux("kill-session", "-t", self.cfg.coral_sess)
        tmux("new-session", "-d", "-s", self.cfg.coral_sess, "-x", "200", "-y", "50")
        tmux_send(self.cfg.coral_sess, f"cd '{self.cfg.project_root}'")
        time.sleep(0.5)
        tmux_send(
            self.cfg.coral_sess,
            "claude --name dispatcher --append-system-prompt "
            "'你是 Coral。启动后运行 cat dispatcher-role.md，然后等指令。回复不超过3行。'",
        )
        self.record_boot("dispatcher")
        log(f"Coral boot sent, waiting for Claude process (max {self.BOOT_WAIT}s)...")
        self._wait_until_ready()

    def _wait_until_ready(self) -> None:
        """Poll until the Claude process is running, or timeout after BOOT_WAIT."""
        import time as _time
        deadline = _time.monotonic() + self.BOOT_WAIT
        while _time.monotonic() < deadline:
            if is_claude_running(self.cfg.coral_sess):
                elapsed = self.BOOT_WAIT - (deadline - _time.monotonic())
                log(f"Coral ready after {elapsed:.1f}s")
                return
            _time.sleep(1)
        log(f"WARNING: Coral not ready after {self.BOOT_WAIT}s, will retry next tick")
