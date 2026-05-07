"""board_admin — suspend / resume / kudos / kudos-list."""

import subprocess
import time

from lib.board_db import BoardDB, ts


def cmd_suspend(db: BoardDB, identity: str, args: list[str]) -> None:
    assert db.env is not None
    name = identity.lower()
    if not args:
        print("Usage: ./board --as <name> suspend <session>")
        raise SystemExit(1)
    target = args[0].lower()

    session_exists = db.scalar("SELECT COUNT(*) FROM sessions WHERE name=?", (target,))
    if not session_exists:
        print(f"ERROR: 会话 '{target}' 不存在")
        raise SystemExit(1)

    already = db.scalar("SELECT COUNT(*) FROM suspended WHERE name=?", (target,))
    if already:
        print(f"{target} 已在停工名单中")
        return

    db.execute("INSERT INTO suspended(name, suspended_by) VALUES (?, ?)", (target, name))

    sf = db.env.suspended_file
    lines = sf.read_text().splitlines() if sf.exists() else []
    if target not in lines:
        lines.append(target)
        sf.write_text("\n".join(lines) + "\n")

    print(f"{target}: 已停工")

    prefix = db.env.prefix
    sess = f"{prefix}-{target}"
    try:
        r = subprocess.run(["tmux", "has-session", "-t", sess], capture_output=True, timeout=5)
        if r.returncode == 0:
            subprocess.run(
                ["tmux", "send-keys", "-t", sess, "/exit", "Enter"],
                capture_output=True,
                timeout=5,
            )
            time.sleep(2)
            subprocess.run(["tmux", "kill-session", "-t", sess], capture_output=True, timeout=5)
            print(f"{target}: tmux session 已关闭")
    except (subprocess.TimeoutExpired, OSError):
        pass

    now = ts()
    db.execute(
        "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, 'SYSTEM', 'all', ?)",
        (now, f"SUSPEND {target} by {name}"),
    )


def cmd_resume(db: BoardDB, identity: str, args: list[str]) -> None:
    assert db.env is not None
    name = identity.lower()
    if not args:
        print("Usage: ./board --as <name> resume <session>")
        raise SystemExit(1)
    target = args[0].lower()

    exists = db.scalar("SELECT COUNT(*) FROM suspended WHERE name=?", (target,))
    if not exists:
        print(f"ERROR: {target} 不在停工名单中")
        raise SystemExit(1)

    db.execute("DELETE FROM suspended WHERE name=?", (target,))

    sf = db.env.suspended_file
    if sf.exists():
        lines = [l for l in sf.read_text().splitlines() if l != target]
        sf.write_text("\n".join(lines) + "\n" if lines else "")

    print(f"{target}: 已恢复")
    now = ts()
    db.execute(
        "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, 'SYSTEM', 'all', ?)",
        (now, f"RESUME {target} by {name}"),
    )


def cmd_kudos(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    if len(args) < 2:
        print("Usage: ./board --as <name> kudos <target> <reason> [--evidence <commit/link>]")
        raise SystemExit(1)

    evidence = ""
    clean_args = []
    i = 0
    while i < len(args):
        if args[i] in ("--evidence", "-e") and i + 1 < len(args):
            evidence = args[i + 1]
            i += 2
            continue
        clean_args.append(args[i])
        i += 1

    target = clean_args[0].lower()
    reason = " ".join(clean_args[1:])

    if name == target:
        print("ERROR: cannot kudos yourself")
        raise SystemExit(1)

    db.execute(
        "INSERT INTO kudos(sender, target, reason, evidence) VALUES (?, ?, ?, ?)",
        (name, target, reason, evidence or None),
    )
    now = ts()
    db.execute(
        "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, 'all', ?)",
        (now, name, f"[KUDOS] → {target}: {reason}"),
    )
    print(f"OK kudos sent to {target} (visible to all)")


def cmd_kudos_list(db: BoardDB) -> None:
    print("=== Kudos Board ===\n")
    print("Leaderboard:")
    for who, count in db.query("SELECT target, COUNT(*) as c FROM kudos GROUP BY target ORDER BY c DESC"):
        print(f"  {who}: {count} kudos")
    print("\nRecent:")
    rows = db.query(
        "SELECT '[' || ts || '] ' || sender || ' → ' || target || ': ' || reason FROM kudos ORDER BY id DESC LIMIT 10"
    )
    for (line,) in reversed(rows):
        print(f"  {line}")
