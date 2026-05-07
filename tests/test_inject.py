"""Tests for lib/inject.py — message injection into tmux/screen sessions."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lib.inject import detect_mode, inject, send_screen, send_tmux

PREFIX = "cc-test"


class TestDetectMode:
    @patch.dict("os.environ", {"SWARM_MODE": "tmux"})
    def test_env_override_tmux(self):
        assert detect_mode(PREFIX) == "tmux"

    @patch.dict("os.environ", {"SWARM_MODE": "screen"})
    def test_env_override_screen(self):
        assert detect_mode(PREFIX) == "screen"

    @patch.dict("os.environ", {}, clear=True)
    @patch("lib.inject.subprocess.run")
    def test_detects_tmux_from_sessions(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="cc-test-alice\ncc-test-bob\n")
        assert detect_mode(PREFIX) == "tmux"

    @patch.dict("os.environ", {}, clear=True)
    @patch("lib.inject.shutil.which", return_value=None)
    @patch("lib.inject.subprocess.run")
    def test_detects_screen_fallback(self, mock_run, mock_which):
        def side_effect(args, **kwargs):
            if args[0] == "tmux":
                return MagicMock(returncode=1, stdout="")
            if args[0] == "screen":
                return MagicMock(returncode=0, stdout=".cc-test-alice\t(Attached)", stderr="")
            return MagicMock(returncode=1)

        mock_run.side_effect = side_effect
        assert detect_mode(PREFIX) == "screen"

    @patch.dict("os.environ", {}, clear=True)
    @patch("lib.inject.shutil.which", return_value="/usr/bin/tmux")
    @patch("lib.inject.subprocess.run")
    def test_fallback_to_which_tmux(self, mock_run, mock_which):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=5)
        assert detect_mode(PREFIX) == "tmux"

    @patch.dict("os.environ", {}, clear=True)
    @patch("lib.inject.shutil.which")
    @patch("lib.inject.subprocess.run")
    def test_returns_none_when_nothing_found(self, mock_run, mock_which):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="cmd", timeout=5)
        mock_which.return_value = None
        assert detect_mode(PREFIX) == "none"


class TestSendTmux:
    @patch("lib.inject.subprocess.run")
    def test_sends_message(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        result = send_tmux(PREFIX, "alice", "hello world")
        assert result is True
        assert mock_run.call_count == 3

    @patch("lib.inject.subprocess.run")
    def test_returns_false_when_session_missing(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        result = send_tmux(PREFIX, "alice", "hello")
        assert result is False

    @patch("lib.inject.subprocess.run")
    def test_returns_false_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="tmux", timeout=5)
        result = send_tmux(PREFIX, "alice", "hello")
        assert result is False

    @patch("lib.inject.subprocess.run")
    def test_newlines_replaced(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        send_tmux(PREFIX, "alice", "line1\nline2\nline3")
        send_call = mock_run.call_args_list[1]
        args = send_call[0][0]
        assert "line1 line2 line3" in args


class TestSendScreen:
    @patch("time.sleep")
    @patch("lib.inject.subprocess.run")
    def test_sends_message(self, mock_run, mock_sleep):
        mock_run.return_value = MagicMock(returncode=0, stdout=".cc-test-alice\t(Attached)", stderr="")
        result = send_screen(PREFIX, "alice", "hello")
        assert result is True
        assert mock_run.call_count == 3

    @patch("lib.inject.subprocess.run")
    def test_returns_false_when_session_missing(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="no matching sessions", stderr="")
        result = send_screen(PREFIX, "alice", "hello")
        assert result is False

    @patch("lib.inject.subprocess.run")
    def test_returns_false_on_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="screen", timeout=5)
        result = send_screen(PREFIX, "alice", "hello")
        assert result is False


class TestInject:
    @patch("lib.inject.send_tmux", return_value=True)
    @patch("lib.inject.detect_mode", return_value="tmux")
    def test_sends_to_single_target(self, mock_mode, mock_send):
        inject("alice", "hello", prefix=PREFIX, sessions=["alice", "bob"])
        mock_send.assert_called_once_with(PREFIX, "alice", "hello")

    @patch("lib.inject.send_tmux", return_value=True)
    @patch("lib.inject.detect_mode", return_value="tmux")
    def test_broadcasts_to_all(self, mock_mode, mock_send):
        inject("all", "broadcast", prefix=PREFIX, sessions=["alice", "bob"])
        assert mock_send.call_count == 2
        mock_send.assert_any_call(PREFIX, "alice", "broadcast")
        mock_send.assert_any_call(PREFIX, "bob", "broadcast")

    @patch("lib.inject.send_screen", return_value=True)
    @patch("lib.inject.detect_mode", return_value="screen")
    def test_uses_screen_when_detected(self, mock_mode, mock_send):
        inject("alice", "hello", prefix=PREFIX, sessions=["alice"])
        mock_send.assert_called_once()

    @patch("lib.inject.detect_mode", return_value="none")
    def test_exits_on_no_mux(self, mock_mode):
        with pytest.raises(SystemExit):
            inject("alice", "hello", prefix=PREFIX, sessions=["alice"])

    @patch("lib.inject.send_tmux", return_value=True)
    @patch("lib.inject.detect_mode", return_value="tmux")
    def test_target_lowercased(self, mock_mode, mock_send):
        inject("Alice", "hello", prefix=PREFIX, sessions=["alice"])
        mock_send.assert_called_once_with(PREFIX, "alice", "hello")
