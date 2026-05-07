"""Tests for lib/board_admin.py — suspend, resume, kudos commands.

Covers: cmd_suspend, cmd_resume, cmd_kudos, cmd_kudos_list including
DB state changes, suspended file sync, system messages, and error handling.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.board_admin import cmd_kudos, cmd_kudos_list, cmd_resume, cmd_suspend


@pytest.fixture
def admin_db(db):
    """BoardDB with env set up for admin commands."""
    db.env.suspended_file.write_text("")
    return db


class TestSuspend:
    def test_suspend_adds_to_db(self, admin_db):
        with patch("lib.board_admin.has_session", return_value=False):
            cmd_suspend(admin_db, "lead", ["alice"])
        row = admin_db.scalar("SELECT COUNT(*) FROM suspended WHERE name='alice'")
        assert row == 1

    def test_suspend_writes_file(self, admin_db):
        with patch("lib.board_admin.has_session", return_value=False):
            cmd_suspend(admin_db, "lead", ["alice"])
        assert "alice" in admin_db.env.suspended_file.read_text()

    def test_suspend_creates_system_message(self, admin_db):
        with patch("lib.board_admin.has_session", return_value=False):
            cmd_suspend(admin_db, "lead", ["alice"])
        msg = admin_db.scalar("SELECT body FROM messages WHERE sender='SYSTEM' ORDER BY id DESC LIMIT 1")
        assert "SUSPEND alice by lead" in msg

    def test_suspend_idempotent(self, admin_db, capsys):
        with patch("lib.board_admin.has_session", return_value=False):
            cmd_suspend(admin_db, "lead", ["alice"])
            cmd_suspend(admin_db, "lead", ["alice"])
        output = capsys.readouterr().out
        assert "已在停工名单中" in output

    def test_suspend_no_args_exits(self, admin_db):
        with pytest.raises(SystemExit):
            cmd_suspend(admin_db, "lead", [])

    def test_suspend_nonexistent_session_errors(self, admin_db):
        with pytest.raises(SystemExit):
            cmd_suspend(admin_db, "lead", ["nonexistent"])

    def test_suspend_records_who_suspended(self, admin_db):
        with patch("lib.board_admin.has_session", return_value=False):
            cmd_suspend(admin_db, "lead", ["bob"])
        who = admin_db.scalar("SELECT suspended_by FROM suspended WHERE name='bob'")
        assert who == "lead"


class TestResume:
    def test_resume_removes_from_db(self, admin_db):
        with patch("lib.board_admin.has_session", return_value=False):
            cmd_suspend(admin_db, "lead", ["alice"])
        cmd_resume(admin_db, "lead", ["alice"])
        row = admin_db.scalar("SELECT COUNT(*) FROM suspended WHERE name='alice'")
        assert row == 0

    def test_resume_removes_from_file(self, admin_db):
        with patch("lib.board_admin.has_session", return_value=False):
            cmd_suspend(admin_db, "lead", ["alice"])
        cmd_resume(admin_db, "lead", ["alice"])
        assert "alice" not in admin_db.env.suspended_file.read_text()

    def test_resume_creates_system_message(self, admin_db):
        with patch("lib.board_admin.has_session", return_value=False):
            cmd_suspend(admin_db, "lead", ["alice"])
        cmd_resume(admin_db, "lead", ["alice"])
        msg = admin_db.scalar("SELECT body FROM messages WHERE sender='SYSTEM' ORDER BY id DESC LIMIT 1")
        assert "RESUME alice by lead" in msg

    def test_resume_not_suspended_exits(self, admin_db):
        with pytest.raises(SystemExit):
            cmd_resume(admin_db, "lead", ["alice"])

    def test_resume_no_args_exits(self, admin_db):
        with pytest.raises(SystemExit):
            cmd_resume(admin_db, "lead", [])


class TestKudos:
    def test_kudos_creates_record(self, admin_db):
        cmd_kudos(admin_db, "alice", ["bob", "great", "work"])
        row = admin_db.query("SELECT sender, target, reason FROM kudos")
        assert len(row) == 1
        assert tuple(row[0]) == ("alice", "bob", "great work")

    def test_kudos_with_evidence(self, admin_db):
        cmd_kudos(admin_db, "alice", ["bob", "fix", "--evidence", "abc123"])
        evidence = admin_db.scalar("SELECT evidence FROM kudos WHERE target='bob'")
        assert evidence == "abc123"

    def test_kudos_broadcasts_message(self, admin_db):
        cmd_kudos(admin_db, "alice", ["bob", "nice job"])
        msg = admin_db.scalar("SELECT body FROM messages WHERE recipient='all' ORDER BY id DESC LIMIT 1")
        assert "[KUDOS]" in msg
        assert "bob" in msg

    def test_cannot_kudos_self(self, admin_db):
        with pytest.raises(SystemExit):
            cmd_kudos(admin_db, "alice", ["alice", "I'm great"])

    def test_kudos_no_args_exits(self, admin_db):
        with pytest.raises(SystemExit):
            cmd_kudos(admin_db, "alice", [])

    def test_kudos_one_arg_exits(self, admin_db):
        with pytest.raises(SystemExit):
            cmd_kudos(admin_db, "alice", ["bob"])

    def test_kudos_nonexistent_target_exits(self, admin_db):
        with pytest.raises(SystemExit):
            cmd_kudos(admin_db, "alice", ["ghost", "great", "work"])


class TestKudosList:
    def test_empty_kudos_list(self, admin_db, capsys):
        cmd_kudos_list(admin_db)
        output = capsys.readouterr().out
        assert "Kudos Board" in output

    def test_kudos_list_shows_leaderboard(self, admin_db, capsys):
        cmd_kudos(admin_db, "alice", ["bob", "great work"])
        cmd_kudos(admin_db, "charlie", ["bob", "nice fix"])
        cmd_kudos(admin_db, "alice", ["charlie", "good review"])
        capsys.readouterr()

        cmd_kudos_list(admin_db)
        output = capsys.readouterr().out
        assert "bob: 2 kudos" in output
        assert "charlie: 1 kudos" in output

    def test_kudos_list_shows_recent(self, admin_db, capsys):
        cmd_kudos(admin_db, "alice", ["bob", "great work"])
        capsys.readouterr()

        cmd_kudos_list(admin_db)
        output = capsys.readouterr().out
        assert "great work" in output
