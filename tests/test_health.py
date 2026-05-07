"""Tests for lib/health.py — session health report helpers."""

from pathlib import Path
from unittest.mock import patch

from lib.health import get_sessions, is_claude_running, session_status

PREFIX = "cc-test"


class TestGetSessions:
    @patch("lib.health._tmux")
    def test_extracts_dev_sessions(self, mock_tmux):
        mock_tmux.return_value = "cc-test-alice\ncc-test-bob\ncc-test-charlie"
        result = get_sessions(PREFIX)
        assert "alice" in result
        assert "bob" in result
        assert "charlie" in result

    @patch("lib.health._tmux")
    def test_excludes_dispatcher_and_lead(self, mock_tmux):
        mock_tmux.return_value = "cc-test-alice\ncc-test-dispatcher\ncc-test-lead"
        result = get_sessions(PREFIX)
        assert result == ["alice"]

    @patch("lib.health._tmux")
    def test_ignores_other_sessions(self, mock_tmux):
        mock_tmux.return_value = "cc-test-alice\nother-session\nrandom"
        result = get_sessions(PREFIX)
        assert result == ["alice"]

    @patch("lib.health._tmux")
    def test_returns_empty_on_failure(self, mock_tmux):
        mock_tmux.return_value = None
        assert get_sessions(PREFIX) == []

    @patch("lib.health._tmux")
    def test_sorted_order(self, mock_tmux):
        mock_tmux.return_value = "cc-test-charlie\ncc-test-alice\ncc-test-bob"
        result = get_sessions(PREFIX)
        assert result == ["alice", "bob", "charlie"]


class TestIsClaudeRunning:
    @patch("lib.health._tmux")
    def test_true_when_node_running(self, mock_tmux):
        mock_tmux.side_effect = lambda *args: {
            ("has-session", "-t", "cc-test-alice"): "",
            ("list-panes", "-t", "cc-test-alice", "-F", "#{pane_current_command}"): "node",
        }.get(args)
        assert is_claude_running("cc-test-alice") is True

    @patch("lib.health._tmux")
    def test_false_when_shell(self, mock_tmux):
        mock_tmux.side_effect = lambda *args: {
            ("has-session", "-t", "cc-test-alice"): "",
            ("list-panes", "-t", "cc-test-alice", "-F", "#{pane_current_command}"): "zsh",
        }.get(args)
        assert is_claude_running("cc-test-alice") is False

    @patch("lib.health._tmux")
    def test_false_when_no_session(self, mock_tmux):
        mock_tmux.return_value = None
        assert is_claude_running("cc-test-alice") is False

    @patch("lib.health._tmux")
    def test_false_when_bash(self, mock_tmux):
        mock_tmux.side_effect = lambda *args: {
            ("has-session", "-t", "cc-test-alice"): "",
            ("list-panes", "-t", "cc-test-alice", "-F", "#{pane_current_command}"): "bash",
        }.get(args)
        assert is_claude_running("cc-test-alice") is False

    @patch("lib.health._tmux")
    def test_false_when_empty_command(self, mock_tmux):
        mock_tmux.side_effect = lambda *args: {
            ("has-session", "-t", "cc-test-alice"): "",
            ("list-panes", "-t", "cc-test-alice", "-F", "#{pane_current_command}"): "",
        }.get(args)
        assert is_claude_running("cc-test-alice") is False


class TestSessionStatus:
    @patch("lib.health._tmux")
    def test_offline_when_no_session(self, mock_tmux):
        mock_tmux.return_value = None
        assert session_status("cc-test-alice", Path("/tmp/idle-cache")) == "offline"

    @patch("lib.health._tmux")
    def test_exited_when_shell(self, mock_tmux):
        mock_tmux.side_effect = lambda *args: {
            ("has-session", "-t", "cc-test-alice"): "",
            ("list-panes", "-t", "cc-test-alice", "-F", "#{pane_current_command}"): "zsh",
        }.get(args)
        assert session_status("cc-test-alice", Path("/tmp/nonexistent-cache")) == "exited"

    @patch("lib.health._tmux")
    def test_idle_from_cache(self, mock_tmux, tmp_path):
        mock_tmux.side_effect = lambda *args: {
            ("has-session", "-t", "cc-test-alice"): "",
            ("list-panes", "-t", "cc-test-alice", "-F", "#{pane_current_command}"): "node",
        }.get(args)
        cache = tmp_path / "idle-cache"
        cache.write_text("cc-test-alice idle\n")
        assert session_status("cc-test-alice", cache) == "idle"

    @patch("lib.health._tmux")
    def test_active_when_running(self, mock_tmux, tmp_path):
        mock_tmux.side_effect = lambda *args: {
            ("has-session", "-t", "cc-test-alice"): "",
            ("list-panes", "-t", "cc-test-alice", "-F", "#{pane_current_command}"): "node",
        }.get(args)
        cache = tmp_path / "idle-cache"
        assert session_status("cc-test-alice", cache) == "active"

    @patch("lib.health._tmux")
    def test_active_when_not_in_idle_cache(self, mock_tmux, tmp_path):
        mock_tmux.side_effect = lambda *args: {
            ("has-session", "-t", "cc-test-alice"): "",
            ("list-panes", "-t", "cc-test-alice", "-F", "#{pane_current_command}"): "node",
        }.get(args)
        cache = tmp_path / "idle-cache"
        cache.write_text("cc-test-bob idle\n")
        assert session_status("cc-test-alice", cache) == "active"
