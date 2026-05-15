"""Tests for the board task queue subsystem.

Covers: task add, task done, task list, auto-promotion from pending
to active, priority ordering, --to assignment, and ownership enforcement.

Tests call actual command functions (_task_add, _task_done, etc.) instead
of duplicating SQL logic.
"""

import pytest

from lib.board_task import _promote_next, _task_add, _task_done, _task_list, _task_next, cmd_task


class TestTaskAdd:
    """Adding tasks to the queue."""

    def test_first_task_becomes_active(self, db, capsys):
        """When no active task exists, the first added task becomes active."""
        _task_add(db, "alice", ["implement feature X"])

        row = db.query_one("SELECT status FROM tasks WHERE session='alice'")
        assert row["status"] == "active"
        assert "OK task #" in capsys.readouterr().out

    def test_second_task_stays_pending(self, db, capsys):
        """When an active task exists, new tasks are added as pending."""
        _task_add(db, "alice", ["task 1"])
        _task_add(db, "alice", ["task 2"])

        rows = db.query("SELECT description, status FROM tasks WHERE session='alice' ORDER BY id")
        assert len(rows) == 2
        assert rows[0]["status"] == "active"
        assert rows[1]["status"] == "pending"

    def test_task_add_with_priority(self, db, capsys):
        """Tasks can be created with a specified priority."""
        _task_add(db, "alice", ["--priority", "5", "high priority task"])
        _task_add(db, "alice", ["normal task"])

        rows = db.query("SELECT description, priority FROM tasks WHERE session='alice' ORDER BY priority DESC")
        assert rows[0]["description"] == "high priority task"
        assert rows[0]["priority"] == 5

    def test_task_add_to_another_session(self, db, capsys):
        """Tasks can be assigned to a different session with --to."""
        _task_add(db, "alice", ["--to", "bob", "task from alice"])

        row = db.query_one("SELECT session, description FROM tasks WHERE session='bob'")
        assert row is not None
        assert row["description"] == "task from alice"
        out = capsys.readouterr().out
        assert "OK task #" in out

    def test_task_add_nudges_assigned_session(self, db, monkeypatch, capsys):
        calls: list[tuple[object, str]] = []

        monkeypatch.setattr("lib.board_task.nudge_session", lambda db_arg, target: calls.append((db_arg, target)))

        _task_add(db, "alice", ["--to", "bob", "task from alice"])
        capsys.readouterr()

        assert calls == [(db, "bob")]

    def test_negative_priority(self, db, capsys):
        """Negative priority values are valid and sort lower."""
        _task_add(db, "alice", ["-p", "-1", "low priority"])
        _task_add(db, "alice", ["-p", "1", "high priority"])

        rows = db.query("SELECT description, priority FROM tasks WHERE session='alice' ORDER BY priority DESC")
        assert rows[0]["description"] == "high priority"
        assert rows[1]["description"] == "low priority"

    def test_task_add_no_description_exits(self, db):
        """Missing description prints usage and exits."""
        with pytest.raises(SystemExit):
            _task_add(db, "alice", [])


class TestTaskDone:
    """Completing tasks and auto-promotion."""

    def test_task_done_marks_as_done(self, db, capsys):
        """Marking a task done updates its status and sets done_at."""
        _task_add(db, "alice", ["finish report"])
        capsys.readouterr()

        _task_done(db, "alice", [])

        row = db.query_one("SELECT status, done_at FROM tasks WHERE session='alice'")
        assert row["status"] == "done"
        assert row["done_at"] is not None

    def test_task_done_promotes_next_pending(self, db, capsys):
        """When active task is completed, the highest-priority pending task becomes active."""
        _task_add(db, "alice", ["task 1"])
        _task_add(db, "alice", ["task 2 low prio"])
        _task_add(db, "alice", ["-p", "5", "task 3 high prio"])
        capsys.readouterr()

        _task_done(db, "alice", [])

        active = db.query_one("SELECT description FROM tasks WHERE session='alice' AND status='active'")
        assert active is not None
        assert active["description"] == "task 3 high prio"

    def test_task_done_no_pending_leaves_empty(self, db, capsys):
        """When no pending tasks remain, no task is promoted."""
        _task_add(db, "alice", ["only task"])
        capsys.readouterr()

        _task_done(db, "alice", [])

        active = db.query_one("SELECT id FROM tasks WHERE session='alice' AND status='active'")
        assert active is None

    def test_already_done_task_noop(self, db, capsys):
        """Completing an already-done task is a no-op."""
        _task_add(db, "alice", ["old task"])
        capsys.readouterr()
        _task_done(db, "alice", [])
        capsys.readouterr()

        # Try to mark done again — should say "already done"
        _task_done(db, "alice", [])
        out = capsys.readouterr().out
        assert "No active task" in out or "already done" in out

    def test_task_done_by_id(self, db, capsys):
        """Can mark a specific task done by ID."""
        _task_add(db, "alice", ["task A"])
        _task_add(db, "alice", ["task B"])
        capsys.readouterr()

        task_id = db.scalar("SELECT id FROM tasks WHERE description='task B'")
        _task_done(db, "alice", [str(task_id)])

        row = db.query_one("SELECT status FROM tasks WHERE id=?", (task_id,))
        assert row["status"] == "done"


