"""board_msg — send / inbox / ack / status / log commands."""

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

from lib.board_db import BoardDB, ts
from lib.common import parse_flags


def _ack_marker_path(db: BoardDB, name: str) -> Path:
    """Path to file recording max message_id seen by last inbox call."""
    return db.env.sessions_dir / f".{name}.ack_max_id"


def _is_idle(sess: str) -> bool:
    """Check if a Claude Code session is idle at its prompt (not mid-response).

    Claude Code's prompt layout puts the prompt marker a few lines above the bottom
    (status bar, project name, permissions line are below it), so we
    check the last ~8 lines rather than just the final line.
    """
    r = subprocess.run(
        ["tmux", "capture-pane", "-t", sess, "-p", "-S", "-10"],
        capture_output=True,
        text=True,
        timeout=3,
    )
    if r.returncode != 0:
        return False
    text = r.stdout.rstrip()
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
    """Inject a fixed prompt into the recipient's tmux session to check inbox.

    Only nudges idle agents — busy agents will pick up messages via the
    PostToolBatch hook. This avoids commands piling up in Claude Code's
    message queue when injected mid-response.
    """
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
        try:
            r = subprocess.run(["tmux", "has-session", "-t", sess], capture_output=True, timeout=5)
            if r.returncode != 0:
                continue
            if not _is_idle(sess):
                continue
            cmd = f"{board} --as {name} inbox"
            subprocess.run(["tmux", "send-keys", "-t", sess, "-l", cmd], capture_output=True, timeout=5)
            subprocess.run(["tmux", "send-keys", "-t", sess, "Enter"], capture_output=True, timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            continue


def cmd_send(db: BoardDB, identity: str, args: list[str]) -> None:
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
    if attach_ref:
        print(f"  附件已存储: {stored_path}")

    _nudge_session(db, to)


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
    print("OK status updated")


def cmd_inbox(db: BoardDB, identity: str) -> None:
    name = identity.lower()
    db.ensure_session(name)
    count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,))
    if not count:
        print("收件箱为空")
    else:
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

    _task_print_queue_short(db, name)


def _task_print_queue_short(db: BoardDB, target: str) -> None:
    rows = db.query(
        "SELECT id, status, priority, description FROM tasks "
        "WHERE session=? AND status != 'done' "
        "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, priority DESC, id ASC",
        (target,),
    )
    print("\n任务队列:")
    if not rows:
        print("  (无待办任务)")
        return
    for tid, status, priority, desc in rows:
        marker = "*" if status == "active" else " "
        print(f"  {marker} #{tid} [{status} p{priority}] {desc}")


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

    print(f"OK {count} 条已清空（完整记录在 messages.log）")
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
