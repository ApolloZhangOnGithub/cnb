"""Tests for lib/concerns/helpers.py — shared helper functions for dispatcher concerns."""

import hashlib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from lib.concerns.config import DispatcherConfig
from lib.concerns.helpers import (
    board_send,
    get_dev_sessions,
    has_tool_process,
    is_claude_running,
    is_pane_typing,
    pane_md5,
    tmux,
    tmux_ok,
    tmux_send,
)

PREFIX = "cc-test"


def make_cfg(tmp_path: Path) -> DispatcherConfig:
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
        dev_sessions=["alice", "bob"],
    )


# ===========================================================================
# tmux()
# ===========================================================================


class TestTmux:
    @patch("lib.concerns.helpers.subprocess.run")
    def test_returns_stdout_on_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="session1\nsession2\n")
        result = tmux("list-sessions", "-F", "#{session_name}")
        assert result == "session1\nsession2"
        mock_run.assert_called_once()

    @patch("lib.concerns.helpers.subprocess.run")
    def test_returns_none_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        result = tmux("has-session", "-t", "nonexistent")
        assert result is None

    @patch("lib.concerns.helpers.subprocess.run")
    def test_returns_none_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=8)
        result = tmux("list-sessions")
        assert result is None

    @patch("lib.concerns.helpers.subprocess.run")
    def test_returns_none_on_os_error(self, mock_run):
        mock_run.side_effect = OSError("tmux not found")
        result = tmux("list-sessions")
        assert result is None


# ===========================================================================
# tmux_ok()
# ===========================================================================


class TestTmuxOk:
    @patch("lib.concerns.helpers.subprocess.run")
    def test_true_on_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert tmux_ok("has-session", "-t", "test") is True

    @patch("lib.concerns.helpers.subprocess.run")
    def test_false_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        assert tmux_ok("has-session", "-t", "nonexistent") is False

    @patch("lib.concerns.helpers.subprocess.run")
    def test_false_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=8)
        assert tmux_ok("has-session", "-t", "test") is False


# ===========================================================================
# tmux_send()
# ===========================================================================


class TestTmuxSend:
    @patch("lib.concerns.helpers.subprocess.run")
    def test_sends_text_then_enter(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = tmux_send("cc-test-alice", "hello world")
        assert result is True
        assert mock_run.call_count == 2
        first_call = mock_run.call_args_list[0]
        assert "-l" in first_call[0][0]
        assert "hello world" in first_call[0][0]
        second_call = mock_run.call_args_list[1]
        assert "Enter" in second_call[0][0]

    @patch("lib.concerns.helpers.subprocess.run")
    def test_returns_false_on_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "tmux")
        result = tmux_send("cc-test-alice", "hello")
        assert result is False

    @patch("lib.concerns.helpers.subprocess.run")
    def test_returns_false_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=8)
        result = tmux_send("cc-test-alice", "hello")
        assert result is False


# ===========================================================================
# is_claude_running()
# ===========================================================================


class TestIsClaudeRunning:
    @patch("lib.concerns.helpers.tmux")
    @patch("lib.concerns.helpers.tmux_ok", return_value=True)
    def test_true_when_claude_process(self, mock_ok, mock_tmux):
        mock_tmux.return_value = "node"
        assert is_claude_running("cc-test-alice") is True

    @patch("lib.concerns.helpers.tmux")
    @patch("lib.concerns.helpers.tmux_ok", return_value=True)
    def test_false_when_shell(self, mock_ok, mock_tmux):
        mock_tmux.return_value = "zsh"
        assert is_claude_running("cc-test-alice") is False

    @patch("lib.concerns.helpers.tmux")
    @patch("lib.concerns.helpers.tmux_ok", return_value=True)
    def test_false_when_bash(self, mock_ok, mock_tmux):
        mock_tmux.return_value = "bash"
        assert is_claude_running("cc-test-alice") is False

    @patch("lib.concerns.helpers.tmux_ok", return_value=False)
    def test_false_when_no_session(self, mock_ok):
        assert is_claude_running("cc-test-alice") is False

    @patch("lib.concerns.helpers.tmux")
    @patch("lib.concerns.helpers.tmux_ok", return_value=True)
    def test_false_when_empty_command(self, mock_ok, mock_tmux):
        mock_tmux.return_value = ""
        assert is_claude_running("cc-test-alice") is False

    @patch("lib.concerns.helpers.tmux")
    @patch("lib.concerns.helpers.tmux_ok", return_value=True)
    def test_false_when_tmux_returns_none(self, mock_ok, mock_tmux):
        mock_tmux.return_value = None
        assert is_claude_running("cc-test-alice") is False


# ===========================================================================
# get_dev_sessions()
# ===========================================================================


class TestGetDevSessions:
    @patch("lib.concerns.helpers.tmux")
    def test_extracts_session_names(self, mock_tmux, tmp_path):
        cfg = make_cfg(tmp_path)
        mock_tmux.return_value = "cc-test-alice\ncc-test-bob\ncc-test-charlie"
        result = get_dev_sessions(cfg)
        assert "alice" in result
        assert "bob" in result
        assert "charlie" in result

    @patch("lib.concerns.helpers.tmux")
    def test_excludes_dispatcher_and_lead(self, mock_tmux, tmp_path):
        cfg = make_cfg(tmp_path)
        mock_tmux.return_value = "cc-test-alice\ncc-test-dispatcher\ncc-test-lead"
        result = get_dev_sessions(cfg)
        assert "alice" in result
        assert "dispatcher" not in result
        assert "lead" not in result

    @patch("lib.concerns.helpers.tmux")
    def test_ignores_non_prefixed_sessions(self, mock_tmux, tmp_path):
        cfg = make_cfg(tmp_path)
        mock_tmux.return_value = "cc-test-alice\nother-session\nrandom"
        result = get_dev_sessions(cfg)
        assert result == ["alice"]

    @patch("lib.concerns.helpers.tmux")
    def test_returns_empty_when_tmux_fails(self, mock_tmux, tmp_path):
        cfg = make_cfg(tmp_path)
        mock_tmux.return_value = None
        assert get_dev_sessions(cfg) == []


