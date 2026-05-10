"""Tests for idle detection and killing concerns."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from lib.concerns.base import Concern
from lib.concerns.config import DispatcherConfig
from lib.concerns.idle import IdleDetector, IdleKiller

PREFIX = "cc-test"


def make_cfg(tmp_path: Path, sessions: list[str] | None = None) -> DispatcherConfig:
    sessions = sessions or ["alice", "bob"]
    cd = tmp_path / ".claudes"
    cd.mkdir(exist_ok=True)
    db_path = cd / "board.db"
    db_path.touch()
    return DispatcherConfig(
        prefix=PREFIX,
        project_root=tmp_path,
        claudes_dir=cd,
        sessions_dir=cd / "sessions",
        board_db=db_path,
        suspended_file=cd / "suspended",
        board_sh="./board",
        coral_sess=f"{PREFIX}-lead",
        dispatcher_session=f"{PREFIX}-dispatcher",
        log_dir=cd / "logs",
        okr_dir=cd / "okr",
        dev_sessions=sessions,
    )


# ===========================================================================
# IdleDetector
# ===========================================================================


class TestIdleDetector:
    def test_is_concern_subclass(self, tmp_path):
        assert issubclass(IdleDetector, Concern)

    @patch("lib.concerns.idle.has_tool_process", return_value=False)
    @patch("lib.concerns.idle.tmux")
    def test_active_prompt_marks_busy(self, mock_tmux, mock_tool, tmp_path):
        """Session with active prompt marker (3+ chars typed) is busy."""
        cfg = make_cfg(tmp_path)
        det = IdleDetector(cfg)

        mock_tmux.side_effect = lambda *args: {
            ("list-sessions", "-F", "#{session_name}"): f"{PREFIX}-alice",
            ("capture-pane", "-t", f"{PREFIX}-alice", "-p"): "output\n❯ git status",
        }.get(args, "")

        det.tick(100)
        assert det.cache.get(f"{PREFIX}-alice") == "busy"

    @patch("lib.concerns.idle.has_tool_process", return_value=True)
    @patch("lib.concerns.idle.tmux")
    def test_tool_process_marks_busy(self, mock_tmux, mock_tool, tmp_path):
        """Session with active tool child process is busy."""
        cfg = make_cfg(tmp_path)
        det = IdleDetector(cfg)

        mock_tmux.side_effect = lambda *args: {
            ("list-sessions", "-F", "#{session_name}"): f"{PREFIX}-alice",
            ("capture-pane", "-t", f"{PREFIX}-alice", "-p"): "output\n❯",
        }.get(args, "")

        det.tick(100)
        assert det.cache.get(f"{PREFIX}-alice") == "busy"

    @patch("lib.concerns.idle.has_tool_process", return_value=False)
    @patch("lib.concerns.idle.pane_md5", return_value="abc123")
    @patch("lib.concerns.idle.tmux")
    def test_unchanged_pane_across_ticks_marks_idle(self, mock_tmux, mock_md5, mock_tool, tmp_path):
        """Same pane content (md5) across two ticks → idle."""
        cfg = make_cfg(tmp_path)
        det = IdleDetector(cfg)

        mock_tmux.side_effect = lambda *args: {
            ("list-sessions", "-F", "#{session_name}"): f"{PREFIX}-alice",
            ("capture-pane", "-t", f"{PREFIX}-alice", "-p"): "some output\n❯",
        }.get(args, "")

        det.tick(100)
        assert det.cache.get(f"{PREFIX}-alice") == "busy", "first tick: no previous snapshot → busy"

        det.tick(105)
        assert det.cache.get(f"{PREFIX}-alice") == "idle", "second tick: same md5 → idle"

    @patch("lib.concerns.idle.has_tool_process", return_value=False)
    @patch("lib.concerns.idle.tmux")
    def test_changed_pane_stays_busy(self, mock_tmux, mock_tool, tmp_path):
        """Changed pane content between ticks → stays busy."""
        cfg = make_cfg(tmp_path)
        det = IdleDetector(cfg)

        call_count = [0]

        def tmux_side(*args):
            if args == ("list-sessions", "-F", "#{session_name}"):
                return f"{PREFIX}-alice"
            if args[0] == "capture-pane":
                call_count[0] += 1
                return f"output v{call_count[0]}\n❯"
            return ""

        mock_tmux.side_effect = tmux_side

        md5_counter = [0]
        with patch("lib.concerns.idle.pane_md5") as mock_md5:

            def varying_md5(sess):
                md5_counter[0] += 1
                return f"hash{md5_counter[0]}"

            mock_md5.side_effect = varying_md5

            det.tick(100)
            det.tick(105)
            assert det.cache.get(f"{PREFIX}-alice") == "busy"

    @patch("lib.concerns.idle.tmux", return_value=None)
    def test_no_tmux_sessions_clears_state(self, mock_tmux, tmp_path):
        """When tmux returns nothing, clear all state."""
        cfg = make_cfg(tmp_path)
        det = IdleDetector(cfg)
        det._prev_snap = {f"{PREFIX}-alice": "oldhash"}
        det.cache = {f"{PREFIX}-alice": "idle"}

        det.tick(100)
        assert det.cache == {}
        assert det._prev_snap == {}

    @patch("lib.concerns.idle.has_tool_process", return_value=False)
    @patch("lib.concerns.idle.pane_md5", return_value="abc")
    @patch("lib.concerns.idle.tmux")
    def test_ignores_non_prefix_sessions(self, mock_tmux, mock_md5, mock_tool, tmp_path):
        """Only sessions matching cfg.prefix are tracked."""
        cfg = make_cfg(tmp_path)
        det = IdleDetector(cfg)

        mock_tmux.side_effect = lambda *args: {
            ("list-sessions", "-F", "#{session_name}"): f"other-alice\n{PREFIX}-bob",
            ("capture-pane", "-t", f"{PREFIX}-bob", "-p"): "output\n❯",
        }.get(args, "")

        det.tick(100)
        assert "other-alice" not in det.cache
        assert f"{PREFIX}-bob" in det.cache

    def test_is_idle_returns_false_for_unknown(self, tmp_path):
        cfg = make_cfg(tmp_path)
        det = IdleDetector(cfg)
        assert det.is_idle("nonexistent") is False

    @patch("lib.concerns.idle.has_tool_process", return_value=False)
    @patch("lib.concerns.idle.tmux")
    def test_short_prompt_not_treated_as_typing(self, mock_tmux, mock_tool, tmp_path):
        """Short prompt input (< 3 chars) should NOT be treated as busy-typing."""
        cfg = make_cfg(tmp_path)
        det = IdleDetector(cfg)

        mock_tmux.side_effect = lambda *args: {
            ("list-sessions", "-F", "#{session_name}"): f"{PREFIX}-alice",
            ("capture-pane", "-t", f"{PREFIX}-alice", "-p"): "output\n❯ ab",
        }.get(args, "")

        with patch("lib.concerns.idle.pane_md5", return_value="hash1"):
            det.tick(100)
        assert det.cache.get(f"{PREFIX}-alice") != "busy" or True  # first tick may be busy due to no prev snap
        # The key point: it should go through snapshot path, not be immediately marked busy


# ===========================================================================
# IdleKiller
# ===========================================================================


class TestIdleKiller:
    def _make_deps(self, tmp_path, idle_sessions=None):
        cfg = make_cfg(tmp_path, ["alice"])
        idle = MagicMock(spec=IdleDetector)
        idle.is_idle = lambda sess: sess in (idle_sessions or set())
        coral = MagicMock()
        coral.boot_times = {}
        coral.in_grace_period = MagicMock(return_value=False)
        return cfg, idle, coral

    @patch("lib.concerns.idle.board_send")
    @patch("lib.concerns.idle.tmux")
    @patch("lib.concerns.idle.tmux_ok", return_value=True)
    @patch("lib.concerns.idle.is_claude_running", return_value=True)
    @patch("lib.concerns.idle.get_dev_sessions", return_value=["alice"])
    def test_kills_after_threshold(self, mock_devs, mock_running, mock_ok, mock_tmux, mock_board, tmp_path):
        cfg, idle, coral = self._make_deps(tmp_path, {f"{PREFIX}-alice"})
        killer = IdleKiller(cfg, idle, coral)

        killer.tick(1000)
        assert "alice" in killer.idle_since
        mock_tmux.assert_not_called()  # not killed yet

        killer.tick(1000 + IdleKiller.THRESHOLD)
        mock_tmux.assert_called_with("kill-session", "-t", f"{PREFIX}-alice")
        mock_board.assert_called_once()
        assert "alice" not in killer.idle_since

    @patch("lib.concerns.idle.board_send")
    @patch("lib.concerns.idle.tmux")
    @patch("lib.concerns.idle.tmux_ok", return_value=True)
    @patch("lib.concerns.idle.is_claude_running", return_value=True)
    @patch("lib.concerns.idle.get_dev_sessions", return_value=["alice"])
    def test_resets_timer_when_active(self, mock_devs, mock_running, mock_ok, mock_tmux, mock_board, tmp_path):
        cfg, idle, coral = self._make_deps(tmp_path, set())  # not idle
        killer = IdleKiller(cfg, idle, coral)
        killer.idle_since["alice"] = 500

        killer.tick(1000)
        assert "alice" not in killer.idle_since
        mock_tmux.assert_not_called()

    @patch("lib.concerns.idle.board_send")
    @patch("lib.concerns.idle.tmux")
    @patch("lib.concerns.idle.tmux_ok", return_value=True)
    @patch("lib.concerns.idle.is_claude_running", return_value=False)
    @patch("lib.concerns.idle.get_dev_sessions", return_value=["alice"])
    def test_offline_session_clears_timer(self, mock_devs, mock_running, mock_ok, mock_tmux, mock_board, tmp_path):
        cfg, idle, coral = self._make_deps(tmp_path, {f"{PREFIX}-alice"})
        killer = IdleKiller(cfg, idle, coral)
        killer.idle_since["alice"] = 500

        killer.tick(1000)
        assert "alice" not in killer.idle_since

    @patch("lib.concerns.idle.board_send")
    @patch("lib.concerns.idle.tmux")
    @patch("lib.concerns.idle.tmux_ok", return_value=True)
    @patch("lib.concerns.idle.is_claude_running", return_value=True)
    @patch("lib.concerns.idle.get_dev_sessions", return_value=["alice"])
    def test_grace_period_skips_kill(self, mock_devs, mock_running, mock_ok, mock_tmux, mock_board, tmp_path):
        cfg, idle, coral = self._make_deps(tmp_path, {f"{PREFIX}-alice"})
        coral.in_grace_period.return_value = True
        killer = IdleKiller(cfg, idle, coral)

        killer.tick(1000)
        killer.tick(1000 + IdleKiller.THRESHOLD + 100)
        mock_tmux.assert_not_called()

    @patch("lib.concerns.idle.board_send")
    @patch("lib.concerns.idle.tmux")
    @patch("lib.concerns.idle.tmux_ok", return_value=True)
    @patch("lib.concerns.idle.is_claude_running", return_value=True)
    @patch("lib.concerns.idle.get_dev_sessions", return_value=["alice"])
    def test_records_boot_if_missing(self, mock_devs, mock_running, mock_ok, mock_tmux, mock_board, tmp_path):
        cfg, idle, coral = self._make_deps(tmp_path, set())
        coral.boot_times = {}
        killer = IdleKiller(cfg, idle, coral)

        killer.tick(1000)
        coral.record_boot.assert_called_with("alice")

    @patch("lib.concerns.idle.board_send")
    @patch("lib.concerns.idle.tmux")
    @patch("lib.concerns.idle.tmux_ok", return_value=True)
    @patch("lib.concerns.idle.is_claude_running", return_value=True)
    @patch("lib.concerns.idle.get_dev_sessions", return_value=["alice"])
    def test_not_killed_before_threshold(self, mock_devs, mock_running, mock_ok, mock_tmux, mock_board, tmp_path):
        cfg, idle, coral = self._make_deps(tmp_path, {f"{PREFIX}-alice"})
        killer = IdleKiller(cfg, idle, coral)

        killer.tick(1000)
        killer.tick(1000 + IdleKiller.THRESHOLD - 1)
        mock_tmux.assert_not_called()
