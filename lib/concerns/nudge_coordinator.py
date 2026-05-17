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
from .helpers import db, get_dev_sessions, has_lead_session, is_claude_running, log, tmux, tmux_ok, tmux_send


@dataclass
class NudgeRecord:
    time: int = 0
    nudge_type: str = ""
    consecutive_ineffective: int = 0


def _already_queued(sess: str, marker: str) -> bool:
    """Return True if `marker` appears in the pane's last few visible lines.

    Used to avoid stacking duplicate nudges when a session is mid-thinking and
    the previous nudge text is still typed at the prompt waiting to be
    processed. Scanning only the tail keeps this cheap and immune to large
    scrollback drifts.
    """
    content = tmux("capture-pane", "-t", sess, "-p") or ""
    tail = "\n".join(content.splitlines()[-6:])
    return marker in tail


class NudgeCoordinator(Concern):
    interval = 2
    COOLDOWN = 15
    LEAD_COOLDOWN = 3
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
        base = self.LEAD_COOLDOWN if name == "lead" else self.COOLDOWN
        rec = self._records.get(name)
        if not rec or rec.consecutive_ineffective <= 1:
            return base
        backoff_exp = min(rec.consecutive_ineffective - 1, 3)
        return int(base * min(2**backoff_exp, self.MAX_BACKOFF_MULTIPLIER))

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
        # Stable suffix instead of absolute board path — the same command can
        # appear with different prefixes (cnb vs absolute), but the trailing
        # `--as <name> inbox` is invariant.
        if _already_queued(sess, f"--as {name} inbox"):
            return False
        tmux_send(sess, f"{self.cfg.board_sh} --as {name} inbox")
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
        # Workers (dev) idle is normal — they wait for lead to assign work.
        # Do not nudge dev idle. Only inbox / queued_flush apply to workers.
        # Lead idle is handled separately in tick() with a different message.
        return False

    def _idle_employee_names(self) -> list[str]:
        """Names of dev sessions (employees, excludes lead) currently idle and not suspended.

        Used by _try_lead_idle (#255) so lead's nudge text already lists who is free,
        saving lead a `board view` round-trip before dispatching work.
        """
        names: list[str] = []
        for name in get_dev_sessions(self.cfg):
            if is_suspended(name, self.cfg.suspended_file):
                continue
            if self.idle.is_idle(f"{self.cfg.prefix}-{name}"):
                names.append(name)
        return names

    def _try_lead_idle(self) -> bool:
        sess = f"{self.cfg.prefix}-lead"
        if not self.idle.is_idle(sess):
            return False
        if _already_queued(sess, "扫描团队"):
            return False
        idle_employees = self._idle_employee_names()
        if idle_employees:
            employee_clause = f"（当前 idle 员工: {', '.join(idle_employees)}）"
        else:
            employee_clause = "（当前无 idle 员工，但仍需扫 PR queue / master CI / open issues）"
        tmux_send(
            sess,
            f"lead 不能 idle。扫描团队状态{employee_clause}：谁空闲、谁阻塞、PR queue、master CI、open issues。"
            "主动给空闲员工派下一个 issue，不要等他们汇报。",
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
        """Check and nudge a specific session immediately."""
        self._process_session(name, now)

    def _process_lead(self, now: int) -> None:
        if not has_lead_session(self.cfg):
            return
        sess = f"{self.cfg.prefix}-lead"
        if not (tmux_ok("has-session", "-t", sess) and is_claude_running(sess)):
            return
        if "lead" in self._records:
            self._check_effectiveness("lead")
        if not self._can_nudge("lead", now):
            return
        for nudge_type, try_fn in [
            ("inbox", lambda n="lead": self._try_inbox(n)),
            ("lead_idle", lambda: self._try_lead_idle()),
        ]:
            if try_fn():
                self._record("lead", nudge_type, now)
                break

    def tick(self, now: int) -> None:
        for name in get_dev_sessions(self.cfg):
            self._process_session(name, now)
        self._process_lead(now)
