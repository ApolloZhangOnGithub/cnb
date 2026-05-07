"""Tests for lib/board_tui.py — tmux-native team UI.

Covers: cmd_tui error paths (no env, no sessions, no online workers),
session construction, style application, and terminal opener dispatch.
All tmux/osascript subprocess calls are mocked.
"""

from unittest.mock import MagicMock, patch

import pytest

from lib.board_tui import UI_SESSION, _apply_style, _open_terminal, _session_exists, _tmux, _tmux_out, cmd_tui

# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestTmuxHelpers:
    def test_tmux_returns_returncode(self):
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0)
            assert _tmux("has-session", "-t", "test") == 0

    def test_tmux_out_success(self):
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="  hello  \n")
            assert _tmux_out("list-windows") == "hello"

    def test_tmux_out_failure(self):
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1, stdout="error")
            assert _tmux_out("bad-cmd") == ""

    def test_session_exists_true(self):
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0)
            assert _session_exists("cnb-alice") is True

    def test_session_exists_false(self):
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1)
            assert _session_exists("cnb-alice") is False


# ---------------------------------------------------------------------------
# cmd_tui error paths
# ---------------------------------------------------------------------------


class TestCmdTuiErrors:
    def test_no_env_exits(self, db):
        db.env = None
        with pytest.raises(SystemExit):
            cmd_tui(db)

    def test_no_sessions_exits(self, db):
        with db.conn() as c:
            c.execute("DELETE FROM sessions")
        with pytest.raises(SystemExit):
            cmd_tui(db)

    def test_no_online_workers_exits(self, db):
        with patch("lib.board_tui._session_exists", return_value=False), pytest.raises(SystemExit):
            cmd_tui(db)


# ---------------------------------------------------------------------------
# cmd_tui happy path
# ---------------------------------------------------------------------------


class TestCmdTuiHappyPath:
    def test_builds_ui_session(self, db):
        tmux_calls = []

        def mock_session_exists(name):
            return name != UI_SESSION

        def mock_tmux(*args):
            tmux_calls.append(args)
            return 0

        def mock_tmux_out(*args):
            tmux_calls.append(args)
            if "list-windows" in args:
                return "1\n2\n3"
            return ""

        with (
            patch("lib.board_tui._session_exists", side_effect=mock_session_exists),
            patch("lib.board_tui._tmux", side_effect=mock_tmux),
            patch("lib.board_tui._tmux_out", side_effect=mock_tmux_out),
            patch("lib.board_tui._open_terminal"),
        ):
            cmd_tui(db)

        new_session_calls = [c for c in tmux_calls if len(c) >= 2 and c[0] == "new-session"]
        assert len(new_session_calls) > 0

    def test_kills_existing_ui_session(self, db):
        tmux_calls = []

        def mock_session_exists(name):
            return True

        def mock_tmux(*args):
            tmux_calls.append(args)
            return 0

        def mock_tmux_out(*args):
            if "list-windows" in args:
                return "1\n2\n3"
            return ""

        with (
            patch("lib.board_tui._session_exists", side_effect=mock_session_exists),
            patch("lib.board_tui._tmux", side_effect=mock_tmux),
            patch("lib.board_tui._tmux_out", side_effect=mock_tmux_out),
            patch("lib.board_tui._open_terminal"),
        ):
            cmd_tui(db)

        kill_calls = [c for c in tmux_calls if "kill-session" in c]
        assert len(kill_calls) > 0


# ---------------------------------------------------------------------------
# _apply_style
# ---------------------------------------------------------------------------


class TestApplyStyle:
    def test_sets_session_and_window_options(self):
        tmux_calls = []

        def mock_tmux(*args):
            tmux_calls.append(args)
            return 0

        with patch("lib.board_tui._tmux", side_effect=mock_tmux):
            _apply_style(3, ["1", "2", "3"])

        set_option_calls = [c for c in tmux_calls if c[0] == "set-option"]
        assert len(set_option_calls) > 0

        session_opts = [c for c in set_option_calls if c[1] == "-t"]
        window_opts = [c for c in set_option_calls if c[1] == "-w"]
        assert len(session_opts) > 0
        assert len(window_opts) > 0

    def test_online_count_in_status(self):
        tmux_calls = []

        def mock_tmux(*args):
            tmux_calls.append(args)
            return 0

        with patch("lib.board_tui._tmux", side_effect=mock_tmux):
            _apply_style(5, ["1"])

        status_right_call = [c for c in tmux_calls if len(c) >= 5 and c[3] == "status-right"]
        assert any("5" in c[4] for c in status_right_call)


# ---------------------------------------------------------------------------
# _open_terminal
# ---------------------------------------------------------------------------


class TestOpenTerminal:
    def test_darwin_iterm(self):
        with (
            patch("sys.platform", "darwin"),
            patch("os.path.isdir", return_value=True),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            _open_terminal()
            args = mock_run.call_args[0][0]
            assert args[0] == "osascript"

    def test_darwin_terminal_app(self):
        with (
            patch("sys.platform", "darwin"),
            patch("os.path.isdir", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            _open_terminal()
            args = mock_run.call_args[0][0]
            assert args[0] == "osascript"

    def test_darwin_osascript_failure(self):
        with (
            patch("sys.platform", "darwin"),
            patch("os.path.isdir", return_value=False),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=1, stderr="permission denied")
            with pytest.raises(SystemExit):
                _open_terminal()

    def test_linux_finds_terminal(self):
        with (
            patch("sys.platform", "linux"),
            patch("shutil.which", return_value="/usr/bin/xterm"),
            patch("subprocess.Popen") as mock_popen,
        ):
            _open_terminal()
            mock_popen.assert_called_once()

    def test_linux_no_terminal_exits(self):
        with patch("sys.platform", "linux"), patch("shutil.which", return_value=None), pytest.raises(SystemExit):
            _open_terminal()
