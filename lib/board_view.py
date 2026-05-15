"""board_view — read-only views: view, dashboard, p0, dirty, prebuild, freshness, relations, roster."""

import re
import subprocess
from datetime import datetime
from pathlib import Path

from lib.board_db import BoardDB
from lib.common import validate_identity
from lib.tmux_utils import capture_pane, has_session, pane_command
from lib.worktree_checkpoint import build_checkpoint, checkpoint_has_blocker, render_checkpoint

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
        return "○ shell", ago

    # A live Claude/Codex pane is not necessarily working; it can be alive at
    # the prompt. Keep this separate so managers do not confuse capacity with progress.
    state = _pane_work_state(sess)
    if state == "working":
        return "● working", ago
    if state == "blocked":
        return "● alive blocked", ago
    return "● alive idle", ago


def _heartbeat_status(last_heartbeat: str | None, prefix: str, name: str) -> tuple[str, str]:
    """Derive visible session state from tmux liveness plus heartbeat freshness."""
    ago = ""
    if last_heartbeat:
        try:
            hb_time = datetime.strptime(last_heartbeat, "%Y-%m-%d %H:%M:%S")
            delta = (datetime.now() - hb_time).total_seconds()
            if delta < 120:
                ago = f"[{int(delta)}s ago]"
                tmux_state = _tmux_status(prefix, name, ago)
                return tmux_state if tmux_state else ("● alive", ago)
            elif delta < 180:
                return "◐ pulse lag", f"[{int(delta / 60)}m ago]"
            elif delta < 600:
                return "○ pulse stale", f"[{int(delta / 60)}m ago]"
            else:
                hours = delta / 3600
                ago = f"[{int(hours)}h ago]" if hours >= 1 else f"[{int(delta / 60)}m ago]"
        except ValueError:
            pass

    tmux_state = _tmux_status(prefix, name, ago)
    if tmux_state:
        return tmux_state
    return "· offline", ago


def cmd_overview(db: BoardDB) -> None:
    """Default view when running cnb with no args."""
    assert db.env is not None
    prefix = db.env.prefix
    now = datetime.now().strftime("%H:%M")
    print(f"=== {db.env.project_root.name}  {now} ===")
    print()

    # ── sessions ──
    for row in db.query("SELECT name, status, last_heartbeat FROM sessions WHERE name != 'all' ORDER BY name"):
        name, task, last_hb = row[0], row[1], row[2]
        status, ago = _heartbeat_status(last_hb, prefix, name)

        inbox = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,)) or 0
        inbox_str = f"  [{inbox} msg]" if inbox else ""
        if task:
            task = task[:60]
        else:
            task = "(no status)"

        line = f"  {status:12s} {name:<10s} {task}"
        if ago:
            line += f"  {ago}"
        if inbox:
            line += f"{inbox_str}"
        print(line)

    # ── recent messages ──
    rows = db.query("SELECT ts, sender, recipient, substr(body, 1, 80) FROM messages ORDER BY id DESC LIMIT 5")
    if rows:
        print()
        print("Recent:")
        for ts_val, sender, recipient, body in reversed(rows):
            print(f"  [{ts_val}] {sender} → {recipient}: {body}")

    # ── open proposals ──
    proposals = db.query("SELECT number || '-' || slug FROM proposals WHERE status='OPEN'")
    if proposals:
        print()
        print(f"Open proposals: {len(proposals)}")

    # ── dispatcher ──
    dispatcher_sess = f"{prefix}-dispatcher"
    print()
    if has_session(dispatcher_sess):
        print(f"  dispatcher: running ({dispatcher_sess})")
    else:
        running = any(
            has_session(f"{prefix}-{n}") for (n,) in db.query("SELECT name FROM sessions WHERE name != 'all'")
        )
        if running:
            print("  dispatcher: NOT RUNNING — run: cnb dispatcher")
        else:
            print("  No sessions running. Start with: cnb swarm start")


