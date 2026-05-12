"""board_view — read-only views: view, dashboard, p0, dirty, prebuild, freshness, relations, roster."""

import re
import subprocess
from datetime import datetime
from pathlib import Path

from lib import fmt
from lib.board_db import BoardDB
from lib.common import validate_identity
from lib.tmux_utils import capture_pane, has_session, pane_command

SHELL_COMMANDS = {"zsh", "bash", "sh", "-zsh", "-bash", ""}
SPINNER_RE = re.compile(r"^\s*(⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏|●)", re.MULTILINE)
WORK_LABEL_RE = re.compile(r"^\s*[•●]\s+(Working|Thinking|Running)\b", re.IGNORECASE | re.MULTILINE)
PROMPT_WITH_INPUT_RE = re.compile(r"^\s*❯ .{3,}", re.MULTILINE)


def _git(project_root: Path, *args: str) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(project_root), *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.stdout
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _pane_work_state(sess: str) -> str:
    """Return a best-effort work state for a live non-shell agent pane."""
    pane = capture_pane(sess, lines=20)
    tail = "\n".join(pane.splitlines()[-8:])
    if "bypass permissions" in tail:
        return "blocked"
    if SPINNER_RE.search(tail) or WORK_LABEL_RE.search(tail) or PROMPT_WITH_INPUT_RE.search(tail):
        return "working"
    return "idle"


def _tmux_status(prefix: str, name: str, ago: str = "") -> tuple[str, str] | None:
    sess = f"{prefix}-{name}"
    if not has_session(sess):
        return None

    cmd = pane_command(sess)
    if cmd in SHELL_COMMANDS:
        return fmt.status_idle("○ shell"), ago

    # A live Claude/Codex pane is not necessarily working; it can be alive at
    # the prompt. Keep this separate so managers do not confuse capacity with progress.
    state = _pane_work_state(sess)
    if state == "working":
        return fmt.status_working("● working"), ago
    if state == "blocked":
        return fmt.status_blocked("● alive blocked"), ago
    return fmt.status_idle("● alive idle"), ago


def _heartbeat_status(last_heartbeat: str | None, prefix: str, name: str) -> tuple[str, str]:
    """Derive visible session state from tmux liveness plus heartbeat freshness."""
    ago = ""
    if last_heartbeat:
        try:
            hb_time = datetime.strptime(last_heartbeat, "%Y-%m-%d %H:%M:%S")
            delta = (datetime.now() - hb_time).total_seconds()
            if delta < 120:
                ago = fmt.dim(f"[{int(delta)}s ago]")
                tmux_state = _tmux_status(prefix, name, ago)
                return tmux_state if tmux_state else (fmt.status_working("● alive"), ago)
            elif delta < 180:
                return fmt.yellow("◐ pulse lag"), fmt.dim(f"[{int(delta / 60)}m ago]")
            elif delta < 600:
                return fmt.status_offline("○ pulse stale"), fmt.dim(f"[{int(delta / 60)}m ago]")
            else:
                hours = delta / 3600
                if hours >= 1:
                    ago = fmt.dim(f"[{int(hours)}h ago]")
                else:
                    ago = fmt.dim(f"[{int(delta / 60)}m ago]")
        except ValueError:
            pass

    tmux_state = _tmux_status(prefix, name, ago)
    if tmux_state:
        return tmux_state
    return fmt.status_offline("· offline"), ago


