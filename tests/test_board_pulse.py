"""Tests for the board pulse (heartbeat) subsystem."""

from datetime import datetime, timedelta
from unittest.mock import patch

from lib.board_pulse import cmd_pulse
from lib.board_view import _heartbeat_status


class TestPulse:
    def test_pulse_writes_heartbeat(self, db):
        row = db.query_one("SELECT last_heartbeat FROM sessions WHERE name='alice'")
        assert row["last_heartbeat"] is None

        cmd_pulse(db, "alice")

        row = db.query_one("SELECT last_heartbeat FROM sessions WHERE name='alice'")
        assert row["last_heartbeat"] is not None

    def test_pulse_no_unread_is_silent(self, db, capsys):
        cmd_pulse(db, "alice")
        assert capsys.readouterr().out == ""

    def test_pulse_reports_unread_count(self, db, capsys):
        from lib.board_msg import cmd_send

        cmd_send(db, "bob", ["alice", "hello"])
        capsys.readouterr()

        cmd_pulse(db, "alice")
        out = capsys.readouterr().out
        assert "1 条未读" in out

    def test_pulse_auto_registers_unknown_session(self, db):
        cmd_pulse(db, "newcomer")
        row = db.query_one("SELECT last_heartbeat FROM sessions WHERE name='newcomer'")
        assert row is not None
        assert row["last_heartbeat"] is not None

    def test_pulse_updates_heartbeat_on_repeat(self, db):
        cmd_pulse(db, "alice")
        first = db.query_one("SELECT last_heartbeat FROM sessions WHERE name='alice'")["last_heartbeat"]

        cmd_pulse(db, "alice")
        second = db.query_one("SELECT last_heartbeat FROM sessions WHERE name='alice'")["last_heartbeat"]

        assert second >= first


class TestHeartbeatStatus:
    """Tests for _heartbeat_status tier logic."""

    def _ts_ago(self, seconds: int) -> str:
        return (datetime.now() - timedelta(seconds=seconds)).strftime("%Y-%m-%d %H:%M:%S")

    def test_active_within_2_minutes(self):
        status, ago = _heartbeat_status(self._ts_ago(30), "cc", "alice")
        assert status == "● active"
        assert "s ago" in ago

    def test_active_boundary(self):
        status, _ = _heartbeat_status(self._ts_ago(119), "cc", "alice")
        assert status == "● active"

    def test_thinking_at_2_minutes(self):
        status, ago = _heartbeat_status(self._ts_ago(121), "cc", "alice")
        assert status == "◐ thinking"
        assert "m ago" in ago

    def test_thinking_boundary(self):
        status, _ = _heartbeat_status(self._ts_ago(179), "cc", "alice")
        assert status == "◐ thinking"

    def test_stale_at_3_minutes(self):
        status, ago = _heartbeat_status(self._ts_ago(181), "cc", "alice")
        assert status == "○ stale"
        assert "m ago" in ago

    def test_stale_boundary(self):
        status, _ = _heartbeat_status(self._ts_ago(599), "cc", "alice")
        assert status == "○ stale"

    def test_offline_at_10_minutes(self):
        status, ago = _heartbeat_status(self._ts_ago(601), "cc", "alice")
        assert status == "· offline"
        assert "ago" in ago

    def test_offline_shows_hours_for_old_heartbeat(self):
        status, ago = _heartbeat_status(self._ts_ago(7200), "cc", "alice")
        assert status == "· offline"
        assert "h ago" in ago

    def test_no_heartbeat_tmux_fallback_offline(self):
        with patch("lib.board_view._tmux_has_session", return_value=False):
            status, ago = _heartbeat_status(None, "cc", "alice")
        assert status == "· offline"
        assert ago == ""

    def test_no_heartbeat_tmux_running(self):
        with (
            patch("lib.board_view._tmux_has_session", return_value=True),
            patch("lib.board_view._tmux_pane_command", return_value="claude"),
        ):
            status, ago = _heartbeat_status(None, "cc", "alice")
        assert status == "● running"

    def test_no_heartbeat_tmux_dead_shell(self):
        with (
            patch("lib.board_view._tmux_has_session", return_value=True),
            patch("lib.board_view._tmux_pane_command", return_value="zsh"),
        ):
            status, ago = _heartbeat_status(None, "cc", "alice")
        assert status == "○ dead"

    def test_malformed_heartbeat_falls_back(self):
        with patch("lib.board_view._tmux_has_session", return_value=False):
            status, _ = _heartbeat_status("not-a-date", "cc", "alice")
        assert status == "· offline"