# ===========================================================================
# pane_md5()
# ===========================================================================


class TestPaneMd5:
    @patch("lib.concerns.helpers.tmux")
    def test_returns_md5_of_content(self, mock_tmux):
        mock_tmux.return_value = "hello world"
        expected = hashlib.md5(b"hello world").hexdigest()
        assert pane_md5("cc-test-alice") == expected

    @patch("lib.concerns.helpers.tmux")
    def test_returns_md5_of_empty_on_none(self, mock_tmux):
        mock_tmux.return_value = None
        expected = hashlib.md5(b"").hexdigest()
        assert pane_md5("cc-test-alice") == expected

    @patch("lib.concerns.helpers.tmux")
    def test_different_content_different_hash(self, mock_tmux):
        mock_tmux.return_value = "content A"
        hash_a = pane_md5("cc-test-alice")
        mock_tmux.return_value = "content B"
        hash_b = pane_md5("cc-test-alice")
        assert hash_a != hash_b


# ===========================================================================
# board_send()
# ===========================================================================


class TestBoardSend:
    @patch("lib.concerns.helpers.subprocess.run")
    def test_calls_board_script(self, mock_run, tmp_path):
        cfg = make_cfg(tmp_path)
        board_send(cfg, "alice", "hello")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == cfg.board_sh
        assert "--as" in args
        assert "dispatcher" in args
        assert "send" in args
        assert "alice" in args
        assert "hello" in args

    @patch("lib.concerns.helpers.subprocess.run")
    def test_survives_timeout(self, mock_run, tmp_path):
        cfg = make_cfg(tmp_path)
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="board", timeout=10)
        board_send(cfg, "alice", "hello")

    @patch("lib.concerns.helpers.subprocess.run")
    def test_survives_os_error(self, mock_run, tmp_path):
        cfg = make_cfg(tmp_path)
        mock_run.side_effect = OSError("not found")
        board_send(cfg, "alice", "hello")


# ===========================================================================
# is_pane_typing()
# ===========================================================================


class TestIsPaneTyping:
    @patch("lib.concerns.helpers.tmux")
    def test_true_when_prompt_has_text(self, mock_tmux):
        mock_tmux.return_value = "some output\n❯ git status"
        assert is_pane_typing("cc-test-alice") is True

    @patch("lib.concerns.helpers.tmux")
    def test_false_when_empty_prompt(self, mock_tmux):
        mock_tmux.return_value = "some output\n❯"
        assert is_pane_typing("cc-test-alice") is False

    @patch("lib.concerns.helpers.tmux")
    def test_false_when_short_prompt(self, mock_tmux):
        mock_tmux.return_value = "some output\n❯ a"
        assert is_pane_typing("cc-test-alice") is False

    @patch("lib.concerns.helpers.tmux")
    def test_false_when_no_prompt(self, mock_tmux):
        mock_tmux.return_value = "just some output"
        assert is_pane_typing("cc-test-alice") is False

    @patch("lib.concerns.helpers.tmux")
    def test_false_when_tmux_returns_none(self, mock_tmux):
        mock_tmux.return_value = None
        assert is_pane_typing("cc-test-alice") is False


# ===========================================================================
# has_tool_process()
# ===========================================================================


class TestHasToolProcess:
    @patch("lib.concerns.helpers.tmux")
    def test_false_when_no_pane_pid(self, mock_tmux):
        mock_tmux.return_value = None
        assert has_tool_process("cc-test-alice") is False

    @patch("lib.concerns.helpers.subprocess.run")
    @patch("lib.concerns.helpers.tmux", return_value="12345")
    def test_false_when_no_children(self, mock_tmux, mock_run):
        mock_run.return_value = MagicMock(stdout="", returncode=1)
        assert has_tool_process("cc-test-alice") is False

    @patch("lib.concerns.helpers.subprocess.run")
    @patch("lib.concerns.helpers.tmux", return_value="12345")
    def test_true_when_non_ignored_child(self, mock_tmux, mock_run):
        def side_effect(args, **kwargs):
            if args[0] == "pgrep" and args[2] == "12345":
                return MagicMock(stdout="67890\n", returncode=0)
            if args[0] == "pgrep" and args[2] == "67890":
                return MagicMock(stdout="11111\n", returncode=0)
            if args[0] == "ps":
                return MagicMock(stdout="python\n", returncode=0)
            return MagicMock(stdout="", returncode=1)

        mock_run.side_effect = side_effect
        assert has_tool_process("cc-test-alice") is True

    @patch("lib.concerns.helpers.subprocess.run")
    @patch("lib.concerns.helpers.tmux", return_value="12345")
    def test_false_when_only_caffeinate(self, mock_tmux, mock_run):
        def side_effect(args, **kwargs):
            if args[0] == "pgrep" and args[2] == "12345":
                return MagicMock(stdout="67890\n", returncode=0)
            if args[0] == "pgrep" and args[2] == "67890":
                return MagicMock(stdout="11111\n", returncode=0)
            if args[0] == "ps":
                return MagicMock(stdout="caffeinate\n", returncode=0)
            return MagicMock(stdout="", returncode=1)

        mock_run.side_effect = side_effect
        assert has_tool_process("cc-test-alice") is False
