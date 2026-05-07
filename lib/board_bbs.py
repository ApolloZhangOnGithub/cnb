"""board_bbs — forum commands: post / reply / thread / threads."""

import hashlib

from lib.board_db import BoardDB, ts
from lib.common import escape_like, validate_identity


def cmd_post(db: BoardDB, identity: str, args: list[str]) -> None:
    validate_identity(db, identity)
    name = identity.lower()
    if len(args) < 2:
        print("Usage: ./board --as <name> post <标题> <内容>")
        raise SystemExit(1)
    title = args[0]
    body = " ".join(args[1:])
    now = ts()
    tid = hashlib.sha256(f"{title}{now}{identity}".encode()).hexdigest()[:6]

    with db.conn() as c:
        db.execute(
            "INSERT INTO threads(id, title, author) VALUES (?, ?, ?)",
            (tid, title, name),
            c=c,
        )
        db.execute(
            "INSERT INTO thread_replies(thread_id, author, body) VALUES (?, ?, ?)",
            (tid, name, body),
            c=c,
        )
        db.post_message(name, "all", f"[BBS] 新帖「{title}」({tid})", c=c)
    print(f"OK 帖子已创建: {tid}")
    print(f"  标题: {title}")
    print(f"  查看: ./board --as <name> thread {tid}")


def cmd_reply(db: BoardDB, identity: str, args: list[str]) -> None:
    validate_identity(db, identity)
    name = identity.lower()
    if len(args) < 2:
        print("Usage: ./board --as <name> reply <帖子ID> <内容>")
        raise SystemExit(1)
    tid = args[0]
    body = " ".join(args[1:])

    full_tid = db.scalar(
        "SELECT id FROM threads WHERE id LIKE ? ESCAPE '\\' LIMIT 1",
        (escape_like(tid) + "%",),
    )
    if not full_tid:
        print(f"ERROR: 帖子 {tid} 不存在")
        raise SystemExit(1)

    title = db.scalar("SELECT title FROM threads WHERE id=?", (full_tid,))
    with db.conn() as c:
        db.execute(
            "INSERT INTO thread_replies(thread_id, author, body) VALUES (?, ?, ?)",
            (full_tid, name, body),
            c=c,
        )
        db.post_message(name, "all", f"[BBS] 回帖「{title}」({full_tid})", c=c)
    print(f"OK 回帖成功 (帖子: {full_tid})")


def cmd_thread(db: BoardDB, args: list[str]) -> None:
    if not args:
        print("Usage: ./board thread <帖子ID>")
        raise SystemExit(1)
    tid = args[0]
    full_tid = db.scalar(
        "SELECT id FROM threads WHERE id LIKE ? ESCAPE '\\' LIMIT 1",
        (escape_like(tid) + "%",),
    )
    if not full_tid:
        print(f"ERROR: 帖子 {tid} 不存在")
        raise SystemExit(1)

    row = db.query_one("SELECT title, author, created_at FROM threads WHERE id=?", (full_tid,))
    if not row:
        print(f"ERROR: 帖子 {full_tid} 数据异常")
        raise SystemExit(1)
    title, author, created = row
    print(f"# {title}")
    print(f"> @{author} — {created}\n")

    for rauthor, rbody, rts in db.query(
        "SELECT author, body, ts FROM thread_replies WHERE thread_id=? ORDER BY id",
        (full_tid,),
    ):
        print("---")
        print(f"> @{rauthor} — {rts}\n")
        print(rbody)


def cmd_threads(db: BoardDB) -> None:
    print("=== BBS 话题列表 ===\n")
    rows = db.query(
        "SELECT t.id, t.title, t.author, t.created_at, "
        "(SELECT COUNT(*) FROM thread_replies r WHERE r.thread_id=t.id) "
        "FROM threads t ORDER BY t.created_at DESC"
    )
    if not rows:
        print("  (暂无话题)\n")
        print("  发帖: ./board --as <name> post <标题> <内容>")
    else:
        for tid, title, author, date, replies in rows:
            print(f"  [{tid}] {title}  ({replies} 回帖)  by {author}  {date}")
    print()
