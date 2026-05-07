"""Tests for lib/monitor.py — file watchers and handle_change."""

import signal
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from lib.monitor import (
    InotifyWatcher,
    PollWatcher,
    create_watcher,
    handle_change,
    has_inotifywait,
    has_kqueue,
    log,
)


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


# ---------------------------------------------------------------------------
# log()
# ---------------------------------------------------------------------------


class TestLog:
    def test_log_format(self, capsys):
        log("hello world")
        out = capsys.readouterr().out
        assert "[monitor]" in out
        assert "hello world" in out

    def test_log_includes_timestamp(self, capsys):
        log("test")
        out = capsys.readouterr().out
        assert ":" in out


# ---------------------------------------------------------------------------
# has_inotifywait
# ---------------------------------------------------------------------------


class TestHasInotifywait:
    @patch("shutil.which", return_value="/usr/bin/inotifywait")
    def test_true_when_found(self, mock_which):
        assert has_inotifywait() is True

    @patch("shutil.which", return_value=None)
    def test_false_when_not_found(self, mock_which):
        assert has_inotifywait() is False


# ---------------------------------------------------------------------------
# InotifyWatcher
# ---------------------------------------------------------------------------


class TestInotifyWatcher:
    def test_init_starts_subprocess(self):
        mock_proc = MagicMock()
        mock_proc.stdout = MagicMock()
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            InotifyWatcher("/some/dir")
            mock_popen.assert_called_once()
            assert "inotifywait" in mock_popen.call_args[0][0][0]

    def test_close_terminates_process(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        with patch("subprocess.Popen", return_value=mock_proc):
            w = InotifyWatcher("/some/dir")
            w.close()
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once()

    def test_close_noop_if_already_exited(self):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        with patch("subprocess.Popen", return_value=mock_proc):
            w = InotifyWatcher("/some/dir")
            w.close()
        mock_proc.terminate.assert_not_called()


# ---------------------------------------------------------------------------
# create_watcher — kqueue / inotify preference
# ---------------------------------------------------------------------------


class TestCreateWatcherPreference:
    @patch("lib.monitor.has_kqueue", return_value=True)
    def test_prefers_kqueue(self, _mock, tmp_path):
        with patch("lib.monitor.KqueueWatcher") as mock_kq:
            mock_kq.return_value = MagicMock()
            create_watcher(str(tmp_path))
            mock_kq.assert_called_once_with(str(tmp_path))

    @patch("lib.monitor.has_kqueue", return_value=False)
    @patch("lib.monitor.has_inotifywait", return_value=True)
    def test_prefers_inotify_over_poll(self, _m1, _m2, tmp_path):
        with patch("lib.monitor.InotifyWatcher") as mock_in:
            mock_in.return_value = MagicMock()
            create_watcher(str(tmp_path))
            mock_in.assert_called_once_with(str(tmp_path))


# ---------------------------------------------------------------------------
# do_watch — signal handling and event loop
# ---------------------------------------------------------------------------


class TestDoWatch:
    def test_stops_on_sigterm(self, tmp_path):
        from lib.monitor import do_watch

        env = MagicMock()
        env.sessions_dir = tmp_path

        mock_watcher = MagicMock()
        call_count = [0]

        def fake_poll(timeout=5.0):
            call_count[0] += 1
            if call_count[0] >= 2:
                signal.raise_signal(signal.SIGTERM)
            return set()

        mock_watcher.poll = fake_poll

        with patch("lib.monitor.create_watcher", return_value=mock_watcher):
            do_watch(env)
        mock_watcher.close.assert_called_once()

    def test_processes_changed_files(self, tmp_path, capsys):
        from lib.monitor import do_watch

        env = MagicMock()
        env.sessions_dir = tmp_path
        env.board_db = tmp_path / "board.db"

        mock_watcher = MagicMock()
        call_count = [0]

        def fake_poll(timeout=5.0):
            call_count[0] += 1
            if call_count[0] == 1:
                return {str(tmp_path / "alice.md")}
            signal.raise_signal(signal.SIGINT)
            return set()

        mock_watcher.poll = fake_poll

        with (
            patch("lib.monitor.create_watcher", return_value=mock_watcher),
            patch("lib.monitor.handle_change") as mock_handle,
        ):
            do_watch(env)
        mock_handle.assert_called_once_with(str(tmp_path / "alice.md"), env)


# ---------------------------------------------------------------------------
# main dispatch
# ---------------------------------------------------------------------------


class TestMain:
    def test_unknown_arg_exits(self):
        from lib.monitor import main

        with (
            patch("lib.monitor.ClaudesEnv") as mock_env_cls,
            patch.object(sys, "argv", ["monitor.py", "--badarg"]),
            pytest.raises(SystemExit),
        ):
            mock_env_cls.load.return_value = MagicMock()
            main()

    def test_help_prints_usage(self, capsys):
        from lib.monitor import main

        with (
            patch("lib.monitor.ClaudesEnv") as mock_env_cls,
            patch.object(sys, "argv", ["monitor.py", "--help"]),
        ):
            mock_env_cls.load.return_value = MagicMock()
            main()
        out = capsys.readouterr().out
        assert "monitor" in out.lower()

    def test_watch_is_default(self):
        from lib.monitor import main

        with (
            patch("lib.monitor.ClaudesEnv") as mock_env_cls,
            patch.object(sys, "argv", ["monitor.py"]),
            patch("lib.monitor.do_watch") as mock_watch,
        ):
            env = MagicMock()
            mock_env_cls.load.return_value = env
            main()
        mock_watch.assert_called_once_with(env)

    def test_test_mode(self):
        from lib.monitor import main

        with (
            patch("lib.monitor.ClaudesEnv") as mock_env_cls,
            patch.object(sys, "argv", ["monitor.py", "--test"]),
            patch("lib.monitor.do_test") as mock_test,
        ):
            env = MagicMock()
            mock_env_cls.load.return_value = env
            main()
        mock_test.assert_called_once_with(env)

    def test_benchmark_mode(self):
        from lib.monitor import main

        with (
            patch("lib.monitor.ClaudesEnv") as mock_env_cls,
            patch.object(sys, "argv", ["monitor.py", "--benchmark"]),
            patch("lib.monitor.do_benchmark") as mock_bench,
        ):
            env = MagicMock()
            mock_env_cls.load.return_value = env
            main()
        mock_bench.assert_called_once_with(env)
