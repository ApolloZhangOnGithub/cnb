"""Tests for lib/tmux_utils.py — shared tmux subprocess wrappers."""

import subprocess
from unittest.mock import MagicMock, patch

from lib.tmux_utils import (
    capture_pane,
    has_session,
    is_agent_running,
    pane_command,
    tmux_ok,
    tmux_run,
    tmux_send,
)


class TestTmuxRun:
    @patch("lib.tmux_utils.subprocess.run")
    def test_returns_stdout_on_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="output\n")
        assert tmux_run("list-sessions") == "output"

    @patch("lib.tmux_utils.subprocess.run")
    def test_returns_none_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="error")
        assert tmux_run("has-session", "-t", "nope") is None

    @patch("lib.tmux_utils.subprocess.run")
    def test_returns_none_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=8)
        assert tmux_run("list-sessions") is None

    @patch("lib.tmux_utils.subprocess.run")
    def test_returns_none_on_os_error(self, mock_run):
        mock_run.side_effect = OSError("tmux not found")
        assert tmux_run("list-sessions") is None

    @patch("lib.tmux_utils.subprocess.run")
    def test_passes_args_to_tmux(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        tmux_run("capture-pane", "-t", "sess", "-p")
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0] == ["tmux", "capture-pane", "-t", "sess", "-p"]


class TestTmuxOk:
    @patch("lib.tmux_utils.subprocess.run")
    def test_true_on_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert tmux_ok("has-session", "-t", "test") is True

    @patch("lib.tmux_utils.subprocess.run")
    def test_false_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        assert tmux_ok("has-session", "-t", "nope") is False

    @patch("lib.tmux_utils.subprocess.run")
    def test_false_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=8)
        assert tmux_ok("has-session", "-t", "test") is False

    @patch("lib.tmux_utils.subprocess.run")
    def test_false_on_os_error(self, mock_run):
        mock_run.side_effect = OSError("no tmux")
        assert tmux_ok("list-sessions") is False


class TestTmuxSend:
    @patch("lib.tmux_utils.subprocess.run")
    def test_pastes_text_then_enter(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert tmux_send("sess", "hello") is True
        assert mock_run.call_count == 3
        first = mock_run.call_args_list[0][0][0]
        assert first[:3] == ["tmux", "load-buffer", "-b"]
        assert mock_run.call_args_list[0].kwargs["input"] == "hello"
        second = mock_run.call_args_list[1][0][0]
        assert second[:2] == ["tmux", "paste-buffer"]
        assert "-p" in second
        assert "-r" in second
        third = mock_run.call_args_list[2][0][0]
        assert "Enter" in third

    @patch("lib.tmux_utils.subprocess.run")
    def test_empty_text_only_sends_enter(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert tmux_send("sess", "") is True
        assert mock_run.call_count == 1
        assert mock_run.call_args_list[0][0][0] == ["tmux", "send-keys", "-t", "sess", "Enter"]

    @patch("lib.tmux_utils.subprocess.run")
    def test_returns_false_on_called_process_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "tmux")
        assert tmux_send("sess", "hello") is False

    @patch("lib.tmux_utils.subprocess.run")
    def test_returns_false_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=8)
        assert tmux_send("sess", "hello") is False

    @patch("lib.tmux_utils.subprocess.run")
    def test_returns_false_on_os_error(self, mock_run):
        mock_run.side_effect = OSError("not found")
        assert tmux_send("sess", "hello") is False


class TestHasSession:
    @patch("lib.tmux_utils.subprocess.run")
    def test_true_when_session_exists(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert has_session("test-sess") is True

    @patch("lib.tmux_utils.subprocess.run")
    def test_false_when_no_session(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        assert has_session("nonexistent") is False


class TestPaneCommand:
    @patch("lib.tmux_utils.subprocess.run")
    def test_returns_first_line(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="node\nbash\n")
        assert pane_command("sess") == "node"

    @patch("lib.tmux_utils.subprocess.run")
    def test_returns_empty_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert pane_command("sess") == ""

    @patch("lib.tmux_utils.subprocess.run")
    def test_returns_empty_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=8)
        assert pane_command("sess") == ""


class TestCapturePaneFunc:
    @patch("lib.tmux_utils.subprocess.run")
    def test_captures_full_pane(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="line1\nline2\n")
        result = capture_pane("sess")
        assert result == "line1\nline2"
        args = mock_run.call_args[0][0]
        assert "-S" not in args

    @patch("lib.tmux_utils.subprocess.run")
    def test_captures_last_n_lines(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="last line\n")
        result = capture_pane("sess", lines=10)
        assert result == "last line"
        args = mock_run.call_args[0][0]
        assert "-S" in args
        assert "-10" in args

    @patch("lib.tmux_utils.subprocess.run")
    def test_returns_empty_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert capture_pane("sess") == ""


class TestIsAgentRunning:
    @patch("lib.tmux_utils.pane_command", return_value="node")
    @patch("lib.tmux_utils.has_session", return_value=True)
    def test_true_when_non_shell(self, _has, _cmd):
        assert is_agent_running("sess") is True

    @patch("lib.tmux_utils.pane_command", return_value="zsh")
    @patch("lib.tmux_utils.has_session", return_value=True)
    def test_false_for_zsh(self, _has, _cmd):
        assert is_agent_running("sess") is False

    @patch("lib.tmux_utils.pane_command", return_value="bash")
    @patch("lib.tmux_utils.has_session", return_value=True)
    def test_false_for_bash(self, _has, _cmd):
        assert is_agent_running("sess") is False

    @patch("lib.tmux_utils.pane_command", return_value="sh")
    @patch("lib.tmux_utils.has_session", return_value=True)
    def test_false_for_sh(self, _has, _cmd):
        assert is_agent_running("sess") is False

    @patch("lib.tmux_utils.pane_command", return_value="-zsh")
    @patch("lib.tmux_utils.has_session", return_value=True)
    def test_false_for_login_zsh(self, _has, _cmd):
        assert is_agent_running("sess") is False

    @patch("lib.tmux_utils.pane_command", return_value="-bash")
    @patch("lib.tmux_utils.has_session", return_value=True)
    def test_false_for_login_bash(self, _has, _cmd):
        assert is_agent_running("sess") is False

    @patch("lib.tmux_utils.pane_command", return_value="")
    @patch("lib.tmux_utils.has_session", return_value=True)
    def test_false_for_empty(self, _has, _cmd):
        assert is_agent_running("sess") is False

    @patch("lib.tmux_utils.has_session", return_value=False)
    def test_false_when_no_session(self, _has):
        assert is_agent_running("sess") is False

    @patch("lib.tmux_utils.pane_command", return_value="python")
    @patch("lib.tmux_utils.has_session", return_value=True)
    def test_true_for_python(self, _has, _cmd):
        assert is_agent_running("sess") is True
