"""Tests for lib/panel.py — status_icon logic.

Covers: session detection, pane command classification, output pattern matching.
All tmux subprocess calls are mocked.
"""

from unittest.mock import MagicMock, patch

from lib.panel import status_icon


def _mock_tmux_calls(has_session=True, pane_cmd="node", capture_output=""):
    def side_effect(cmd, **kwargs):
        r = MagicMock()
        r.returncode = 0
        r.stdout = ""
        if "has-session" in cmd:
            r.returncode = 0 if has_session else 1
            r.stdout = "" if has_session else None
        elif "list-panes" in cmd:
            r.stdout = pane_cmd
        elif "capture-pane" in cmd:
            r.stdout = capture_output
        return r

    return side_effect


class TestStatusIcon:
    def test_offline_session(self):
        with patch("lib.panel._tmux", return_value=None):
            assert status_icon("cnb", "alice") == "  "

    def test_shell_only_session(self):
        with patch("lib.panel._tmux") as mock:
            call_count = [0]

            def side_effect(*args):
                call_count[0] += 1
                if call_count[0] == 1:
                    return ""  # has-session ok
                if call_count[0] == 2:
                    return "zsh"  # pane command is shell
                return ""

            mock.side_effect = side_effect
            result = status_icon("cnb", "alice")
            assert result == "!!"

    def test_shell_variants(self):
        for shell in ("zsh", "bash", "sh", "-zsh", "-bash", ""):
            with patch("lib.panel._tmux") as mock:

                def make_side_effect(s):
                    counter = [0]

                    def side_effect(*args):
                        counter[0] += 1
                        if counter[0] == 1:
                            return ""
                        if counter[0] == 2:
                            return s
                        return ""

                    return side_effect

                mock.side_effect = make_side_effect(shell)
                assert status_icon("cnb", "alice") == "!!", f"expected !! for shell {shell!r}"

    def test_active_spinner(self):
        with patch("lib.panel._tmux") as mock:
            call_count = [0]

            def side_effect(*args):
                call_count[0] += 1
                if call_count[0] == 1:
                    return ""
                if call_count[0] == 2:
                    return "node"
                if call_count[0] == 3:
                    return "some output\n⠋ Working on task..."
                return ""

            mock.side_effect = side_effect
            assert status_icon("cnb", "alice") == ">>"

    def test_bypass_permissions(self):
        with patch("lib.panel._tmux") as mock:
            call_count = [0]

            def side_effect(*args):
                call_count[0] += 1
                if call_count[0] == 1:
                    return ""
                if call_count[0] == 2:
                    return "node"
                if call_count[0] == 3:
                    return "line1\nline2\nbypass permissions\nline4"
                return ""

            mock.side_effect = side_effect
            assert status_icon("cnb", "alice") == ".."

    def test_idle_with_capture(self):
        with patch("lib.panel._tmux") as mock:
            call_count = [0]

            def side_effect(*args):
                call_count[0] += 1
                if call_count[0] == 1:
                    return ""
                if call_count[0] == 2:
                    return "node"
                if call_count[0] == 3:
                    return "some regular output"
                return ""

            mock.side_effect = side_effect
            assert status_icon("cnb", "alice") == "~~"

    def test_capture_pane_returns_none(self):
        with patch("lib.panel._tmux") as mock:
            call_count = [0]

            def side_effect(*args):
                call_count[0] += 1
                if call_count[0] == 1:
                    return ""
                if call_count[0] == 2:
                    return "node"
                if call_count[0] == 3:
                    return None
                return ""

            mock.side_effect = side_effect
            assert status_icon("cnb", "alice") == "~~"
