"""NudgeCoordinator — unified nudge orchestrator replacing InboxNudger, QueuedMessageFlusher, IdleNudger.

Consolidates all nudge decisions into a single Concern with:
  - per-session cooldown across all nudge types
  - nudge-type priority: inbox > queued_flush > idle
  - post-nudge effectiveness tracking with backoff
  - cached session status checks (one tmux call per session per tick)
"""

from dataclasses import dataclass

from lib.common import is_suspended

from .base import Concern
from .config import DispatcherConfig
from .helpers import db, get_dev_sessions, is_claude_running, log, tmux, tmux_ok, tmux_send


@dataclass
class NudgeRecord:
    time: int = 0
    nudge_type: str = ""
    consecutive_ineffective: int = 0


class NudgeCoordinator(Concern):
    interval = 5
    COOLDOWN = 15
    MAX_BACKOFF_MULTIPLIER = 8

    def __init__(self, cfg: DispatcherConfig, idle) -> None:
        super().__init__()
        self.cfg = cfg
        self.idle = idle
        self._records: dict[str, NudgeRecord] = {}
        self._session_ok: dict[str, bool] = {}
        self._cache_tick: int = 0

    def _session_ready(self, name: str, now: int) -> bool:
        if now != self._cache_tick:
            self._session_ok.clear()
            self._cache_tick = now
        if name not in self._session_ok:
            sess = f"{self.cfg.prefix}-{name}"
            self._session_ok[name] = tmux_ok("has-session", "-t", sess) and is_claude_running(sess)
        return self._session_ok[name]

    def _effective_cooldown(self, name: str) -> int:
        rec = self._records.get(name)
        if not rec or rec.consecutive_ineffective <= 1:
            return self.COOLDOWN
        backoff_exp = min(rec.consecutive_ineffective - 1, 3)
        return self.COOLDOWN * min(2**backoff_exp, self.MAX_BACKOFF_MULTIPLIER)

    def _can_nudge(self, name: str, now: int) -> bool:
        rec = self._records.get(name)
        if not rec:
            return True
        return (now - rec.time) >= self._effective_cooldown(name)

    def _check_effectiveness(self, name: str) -> None:
        rec = self._records.get(name)
        if not rec:
            return
        sess = f"{self.cfg.prefix}-{name}"
        if self.idle.is_idle(sess):
            rec.consecutive_ineffective += 1
        else:
            rec.consecutive_ineffective = 0

    def _record(self, name: str, nudge_type: str, now: int) -> None:
        rec = self._records.get(name)
        old_ineffective = rec.consecutive_ineffective if rec else 0
        self._records[name] = NudgeRecord(time=now, nudge_type=nudge_type, consecutive_ineffective=old_ineffective)
        log(f"NUDGE [{nudge_type}] {name}")

    def _try_inbox(self, name: str) -> bool:
        if not self.cfg.board_db.exists():
            return False
        try:
            unread = db(self.cfg).scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,)) or 0
        except Exception:
            return False
        if unread <= 0:
            return False
        sess = f"{self.cfg.prefix}-{name}"
        tmux_send(sess, f"./board --as {name} inbox")
        return True

    def _try_queued_flush(self, name: str) -> bool:
        sess = f"{self.cfg.prefix}-{name}"
        content = tmux("capture-pane", "-t", sess, "-p") or ""
        if "queued message" not in content.lower():
            return False
        lines = content.splitlines()[-5:]
        if not any(line.rstrip() == "❯" for line in lines):
            return False
        tmux_send(sess, "")
        return True

    def _try_idle(self, name: str) -> bool:
        sess = f"{self.cfg.prefix}-{name}"
        if not self.idle.is_idle(sess):
            return False
        tmux_send(
            sess,
            f"继续工作。检查你的 OKR ({self.cfg.okr_dir}/{name}.md)，推进你的活跃 KR。自己决定优先级。",
        )
        return True

    def get_nudge_stats(self, name: str) -> dict:
        rec = self._records.get(name)
        if not rec:
            return {"consecutive_ineffective": 0, "last_nudge_type": "", "last_nudge_time": 0}
        return {
            "consecutive_ineffective": rec.consecutive_ineffective,
            "last_nudge_type": rec.nudge_type,
            "last_nudge_time": rec.time,
        }

    def _process_session(self, name: str, now: int) -> None:
        if is_suspended(name, self.cfg.suspended_file):
            return
        if not self._session_ready(name, now):
            return

        if name in self._records:
            self._check_effectiveness(name)

        if not self._can_nudge(name, now):
            return

        for nudge_type, try_fn in [
            ("inbox", self._try_inbox),
            ("flush", self._try_queued_flush),
            ("idle", self._try_idle),
        ]:
            if try_fn(name):
                self._record(name, nudge_type, now)
                break

    def check_session(self, name: str, now: int) -> None:
        """Check and nudge a specific session (used by FileWatcher for instant inbox detection)."""
        self._process_session(name, now)

    def tick(self, now: int) -> None:
        for name in get_dev_sessions(self.cfg):
            self._process_session(name, now)
