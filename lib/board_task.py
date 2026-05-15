"""board_task — task queue: add / done / list / next."""

from lib.board_db import BoardDB, ts
from lib.board_display import print_task_queue
from lib.board_own import auto_pr, verify_task
from lib.common import is_privileged, is_terminal_task_status, parse_flags, validate_identity
from lib.fmt import error, heading, ok, warn


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


def cmd_task(db: BoardDB, identity: str, args: list[str]) -> None:
    validate_identity(db, identity)
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
        print(ok(f"OK task #{task_id} added to {target} ({status})"))

        if target != name:
            db.post_message(name, target, f"[TASK #{task_id}] {desc}", deliver=True, c=c)
            print(ok(f"OK notified {target}"))
    print_task_queue(db, target)


def _task_done(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    flags, positional = parse_flags(args, bool_flags={"skip_verify": ["--skip-verify"]})
    skip_verify = bool(flags.get("skip_verify"))

    raw_id: str | int | None = positional[0] if positional else None

    if not raw_id:
        _promote_next(db, name)
        raw_id = db.scalar(
            "SELECT id FROM tasks WHERE session=? AND status='active' ORDER BY id ASC LIMIT 1",
            (name,),
        )
    if not raw_id:
        print(warn(f"No active task for {name}."))
        print_task_queue(db, name)
        return

    try:
        task_id = int(raw_id)
    except (ValueError, TypeError):
        print(error(f"ERROR: 无效的任务 ID: {raw_id}"))
        raise SystemExit(1)
    row = db.query_one("SELECT session, status, description FROM tasks WHERE id=?", (task_id,))
    if not row:
        print(error(f"ERROR: task #{task_id} not found"))
        raise SystemExit(1)

    assignee, status, desc = row
    if assignee != name and not is_privileged(name):
        print(error(f"ERROR: task #{task_id} belongs to {assignee}; only owner, Orca, or Coral can mark it done"))
        raise SystemExit(1)

    if is_terminal_task_status(status):
        print(warn(f"Task #{task_id} is already done."))
        print_task_queue(db, assignee)
        return

    # --- Verify: run tests before marking done ---
    env = db.env
    if env and not skip_verify:
        print("验证中: 运行测试...", flush=True)
        passed, summary = verify_task(env.project_root)
        if not passed:
            print(error(f"ERROR: 测试未通过，task #{task_id} 未标记完成"))
            print(f"  {summary}")
            print("  使用 --skip-verify 强制跳过")
            return

        print(f"  测试通过: {summary}")

    now = ts()
    db.execute("UPDATE tasks SET status='done', done_at=? WHERE id=?", (now, task_id))
    print(ok(f"OK task #{task_id} done: {desc}"))

    # --- Auto-PR: create PR if on a feature branch ---
    if env:
        pr_url = auto_pr(env.project_root, desc, name)
        if pr_url:
            print(ok(f"OK PR created: {pr_url}"))

    _promote_next(db, assignee)
    nxt = db.query_one(
        "SELECT id, description FROM tasks WHERE session=? AND status='active' ORDER BY id ASC LIMIT 1",
        (assignee,),
    )
    if nxt:
        print(ok(f"Next: #{nxt[0]} {nxt[1]}"))
    else:
        print(warn(f"No remaining active/pending tasks for {assignee}."))
    print_task_queue(db, assignee)


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
        print(heading("=== Task Queue ==="))
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
    print_task_queue(db, target, include_done=include_done)


def _task_next(db: BoardDB, identity: str) -> None:
    name = identity.lower()

    _promote_next(db, name)
    print_task_queue(db, name)
