"""Idle detection and killing for dispatcher sessions."""

import re

from .base import Concern
from .config import DispatcherConfig
from .coral import CoralManager
from .helpers import (
    board_send,
    get_dev_sessions,
    has_tool_process,
    is_claude_running,
    log,
    pane_md5,
    tmux,
    tmux_ok,
)


class IdleDetector(Concern):
    interval = 5

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.cache: dict[str, str] = {}  # sess -> "idle" | "busy"
        self._prev_snap: dict[str, str] = {}  # sess -> md5 from previous tick

    def is_idle(self, sess: str) -> bool:
        return self.cache.get(sess) == "idle"

    def tick(self, now: int) -> None:
        self.cache.clear()
        raw = tmux("list-sessions", "-F", "#{session_name}")
        if not raw:
            self._prev_snap.clear()
            return

        all_sessions = [s for s in raw.splitlines() if s.startswith(f"{self.cfg.prefix}-")]
        need_snapshot: list[str] = []

        for sess in all_sessions:
            pane = tmux("capture-pane", "-t", sess, "-p") or ""
            prompts = [l for l in pane.splitlines() if l.startswith("❯")]
            if prompts and re.match(r"^❯ .{3,}", prompts[-1]):
                self.cache[sess] = "busy"
                continue
            if has_tool_process(sess):
                self.cache[sess] = "busy"
                continue
            need_snapshot.append(sess)

        current_snap: dict[str, str] = {}
        for sess in need_snapshot:
            md5 = pane_md5(sess)
            current_snap[sess] = md5
            if sess in self._prev_snap and self._prev_snap[sess] == md5:
                self.cache[sess] = "idle"
            else:
                self.cache[sess] = "busy"

        self._prev_snap = {s: pane_md5(s) for s in all_sessions if s not in self.cache or self.cache[s] != "busy"}
        self._prev_snap.update(current_snap)


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
