"""Tests for NudgeCoordinator — unified nudge orchestrator.

NudgeCoordinator replaces the independent InboxNudger / IdleNudger /
QueuedMessageFlusher with a single concern that enforces:
  - per-session cooldown (no repeated nudges in short window)
  - post-nudge effectiveness check
  - nudge-type priority (inbox > queued_flush > idle)
  - offline sessions are never nudged

These tests define the behavioural contract; lisa-su implements against them.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.concerns.base import Concern
from lib.concerns.config import DispatcherConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_cfg(tmp_path: Path, sessions: list[str] | None = None) -> DispatcherConfig:
    sessions = sessions or ["alice", "bob"]
    cd = tmp_path / ".claudes"
    cd.mkdir(exist_ok=True)
    db_path = cd / "board.db"
    db_path.touch()
    return DispatcherConfig(
        prefix="cc-test",
        project_root=tmp_path,
        claudes_dir=cd,
        sessions_dir=cd / "sessions",
        board_db=db_path,
        suspended_file=cd / "suspended",
        board_sh=str(tmp_path / "bin" / "board"),
        coral_sess="cc-test-lead",
        dispatcher_session="cc-test-dispatcher",
        log_dir=cd / "logs",
        okr_dir=cd / "okr",
        dev_sessions=sessions,
    )


def make_idle(idle_sessions: set[str] | None = None):
    """Return a mock IdleDetector where .is_idle() is controllable."""
    idle_sessions = idle_sessions or set()
    detector = MagicMock()
    detector.is_idle = lambda sess: sess in idle_sessions
    return detector


# ---------------------------------------------------------------------------
# Fixture: lazily import NudgeCoordinator so tests fail clearly if it
# doesn't exist yet rather than crashing the entire module import.
# ---------------------------------------------------------------------------


@pytest.fixture
def NudgeCoordinator():
    try:
        from lib.concerns.nudge_coordinator import NudgeCoordinator as NC
    except ImportError:
        pytest.skip("NudgeCoordinator not implemented yet")
    return NC


# ---------------------------------------------------------------------------
# 1. Same session cannot be nudged repeatedly within cooldown
# ---------------------------------------------------------------------------


class TestCooldown:
    """A session that was just nudged must not be nudged again until the
    cooldown expires, regardless of nudge type."""

    @patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=True)
    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=True)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice"])
    def test_second_nudge_within_cooldown_is_suppressed(
        self, mock_devs, mock_send, mock_running, mock_ok, NudgeCoordinator, tmp_path
    ):
        cfg = make_cfg(tmp_path, ["alice"])
        idle = make_idle({"cc-test-alice"})
        coord = NudgeCoordinator(cfg, idle)

        coord.tick(1000)
        first_count = mock_send.call_count
        assert first_count >= 1, "first tick should nudge idle alice"

        mock_send.reset_mock()
        coord.tick(1001)
        assert mock_send.call_count == 0, "second tick 1s later must be suppressed"

    @patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=True)
    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=True)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice"])
    def test_nudge_allowed_after_cooldown_expires(
        self, mock_devs, mock_send, mock_running, mock_ok, NudgeCoordinator, tmp_path
    ):
        cfg = make_cfg(tmp_path, ["alice"])
        idle = make_idle({"cc-test-alice"})
        coord = NudgeCoordinator(cfg, idle)

        coord.tick(1000)
        assert mock_send.call_count >= 1

        mock_send.reset_mock()
        coord.tick(1000 + coord.COOLDOWN + 1)
        assert mock_send.call_count >= 1, "nudge should fire again after cooldown"

    @patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=True)
    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=True)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice", "bob"])
    def test_cooldown_is_per_session(self, mock_devs, mock_send, mock_running, mock_ok, NudgeCoordinator, tmp_path):
        cfg = make_cfg(tmp_path, ["alice", "bob"])
        idle = make_idle({"cc-test-alice", "cc-test-bob"})
        coord = NudgeCoordinator(cfg, idle)

        coord.tick(1000)
        calls_t0 = mock_send.call_count
        assert calls_t0 >= 2, "both alice and bob should be nudged"

        mock_send.reset_mock()
        coord.tick(1001)
        assert mock_send.call_count == 0, "both suppressed during cooldown"


# ---------------------------------------------------------------------------
# 2. Post-nudge effectiveness check
# ---------------------------------------------------------------------------


class TestEffectivenessCheck:
    """After nudging, the coordinator should verify the nudge had an effect
    (e.g. the session is no longer idle / inbox was read). If repeated
    nudges have no effect, the coordinator should back off or escalate."""

    @patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=True)
    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=True)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice"])
    def test_tracks_consecutive_ineffective_nudges(
        self, mock_devs, mock_send, mock_running, mock_ok, NudgeCoordinator, tmp_path
    ):
        cfg = make_cfg(tmp_path, ["alice"])
        idle = make_idle({"cc-test-alice"})
        coord = NudgeCoordinator(cfg, idle)

        t = 1000
        for _ in range(3):
            coord.tick(t)
            t += coord.COOLDOWN + 1

        stats = coord.get_nudge_stats("alice")
        assert stats["consecutive_ineffective"] >= 2, (
            "session stayed idle across multiple nudges — should track ineffectiveness"
        )

    @patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=True)
    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=True)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice"])
    def test_resets_ineffective_count_when_session_becomes_active(
        self, mock_devs, mock_send, mock_running, mock_ok, NudgeCoordinator, tmp_path
    ):
        cfg = make_cfg(tmp_path, ["alice"])
        idle_set = {"cc-test-alice"}
        idle = make_idle(idle_set)
        coord = NudgeCoordinator(cfg, idle)

        coord.tick(1000)
        coord.tick(1000 + coord.COOLDOWN + 1)

        idle_set.discard("cc-test-alice")
        coord.tick(1000 + 2 * (coord.COOLDOWN + 1))

        stats = coord.get_nudge_stats("alice")
        assert stats["consecutive_ineffective"] == 0, "counter should reset once session resumes activity"

    @patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=True)
    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=True)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice"])
    def test_backoff_after_repeated_ineffective_nudges(
        self, mock_devs, mock_send, mock_running, mock_ok, NudgeCoordinator, tmp_path
    ):
        """After N consecutive ineffective nudges the coordinator should
        increase the effective cooldown (exponential backoff or similar)."""
        cfg = make_cfg(tmp_path, ["alice"])
        idle = make_idle({"cc-test-alice"})
        coord = NudgeCoordinator(cfg, idle)

        nudge_times: list[int] = []
        original_send = mock_send.side_effect

        def track_send(*a, **kw):
            nudge_times.append(len(nudge_times))
            if original_send:
                return original_send(*a, **kw)
            return True

        mock_send.side_effect = track_send

        t = 1000
        for _ in range(10):
            coord.tick(t)
            t += coord.COOLDOWN + 1

        total_nudges = mock_send.call_count
        assert total_nudges < 10, f"should back off after ineffective nudges, but sent {total_nudges}/10"


# ---------------------------------------------------------------------------
# 3. Nudge type priority
# ---------------------------------------------------------------------------


class TestPriority:
    """When multiple nudge reasons apply to the same session in a single
    tick, only the highest-priority nudge should fire."""

    @patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=True)
    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=True)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.nudge_coordinator.tmux", return_value="some output\nqueued message\n❯")
    def test_inbox_beats_idle_and_queued(
        self, mock_tmux, mock_devs, mock_send, mock_running, mock_ok, NudgeCoordinator, tmp_path
    ):
        """inbox nudge has the highest priority."""
        cfg = make_cfg(tmp_path, ["alice"])
        idle = make_idle({"cc-test-alice"})
        coord = NudgeCoordinator(cfg, idle)

        with patch("lib.concerns.nudge_coordinator.db") as mock_db:
            mock_db.return_value.scalar.return_value = 3  # 3 unread messages
            coord.tick(1000)

        assert mock_send.call_count == 1, "only one nudge per session per tick"
        sent_text = mock_send.call_args[0][1] if mock_send.call_args[0] else str(mock_send.call_args)
        assert "inbox" in sent_text.lower(), "inbox nudge should win over idle/queued"
        assert sent_text == f"{cfg.board_sh} --as alice inbox"
        assert "./board" not in sent_text

    @patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=True)
    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=True)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.nudge_coordinator.tmux", return_value="some output\nqueued message\n❯")
    def test_queued_flush_beats_idle(
        self, mock_tmux, mock_devs, mock_send, mock_running, mock_ok, NudgeCoordinator, tmp_path
    ):
        cfg = make_cfg(tmp_path, ["alice"])
        idle = make_idle({"cc-test-alice"})
        coord = NudgeCoordinator(cfg, idle)

        with patch("lib.concerns.nudge_coordinator.db") as mock_db:
            mock_db.return_value.scalar.return_value = 0  # no unread
            coord.tick(1000)

        assert mock_send.call_count == 1
        args = mock_send.call_args
        sent_text = str(args)
        assert "Enter" in sent_text or "queued" in sent_text.lower() or args[0][1] == "", (
            "queued flush (Enter key) should take priority over idle nudge"
        )

    @patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=True)
    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=True)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.nudge_coordinator.tmux", return_value="normal output\n❯ working")
    def test_idle_nudge_when_no_other_reasons(
        self, mock_tmux, mock_devs, mock_send, mock_running, mock_ok, NudgeCoordinator, tmp_path
    ):
        cfg = make_cfg(tmp_path, ["alice"])
        idle = make_idle({"cc-test-alice"})
        coord = NudgeCoordinator(cfg, idle)

        with patch("lib.concerns.nudge_coordinator.db") as mock_db:
            mock_db.return_value.scalar.return_value = 0
            coord.tick(1000)

        assert mock_send.call_count == 1
        sent_text = mock_send.call_args[0][1]
        assert "继续" in sent_text or "KR" in sent_text or "okr" in sent_text.lower(), (
            "fallback idle nudge should prompt to continue work"
        )


# ---------------------------------------------------------------------------
# 4. Offline sessions are never nudged
# ---------------------------------------------------------------------------


class TestOfflineSessions:
    """Sessions that don't exist in tmux or aren't running Claude must
    not receive any nudge."""

    @patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=False)
    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=False)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice"])
    def test_no_nudge_when_session_not_in_tmux(
        self, mock_devs, mock_send, mock_running, mock_ok, NudgeCoordinator, tmp_path
    ):
        cfg = make_cfg(tmp_path, ["alice"])
        idle = make_idle({"cc-test-alice"})
        coord = NudgeCoordinator(cfg, idle)

        coord.tick(1000)
        assert mock_send.call_count == 0, "offline session must not be nudged"

    @patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=True)
    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=False)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice"])
    def test_no_nudge_when_claude_not_running(
        self, mock_devs, mock_send, mock_running, mock_ok, NudgeCoordinator, tmp_path
    ):
        cfg = make_cfg(tmp_path, ["alice"])
        idle = make_idle({"cc-test-alice"})
        coord = NudgeCoordinator(cfg, idle)

        coord.tick(1000)
        assert mock_send.call_count == 0, "session without Claude running must not be nudged"

    @patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=True)
    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=True)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice", "bob"])
    def test_only_online_sessions_nudged(self, mock_devs, mock_send, mock_running, mock_ok, NudgeCoordinator, tmp_path):
        cfg = make_cfg(tmp_path, ["alice", "bob"])
        idle = make_idle({"cc-test-alice"})  # only alice is idle
        coord = NudgeCoordinator(cfg, idle)

        coord.tick(1000)
        if mock_send.call_count > 0:
            for call in mock_send.call_args_list:
                sess = call[0][0]
                assert "alice" in sess, "only alice (idle) should be nudged, not bob"

    @patch("lib.concerns.nudge_coordinator.is_claude_running", return_value=True)
    @patch("lib.concerns.nudge_coordinator.tmux_send", return_value=True)
    @patch("lib.concerns.nudge_coordinator.get_dev_sessions", return_value=["alice"])
    def test_no_nudge_when_session_suspended(self, mock_devs, mock_send, mock_running, NudgeCoordinator, tmp_path):
        cfg = make_cfg(tmp_path, ["alice"])
        suspended = cfg.suspended_file
        suspended.write_text("alice\n")
        idle = make_idle({"cc-test-alice"})
        coord = NudgeCoordinator(cfg, idle)

        with (
            patch("lib.concerns.nudge_coordinator.tmux_ok", return_value=True),
            patch("lib.concerns.nudge_coordinator.is_suspended", return_value=True),
        ):
            coord.tick(1000)

        assert mock_send.call_count == 0, "suspended session must not be nudged"


# ---------------------------------------------------------------------------
# Structural: NudgeCoordinator is a proper Concern
# ---------------------------------------------------------------------------


class TestStructure:
    def test_is_concern_subclass(self, NudgeCoordinator):
        assert issubclass(NudgeCoordinator, Concern)

    def test_has_required_attributes(self, NudgeCoordinator, tmp_path):
        cfg = make_cfg(tmp_path)
        idle = make_idle()
        coord = NudgeCoordinator(cfg, idle)
        assert hasattr(coord, "COOLDOWN")
        assert isinstance(coord.COOLDOWN, int)
        assert coord.COOLDOWN > 0

    def test_has_get_nudge_stats(self, NudgeCoordinator, tmp_path):
        cfg = make_cfg(tmp_path)
        idle = make_idle()
        coord = NudgeCoordinator(cfg, idle)
        stats = coord.get_nudge_stats("nonexistent")
        assert "consecutive_ineffective" in stats
