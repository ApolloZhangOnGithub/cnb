"""board_view — read-only views: view, dashboard, p0, dirty, prebuild, freshness, relations, history, roster, files, get."""

import glob
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

from lib.board_db import BoardDB


def _git(project_root: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", "-C", str(project_root), *args],
        capture_output=True,
        text=True,
    )
    return r.stdout


def _tmux_has_session(name: str) -> bool:
    try:
        r = subprocess.run(["tmux", "has-session", "-t", name], capture_output=True, timeout=3)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _tmux_pane_command(name: str) -> str:
    try:
        r = subprocess.run(
            ["tmux", "list-panes", "-t", name, "-F", "#{pane_current_command}"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return r.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _pgrep(pattern: str) -> str | None:
    try:
        r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            return r.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def cmd_overview(db: BoardDB) -> None:
    """Default view when running cnb with no args."""
    prefix = db.env.prefix
    now = datetime.now().strftime("%H:%M")
    print(f"=== {db.env.project_root.name}  {now} ===")
    print()

    # ── sessions ──
    for (name,) in db.query("SELECT name FROM sessions WHERE name != 'all' ORDER BY name"):
        sess = f"{prefix}-{name}"
        if _tmux_has_session(sess):
            cmd = _tmux_pane_command(sess)
            status = "● running" if cmd not in ("zsh", "bash", "sh", "-zsh", "-bash") else "○ dead"
        else:
            status = "· offline"

        inbox = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,)) or 0
        inbox_str = f"  [{inbox} msg]" if inbox else ""
        task = db.scalar("SELECT status FROM sessions WHERE name=?", (name,)) or ""
        if task:
            task = task[:60]
        else:
            task = "(no status)"

        line = f"  {status:12s} {name:<10s} {task}"
        if inbox:
            line += f"{inbox_str}"
        print(line)

    # ── recent messages ──
    rows = db.query(
        "SELECT ts, sender, recipient, substr(body, 1, 80) "
        "FROM messages ORDER BY id DESC LIMIT 5"
    )
    if rows:
        print()
        print("Recent:")
        for ts_val, sender, recipient, body in reversed(rows):
            print(f"  [{ts_val}] {sender} → {recipient}: {body}")

    # ── open proposals ──
    proposals = db.query(
        "SELECT number || '-' || slug FROM proposals WHERE status='OPEN'"
    )
    if proposals:
        print()
        print(f"Open proposals: {len(proposals)}")

    # ── dispatcher ──
    pid = _pgrep("dispatcher")
    print()
    if pid:
        print(f"  dispatcher: running (pid {pid})")
    else:
        running = any(_tmux_has_session(f"{prefix}-{n}") for (n,) in db.query("SELECT name FROM sessions WHERE name != 'all'"))
        if running:
            print("  dispatcher: NOT RUNNING — run: cnb dispatcher")
        else:
            print("  No sessions running. Start with: cnb swarm start")


def cmd_view(db: BoardDB, identity: str) -> None:
    print("=== Board ===\n")

    roadmap = db.env.project_root / "ROADMAP.md"
    p0_locked = False
    if roadmap.is_file():
        text = roadmap.read_text()
        m = re.search(r"端到端状态.*?(?=\n## [A-Z]|\Z)", text, re.DOTALL)
        if m and re.search(r"从未|未验证|阻塞", m.group()):
            p0_locked = True
            print("!!! P0 LOCKED — 端到端未验证，全员聚焦 P0 !!!")
            print("    运行 ./board p0 查看详情\n")

    if identity:
        me = identity.lower()
        count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (me,))
        if count:
            print(f">>> 你有 {count} 条未读消息，运行 ./board inbox 查看 <<<\n")

    print("Status:")
    for name, task in db.query("SELECT name, status FROM sessions ORDER BY name"):
        cap = name[0].upper() + name[1:] if name else name
        task = task or "(none)"
        tag = ""
        if p0_locked and "[P0]" not in task:
            tag = " [!! 未标 P0]"
        if len(task) > 72:
            task = task[:69] + "..."
        print(f"  {cap:<8s} {task}{tag}")
    print()

    print("Recent messages:")
    rows = db.query(
        "SELECT '[' || ts || '] ' || sender || ' → ' || recipient || ': ' || substr(body, 1, 80) "
        "FROM messages ORDER BY id DESC LIMIT 8"
    )
    for (line,) in reversed(rows):
        print(f"  {line}")
    print()

    print("Proposals:")
    rows = db.query(
        "SELECT number || '-' || slug, status, "
        "(SELECT COUNT(*) FROM votes v WHERE v.proposal_id=p.id AND v.decision='SUPPORT'), "
        "(SELECT COUNT(*) FROM votes v WHERE v.proposal_id=p.id AND v.decision='OBJECT') "
        "FROM proposals p WHERE status='OPEN'"
    )
    if not rows:
        print("  (none)")
    else:
        for pname, _, s, o in rows:
            print(f"  {pname} [OPEN] S={s} O={o}")


