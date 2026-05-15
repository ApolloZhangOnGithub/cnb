"""Tests for board progress tracking view."""

from lib.board_progress import cmd_progress


def test_progress_view_summarizes_board_state(db, capsys):
    msg_id = db.post_message("bob", "alice", "please review", deliver=True)
    db.execute(
        "INSERT INTO tasks(session, description, status, priority, created_at) VALUES (?, ?, ?, ?, ?)",
        ("alice", "ship progress view", "active", 10, "2026-05-15 10:00"),
    )
    db.execute(
        "INSERT INTO tasks(session, description, status, priority, created_at) VALUES (?, ?, ?, ?, ?)",
        ("bob", "wait for review", "pending", 3, "2026-05-15 10:01"),
    )
    db.execute(
        "INSERT INTO tasks(session, description, status, priority, created_at) VALUES (?, ?, ?, ?, ?)",
        ("charlie", "already done", "done", 0, "2026-05-15 09:00"),
    )
    db.execute(
        "INSERT INTO bugs(id, severity, sla, reporter, assignee, status, description, reported_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("BUG-001", "P1", "4h", "alice", "bob", "OPEN", "progress stale", "2026-05-15 10:02"),
    )
    db.execute(
        "INSERT INTO pending_actions(type, command, reason, created_by, status) VALUES (?, ?, ?, ?, ?)",
        ("approve", "gh pr merge 1", "merge needs approval", "alice", "pending"),
    )
    db.execute(
        "UPDATE sessions SET status=?, updated_at=?, last_heartbeat=? WHERE name=?",
        ("working on progress", "2026-05-15 10:03", "2026-05-15 10:03:30", "alice"),
    )

    cmd_progress(db)

    out = capsys.readouterr().out
    assert msg_id > 0
    assert "=== Progress Tracking ===" in out
    assert "tasks=1 active/1 pending" in out
    assert "bugs=1 open" in out
    assert "pending_actions=1" in out
    assert "unread=1" in out
    assert "ship progress view" in out
    assert "wait for review" in out
    assert "already done" not in out
    assert "BUG-001 [P1] OPEN owner=bob" in out
    assert "merge needs approval" in out
    assert "alice" in out
    assert "unread=1" in out
    assert "working on progress" in out


def test_progress_view_handles_empty_work_items(db, capsys):
    db.execute("INSERT INTO sessions(name, status) VALUES ('all', 'system')")

    cmd_progress(db)

    out = capsys.readouterr().out
    assert "sessions=3" in out
    assert "tasks=0 active/0 pending" in out
    assert "bugs=0 open" in out
    assert "pending_actions=0" in out
    assert "Tasks\n  (none)" in out
    assert "Open Bugs\n  (none)" in out
    assert "Pending Actions\n  (none)" in out
    assert "all" not in out
