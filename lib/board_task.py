"""board_task — task queue: add / done / list / next."""

from lib.board_db import BoardDB, ts
from lib.common import is_privileged, is_terminal_task_status, parse_flags


def _promote_next(db: BoardDB, target: str) -> None:
    with db.conn() as c:
        active = db.scalar("SELECT COUNT(*) FROM tasks WHERE session=? AND status='active'", (target,), c=c)
        if active:
            return
        next_id = db.scalar(
            "SELECT id FROM tasks WHERE session=? AND status='pending' ORDER BY priority DESC, id ASC LIMIT 1",
            (target,),
            c=c,
        )
        if next_id:
            db.execute("UPDATE tasks SET status='active' WHERE id=?", (next_id,), c=c)


def _print_queue(db: BoardDB, target: str, include_done: bool = False) -> None:
    if include_done:
        rows = db.query(
            "SELECT id, status, priority, description, created_at, COALESCE(done_at, '') "
            "FROM tasks WHERE session=? "
            "ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END, "
            "priority DESC, id ASC",
            (target,),
        )
    else:
        rows = db.query(
            "SELECT id, status, priority, description, created_at, '' "
            "FROM tasks WHERE session=? AND status NOT IN ('done') "
            "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, "
            "priority DESC, id ASC",
            (target,),
        )
    print("\n任务队列:")
    if not rows:
        print("  (无待办任务)")
        return
    for tid, status, priority, desc, _created, done_at in rows:
        marker = "*" if status == "active" else " "
        if status == "done":
            print(f"  {marker} #{tid} [{status} p{priority}] {desc} (done {done_at})")
        else:
            print(f"  {marker} #{tid} [{status} p{priority}] {desc}")


def cmd_task(db: BoardDB, identity: str, args: list[str]) -> None:
    subcmd = args[0] if args else "list"
    rest = args[1:] if len(args) > 1 else []

    if subcmd == "add":
        _task_add(db, identity, rest)
    elif subcmd == "done":
        _task_done(db, identity, rest)
    elif subcmd == "list":
        _task_list(db, identity, rest)
    elif subcmd == "next":
        _task_next(db, identity)
    else:
        print("Usage: ./board --as <name> task {add|done|list|next}")
        raise SystemExit(1)


def _task_add(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    flags, desc_parts = parse_flags(
        args,
        value_flags={"to": ["--to"], "priority": ["--priority", "-p"]},
    )
    target = str(flags.get("to", name)).lower()
    priority = int(flags["priority"]) if "priority" in flags else 0

    if not desc_parts:
        print("Usage: ./board --as <name> task add [--to session] [--priority N] <description>")
        raise SystemExit(1)

    desc = " ".join(desc_parts)

    with db.conn() as c:
        db.ensure_session(target, c=c)

        active = db.scalar("SELECT COUNT(*) FROM tasks WHERE session=? AND status='active'", (target,), c=c)
        status = "active" if not active else "pending"

        task_id = db.execute(
            "INSERT INTO tasks(session, description, status, priority) VALUES (?, ?, ?, ?)",
            (target, desc, status, priority),
            c=c,
        )
        print(f"OK task #{task_id} added to {target} ({status})")

        if target != name:
            now = ts()
            msg_id = db.execute(
                "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
                (now, name, target, f"[TASK #{task_id}] {desc}"),
                c=c,
            )
            db.execute("INSERT INTO inbox(session, message_id) VALUES (?, ?)", (target, msg_id), c=c)
            print(f"OK notified {target}")
    _print_queue(db, target)


def _task_done(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()

    raw_id: str | int | None = args[0] if args else None

    if not raw_id:
        _promote_next(db, name)
        raw_id = db.scalar(
            "SELECT id FROM tasks WHERE session=? AND status='active' ORDER BY id ASC LIMIT 1",
            (name,),
        )
    if not raw_id:
        print(f"No active task for {name}.")
        _print_queue(db, name)
        return

    try:
        task_id = int(raw_id)
    except (ValueError, TypeError):
        print(f"ERROR: 无效的任务 ID: {raw_id}")
        raise SystemExit(1)
    row = db.query_one("SELECT session, status, description FROM tasks WHERE id=?", (task_id,))
    if not row:
        print(f"ERROR: task #{task_id} not found")
        raise SystemExit(1)

    assignee, status, desc = row
    if assignee != name and not is_privileged(name):
        print(f"ERROR: task #{task_id} belongs to {assignee}; only owner, Orca, or Coral can mark it done")
        raise SystemExit(1)

    if is_terminal_task_status(status):
        print(f"Task #{task_id} is already done.")
        _print_queue(db, assignee)
        return

    now = ts()
    db.execute("UPDATE tasks SET status='done', done_at=? WHERE id=?", (now, task_id))
    print(f"OK task #{task_id} done: {desc}")

    _promote_next(db, assignee)
    nxt = db.query_one(
        "SELECT id, description FROM tasks WHERE session=? AND status='active' ORDER BY id ASC LIMIT 1",
        (assignee,),
    )
    if nxt:
        print(f"Next: #{nxt[0]} {nxt[1]}")
    else:
        print(f"No remaining active/pending tasks for {assignee}.")
    _print_queue(db, assignee)


def _task_list(db: BoardDB, identity: str, args: list[str]) -> None:
    flags, positional = parse_flags(
        args,
        value_flags={"session": ["--session"]},
        bool_flags={"all": ["--all"], "done": ["--done", "--include-done"]},
    )
    all_sessions = bool(flags.get("all"))
    include_done = bool(flags.get("done"))
    target = str(flags["session"]).lower() if "session" in flags else ""

    if not target and positional:
        target = positional[0].lower()
        if len(positional) > 1:
            print("Usage: ./board task list [session|--all] [--done]")
            raise SystemExit(1)

    if all_sessions:
        print("=== Task Queue ===")
        if include_done:
            rows = db.query(
                "SELECT session, id, status, priority, description FROM tasks "
                "ORDER BY session, CASE status WHEN 'active' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END, "
                "priority DESC, id ASC"
            )
        else:
            rows = db.query(
                "SELECT session, id, status, priority, description FROM tasks WHERE status != 'done' "
                "ORDER BY session, CASE status WHEN 'active' THEN 0 ELSE 1 END, "
                "priority DESC, id ASC"
            )
        if not rows:
            print("  (no tasks)")
            return
        for session, tid, status, priority, desc in rows:
            print(f"  {session:<8s} #{tid} [{status} p{priority}] {desc}")
        return

    if not target:
        if not identity:
            print("Usage: ./board task list [session|--all] [--done]")
            raise SystemExit(1)
        target = identity.lower()
    _print_queue(db, target, include_done)


def _task_next(db: BoardDB, identity: str) -> None:
    name = identity.lower()

    _promote_next(db, name)
    _print_queue(db, name)
