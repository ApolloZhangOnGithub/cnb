"""Coral: dispatcher session lifecycle management and heartbeat."""

import os
import re
import shlex
import time

from lib.common import is_suspended
from lib.swarm import CODEX_PERMISSION_FLAGS

from .base import Concern
from .config import DispatcherConfig
from .helpers import db, is_claude_running, log, pane_md5, tmux, tmux_ok, tmux_send


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
        tmux_send(self.cfg.coral_sess, f"cd '{self.cfg.project_root}' && export CNB_PROJECT='{self.cfg.project_root}'")
        time.sleep(0.5)
        tmux_send(self.cfg.coral_sess, self._agent_cmd())
        self.record_boot("dispatcher")
        log(f"Coral boot sent, waiting for agent process (max {self.BOOT_WAIT}s)...")
        self._wait_until_ready()

    def _agent_cmd(self) -> str:
        prompt = "你是 Coral。启动后运行 cat dispatcher-role.md，然后等指令。回复不超过3行。"
        agent = os.environ.get("SWARM_AGENT") or os.environ.get("CNB_AGENT", "claude")
        if agent == "codex":
            flags = " ".join(CODEX_PERMISSION_FLAGS)
            return f"codex {flags} --cd {shlex.quote(str(self.cfg.project_root))} {shlex.quote(prompt)}"
        return f"claude --name dispatcher --append-system-prompt {shlex.quote(prompt)}"

    def _wait_until_ready(self) -> None:
        import time as _time

        deadline = _time.monotonic() + self.BOOT_WAIT
        while _time.monotonic() < deadline:
            if is_claude_running(self.cfg.coral_sess):
                elapsed = self.BOOT_WAIT - (deadline - _time.monotonic())
                log(f"Coral ready after {elapsed:.1f}s")
                return
            _time.sleep(1)
        log(f"WARNING: Coral not ready after {self.BOOT_WAIT}s, will retry next tick")


class CoralPoker(Concern):
    interval = 120

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.last_poke: int = int(time.time())

    def poke(self, msg: str) -> bool:
        if not tmux_ok("has-session", "-t", self.cfg.coral_sess) or not is_claude_running(self.cfg.coral_sess):
            return False

        content = tmux("capture-pane", "-t", self.cfg.coral_sess, "-p") or ""
        prompts = [l for l in content.splitlines() if l.startswith("❯")]
        if prompts and re.match(r"^❯ .{3,}", prompts[-1]):
            log("Coral: skip (typing)")
            return False

        h1 = pane_md5(self.cfg.coral_sess)
        time.sleep(1)
        if h1 != pane_md5(self.cfg.coral_sess):
            log("Coral: skip (busy)")
            return False

        log("Coral: poking")
        tmux_send(self.cfg.coral_sess, msg)
        self.last_poke = int(time.time())
        return True

    def tick(self, now: int) -> None:
        unread = 0
        if self.cfg.board_db.exists():
            try:
                unread = (
                    db(self.cfg).scalar(
                        "SELECT COUNT(*) FROM inbox WHERE session=? AND read=0",
                        (self.cfg.dispatcher_session,),
                    )
                    or 0
                )
            except Exception:
                pass

        if unread > 0:
            self.poke(f"[Dispatcher] 你有 {unread} 条未读消息")
        elif (now - self.last_poke) >= self.interval:
            self.poke(f"[Dispatcher] heartbeat {time.strftime('%H:%M:%S')}")