class TestTaskOwnership:
    """Task ownership and access control."""

    def test_wrong_session_cannot_complete_others_task(self, db, capsys):
        """Non-owner cannot mark another session's task done."""
        _task_add(db, "bob", ["bob's task"])
        capsys.readouterr()

        task_id = db.scalar("SELECT id FROM tasks WHERE session='bob'")
        with pytest.raises(SystemExit):
            _task_done(db, "alice", [str(task_id)])

    def test_privileged_can_complete_others_task(self, db, capsys):
        """Lead can mark anyone's task done."""
        _task_add(db, "bob", ["bob's task"])
        capsys.readouterr()

        task_id = db.scalar("SELECT id FROM tasks WHERE session='bob'")
        _task_done(db, "lead", [str(task_id)])

        row = db.query_one("SELECT status FROM tasks WHERE id=?", (task_id,))
        assert row["status"] == "done"


class TestTaskList:
    """Task listing and filtering."""

    def test_task_list_shows_correct_state(self, db, capsys):
        """Task list distinguishes active, pending, and done tasks."""
        _task_add(db, "alice", ["active task"])
        _task_add(db, "alice", ["pending task"])
        capsys.readouterr()

        _task_list(db, "alice", [])
        out = capsys.readouterr().out
        assert "active task" in out
        assert "pending task" in out

    def test_task_list_all_sessions(self, db, capsys):
        """--all flag shows tasks from all sessions."""
        _task_add(db, "alice", ["alice task"])
        _task_add(db, "bob", ["bob task"])
        capsys.readouterr()

        _task_list(db, "alice", ["--all"])
        out = capsys.readouterr().out
        assert "alice" in out
        assert "bob" in out

    def test_task_list_include_done(self, db, capsys):
        """Including done tasks shows the full history."""
        _task_add(db, "alice", ["current"])
        _task_add(db, "alice", ["will be done"])
        capsys.readouterr()
        _task_done(db, "alice", [])
        capsys.readouterr()

        _task_list(db, "alice", ["--done"])
        out = capsys.readouterr().out
        assert "current" in out
        assert "will be done" in out

    def test_task_ordering_by_priority_and_id(self, db, capsys):
        """Tasks are ordered by priority DESC, then id ASC."""
        _task_add(db, "alice", ["first added"])
        # Add two more pending tasks with different priorities
        _task_add(db, "alice", ["-p", "10", "high prio"])
        _task_add(db, "alice", ["second added"])
        capsys.readouterr()

        _task_list(db, "alice", [])
        out = capsys.readouterr().out
        # active task ("first added") shown first, then high prio, then second added
        first_pos = out.index("first added")
        high_pos = out.index("high prio")
        second_pos = out.index("second added")
        assert first_pos < high_pos < second_pos


class TestPromoteNext:
    """Auto-promotion logic."""

    def test_promote_next_when_no_active(self, db):
        """Promotes highest-priority pending task when no active task exists."""
        db.execute(
            "INSERT INTO tasks(session, description, status, priority) VALUES (?, ?, 'pending', 0)", ("alice", "low")
        )
        db.execute(
            "INSERT INTO tasks(session, description, status, priority) VALUES (?, ?, 'pending', 5)", ("alice", "high")
        )

        _promote_next(db, "alice")

        active = db.query_one("SELECT description FROM tasks WHERE session='alice' AND status='active'")
        assert active["description"] == "high"

    def test_promote_next_noop_when_active_exists(self, db):
        """Does nothing when an active task already exists."""
        db.execute(
            "INSERT INTO tasks(session, description, status, priority) VALUES (?, ?, 'active', 0)", ("alice", "current")
        )
        db.execute(
            "INSERT INTO tasks(session, description, status, priority) VALUES (?, ?, 'pending', 5)",
            ("alice", "waiting"),
        )

        _promote_next(db, "alice")

        pending = db.query_one("SELECT status FROM tasks WHERE description='waiting'")
        assert pending["status"] == "pending"

    def test_task_next_shows_queue(self, db, capsys):
        """task next promotes and displays the queue."""
        _task_add(db, "alice", ["only task"])
        _task_done(db, "alice", [])
        _task_add(db, "alice", ["next task"])
        capsys.readouterr()

        _task_next(db, "alice")
        out = capsys.readouterr().out
        assert "next task" in out


class TestCmdTask:
    """cmd_task dispatch and edge cases."""

    def test_invalid_subcommand_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_task(db, "alice", ["bogus"])

    def test_no_args_defaults_to_list(self, db, capsys):
        cmd_task(db, "alice", [])
        out = capsys.readouterr().out
        assert "任务队列" in out

    def test_dispatches_add(self, db, capsys):
        cmd_task(db, "alice", ["add", "test task"])
        out = capsys.readouterr().out
        assert "OK task #" in out

    def test_done_invalid_id_exits(self, db):
        with pytest.raises(SystemExit):
            _task_done(db, "alice", ["notanumber"])

    def test_done_nonexistent_id_exits(self, db):
        with pytest.raises(SystemExit):
            _task_done(db, "alice", ["9999"])

    def test_list_by_positional_session(self, db, capsys):
        _task_add(db, "bob", ["bob task"])
        capsys.readouterr()
        _task_list(db, "alice", ["bob"])
        out = capsys.readouterr().out
        assert "bob task" in out

    def test_list_too_many_positional_exits(self, db):
        with pytest.raises(SystemExit):
            _task_list(db, "alice", ["bob", "charlie"])

    def test_list_all_include_done(self, db, capsys):
        _task_add(db, "alice", ["will finish"])
        capsys.readouterr()
        _task_done(db, "alice", [])
        capsys.readouterr()
        _task_list(db, "alice", ["--all", "--done"])
        out = capsys.readouterr().out
        assert "will finish" in out
        assert "done" in out