def cmd_overview(db: BoardDB) -> None:
    """Default view when running cnb with no args."""
    assert db.env is not None
    prefix = db.env.prefix
    now = datetime.now().strftime("%H:%M")
    print(fmt.header(f"=== {db.env.project_root.name}  {now} ==="))
    print()

    # ── sessions ──
    for row in db.query("SELECT name, status, last_heartbeat FROM sessions WHERE name != 'all' ORDER BY name"):
        name, task, last_hb = row[0], row[1], row[2]
        status, ago = _heartbeat_status(last_hb, prefix, name)

        inbox = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,)) or 0
        inbox_str = f"  {fmt.yellow(f'[{inbox} msg]')}" if inbox else ""
        if task:
            task = task[:60]
        else:
            task = fmt.dim("(no status)")

        line = f"  {status}  {fmt.bold(name.ljust(10))} {task}"
        if ago:
            line += f"  {ago}"
        if inbox:
            line += inbox_str
        print(line)

    # ── recent messages ──
    rows = db.query("SELECT ts, sender, recipient, substr(body, 1, 80) FROM messages ORDER BY id DESC LIMIT 5")
    if rows:
        print()
        print(fmt.subheader("Recent:"))
        for ts_val, sender, recipient, body in reversed(rows):
            print(f"  {fmt.dim(f'[{ts_val}]')} {fmt.sender_name(sender)} → {recipient}: {body}")

    # ── open proposals ──
    proposals = db.query("SELECT number || '-' || slug FROM proposals WHERE status='OPEN'")
    if proposals:
        print()
        print(fmt.subheader(f"Open proposals: {len(proposals)}"))

    # ── dispatcher ──
    dispatcher_sess = f"{prefix}-dispatcher"
    print()
    if has_session(dispatcher_sess):
        print(f"  dispatcher: {fmt.green('running')} ({dispatcher_sess})")
    else:
        running = any(
            has_session(f"{prefix}-{n}") for (n,) in db.query("SELECT name FROM sessions WHERE name != 'all'")
        )
        if running:
            print(f"  dispatcher: {fmt.red('NOT RUNNING')} — run: cnb dispatcher")
        else:
            print(f"  {fmt.dim('No sessions running. Start with: cnb swarm start')}")


def cmd_view(db: BoardDB, identity: str) -> None:
    if identity:
        validate_identity(db, identity)
    assert db.env is not None
    print(fmt.header("=== Board ===") + "\n")

    roadmap = db.env.project_root / "ROADMAP.md"
    p0_locked = False
    if roadmap.is_file():
        text = roadmap.read_text()
        m = re.search(r"端到端状态.*?(?=\n## [A-Z]|\Z)", text, re.DOTALL)
        if m and re.search(r"从未|未验证|阻塞", m.group()):
            p0_locked = True
            print(fmt.status_blocked("!!! P0 LOCKED — 端到端未验证，全员聚焦 P0 !!!"))
            print(f"    运行 {fmt.bold('./board p0')} 查看详情\n")

    if identity:
        me = identity.lower()
        count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (me,))
        if count:
            print(fmt.yellow(f">>> 你有 {count} 条未读消息，运行 ./board inbox 查看 <<<") + "\n")

    prefix = db.env.prefix
    print(fmt.subheader("Status:"))
    for name, task, last_hb in db.query("SELECT name, status, last_heartbeat FROM sessions ORDER BY name"):
        cap = name[0].upper() + name[1:] if name else name
        status, ago = _heartbeat_status(last_hb, prefix, name)
        task = task or fmt.dim("(none)")
        tag = ""
        if p0_locked and "[P0]" not in (task if isinstance(task, str) else ""):
            tag = f" {fmt.red('[!! 未标 P0]')}"
        if len(task) > 60:
            task = task[:57] + "..."
        ago_str = f"  {ago}" if ago else ""
        print(f"  {status}  {fmt.bold(cap.ljust(10))} {task}{tag}{ago_str}")
    print()

    print(fmt.subheader("Recent messages:"))
    rows = db.query("SELECT ts, sender, recipient, substr(body, 1, 80) FROM messages ORDER BY id DESC LIMIT 8")
    for ts_val, sender_val, recipient_val, body_val in reversed(rows):
        print(f"  {fmt.dim(f'[{ts_val}]')} {fmt.sender_name(sender_val)} → {recipient_val}: {body_val}")
    print()

    print(fmt.subheader("Proposals:"))
    rows = db.query(
        "SELECT number || '-' || slug, status, "
        "(SELECT COUNT(*) FROM votes v WHERE v.proposal_id=p.id AND v.decision='SUPPORT'), "
        "(SELECT COUNT(*) FROM votes v WHERE v.proposal_id=p.id AND v.decision='OBJECT') "
        "FROM proposals p WHERE status='OPEN'"
    )
    if not rows:
        print(f"  {fmt.dim('(none)')}")
    else:
        for pname, _, s, o in rows:
            print(f"  {fmt.cyan(pname)} {fmt.yellow('[OPEN]')} S={fmt.green(str(s))} O={fmt.red(str(o))}")


