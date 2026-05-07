"""Tests for lib/monitor.py — file watchers and handle_change."""

import time
from unittest.mock import MagicMock, patch

from lib.monitor import PollWatcher, create_watcher, handle_change, has_kqueue


class TestHasKqueue:
    def test_returns_bool(self):
        result = has_kqueue()
        assert isinstance(result, bool)

    @patch("lib.monitor.select")
    def test_true_when_kqueue_exists(self, mock_select):
        mock_select.kqueue = lambda: None
        assert has_kqueue() is True

    @patch("lib.monitor.select")
    def test_false_when_no_kqueue(self, mock_select):
        del mock_select.kqueue
        assert has_kqueue() is False


class TestPollWatcher:
    def test_init_scans_md_files(self, tmp_path):
        (tmp_path / "alice.md").write_text("data")
        (tmp_path / "bob.md").write_text("data")
        (tmp_path / "ignore.txt").write_text("data")

        pw = PollWatcher(str(tmp_path))
        assert len(pw.mtimes) == 2
        assert any("alice.md" in k for k in pw.mtimes)
        assert any("bob.md" in k for k in pw.mtimes)
        assert not any("ignore.txt" in k for k in pw.mtimes)

    def test_poll_detects_change(self, tmp_path):
        f = tmp_path / "alice.md"
        f.write_text("initial")
        pw = PollWatcher(str(tmp_path))

        time.sleep(0.05)
        f.write_text("modified")

        changed = pw._scan()
        assert len(changed) == 1
        assert str(f) in changed

    def test_poll_no_change(self, tmp_path):
        (tmp_path / "alice.md").write_text("data")
        pw = PollWatcher(str(tmp_path))

        changed = pw._scan()
        assert len(changed) == 0

    def test_poll_detects_new_file(self, tmp_path):
        pw = PollWatcher(str(tmp_path))
        assert len(pw.mtimes) == 0

        (tmp_path / "new.md").write_text("hello")
        changed = pw._scan()
        assert len(changed) == 0
        assert len(pw.mtimes) == 1

    def test_close_is_noop(self, tmp_path):
        pw = PollWatcher(str(tmp_path))
        pw.close()

    def test_ignores_non_md_changes(self, tmp_path):
        (tmp_path / "data.txt").write_text("initial")
        pw = PollWatcher(str(tmp_path))
        assert len(pw.mtimes) == 0

    def test_handles_missing_file_during_scan(self, tmp_path):
        f = tmp_path / "alice.md"
        f.write_text("data")
        pw = PollWatcher(str(tmp_path))

        f.unlink()
        changed = pw._scan()
        assert len(changed) == 0


class TestCreateWatcher:
    def test_returns_watcher_instance(self, tmp_path):
        watcher = create_watcher(str(tmp_path))
        assert hasattr(watcher, "poll")
        assert hasattr(watcher, "close")
        watcher.close()

    @patch("lib.monitor.has_kqueue", return_value=False)
    @patch("lib.monitor.has_inotifywait", return_value=False)
    def test_falls_back_to_poll(self, mock_inotify, mock_kqueue, tmp_path):
        watcher = create_watcher(str(tmp_path))
        assert isinstance(watcher, PollWatcher)
        watcher.close()


class TestHandleChange:
    def test_logs_when_unread(self, tmp_path, capsys):
        env = MagicMock()
        env.board_db = tmp_path / "board.db"

        mock_db = MagicMock()
        mock_db.scalar.return_value = 3
        with patch("lib.monitor.BoardDB", return_value=mock_db):
            (tmp_path / "board.db").touch()
            handle_change(str(tmp_path / "alice.md"), env)

        captured = capsys.readouterr()
        assert "alice" in captured.out
        assert "3 unread" in captured.out

    def test_silent_when_no_unread(self, tmp_path, capsys):
        env = MagicMock()
        env.board_db = tmp_path / "board.db"

        mock_db = MagicMock()
        mock_db.scalar.return_value = 0
        with patch("lib.monitor.BoardDB", return_value=mock_db):
            (tmp_path / "board.db").touch()
            handle_change(str(tmp_path / "alice.md"), env)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_silent_when_db_missing(self, tmp_path, capsys):
        env = MagicMock()
        env.board_db = tmp_path / "nonexistent.db"

        handle_change(str(tmp_path / "alice.md"), env)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_silent_on_db_error(self, tmp_path, capsys):
        env = MagicMock()
        env.board_db = tmp_path / "board.db"
        (tmp_path / "board.db").touch()

        import sqlite3

        with patch("lib.monitor.BoardDB", side_effect=sqlite3.Error("locked")):
            handle_change(str(tmp_path / "alice.md"), env)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_extracts_name_from_path(self, tmp_path):
        env = MagicMock()
        env.board_db = tmp_path / "board.db"

        mock_db = MagicMock()
        mock_db.scalar.return_value = 1
        with patch("lib.monitor.BoardDB", return_value=mock_db):
            (tmp_path / "board.db").touch()
            handle_change("/some/path/bob-jones.md", env)

        mock_db.scalar.assert_called_once()
        args = mock_db.scalar.call_args[0]
        assert "bob-jones" in args[1]
