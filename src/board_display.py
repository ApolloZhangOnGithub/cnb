"""Shared display helpers for inbox and task queue rendering."""

from lib import fmt
from src.board_db import BoardDB


def print_unread_inbox(db: BoardDB, target: str, *, write_ack_marker: bool = False) -> None:
    count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (target,))
    if not count:
        print(fmt.dim("收件箱为空"))
        return

    rows = db.query(
        "SELECT i.message_id, m.ts, m.sender, m.body "
        "FROM inbox i JOIN messages m ON i.message_id=m.id "
        "WHERE i.session=? AND i.read=0 ORDER BY m.ts",
        (target,),
    )

    max_id = 0
    for msg_id, msg_ts, sender, body in rows:
        tag_open = (
            fmt.dim("<message")
            + " "
            + fmt.dim('from="')
            + fmt.sender_name(sender)
            + fmt.dim('"')
            + " "
            + fmt.dim('ts="')
            + fmt.dim(msg_ts)
            + fmt.dim('">')
        )
        tag_close = fmt.dim("</message>")
        print(f"{tag_open}\n{body}\n{tag_close}")
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

    print("\n" + fmt.subheader("任务队列:"))
    if not rows:
        print("  " + fmt.dim("(无待办任务)"))
        return
    for tid, status, priority, desc, _created, done_at in rows:
        tag = f"#{tid} [{status} p{priority}]"
        if status == "active":
            marker = fmt.task_active("▸")
            tag_colored = fmt.task_active(tag)
        elif status == "done":
            marker = " "
            tag_colored = fmt.task_done(tag)
        else:
            marker = " "
            tag_colored = fmt.task_pending(tag)
        if status == "done":
            print("  {} {} {} {}".format(marker, tag_colored, fmt.dim(desc), fmt.dim(f"(done {done_at})")))
        else:
            print(f"  {marker} {tag_colored} {desc}")