def cmd_p0(db: BoardDB) -> None:
    assert db.env is not None
    roadmap = db.env.project_root / "ROADMAP.md"
    if not roadmap.is_file():
        print(fmt.err("ROADMAP.md not found"))
        raise SystemExit(1)

    text = roadmap.read_text()
    m = re.search(r"端到端状态(.*?)(?=\n## [A-Z]|\Z)", text, re.DOTALL)
    status_block = m.group() if m else ""
    locked = bool(re.search(r"从未|未验证|阻塞", status_block))

    if locked:
        print(fmt.status_blocked("=== P0 LOCKED ===") + "\n")
        print(fmt.subheader("Status from ROADMAP.md:"))
        for line in status_block.split("\n"):
            print(f"  {line}")
        print(f"\n{fmt.subheader('Session alignment:')}")
        for name, task in db.query("SELECT name, status FROM sessions ORDER BY name"):
            cap = name[0].upper() + name[1:] if name else name
            task = task or fmt.dim("(no status)")
            tag = fmt.green("[OK]") if "[P0]" in task else fmt.red("[!!]")
            print(f"  {fmt.bold(cap.ljust(8))} {tag} {task}")
    else:
        print(fmt.header("=== P0 CLEAR ==="))
        print(fmt.green("No active P0 blocker. Normal work allowed."))


def cmd_prebuild(db: BoardDB) -> None:
    assert db.env is not None
    print(fmt.header("=== Pre-build Check ===") + "\n")
    has_fail = False
    pr = db.env.project_root

    dirty = _git(pr, "status", "--porcelain")
    code = "\n".join(l for l in dirty.splitlines() if not l.startswith("??") and "board/" not in l)
    if code:
        print(fmt.red("FAIL: uncommitted code changes:"))
        for l in code.splitlines():
            print(f"  {l}")
        has_fail = True
    else:
        print(fmt.ok("working tree clean (code files)"))

    print(f"\n{fmt.subheader('Last 3 commits:')}")
    log = _git(pr, "log", "--oneline", "-3")
    for l in log.splitlines():
        print(f"  {fmt.dim(l)}")
    print()
    if has_fail:
        print(fmt.red("NOT ready to build. Fix issues above first."))
        raise SystemExit(1)
    print(fmt.green("Ready to build."))


def cmd_dirty(db: BoardDB) -> None:
    assert db.env is not None
    print(fmt.header("=== Uncommitted Changes ===") + "\n")
    pr = db.env.project_root
    changes = _git(pr, "status", "--porcelain").strip()
    if not changes:
        print(fmt.green("Working tree clean."))
        return
    code = "\n".join(l for l in changes.splitlines() if "board/" not in l)
    if code:
        print(fmt.subheader("Code:"))
        for l in code.splitlines():
            print(f"  {fmt.yellow(l)}")
        print()
    board = "\n".join(l for l in changes.splitlines() if "board/" in l)
    if board:
        board_count = len(board.splitlines())
        print(fmt.dim(f"Board: {board_count} files (normal churn)"))
    print()
    log = _git(pr, "log", "--oneline", "-1").strip()
    print(f"{fmt.subheader('Last commit:')} {fmt.dim(log)}")


