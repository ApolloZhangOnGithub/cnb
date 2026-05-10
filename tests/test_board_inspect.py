"""Tests for board_inspect: read-only cross-session inspection."""

import pytest

from lib.board_inspect import cmd_inspect
from lib.board_msg import cmd_send


class TestInspectInbox:
    def test_privileged_inspect_inbox_shows_unread_without_ack_marker(self, db, sessions_dir, capsys):
        cmd_send(db, "bob", ["alice", "read-only hello"])
        capsys.readouterr()

        cmd_inspect(db, "dispatcher", ["inbox", "alice"])
        out = capsys.readouterr().out

        assert "read-only hello" in out
        assert "bob" in out
        assert not (sessions_dir / ".alice.ack_max_id").exists()
        unread = db.scalar("SELECT COUNT(*) FROM inbox WHERE session='alice' AND read=0")
        assert unread == 1

    def test_normal_session_cannot_inspect_another_inbox(self, db, capsys):
        with pytest.raises(SystemExit):
            cmd_inspect(db, "alice", ["inbox", "bob"])

        out = capsys.readouterr().out
        assert "requires lead or dispatcher" in out

    def test_session_can_inspect_own_inbox_without_ack_marker(self, db, sessions_dir, capsys):
        cmd_send(db, "bob", ["alice", "own read-only check"])
        capsys.readouterr()

        cmd_inspect(db, "alice", ["inbox", "alice"])
        out = capsys.readouterr().out

        assert "own read-only check" in out
        assert not (sessions_dir / ".alice.ack_max_id").exists()
        unread = db.scalar("SELECT COUNT(*) FROM inbox WHERE session='alice' AND read=0")
        assert unread == 1


class TestInspectTasks:
    def test_privileged_inspect_tasks_shows_active_and_pending(self, db, capsys):
        db.execute(
            "INSERT INTO tasks(session, description, status, priority) VALUES (?, ?, ?, ?)",
            ("alice", "active task", "active", 0),
        )
        db.execute(
            "INSERT INTO tasks(session, description, status, priority) VALUES (?, ?, ?, ?)",
            ("alice", "pending task", "pending", 5),
        )
        db.execute(
            "INSERT INTO tasks(session, description, status, priority, done_at) VALUES (?, ?, ?, ?, ?)",
            ("alice", "done task", "done", 0, "2026-05-10 12:00:00"),
        )

        cmd_inspect(db, "lead", ["tasks", "alice"])
        out = capsys.readouterr().out

        assert "active task" in out
        assert "pending task" in out
        assert "done task" not in out

    def test_inspect_tasks_include_done(self, db, capsys):
        db.execute(
            "INSERT INTO tasks(session, description, status, priority, done_at) VALUES (?, ?, ?, ?, ?)",
            ("alice", "done task", "done", 0, "2026-05-10 12:00:00"),
        )

        cmd_inspect(db, "dispatcher", ["tasks", "alice", "--done"])
        out = capsys.readouterr().out

        assert "done task" in out
        assert "[done p0]" in out

    def test_normal_session_cannot_inspect_another_task_queue(self, db):
        with pytest.raises(SystemExit):
            cmd_inspect(db, "alice", ["tasks", "bob"])


class TestInspectUsage:
    def test_missing_args_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_inspect(db, "dispatcher", [])

    def test_unknown_subcommand_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_inspect(db, "dispatcher", ["status", "alice"])
