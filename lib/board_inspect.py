"""board_inspect — privileged read-only session inspection."""

from lib.board_db import BoardDB
from lib.common import is_privileged, parse_flags, validate_identity


def _usage() -> None:
    print("Usage: ./board --as <lead|dispatcher> inspect {inbox|tasks} <session> [--done]")


def _target_for_inspection(db: BoardDB, identity: str, raw_target: str) -> str:
    validate_identity(db, identity)
    observer = identity.lower()
    target = raw_target.lower()
    validate_identity(db, target)
    if target != observer and not is_privileged(observer):
        print("ERROR: inspect requires lead or dispatcher to read another session")
        raise SystemExit(1)
    return target


def _print_unread_inbox(db: BoardDB, target: str) -> None:
    print(f"=== Inbox: {target} (read-only) ===")
    rows = db.query(
        "SELECT i.message_id, m.ts, m.sender, m.body "
        "FROM inbox i JOIN messages m ON i.message_id=m.id "
        "WHERE i.session=? AND i.read=0 ORDER BY i.message_id",
        (target,),
    )
    if not rows:
        print("收件箱为空")
        return
    for _msg_id, msg_ts, sender, body in rows:
        print(f'<message from="{sender}" ts="{msg_ts}">\n{body}\n</message>')


def _print_task_queue(db: BoardDB, target: str, *, include_done: bool = False) -> None:
    print(f"=== Task Queue: {target} (read-only) ===")
    if include_done:
        rows = db.query(
            "SELECT id, status, priority, description, COALESCE(done_at, '') "
            "FROM tasks WHERE session=? "
            "ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END, "
            "priority DESC, id ASC",
            (target,),
        )
    else:
        rows = db.query(
            "SELECT id, status, priority, description, '' "
            "FROM tasks WHERE session=? AND status != 'done' "
            "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, priority DESC, id ASC",
            (target,),
        )

    print("\n任务队列:")
    if not rows:
        print("  (无待办任务)")
        return
    for tid, status, priority, desc, done_at in rows:
        marker = "*" if status == "active" else " "
        if status == "done":
            print(f"  {marker} #{tid} [{status} p{priority}] {desc} (done {done_at})")
        else:
            print(f"  {marker} #{tid} [{status} p{priority}] {desc}")


def cmd_inspect(db: BoardDB, identity: str, args: list[str]) -> None:
    if len(args) < 2:
        _usage()
        raise SystemExit(1)

    subcmd = args[0].lower()
    target = _target_for_inspection(db, identity, args[1])
    rest = args[2:]

    if subcmd in ("inbox", "messages"):
        if rest:
            _usage()
            raise SystemExit(1)
        _print_unread_inbox(db, target)
        return

    if subcmd in ("task", "tasks", "queue"):
        flags, positional = parse_flags(rest, bool_flags={"done": ["--done", "--include-done"]})
        if positional:
            _usage()
            raise SystemExit(1)
        _print_task_queue(db, target, include_done=bool(flags.get("done")))
        return

    _usage()
    raise SystemExit(1)