def cmd_view(db: BoardDB, identity: str) -> None:
    if identity:
        validate_identity(db, identity)
    assert db.env is not None
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

    prefix = db.env.prefix
    print("Status:")
    for name, task, last_hb in db.query("SELECT name, status, last_heartbeat FROM sessions ORDER BY name"):
        cap = name[0].upper() + name[1:] if name else name
        status, ago = _heartbeat_status(last_hb, prefix, name)
        task = task or "(none)"
        tag = ""
        if p0_locked and "[P0]" not in task:
            tag = " [!! 未标 P0]"
        if len(task) > 60:
            task = task[:57] + "..."
        ago_str = f"  {ago}" if ago else ""
        print(f"  {status:12s} {cap:<10s} {task}{tag}{ago_str}")
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
    assert db.env is not None
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
    assert db.env is not None
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
    assert db.env is not None
    print(render_checkpoint(build_checkpoint(db.env.project_root)))


def cmd_checkpoint(db: BoardDB) -> None:
    assert db.env is not None
    checkpoint = build_checkpoint(db.env.project_root)
    print(render_checkpoint(checkpoint, guard=True))
    if checkpoint_has_blocker(checkpoint):
        raise SystemExit(1)


def cmd_dashboard(db: BoardDB) -> None:
    assert db.env is not None
    prefix = db.env.prefix
    print(f"=== Team Dashboard {datetime.now().strftime('%H:%M')} ===\n")
    for row in db.query("SELECT name, status, last_heartbeat FROM sessions ORDER BY name"):
        name, task, last_hb = row[0], row[1], row[2]
        status, ago = _heartbeat_status(last_hb, prefix, name)

        inbox_count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,))
        inbox_str = f" [{inbox_count}msg]" if inbox_count else ""
        task = task[:50] if task else "-"
        ago_str = f"  {ago}" if ago else ""
        print(f"  {name:<7s} {status:<12s}{inbox_str}{ago_str}")
        print(f"         {task}")
    print()
    dispatcher_sess = f"{prefix}-dispatcher"
    if has_session(dispatcher_sess):
        print(f"  dispatcher: running ({dispatcher_sess})")
    else:
        print("  dispatcher: NOT RUNNING")


def cmd_freshness(db: BoardDB) -> None:
    print("=== 数据新鲜度 ===\n")
    print(f"  {'Session':<8s}  {'Last status':<20s}  {'Last heartbeat':<20s}  {'Unread'}")
    print(f"  {'-------':<8s}  {'-----------':<20s}  {'--------------':<20s}  {'------'}")
    rows = db.query(
        "SELECT s.name, s.updated_at, s.last_heartbeat, "
        "(SELECT COUNT(*) FROM inbox i WHERE i.session=s.name AND i.read=0) "
        "FROM sessions s ORDER BY s.name"
    )
    for name, updated, heartbeat, inbox_count in rows:
        print(f"  {name:<8s}  {updated or '(never)':<20s}  {heartbeat or '(never)':<20s}  {inbox_count}")


def cmd_relations(db: BoardDB) -> None:
    print("=== 通信关系图 ===\n")
    rows = db.query(
        "SELECT sender, recipient, COUNT(*) as c FROM messages "
        "WHERE sender != 'SYSTEM' GROUP BY sender, recipient ORDER BY c DESC LIMIT 20"
    )
    for sender, recipient, count in rows:
        print(f"  {sender} → {recipient}: {count} messages")


def cmd_roster(db: BoardDB) -> None:
    assert db.env is not None
    print("=== 员工状态 ===")
    prefix = db.env.prefix
    rows = db.query(
        "SELECT s.name, CASE WHEN su.name IS NOT NULL THEN 'SUSPENDED' ELSE 'active' END "
        "FROM sessions s LEFT JOIN suspended su ON s.name=su.name ORDER BY s.name"
    )
    for name, state in rows:
        online = "online" if has_session(f"{prefix}-{name}") else "offline"
        print(f"  {name:<8s}  {state:<10s}  {online}")
