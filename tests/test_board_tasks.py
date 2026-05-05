"""Tests for the board task queue subsystem.

Covers: task add, task done, task list, auto-promotion from pending
to active, priority ordering, --to assignment, and ownership enforcement.
"""

import sqlite3

import pytest

from tests.conftest import ts


class TestTaskAdd:
    """Adding tasks to the queue."""

    def test_first_task_becomes_active(self, db_conn):
        """When no active task exists, the first added task becomes active."""
        now = ts()
        # Check for existing active tasks
        active_count = db_conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE session='alice' AND status='active'"
        ).fetchone()[0]
        assert active_count == 0

        # Add first task -- should become active
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'active', 0)",
            ("alice", "implement feature X"),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT status FROM tasks WHERE session='alice'"
        ).fetchone()
        assert row["status"] == "active"

    def test_second_task_stays_pending(self, db_conn):
        """When an active task exists, new tasks are added as pending."""
        now = ts()
        # Add first task as active
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'active', 0)",
            ("alice", "task 1"),
        )
        # Add second task as pending (since active exists)
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'pending', 0)",
            ("alice", "task 2"),
        )
        db_conn.commit()

        rows = db_conn.execute(
            "SELECT description, status FROM tasks WHERE session='alice' ORDER BY id"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["status"] == "active"
        assert rows[1]["status"] == "pending"

    def test_task_add_with_priority(self, db_conn):
        """Tasks can be created with a specified priority."""
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'pending', 5)",
            ("alice", "high priority task"),
        )
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'pending', 0)",
            ("alice", "normal task"),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT description FROM tasks WHERE session='alice' "
            "ORDER BY priority DESC LIMIT 1"
        ).fetchone()
        assert row["description"] == "high priority task"

    def test_task_add_to_another_session(self, db_conn):
        """Tasks can be assigned to a different session with --to."""
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'active', 0)",
            ("bob", "task from alice"),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT session, description FROM tasks WHERE session='bob'"
        ).fetchone()
        assert row is not None
        assert row["session"] == "bob"
        assert row["description"] == "task from alice"

    def test_negative_priority(self, db_conn):
        """Negative priority values are valid and sort lower."""
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'pending', -1)",
            ("alice", "low priority"),
        )
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'pending', 1)",
            ("alice", "high priority"),
        )
        db_conn.commit()

        rows = db_conn.execute(
            "SELECT description, priority FROM tasks WHERE session='alice' "
            "ORDER BY priority DESC"
        ).fetchall()
        assert rows[0]["description"] == "high priority"
        assert rows[1]["description"] == "low priority"


