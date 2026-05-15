"""Shared display helpers for inbox and task queue rendering."""

from lib.board_db import BoardDB
from lib.fmt import active, done, heading, pending


def print_unread_inbox(db: BoardDB, target: str, *, write_ack_marker: bool = False) -> None:
    count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (target,))
    if not count:
        print("收件箱为空")
        return

    rows = db.query(
        "SELECT i.message_id, m.ts, m.sender, m.body "
        "FROM inbox i JOIN messages m ON i.message_id=m.id "
        "WHERE i.session=? AND i.read=0 ORDER BY m.ts",
        (target,),
    )

    max_id = 0
    for msg_id, msg_ts, sender, body in rows:
        print(f'<message from="{sender}" ts="{msg_ts}">\n{body}\n</message>')
        if msg_id > max_id:
            max_id = msg_id

    if write_ack_marker and max_id > 0 and db.env is not None:
        (db.env.sessions_dir / f".{target}.ack_max_id").write_text(str(max_id))


def print_task_queue(db: BoardDB, target: str, *, include_done: bool = False) -> None:
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
            "FROM tasks WHERE session=? AND status != 'done' "
            "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, "
            "priority DESC, id ASC",
            (target,),
        )

    print("\n" + heading("任务队列:"))
    if not rows:
        print("  (无待办任务)")
        return
    for tid, status, priority, desc, _created, done_at in rows:
        marker = "*" if status == "active" else " "
        status_text = {
            "active": active(status),
            "pending": pending(status),
            "done": done(status),
        }.get(status, status)
        if status == "done":
            print(f"  {marker} #{tid} [{status_text} p{priority}] {desc} (done {done_at})")
        else:
            print(f"  {marker} #{tid} [{status_text} p{priority}] {desc}")