def cmd_dashboard(db: BoardDB) -> None:
    assert db.env is not None
    prefix = db.env.prefix
    now_str = datetime.now().strftime("%H:%M")
    print(fmt.header(f"=== Team Dashboard {now_str} ===") + "\n")
    for row in db.query("SELECT name, status, last_heartbeat FROM sessions ORDER BY name"):
        name, task, last_hb = row[0], row[1], row[2]
        status, ago = _heartbeat_status(last_hb, prefix, name)

        inbox_count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,))
        inbox_str = f" {fmt.yellow(f'[{inbox_count}msg]')}" if inbox_count else ""
        task = task[:50] if task else fmt.dim("-")
        ago_str = f"  {ago}" if ago else ""
        print(f"  {fmt.bold(name.ljust(7))} {status}{inbox_str}{ago_str}")
        print(f"         {task}")
    print()
    dispatcher_sess = f"{prefix}-dispatcher"
    if has_session(dispatcher_sess):
        print(f"  dispatcher: {fmt.green('running')} ({dispatcher_sess})")
    else:
        print(f"  dispatcher: {fmt.red('NOT RUNNING')}")


def cmd_freshness(db: BoardDB) -> None:
    print(fmt.header("=== 数据新鲜度 ===") + "\n")
    print(
        f"  {fmt.bold('Session'.ljust(8))}  "
        f"{fmt.bold('Last status'.ljust(20))}  "
        f"{fmt.bold('Last heartbeat'.ljust(20))}  "
        f"{fmt.bold('Unread')}"
    )
    print(
        f"  {fmt.dim('-------'.ljust(8))}  "
        f"{fmt.dim('-----------'.ljust(20))}  "
        f"{fmt.dim('--------------'.ljust(20))}  "
        f"{fmt.dim('------')}"
    )
    rows = db.query(
        "SELECT s.name, s.updated_at, s.last_heartbeat, "
        "(SELECT COUNT(*) FROM inbox i WHERE i.session=s.name AND i.read=0) "
        "FROM sessions s ORDER BY s.name"
    )
    for name, updated, heartbeat, inbox_count in rows:
        updated_str = updated or fmt.dim("(never)")
        heartbeat_str = heartbeat or fmt.dim("(never)")
        unread = fmt.yellow(str(inbox_count)) if inbox_count else fmt.dim("0")
        # Pad plain-text portion before applying color
        updated_padded = f"{updated_str:<20s}" if updated else fmt.dim("(never)".ljust(20))
        heartbeat_padded = f"{heartbeat_str:<20s}" if heartbeat else fmt.dim("(never)".ljust(20))
        print(f"  {fmt.bold(name.ljust(8))}  {updated_padded}  {heartbeat_padded}  {unread}")


def cmd_relations(db: BoardDB) -> None:
    print(fmt.header("=== 通信关系图 ===") + "\n")
    rows = db.query(
        "SELECT sender, recipient, COUNT(*) as c FROM messages "
        "WHERE sender != 'SYSTEM' GROUP BY sender, recipient ORDER BY c DESC LIMIT 20"
    )
    for sender, recipient, count in rows:
        print(f"  {fmt.sender_name(sender)} → {recipient}: {fmt.bold(str(count))} messages")


def cmd_roster(db: BoardDB) -> None:
    assert db.env is not None
    print(fmt.header("=== 员工状态 ==="))
    prefix = db.env.prefix
    rows = db.query(
        "SELECT s.name, CASE WHEN su.name IS NOT NULL THEN 'SUSPENDED' ELSE 'active' END "
        "FROM sessions s LEFT JOIN suspended su ON s.name=su.name ORDER BY s.name"
    )
    for name, state in rows:
        is_online = has_session(f"{prefix}-{name}")
        state_str = fmt.red("SUSPENDED") if state == "SUSPENDED" else fmt.green("active")
        online_str = fmt.green("online") if is_online else fmt.dim("offline")
        print(f"  {fmt.bold(name.ljust(8))}  {state_str}  {online_str}")