def cmd_p0(db: BoardDB) -> None:
    roadmap = db.env.project_root / "ROADMAP.md"
    if not roadmap.is_file():
        print("ERROR: ROADMAP.md not found")
        raise SystemExit(1)

    text = roadmap.read_text()
    m = re.search(r"端到端状态(.*?)(?=\n## [A-Z]|\Z)", text, re.DOTALL)
    status_block = m.group() if m else ""
    locked = bool(re.search(r"从未|未验证|阻塞", status_block))

    if locked:
        print("=== P0 LOCKED ===\n")
        print("Status from ROADMAP.md:")
        for line in status_block.split("\n"):
            print(f"  {line}")
        print("\nSession alignment:")
        for name, task in db.query("SELECT name, status FROM sessions ORDER BY name"):
            cap = name[0].upper() + name[1:] if name else name
            task = task or "(no status)"
            tag = "[OK]" if "[P0]" in task else "[!!]"
            print(f"  {cap:<8s} {tag} {task}")
    else:
        print("=== P0 CLEAR ===")
        print("No active P0 blocker. Normal work allowed.")


def cmd_prebuild(db: BoardDB) -> None:
    print("=== Pre-build Check ===\n")
    has_fail = False
    pr = db.env.project_root

    dirty = _git(pr, "status", "--porcelain")
    code = "\n".join(l for l in dirty.splitlines() if not l.startswith("??") and "board/" not in l)
    if code:
        print("FAIL: uncommitted code changes:")
        for l in code.splitlines():
            print(f"  {l}")
        has_fail = True
    else:
        print("OK: working tree clean (code files)")

    print("\nLast 3 commits:")
    log = _git(pr, "log", "--oneline", "-3")
    for l in log.splitlines():
        print(f"  {l}")
    print()
    if has_fail:
        print("NOT ready to build. Fix issues above first.")
        raise SystemExit(1)
    print("Ready to build.")


def cmd_dirty(db: BoardDB) -> None:
    print("=== Uncommitted Changes ===\n")
    pr = db.env.project_root
    changes = _git(pr, "status", "--porcelain").strip()
    if not changes:
        print("Working tree clean.")
        return
    code = "\n".join(l for l in changes.splitlines() if "board/" not in l)
    if code:
        print("Code:")
        for l in code.splitlines():
            print(f"  {l}")
        print()
    board = "\n".join(l for l in changes.splitlines() if "board/" in l)
    if board:
        print(f"Board: {len(board.splitlines())} files (normal churn)")
    print()
    log = _git(pr, "log", "--oneline", "-1").strip()
    print(f"Last commit: {log}")


def cmd_dashboard(db: BoardDB) -> None:
    prefix = db.env.prefix
    print(f"=== Team Dashboard {datetime.now().strftime('%H:%M')} ===\n")
    for (name,) in db.query("SELECT name FROM sessions ORDER BY name"):
        session_name = f"{prefix}-{name}"
        status = "offline"
        if _tmux_has_session(session_name):
            cmd = _tmux_pane_command(session_name)
            if cmd in ("zsh", "bash", "sh", "-zsh", "-bash"):
                status = "DEAD"
            else:
                status = "running"

        inbox_count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,))
        inbox_str = f" [{inbox_count}msg]" if inbox_count else ""
        task = db.scalar("SELECT substr(status, 1, 50) FROM sessions WHERE name=?", (name,)) or "-"
        print(f"  {name:<7s} {status:<8s}{inbox_str}")
        print(f"         {task}")
    print()
    pid = _pgrep("dispatcher")
    if pid:
        print(f"  dispatcher: running (PID {pid})")
    else:
        print("  dispatcher: NOT RUNNING")


