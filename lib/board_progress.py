"""board_progress — single progress tracking view."""

from lib.board_db import BoardDB


def _count(db: BoardDB, sql: str, params: tuple[object, ...] = ()) -> int:
    return int(db.scalar(sql, params) or 0)


def _print_tasks(db: BoardDB) -> None:
    rows = db.query(
        "SELECT session, id, status, priority, description, created_at "
        "FROM tasks WHERE status IN ('active', 'pending') "
        "ORDER BY session, CASE status WHEN 'active' THEN 0 ELSE 1 END, priority DESC, id ASC"
    )
    print("\nTasks")
    if not rows:
        print("  (none)")
        return
    for session, task_id, status, priority, desc, created in rows:
        marker = "*" if status == "active" else " "
        print(f"  {marker} {session:<16} #{task_id} [{status} p{priority}] {desc} (created {created})")


def _print_bugs(db: BoardDB) -> None:
    rows = db.query(
        "SELECT id, severity, status, COALESCE(assignee, ''), reporter, reported_at, description "
        "FROM bugs WHERE status != 'FIXED' ORDER BY severity, reported_at, id"
    )
    print("\nOpen Bugs")
    if not rows:
        print("  (none)")
        return
    for bug_id, severity, status, assignee, reporter, reported, desc in rows:
        owner = assignee or "unassigned"
        print(f"  {bug_id} [{severity}] {status} owner={owner} reporter={reporter} reported={reported}")
        print(f"    {desc}")


def _print_pending_actions(db: BoardDB) -> None:
    rows = db.query(
        "SELECT id, type, status, created_by, command, reason "
        "FROM pending_actions WHERE status IN ('pending', 'reminded') ORDER BY id"
    )
    print("\nPending Actions")
    if not rows:
        print("  (none)")
        return
    for action_id, action_type, status, creator, command, reason in rows:
        print(f"  #{action_id} [{status}] ({action_type}) by {creator}: {reason}")
        print(f"    ! {command}")


def _print_sessions(db: BoardDB) -> None:
    rows = db.query(
        "SELECT s.name, COALESCE(s.status, ''), COALESCE(s.updated_at, ''), COALESCE(s.last_heartbeat, ''), "
        "COALESCE(SUM(CASE WHEN i.read=0 THEN 1 ELSE 0 END), 0) AS unread "
        "FROM sessions s LEFT JOIN inbox i ON i.session=s.name "
        "WHERE s.name != 'all' GROUP BY s.name ORDER BY s.name"
    )
    print("\nSessions")
    if not rows:
        print("  (none)")
        return
    for name, status, updated, heartbeat, unread in rows:
        status_text = status or "(no status)"
        heartbeat_text = heartbeat or "no heartbeat"
        print(f"  {name:<16} unread={int(unread):<3} status={status_text} updated={updated} heartbeat={heartbeat_text}")


def cmd_progress(db: BoardDB) -> None:
    """Print a paste-friendly board-wide progress snapshot."""
    active_tasks = _count(db, "SELECT COUNT(*) FROM tasks WHERE status='active'")
    pending_tasks = _count(db, "SELECT COUNT(*) FROM tasks WHERE status='pending'")
    open_bugs = _count(db, "SELECT COUNT(*) FROM bugs WHERE status != 'FIXED'")
    pending_actions = _count(db, "SELECT COUNT(*) FROM pending_actions WHERE status IN ('pending', 'reminded')")
    unread = _count(db, "SELECT COUNT(*) FROM inbox WHERE read=0")
    sessions = _count(db, "SELECT COUNT(*) FROM sessions WHERE name != 'all'")

    print("=== Progress Tracking ===")
    print(
        "Summary: "
        f"sessions={sessions} "
        f"tasks={active_tasks} active/{pending_tasks} pending "
        f"bugs={open_bugs} open "
        f"pending_actions={pending_actions} "
        f"unread={unread}"
    )
    _print_tasks(db)
    _print_bugs(db)
    _print_pending_actions(db)
    _print_sessions(db)