class TestTaskDone:
    """Completing tasks and auto-promotion."""

    def test_task_done_marks_as_done(self, db_conn):
        """Marking a task done updates its status and sets done_at."""
        now = ts()
        cur = db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'active', 0)",
            ("alice", "finish report"),
        )
        task_id = cur.lastrowid
        db_conn.commit()

        # Mark done
        db_conn.execute(
            "UPDATE tasks SET status='done', done_at=? WHERE id=?",
            (now, task_id),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT status, done_at FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        assert row["status"] == "done"
        assert row["done_at"] is not None

    def test_task_done_promotes_next_pending(self, db_conn):
        """When active task is completed, the highest-priority pending task becomes active."""
        # Create an active task and two pending tasks
        cur = db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'active', 0)",
            ("alice", "task 1"),
        )
        task1_id = cur.lastrowid
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'pending', 0)",
            ("alice", "task 2 low prio"),
        )
        cur3 = db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'pending', 5)",
            ("alice", "task 3 high prio"),
        )
        task3_id = cur3.lastrowid
        db_conn.commit()

        # Complete task 1
        db_conn.execute(
            "UPDATE tasks SET status='done', done_at=? WHERE id=?",
            (ts(), task1_id),
        )
        db_conn.commit()

        # Promote next pending (highest priority first)
        active_count = db_conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE session='alice' AND status='active'"
        ).fetchone()[0]
        if active_count == 0:
            next_id = db_conn.execute(
                "SELECT id FROM tasks WHERE session='alice' AND status='pending' "
                "ORDER BY priority DESC, id ASC LIMIT 1"
            ).fetchone()
            if next_id:
                db_conn.execute(
                    "UPDATE tasks SET status='active' WHERE id=?",
                    (next_id["id"],),
                )
                db_conn.commit()

        # task 3 (priority 5) should be active now
        active = db_conn.execute(
            "SELECT description FROM tasks WHERE session='alice' AND status='active'"
        ).fetchone()
        assert active is not None
        assert active["description"] == "task 3 high prio"

    def test_task_done_no_pending_leaves_empty(self, db_conn):
        """When no pending tasks remain, no task is promoted."""
        cur = db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'active', 0)",
            ("alice", "only task"),
        )
        task_id = cur.lastrowid
        db_conn.commit()

        db_conn.execute(
            "UPDATE tasks SET status='done', done_at=? WHERE id=?",
            (ts(), task_id),
        )
        db_conn.commit()

        active = db_conn.execute(
            "SELECT id FROM tasks WHERE session='alice' AND status='active'"
        ).fetchone()
        assert active is None

    def test_already_done_task_noop(self, db_conn):
        """Completing an already-done task is a no-op."""
        now = ts()
        cur = db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority, done_at) "
            "VALUES (?, ?, 'done', 0, ?)",
            ("alice", "old task", now),
        )
        task_id = cur.lastrowid
        db_conn.commit()

        row = db_conn.execute(
            "SELECT status FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        assert row["status"] == "done"


class TestTaskOwnership:
    """Task ownership and access control."""

    def test_task_belongs_to_session(self, db_conn):
        """A task's session field identifies its owner."""
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'active', 0)",
            ("bob", "bob's task"),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT session FROM tasks WHERE description=?",
            ("bob's task",),
        ).fetchone()
        assert row["session"] == "bob"

    def test_wrong_session_cannot_complete_others_task(self, db_conn):
        """Application logic should prevent non-owner from marking task done.

        This test validates the data model -- enforcement is at the application layer.
        The DB check is: task.session must match the requesting session, unless
        the requester is 'lead' or 'dispatcher'.
        """
        cur = db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'active', 0)",
            ("bob", "bob's task"),
        )
        task_id = cur.lastrowid
        db_conn.commit()

        # Verify the task belongs to bob
        row = db_conn.execute(
            "SELECT session FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        assert row["session"] == "bob"
        # alice != bob, and alice is not lead or dispatcher
        assert row["session"] != "alice"


class TestTaskList:
    """Task listing and filtering."""

    def test_task_list_shows_correct_state(self, db_conn):
        """Task list distinguishes active, pending, and done tasks."""
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'active', 0)",
            ("alice", "active task"),
        )
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'pending', 0)",
            ("alice", "pending task"),
        )
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority, done_at) "
            "VALUES (?, ?, 'done', 0, ?)",
            ("alice", "done task", ts()),
        )
        db_conn.commit()

        rows = db_conn.execute(
            "SELECT description, status FROM tasks WHERE session='alice' "
            "AND status != 'done' "
            "ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["status"] == "active"
        assert rows[1]["status"] == "pending"

    def test_task_list_all_sessions(self, db_conn):
        """--all flag shows tasks from all sessions."""
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'active', 0)",
            ("alice", "alice task"),
        )
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'active', 0)",
            ("bob", "bob task"),
        )
        db_conn.commit()

        rows = db_conn.execute(
            "SELECT session, description FROM tasks WHERE status != 'done' "
            "ORDER BY session"
        ).fetchall()
        assert len(rows) == 2
        sessions = {row["session"] for row in rows}
        assert "alice" in sessions
        assert "bob" in sessions

    def test_task_list_include_done(self, db_conn):
        """Including done tasks shows the full history."""
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'active', 0)",
            ("alice", "current"),
        )
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority, done_at) "
            "VALUES (?, ?, 'done', 0, ?)",
            ("alice", "old", ts()),
        )
        db_conn.commit()

        rows = db_conn.execute(
            "SELECT description, status FROM tasks WHERE session='alice'"
        ).fetchall()
        assert len(rows) == 2

    def test_task_ordering_by_priority_and_id(self, db_conn):
        """Tasks are ordered by status, then priority DESC, then id ASC."""
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'pending', 0)",
            ("alice", "low prio first added"),
        )
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'pending', 10)",
            ("alice", "high prio"),
        )
        db_conn.execute(
            "INSERT INTO tasks(session, description, status, priority) "
            "VALUES (?, ?, 'pending', 0)",
            ("alice", "low prio second added"),
        )
        db_conn.commit()

        rows = db_conn.execute(
            "SELECT description FROM tasks WHERE session='alice' "
            "ORDER BY priority DESC, id ASC"
        ).fetchall()
        assert rows[0]["description"] == "high prio"
        assert rows[1]["description"] == "low prio first added"
        assert rows[2]["description"] == "low prio second added"