def cmd_files(db: BoardDB) -> None:
    print("=== 共享文件 ===\n")
    rows = db.query("SELECT hash, original_name, sender, ts FROM files ORDER BY ts DESC")
    if not rows:
        print("  (none)")
    else:
        for h, orig, sender, date in rows:
            size = 0
            for f in glob.glob(str(db.env.claudes_dir / "files" / f"{h}.*")):
                if os.path.isfile(f):
                    size = os.path.getsize(f)
                    break
            print(f"  {h:<14s} {orig:<30s} {size:>6d} bytes  by {sender:<6s}  {date}")
    print("\n查看文件: ./board get <hash前缀或文件名>")


def cmd_get(db: BoardDB, args: list[str]) -> None:
    if not args:
        print("Usage: ./board get <hash-prefix|filename>")
        raise SystemExit(1)
    query = args[0]
    row = db.query_one(
        "SELECT hash, original_name, sender, ts, stored_path FROM files "
        "WHERE hash LIKE ? ESCAPE '\\' OR original_name=? LIMIT 1",
        (query + "%", query),
    )
    if not row:
        print(f"ERROR: no file matching '{query}'")
        raise SystemExit(1)
    h, orig, sender, date, path = row
    print("--- 文件信息 ---")
    print(f"  Name: {orig}")
    print(f"  Hash: {h}")
    print(f"  Sender: {sender}")
    print(f"  Date: {date}")
    print("\n--- 内容 ---")
    full_path = db.env.claudes_dir / path
    if full_path.is_file():
        print(full_path.read_text(), end="")
    else:
        print("(file content not on disk)")


def cmd_freshness(db: BoardDB) -> None:
    print("=== 数据新鲜度 ===\n")
    print(f"  {'Session':<8s}  {'Last status update':<20s}  {'Unread inbox'}")
    print(f"  {'-------':<8s}  {'------------------':<20s}  {'------------'}")
    rows = db.query(
        "SELECT s.name, s.updated_at, "
        "(SELECT COUNT(*) FROM inbox i WHERE i.session=s.name AND i.read=0) "
        "FROM sessions s ORDER BY s.name"
    )
    for name, updated, inbox_count in rows:
        print(f"  {name:<8s}  {updated or '(never)':<20s}  {inbox_count}")


def cmd_relations(db: BoardDB) -> None:
    print("=== 通信关系图 ===\n")
    rows = db.query(
        "SELECT sender, recipient, COUNT(*) as c FROM messages "
        "WHERE sender != 'SYSTEM' GROUP BY sender, recipient ORDER BY c DESC LIMIT 20"
    )
    for sender, recipient, count in rows:
        print(f"  {sender} → {recipient}: {count} messages")


def cmd_history(db: BoardDB, args: list[str]) -> None:
    if not args:
        print("Usage: ./board history <session|topic> [limit]")
        raise SystemExit(1)
    subject = args[0].lower()
    limit = int(args[1]) if len(args) > 1 else 20

    print(f"=== History: {args[0]} ===\n")
    print(f"Messages involving {args[0]} (last {limit}):")
    rows = db.query(
        "SELECT '[' || ts || '] ' || sender || ' → ' || recipient || ': ' || substr(body, 1, 100) "
        "FROM messages WHERE sender=? OR recipient=? OR (recipient='all' AND sender=?) "
        "OR body LIKE '%' || ? || '%' ESCAPE '\\' ORDER BY id DESC LIMIT ?",
        (subject, subject, subject, subject, limit),
    )
    for (line,) in reversed(rows):
        print(f"  {line}")
    print()
    print("Status changes:")
    for updated_at, status in db.query("SELECT updated_at, status FROM sessions WHERE name=?", (subject,)):
        print(f"  [{updated_at}] {status}")


def cmd_roster(db: BoardDB) -> None:
    print("=== 员工状态 ===")
    prefix = db.env.prefix
    rows = db.query(
        "SELECT s.name, CASE WHEN su.name IS NOT NULL THEN 'SUSPENDED' ELSE 'active' END "
        "FROM sessions s LEFT JOIN suspended su ON s.name=su.name ORDER BY s.name"
    )
    for name, state in rows:
        online = "online" if _tmux_has_session(f"{prefix}-{name}") else "offline"
        print(f"  {name:<8s}  {state:<10s}  {online}")
