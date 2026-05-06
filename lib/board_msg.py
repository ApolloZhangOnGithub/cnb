"""board_msg — send / inbox / ack / status / log commands."""

import hashlib
import shutil
from pathlib import Path

from lib.board_db import BoardDB, ts
from lib.common import parse_flags


def _ack_marker_path(db: BoardDB, name: str) -> Path:
    """Path to file recording max message_id seen by last inbox call."""
    return db.env.sessions_dir / f".{name}.ack_max_id"


def cmd_send(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    flags, send_args = parse_flags(args, value_flags={"attach": ["--attach", "-a"]})
    attach_file = flags.get("attach")

    if not send_args:
        print("Usage: ./board --as <name> send <to> <message> [--attach <file>]")
        raise SystemExit(1)

    to = send_args[0].lower()

    if to != "all" and not db.scalar("SELECT COUNT(*) FROM sessions WHERE name=?", (to,)):
        print(f"ERROR: 收件人 '{to}' 不存在")
        raise SystemExit(1)

    msg = " ".join(send_args[1:]) if len(send_args) > 1 else ""

    if not msg and not attach_file:
        print("ERROR: 消息不能为空")
        raise SystemExit(1)

    attach_ref = ""
    stored_path = ""
    h = ""
    if attach_file:
        path = Path(attach_file)
        if not path.is_file():
            print(f"ERROR: file not found: {attach_file}")
            raise SystemExit(1)
        data = path.read_bytes()
        h = hashlib.sha256(data).hexdigest()[:12]
        ext = path.suffix.lstrip(".")
        orig = path.name
        stored_path = f"files/{h}.{ext}" if ext else f"files/{h}"
        files_dir = db.env.claudes_dir / "files"
        files_dir.mkdir(exist_ok=True)
        dest = db.env.claudes_dir / stored_path
        if not dest.exists():
            shutil.copy2(str(path), str(dest))
        attach_ref = f" [附件: {orig} → {stored_path}]"
        if not msg:
            msg = f"分享文件: {orig}"

    full_msg = msg + attach_ref
    now = ts()
    attach_val = h if attach_file else None

    with db.conn() as c:
        if attach_file:
            db.execute(
                "INSERT OR IGNORE INTO files(hash, original_name, extension, sender, stored_path) "
                "VALUES (?, ?, ?, ?, ?)",
                (h, orig, ext, name, stored_path),
                c=c,
            )
        msg_id = db.execute(
            "INSERT INTO messages(ts, sender, recipient, body, attachment) VALUES (?, ?, ?, ?, ?)",
            (now, name, to, full_msg, attach_val),
            c=c,
        )
        db.deliver_to_inbox(name, to, msg_id, c=c)

    print("OK sent")


def cmd_status(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    if not args:
        print("Usage: ./board --as <name> status <description>")
        raise SystemExit(1)
    desc = " ".join(args)
    now = ts()
    full_status = f"{desc} — {now}"
    db.execute(
        "UPDATE sessions SET status=?, updated_at=? WHERE name=?",
        (full_status, now, name),
    )
    print("OK")


def cmd_inbox(db: BoardDB, identity: str) -> None:
    name = identity.lower()
    if not db.scalar("SELECT COUNT(*) FROM sessions WHERE name=?", (name,)):
        print(f"ERROR: 会话 '{name}' 未注册")
        raise SystemExit(1)
    count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,))
    if not count:
        print("(empty)")
        return
    rows = db.query(
        "SELECT i.message_id, m.ts, m.sender, m.body "
        "FROM inbox i JOIN messages m ON i.message_id=m.id "
        "WHERE i.session=? AND i.read=0 ORDER BY m.ts",
        (name,),
    )
    max_id = 0
    for msg_id, msg_ts, sender, body in rows:
        print(f'<message from="{sender}" ts="{msg_ts}">\n{body}\n</message>')
        if msg_id > max_id:
            max_id = msg_id
    if max_id > 0:
        _ack_marker_path(db, name).write_text(str(max_id))


def cmd_ack(db: BoardDB, identity: str) -> None:
    name = identity.lower()
    marker = _ack_marker_path(db, name)
    max_id = None
    if marker.exists():
        try:
            max_id = int(marker.read_text().strip())
        except ValueError:
            pass

    if max_id:
        count = db.scalar(
            "SELECT COUNT(*) FROM inbox WHERE session=? AND read=0 AND message_id<=?",
            (name, max_id),
        )
    else:
        count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,))

    if count == 0:
        print("OK")
        marker.unlink(missing_ok=True)
        return

    if max_id:
        db.execute(
            "UPDATE inbox SET read=1 WHERE session=? AND read=0 AND message_id<=?",
            (name, max_id),
        )
    else:
        db.execute("UPDATE inbox SET read=1 WHERE session=? AND read=0", (name,))

    print(f"OK {count}")
    marker.unlink(missing_ok=True)


def cmd_log(db: BoardDB, identity: str, args: list[str]) -> None:
    flags, positional = parse_flags(args, bool_flags={"mine": ["--mine"]})
    filter_name = identity.lower() if flags.get("mine") and identity else ""
    n = 20
    for a in positional:
        try:
            n = int(a)
        except ValueError:
            pass

    if filter_name:
        rows = db.query(
            "SELECT '[' || ts || '] ' || sender || ' → ' || recipient || ': ' || body "
            "FROM messages WHERE sender=? OR recipient=? OR recipient='all' "
            "ORDER BY id DESC LIMIT ?",
            (filter_name, filter_name, n),
        )
    else:
        rows = db.query(
            "SELECT '[' || ts || '] ' || sender || ' → ' || recipient || ': ' || body "
            "FROM messages ORDER BY id DESC LIMIT ?",
            (n,),
        )
    for (line,) in reversed(rows):
        print(line)
