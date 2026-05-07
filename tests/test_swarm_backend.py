"""Tests for lib/swarm_backend.py — TmuxBackend and ScreenBackend methods.

Covers: session name construction, is_running, is_agent_active, capture_pane,
inject, stop_session (graceful + force-kill), status_line, ScreenBackend parsing.
All subprocess calls are mocked per project convention.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.swarm_backend import ScreenBackend, TmuxBackend, detect_backend

# ---------------------------------------------------------------------------
# TmuxBackend
# ---------------------------------------------------------------------------


class TestTmuxSessionName:
    def test_sess_format(self):
        b = TmuxBackend()
        assert b._sess("cnb", "alice") == "cnb-alice"
        assert b._sess("cc-test", "bob") == "cc-test-bob"


class TestTmuxIsRunning:
    def test_running_session(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0)
            assert b.is_running("cnb", "alice") is True
            mock.assert_called_once_with(
                ["tmux", "has-session", "-t", "cnb-alice"],
                capture_output=True,
                timeout=5,
            )

    def test_not_running_session(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1)
            assert b.is_running("cnb", "alice") is False


class TestTmuxPaneCommand:
    def test_returns_first_command(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="node\nbash\n")
            assert b._pane_command("cnb", "alice") == "node"

    def test_returns_empty_on_failure(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1, stdout="")
            assert b._pane_command("cnb", "alice") == ""


class TestTmuxIsAgentActive:
    def test_active_when_non_shell_command(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.side_effect = [
                MagicMock(returncode=0),  # has-session
                MagicMock(returncode=0, stdout="node\n"),  # list-panes
            ]
            assert b.is_agent_active("cnb", "alice") is True

    def test_inactive_when_shell(self):
        b = TmuxBackend()
        for shell in ("zsh", "bash", "sh", "-zsh", "-bash", ""):
            with patch("subprocess.run") as mock:
                mock.side_effect = [
                    MagicMock(returncode=0),  # has-session
                    MagicMock(returncode=0, stdout=f"{shell}\n"),  # list-panes
                ]
                assert b.is_agent_active("cnb", "alice") is False, f"should be inactive for {shell!r}"

    def test_inactive_when_session_not_running(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1)
            assert b.is_agent_active("cnb", "alice") is False


class TestTmuxCapturePane:
    def test_capture_success(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="hello world\n❯ ")
            result = b.capture_pane("cnb", "alice")
            assert result == "hello world\n❯ "

    def test_capture_failure(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1, stdout="")
            assert b.capture_pane("cnb", "alice") == ""


class TestTmuxStatusLine:
    def test_format(self):
        b = TmuxBackend()
        assert b.status_line("cnb", "alice", "claude") == "running (tmux, engine: claude)"


class TestTmuxInject:
    def test_inject_to_running_session(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0)
            b.inject("cnb", "alice", "hello world")
            assert mock.call_count == 3  # has-session, send-keys -l, send-keys Enter

    def test_inject_to_stopped_session_exits(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1)  # has-session fails
            with pytest.raises(SystemExit):
                b.inject("cnb", "alice", "hello")

    def test_inject_replaces_newlines(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0)
            b.inject("cnb", "alice", "line1\nline2")
            send_keys_call = mock.call_args_list[1]
            assert "line1 line2" in send_keys_call[0][0]


class TestTmuxStopSession:
    def test_graceful_exit(self):
        b = TmuxBackend()
        call_count = [0]

        def side_effect(cmd, **kwargs):
            r = MagicMock()
            if cmd == ["tmux", "has-session", "-t", "cnb-alice"]:
                call_count[0] += 1
                r.returncode = 0 if call_count[0] <= 1 else 1
            else:
                r.returncode = 0
            return r

        with patch("subprocess.run", side_effect=side_effect), patch("time.sleep"):
            b.stop_session("cnb", "alice", "save-state")

    def test_force_kill_after_timeout(self, capsys):
        b = TmuxBackend()

        def always_running(cmd, **kwargs):
            r = MagicMock()
            if cmd == ["tmux", "has-session", "-t", "cnb-alice"]:
                r.returncode = 0  # always running
            else:
                r.returncode = 0
            return r

        with patch("subprocess.run", side_effect=always_running), patch("time.sleep"):
            b.stop_session("cnb", "alice", "save-state")
        out = capsys.readouterr().out
        assert "force killed" in out


class TestTmuxWaitForShell:
    def test_finds_shell_prompt(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="user@host $ ")
            with patch("time.sleep"):
                assert b.wait_for_shell("cnb", "alice", timeout=5) is True

    def test_timeout_no_prompt(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="loading...")
            with patch("time.sleep"):
                assert b.wait_for_shell("cnb", "alice", timeout=3) is False


class TestTmuxWaitForPrompt:
    def test_finds_claude_prompt(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="some output\n❯ ")
            with patch("time.sleep"):
                assert b.wait_for_prompt("cnb", "alice", timeout=10) is True

    def test_timeout_no_claude_prompt(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="still loading")
            with patch("time.sleep"):
                assert b.wait_for_prompt("cnb", "alice", timeout=4) is False


class TestTmuxAutoAcceptTrust:
    def test_accepts_trust_dialog(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="I trust this project")
            with patch("time.sleep"):
                b.auto_accept_trust("cnb", "alice")
            send_enter = [c for c in mock.call_args_list if "Enter" in str(c)]
            assert len(send_enter) > 0

    def test_times_out_without_trust(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="regular output")
            with patch("time.sleep"):
                b.auto_accept_trust("cnb", "alice")


class TestTmuxStartSession:
    def test_creates_session_and_sends_cmd(self):
        b = TmuxBackend()
        calls = []

        def track(cmd, **kwargs):
            calls.append(cmd)
            r = MagicMock()
            r.returncode = 0
            r.stdout = "user@host $ "
            return r

        with patch("subprocess.run", side_effect=track), patch("time.sleep"):
            result = b.start_session("cnb", "alice", Path("/project"), "claude --name alice")
        assert result == "cnb-alice"
        assert ["tmux", "new-session", "-d", "-s", "cnb-alice", "-x", "200", "-y", "50"] in calls


class TestTmuxEnableMouse:
    def test_sets_mouse_option(self):
        b = TmuxBackend()
        with patch("subprocess.run") as mock:
            b.enable_mouse()
            mock.assert_called_once_with(
                ["tmux", "set", "-g", "mouse", "on"],
                capture_output=True,
                timeout=10,
            )


# ---------------------------------------------------------------------------
# ScreenBackend
# ---------------------------------------------------------------------------


class TestScreenSessionName:
    def test_sess_format(self):
        b = ScreenBackend()
        assert b._sess("cnb", "alice") == "cnb-alice"


class TestScreenIsRunning:
    def test_running_when_in_list(self):
        b = ScreenBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                returncode=0,
                stdout="123.cnb-alice\t(Attached)\n456.cnb-bob\t(Detached)\n",
                stderr="",
            )
            assert b.is_running("cnb", "alice") is True

    def test_not_running_when_absent(self):
        b = ScreenBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                returncode=0,
                stdout="456.cnb-bob\t(Detached)\n",
                stderr="",
            )
            assert b.is_running("cnb", "alice") is False

    def test_handles_no_screen_sessions(self):
        b = ScreenBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="No Sockets found in /var/folders/...\n",
            )
            assert b.is_running("cnb", "alice") is False


class TestScreenCapturePane:
    def test_always_empty(self):
        b = ScreenBackend()
        assert b.capture_pane("cnb", "alice") == ""


class TestScreenStatusLine:
    def test_extracts_state_from_screen_list(self):
        b = ScreenBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                returncode=0,
                stdout="123.cnb-alice\t(Attached)\n",
                stderr="",
            )
            result = b.status_line("cnb", "alice", "claude")
            assert "screen" in result
            assert "claude" in result
            assert "(Attached)" in result

    def test_no_match_returns_empty_state(self):
        b = ScreenBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = b.status_line("cnb", "alice", "claude")
            assert "screen" in result


class TestScreenInject:
    def test_inject_to_running_session(self):
        b = ScreenBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(
                returncode=0,
                stdout="123.cnb-alice\t(Attached)\n",
                stderr="",
            )
            with patch("time.sleep"):
                b.inject("cnb", "alice", "hello")

    def test_inject_to_stopped_session_exits(self):
        b = ScreenBackend()
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1, stdout="", stderr="No Sockets")
            with pytest.raises(SystemExit):
                b.inject("cnb", "alice", "hello")

    def test_inject_replaces_newlines(self):
        b = ScreenBackend()
        calls = []

        def track(cmd, **kwargs):
            calls.append(cmd)
            r = MagicMock()
            r.returncode = 0
            r.stdout = "123.cnb-alice\t(Attached)\n"
            r.stderr = ""
            return r

        with patch("subprocess.run", side_effect=track), patch("time.sleep"):
            b.inject("cnb", "alice", "line1\nline2")
        stuff_calls = [c for c in calls if "stuff" in c]
        assert any("line1 line2" in str(c) for c in stuff_calls)


class TestScreenStopSession:
    def test_force_kill_after_timeout(self, capsys):
        b = ScreenBackend()

        def always_running(cmd, **kwargs):
            r = MagicMock()
            r.returncode = 0
            r.stdout = "123.cnb-alice\t(Attached)\n"
            r.stderr = ""
            return r

        with patch("subprocess.run", side_effect=always_running), patch("time.sleep"):
            b.stop_session("cnb", "alice", "save-state")
        out = capsys.readouterr().out
        assert "force killed" in out


class TestScreenStartSession:
    def test_creates_session_and_sends_cmd(self):
        b = ScreenBackend()
        calls = []

        def track(cmd, **kwargs):
            calls.append(cmd)
            return MagicMock(returncode=0)

        with patch("subprocess.run", side_effect=track), patch("time.sleep"):
            result = b.start_session("cnb", "alice", Path("/project"), "claude --name alice")
        assert result == "cnb-alice"
        assert ["screen", "-dmS", "cnb-alice"] in calls


# ---------------------------------------------------------------------------
# detect_backend (additional cases beyond test_swarm.py)
# ---------------------------------------------------------------------------


class TestDetectBackendFallback:
    def test_prefers_tmux_over_screen(self):
        with patch.dict("os.environ", {}, clear=False):
            env_no_override = {k: v for k, v in __import__("os").environ.items() if k != "SWARM_MODE"}
            with patch.dict("os.environ", env_no_override, clear=True):
                with patch("shutil.which", side_effect=lambda x: "/usr/bin/tmux" if x == "tmux" else None):
                    b = detect_backend()
                assert isinstance(b, TmuxBackend)

    def test_falls_back_to_screen(self):
        env_no_override = {k: v for k, v in __import__("os").environ.items() if k != "SWARM_MODE"}
        with patch.dict("os.environ", env_no_override, clear=True):
            with patch("shutil.which", side_effect=lambda x: "/usr/bin/screen" if x == "screen" else None):
                b = detect_backend()
            assert isinstance(b, ScreenBackend)
