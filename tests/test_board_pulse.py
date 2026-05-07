"""Tests for the board pulse (heartbeat) subsystem."""

from lib.board_pulse import cmd_pulse


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
