"""board_msg — send / inbox / ack / status / log commands."""

import hashlib
import re
import shutil
from pathlib import Path

from lib.board_db import BoardDB, ts
from lib.board_display import print_task_queue, print_unread_inbox
from lib.common import escape_like, parse_flags, validate_identity
from lib.fmt import error, heading, ok
from lib.tmux_utils import capture_pane, has_session, tmux_send


def _ack_marker_path(db: BoardDB, name: str) -> Path:
    assert db.env is not None
    return db.env.sessions_dir / f".{name}.ack_max_id"


def _is_idle(sess: str) -> bool:
    text = capture_pane(sess, lines=10)
    if not text:
        return False
    busy_indicators = ("Choreographing", "Seasoning", "Churned", "Gitifying", "Running", "ctrl+b", "thinking")
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        if any(ind in stripped for ind in busy_indicators):
            return False
        if "❯" in stripped or "Press up to edit" in stripped:
            return True
        break
    return "❯" in text or "Press up to edit" in text


def _nudge_session(db: BoardDB, recipient: str) -> None:
    assert db.env is not None
    if recipient == "all":
        sessions = [r[0] for r in db.query("SELECT name FROM sessions WHERE name != 'all'")]
    else:
        sessions = [recipient]
    prefix = db.env.prefix
    board = db.env.install_home / "bin" / "board"
    for name in sessions:
        if not re.match(r"^[a-z0-9][a-z0-9_-]*$", name):
            continue
        sess = f"{prefix}-{name}"
        if not has_session(sess):
            continue
        if not _is_idle(sess):
            continue
        tmux_send(sess, f"{board} --as {name} inbox")


def cmd_send(db: BoardDB, identity: str, args: list[str]) -> None:
    assert db.env is not None
    validate_identity(db, identity)
    name = identity.lower()
    flags, send_args = parse_flags(args, value_flags={"attach": ["--attach", "-a"]})
    attach_file = flags.get("attach")

    if not send_args:
        print("Usage: ./board --as <name> send <to> <message> [--attach <file>]")
        raise SystemExit(1)

    to = send_args[0].lower()

    if to != "all":
        db.ensure_session(to)

    msg = " ".join(send_args[1:]) if len(send_args) > 1 else ""

    if not msg and not attach_file:
        print(error("ERROR: 消息不能为空"))
        raise SystemExit(1)

    attach_ref = ""
    stored_path = ""
    h = ""
    if attach_file:
        path = Path(str(attach_file))
        if not path.is_file():
            print(error(f"ERROR: file not found: {attach_file}"))
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

    print(ok("OK sent"))
    if attach_ref:
        print(f"  附件已存储: {stored_path}")

    _nudge_session(db, to)


def cmd_status(db: BoardDB, identity: str, args: list[str]) -> None:
    validate_identity(db, identity)
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
    print(ok("OK status updated"))


def cmd_inbox(db: BoardDB, identity: str) -> None:
    validate_identity(db, identity)
    name = identity.lower()
    print_unread_inbox(db, name, write_ack_marker=True)
    print_task_queue(db, name)


def cmd_ack(db: BoardDB, identity: str) -> None:
    validate_identity(db, identity)
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
        print("收件箱已经是空的")
        marker.unlink(missing_ok=True)
        return

    if max_id:
        db.execute(
            "UPDATE inbox SET read=1 WHERE session=? AND read=0 AND message_id<=?",
            (name, max_id),
        )
    else:
        db.execute("UPDATE inbox SET read=1 WHERE session=? AND read=0", (name,))

    print(ok(f"OK {count} 条已清空（完整记录在 messages.log）"))
    marker.unlink(missing_ok=True)


def cmd_log(db: BoardDB, identity: str, args: list[str]) -> None:
    if identity:
        validate_identity(db, identity)
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


def cmd_history(db: BoardDB, args: list[str]) -> None:
    if not args:
        print("Usage: board history <session|topic> [limit]")
        raise SystemExit(1)
    subject = args[0].lower()
    try:
        limit = int(args[1]) if len(args) > 1 else 20
    except ValueError:
        print(error(f"ERROR: 无效的数字: {args[1]}"))
        raise SystemExit(1)

    print(heading(f"=== History: {args[0]} ===") + "\n")
    print(f"Messages involving {args[0]} (last {limit}):")
    rows = db.query(
        "SELECT '[' || ts || '] ' || sender || ' → ' || recipient || ': ' || substr(body, 1, 100) "
        "FROM messages WHERE sender=? OR recipient=? OR (recipient='all' AND sender=?) "
        "OR body LIKE '%' || ? || '%' ESCAPE '\\' ORDER BY id DESC LIMIT ?",
        (subject, subject, subject, escape_like(subject), limit),
    )
    for (line,) in reversed(rows):
        print(f"  {line}")
    print()
    print("Status changes:")
    for updated_at, status in db.query("SELECT updated_at, status FROM sessions WHERE name=?", (subject,)):
        print(f"  [{updated_at}] {status}")
