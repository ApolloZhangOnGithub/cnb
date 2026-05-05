"""IdleDetector — batch screen snapshot comparison (non-blocking).

Compares snapshots across consecutive ticks instead of sleeping mid-tick.
"""

import re

from .base import Concern
from .config import DispatcherConfig
from .helpers import has_tool_process, pane_md5, tmux


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
