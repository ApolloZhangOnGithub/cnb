"""Tests for board_task: add / done / list / next commands."""

import pytest

from lib.board_task import cmd_task


class TestTaskAdd:
    def test_add_first_task_becomes_active(self, db, capsys):
        cmd_task(db, "alice", ["add", "implement feature X"])
        out = capsys.readouterr().out
        assert "OK task #" in out
        assert "active" in out

        row = db.query_one("SELECT status, description FROM tasks WHERE session='alice'")
        assert row["status"] == "active"
        assert row["description"] == "implement feature X"

    def test_add_second_task_becomes_pending(self, db, capsys):
        cmd_task(db, "alice", ["add", "first task"])
        capsys.readouterr()

        cmd_task(db, "alice", ["add", "second task"])
        out = capsys.readouterr().out
        assert "pending" in out

        rows = db.query("SELECT status FROM tasks WHERE session='alice' ORDER BY id")
        assert rows[0]["status"] == "active"
        assert rows[1]["status"] == "pending"

    def test_add_with_priority(self, db, capsys):
        cmd_task(db, "alice", ["add", "--priority", "5", "high priority task"])
        capsys.readouterr()
        row = db.query_one("SELECT priority FROM tasks WHERE session='alice'")
        assert row["priority"] == 5

    def test_add_to_another_session(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.nudge_session", lambda db, to: None)
        cmd_task(db, "alice", ["add", "--to", "bob", "task for bob"])
        out = capsys.readouterr().out
        assert "bob" in out
        assert "notified bob" in out

        row = db.query_one("SELECT session, description FROM tasks WHERE session='bob'")
        assert row["session"] == "bob"
        assert row["description"] == "task for bob"

    def test_add_no_description_fails(self, db):
        with pytest.raises(SystemExit):
            cmd_task(db, "alice", ["add"])

    def test_add_to_nonexistent_session_fails(self, db, monkeypatch):
        monkeypatch.setattr("lib.board_task.nudge_session", lambda db, to: None)
        with pytest.raises(SystemExit):
            cmd_task(db, "alice", ["add", "--to", "nonexistent", "task"])


class TestTaskDone:
    def test_done_marks_active_task(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.verify_task", lambda root: (True, "5 passed"))
        monkeypatch.setattr("lib.board_task.auto_pr", lambda root, desc, name: None)

        cmd_task(db, "alice", ["add", "finish this"])
        capsys.readouterr()

        cmd_task(db, "alice", ["done"])
        out = capsys.readouterr().out
        assert "OK task #" in out
        assert "done" in out

        row = db.query_one("SELECT status FROM tasks WHERE session='alice'")
        assert row["status"] == "done"

    def test_done_promotes_next_task(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.verify_task", lambda root: (True, "ok"))
        monkeypatch.setattr("lib.board_task.auto_pr", lambda root, desc, name: None)

        cmd_task(db, "alice", ["add", "first"])
        cmd_task(db, "alice", ["add", "second"])
        capsys.readouterr()

        cmd_task(db, "alice", ["done"])
        out = capsys.readouterr().out
        assert "Next:" in out
        assert "second" in out

        rows = db.query("SELECT id, status FROM tasks WHERE session='alice' ORDER BY id")
        assert rows[0]["status"] == "done"
        assert rows[1]["status"] == "active"

    def test_done_skip_verify(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.auto_pr", lambda root, desc, name: None)

        cmd_task(db, "alice", ["add", "quick fix"])
        capsys.readouterr()

        cmd_task(db, "alice", ["done", "--skip-verify"])
        out = capsys.readouterr().out
        assert "OK task #" in out
        assert "验证中" not in out

    def test_done_verify_fails_blocks_completion(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.verify_task", lambda root: (False, "2 failed"))

        cmd_task(db, "alice", ["add", "broken"])
        capsys.readouterr()

        cmd_task(db, "alice", ["done"])
        out = capsys.readouterr().out
        assert "测试未通过" in out
        assert "--skip-verify" in out

        row = db.query_one("SELECT status FROM tasks WHERE session='alice'")
        assert row["status"] == "active"

    def test_done_no_active_task(self, db, capsys):
        cmd_task(db, "alice", ["done"])
        out = capsys.readouterr().out
        assert "No active task" in out

    def test_done_by_id(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.verify_task", lambda root: (True, "ok"))
        monkeypatch.setattr("lib.board_task.auto_pr", lambda root, desc, name: None)

        cmd_task(db, "alice", ["add", "task one"])
        capsys.readouterr()

        task_id = db.scalar("SELECT id FROM tasks WHERE session='alice' LIMIT 1")
        cmd_task(db, "alice", ["done", str(task_id)])
        out = capsys.readouterr().out
        assert f"OK task #{task_id} done" in out

    def test_done_other_session_task_fails(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.nudge_session", lambda db, to: None)
        cmd_task(db, "alice", ["add", "--to", "bob", "bob's task"])
        capsys.readouterr()

        task_id = db.scalar("SELECT id FROM tasks WHERE session='bob'")
        with pytest.raises(SystemExit):
            cmd_task(db, "charlie", ["done", str(task_id)])

    def test_done_already_done_task(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.verify_task", lambda root: (True, "ok"))
        monkeypatch.setattr("lib.board_task.auto_pr", lambda root, desc, name: None)

        cmd_task(db, "alice", ["add", "already done"])
        capsys.readouterr()
        cmd_task(db, "alice", ["done"])
        capsys.readouterr()

        task_id = db.scalar("SELECT id FROM tasks WHERE session='alice'")
        cmd_task(db, "alice", ["done", str(task_id)])
        out = capsys.readouterr().out
        assert "already done" in out

    def test_done_nonexistent_id(self, db):
        with pytest.raises(SystemExit):
            cmd_task(db, "alice", ["done", "999"])

    def test_done_with_auto_pr(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.verify_task", lambda root: (True, "ok"))
        monkeypatch.setattr(
            "lib.board_task.auto_pr",
            lambda root, desc, name: "https://github.com/org/repo/pull/42",
        )

        cmd_task(db, "alice", ["add", "feature with PR"])
        capsys.readouterr()

        cmd_task(db, "alice", ["done"])
        out = capsys.readouterr().out
        assert "PR created" in out
        assert "pull/42" in out


class TestTaskList:
    def test_list_empty(self, db, capsys):
        cmd_task(db, "alice", ["list"])
        out = capsys.readouterr().out
        assert "无待办任务" in out

    def test_list_shows_tasks(self, db, capsys):
        cmd_task(db, "alice", ["add", "my task"])
        capsys.readouterr()

        cmd_task(db, "alice", ["list"])
        out = capsys.readouterr().out
        assert "my task" in out
        assert "active" in out

    def test_list_another_session(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.nudge_session", lambda db, to: None)
        cmd_task(db, "alice", ["add", "--to", "bob", "bob's work"])
        capsys.readouterr()

        cmd_task(db, "alice", ["list", "bob"])
        out = capsys.readouterr().out
        assert "bob's work" in out

    def test_list_all_sessions(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.nudge_session", lambda db, to: None)
        cmd_task(db, "alice", ["add", "alice task"])
        cmd_task(db, "alice", ["add", "--to", "bob", "bob task"])
        capsys.readouterr()

        cmd_task(db, "alice", ["list", "--all"])
        out = capsys.readouterr().out
        assert "alice task" in out
        assert "bob task" in out
        assert "Task Queue" in out

    def test_list_include_done(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.verify_task", lambda root: (True, "ok"))
        monkeypatch.setattr("lib.board_task.auto_pr", lambda root, desc, name: None)

        cmd_task(db, "alice", ["add", "completed task"])
        capsys.readouterr()
        cmd_task(db, "alice", ["done"])
        capsys.readouterr()

        cmd_task(db, "alice", ["list"])
        out_default = capsys.readouterr().out
        assert "completed task" not in out_default

        cmd_task(db, "alice", ["list", "--done"])
        out_done = capsys.readouterr().out
        assert "completed task" in out_done

    def test_default_is_list(self, db, capsys):
        cmd_task(db, "alice", [])
        out = capsys.readouterr().out
        assert "任务队列" in out


class TestTaskNext:
    def test_next_promotes_pending(self, db, monkeypatch, capsys):
        monkeypatch.setattr("lib.board_task.verify_task", lambda root: (True, "ok"))
        monkeypatch.setattr("lib.board_task.auto_pr", lambda root, desc, name: None)

        cmd_task(db, "alice", ["add", "first"])
        cmd_task(db, "alice", ["add", "second"])
        capsys.readouterr()

        cmd_task(db, "alice", ["done"])
        capsys.readouterr()

        cmd_task(db, "alice", ["next"])
        out = capsys.readouterr().out
        assert "second" in out

    def test_next_respects_priority(self, db, capsys):
        db.execute(
            "INSERT INTO tasks(session, description, status, priority) VALUES (?, ?, 'pending', ?)",
            ("alice", "low priority", 1),
        )
        db.execute(
            "INSERT INTO tasks(session, description, status, priority) VALUES (?, ?, 'pending', ?)",
            ("alice", "high priority", 10),
        )

        cmd_task(db, "alice", ["next"])
        capsys.readouterr()

        row = db.query_one("SELECT description FROM tasks WHERE session='alice' AND status='active'")
        assert row["description"] == "high priority"

    def test_next_no_pending(self, db, capsys):
        cmd_task(db, "alice", ["next"])
        out = capsys.readouterr().out
        assert "无待办任务" in out


class TestTaskDispatch:
    def test_invalid_subcommand(self, db):
        with pytest.raises(SystemExit):
            cmd_task(db, "alice", ["invalid"])
