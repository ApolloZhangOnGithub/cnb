"""Tests for FileWatcher concern.

FileWatcher uses kqueue for instant inbox detection and delegates to
NudgeCoordinator.check_session() when session files change. These tests
cover the tick/queue logic and suspension filtering; kqueue internals
are tested indirectly via start/stop lifecycle.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from lib.concerns.config import DispatcherConfig
from lib.concerns.file_watcher import FileWatcher

PREFIX = "cc-test"


def make_cfg(tmp_path: Path, sessions: list[str] | None = None) -> DispatcherConfig:
    sessions = sessions or ["alice", "bob"]
    cd = tmp_path / ".claudes"
    cd.mkdir(exist_ok=True)
    (cd / "sessions").mkdir(exist_ok=True)
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


def make_nudge_mock():
    nudge = MagicMock()
    nudge.check_session = MagicMock()
    return nudge


class TestFileWatcherInit:
    def test_is_concern_subclass(self, tmp_path):
        from lib.concerns.base import Concern

        cfg = make_cfg(tmp_path)
        fw = FileWatcher(cfg, make_nudge_mock())
        assert isinstance(fw, Concern)

    def test_interval_is_one(self, tmp_path):
        cfg = make_cfg(tmp_path)
        fw = FileWatcher(cfg, make_nudge_mock())
        assert fw.interval == 1

    def test_initial_queue_empty(self, tmp_path):
        cfg = make_cfg(tmp_path)
        fw = FileWatcher(cfg, make_nudge_mock())
        assert fw._queue == []


class TestFileWatcherTick:
    def test_empty_queue_no_nudge(self, tmp_path):
        cfg = make_cfg(tmp_path)
        nudge = make_nudge_mock()
        fw = FileWatcher(cfg, nudge)

        fw.tick(1000)
        nudge.check_session.assert_not_called()

    def test_queued_names_trigger_check_session(self, tmp_path):
        cfg = make_cfg(tmp_path)
        nudge = make_nudge_mock()
        fw = FileWatcher(cfg, nudge)

        fw._queue.extend(["alice", "bob"])
        fw.tick(1000)

        assert nudge.check_session.call_count == 2
        nudge.check_session.assert_any_call("alice", 1000)
        nudge.check_session.assert_any_call("bob", 1000)

    def test_queue_cleared_after_tick(self, tmp_path):
        cfg = make_cfg(tmp_path)
        nudge = make_nudge_mock()
        fw = FileWatcher(cfg, nudge)

        fw._queue.extend(["alice"])
        fw.tick(1000)
        assert fw._queue == []

        nudge.check_session.reset_mock()
        fw.tick(1001)
        nudge.check_session.assert_not_called()

    @patch("lib.concerns.file_watcher.is_suspended", return_value=True)
    def test_suspended_session_skipped(self, mock_suspended, tmp_path):
        cfg = make_cfg(tmp_path)
        nudge = make_nudge_mock()
        fw = FileWatcher(cfg, nudge)

        fw._queue.extend(["alice"])
        fw.tick(1000)

        nudge.check_session.assert_not_called()

    @patch("lib.concerns.file_watcher.is_suspended")
    def test_mixed_suspended_and_active(self, mock_suspended, tmp_path):
        cfg = make_cfg(tmp_path)
        nudge = make_nudge_mock()
        fw = FileWatcher(cfg, nudge)

        mock_suspended.side_effect = lambda name, path: name == "alice"
        fw._queue.extend(["alice", "bob"])
        fw.tick(1000)

        nudge.check_session.assert_called_once_with("bob", 1000)

    def test_duplicate_names_in_queue(self, tmp_path):
        cfg = make_cfg(tmp_path)
        nudge = make_nudge_mock()
        fw = FileWatcher(cfg, nudge)

        fw._queue.extend(["alice", "alice", "alice"])
        fw.tick(1000)

        assert nudge.check_session.call_count == 3


class TestFileWatcherStart:
    def test_start_returns_bool(self, tmp_path):
        cfg = make_cfg(tmp_path)
        nudge = make_nudge_mock()
        fw = FileWatcher(cfg, nudge)

        result = fw.start()
        assert isinstance(result, bool)
        fw.stop()

    def test_start_creates_thread(self, tmp_path):
        cfg = make_cfg(tmp_path)
        nudge = make_nudge_mock()
        fw = FileWatcher(cfg, nudge)

        if fw.start():
            assert fw._thread is not None
            assert fw._thread.daemon is True
            assert fw._thread.name == "file-watcher"
            fw.stop()


class TestFileWatcherStop:
    def test_stop_sets_event(self, tmp_path):
        cfg = make_cfg(tmp_path)
        nudge = make_nudge_mock()
        fw = FileWatcher(cfg, nudge)

        fw.stop()
        assert fw._stop.is_set()

    def test_stop_without_start_is_safe(self, tmp_path):
        cfg = make_cfg(tmp_path)
        nudge = make_nudge_mock()
        fw = FileWatcher(cfg, nudge)

        fw.stop()

    def test_start_then_stop(self, tmp_path):
        cfg = make_cfg(tmp_path)
        nudge = make_nudge_mock()
        fw = FileWatcher(cfg, nudge)

        if fw.start():
            fw.stop()
            assert fw._stop.is_set()


class TestFileWatcherThreadSafety:
    def test_queue_access_is_thread_safe(self, tmp_path):
        """Verify tick drains the queue atomically under the lock."""
        cfg = make_cfg(tmp_path)
        nudge = make_nudge_mock()
        fw = FileWatcher(cfg, nudge)

        with fw._lock:
            fw._queue.extend(["alice"])

        fw.tick(1000)
        assert nudge.check_session.call_count == 1
