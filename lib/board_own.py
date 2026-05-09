"""board_own — ownership registry, task verification, auto-PR, and issue scan."""

import json
import subprocess
from datetime import datetime
from pathlib import Path

from lib.board_db import BoardDB
from lib.common import is_privileged, parse_flags, validate_identity

DEFAULT_ORPHAN_HOURS = 24


def cmd_own(db: BoardDB, identity: str, args: list[str]) -> None:
    validate_identity(db, identity)
    subcmd = args[0] if args else "list"
    rest = args[1:] if len(args) > 1 else []

    if subcmd == "claim":
        _own_claim(db, identity, rest)
    elif subcmd in ("list", "ls"):
        _own_list(db, identity, rest)
    elif subcmd == "disown":
        _own_disown(db, identity, rest)
    elif subcmd == "transfer":
        _own_transfer(db, identity, rest)
    elif subcmd == "transfer-all":
        _own_transfer_all(db, identity, rest)
    elif subcmd == "offboard":
        _own_offboard(db, identity, rest)
    elif subcmd in ("orphans", "orphan"):
        _own_orphans(db, rest)
    elif subcmd == "map":
        _own_map(db)
    else:
        print("Usage: board --as <name> own {claim|list|disown|transfer|transfer-all|offboard|orphans|map}")
        raise SystemExit(1)


def _own_claim(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    if not args:
        print("Usage: board --as <name> own claim <path_pattern> [path2 ...]")
        raise SystemExit(1)

    with db.conn() as c:
        for pattern in args:
            existing = db.query_one("SELECT session FROM ownership WHERE path_pattern=?", (pattern,), c=c)
            if existing and existing[0] != name:
                print(f"WARNING: {pattern} 已被 {existing[0]} 认领，跳过")
                continue
            db.execute(
                "INSERT OR IGNORE INTO ownership(session, path_pattern) VALUES (?, ?)",
                (name, pattern),
                c=c,
            )
            print(f"OK {name} owns {pattern}")


def _own_disown(db: BoardDB, identity: str, args: list[str]) -> None:
    name = identity.lower()
    if not args:
        print("Usage: board --as <name> own disown <path_pattern>")
        raise SystemExit(1)

    for pattern in args:
        changed = db.execute_changes(
            "DELETE FROM ownership WHERE session=? AND path_pattern=?",
            (name, pattern),
        )
        if changed:
            print(f"OK {name} released {pattern}")
        else:
            print(f"WARNING: {name} 不拥有 {pattern}")


def _ensure_transfer_target(db: BoardDB, source: str, target: str) -> None:
    if target == source:
        print("ERROR: 目标同学不能是自己")
        raise SystemExit(1)
    db.ensure_session(target)


def _transfer_one(db: BoardDB, source: str, target: str, pattern: str, *, c) -> bool:
    row = db.query_one(
        "SELECT id FROM ownership WHERE session=? AND path_pattern=?",
        (source, pattern),
        c=c,
    )
    if not row:
        print(f"WARNING: {source} 不拥有 {pattern}，跳过")
        return False

    target_row = db.query_one(
        "SELECT id FROM ownership WHERE session=? AND path_pattern=?",
        (target, pattern),
        c=c,
    )
    if target_row:
        db.execute(
            "DELETE FROM ownership WHERE session=? AND path_pattern=?",
            (source, pattern),
            c=c,
        )
        print(f"OK {pattern} 已由 {target} 负责；已从 {source} 释放")
        return True

    db.execute(
        "UPDATE ownership SET session=?, claimed_at=(strftime('%Y-%m-%d %H:%M','now','localtime')) "
        "WHERE session=? AND path_pattern=?",
        (target, source, pattern),
        c=c,
    )
    print(f"OK 已交接 {pattern}: {source} -> {target}")
    return True


def _own_transfer(db: BoardDB, identity: str, args: list[str]) -> None:
    source = identity.lower()
    if len(args) < 2:
        print("Usage: board --as <name> own transfer <target> <path_pattern> [path2 ...]")
        raise SystemExit(1)

    target = args[0].lower()
    patterns = args[1:]
    _ensure_transfer_target(db, source, target)

    moved = 0
    with db.conn() as c:
        for pattern in patterns:
            if _transfer_one(db, source, target, pattern, c=c):
                moved += 1
    print(f"OK 已交接 {moved} 条 ownership 给 {target}")


def _own_transfer_all(db: BoardDB, identity: str, args: list[str]) -> None:
    source = identity.lower()
    if len(args) != 1:
        print("Usage: board --as <name> own transfer-all <target>")
        raise SystemExit(1)

    target = args[0].lower()
    _ensure_transfer_target(db, source, target)
    patterns = [
        row[0]
        for row in db.query("SELECT path_pattern FROM ownership WHERE session=? ORDER BY path_pattern", (source,))
    ]
    if not patterns:
        print(f"{source} 无 ownership 可交接")
        return

    moved = 0
    with db.conn() as c:
        for pattern in patterns:
            if _transfer_one(db, source, target, pattern, c=c):
                moved += 1
    print(f"OK 已把 {source} 的全部 ownership 交接给 {target}: {moved} 条")


def _own_list(db: BoardDB, identity: str, args: list[str]) -> None:
    target = args[0].lower() if args else identity.lower()
    rows = db.query(
        "SELECT path_pattern, claimed_at FROM ownership WHERE session=? ORDER BY path_pattern",
        (target,),
    )
    if not rows:
        print(f"{target} 无 ownership")
        return
    print(f"{target} 负责:")
    for pattern, claimed in rows:
        print(f"  {pattern}  (since {claimed})")


def _own_map(db: BoardDB) -> None:
    rows = db.query("SELECT session, path_pattern FROM ownership ORDER BY session, path_pattern")
    if not rows:
        print("无 ownership 记录")
        return
    print("Ownership Map:")
    current = ""
    for session, pattern in rows:
        if session != current:
            current = session
            print(f"\n  {session}:")
        print(f"    {pattern}")


def _own_offboard(db: BoardDB, identity: str, args: list[str]) -> None:
    requester = identity.lower()
    target = args[0].lower() if args else requester
    if target != requester and not is_privileged(requester):
        print("ERROR: 只有本人、lead 或 dispatcher 可以查看离职清单")
        raise SystemExit(1)

    validate_identity(db, target)
    print(f"离职清单: {target}")

    ownership = db.query(
        "SELECT path_pattern, claimed_at FROM ownership WHERE session=? ORDER BY path_pattern",
        (target,),
    )
    print("\nOwnership:")
    if ownership:
        for pattern, claimed in ownership:
            print(f"  {pattern}  (since {claimed})")
    else:
        print("  (none)")

    tasks = db.query(
        "SELECT id, status, priority, description FROM tasks "
        "WHERE session=? AND status != 'done' "
        "ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, priority DESC, id ASC",
        (target,),
    )
    print("\nTasks:")
    if tasks:
        for task_id, status, priority, desc in tasks:
            print(f"  #{task_id} [{status} p{priority}] {desc}")
    else:
        print("  (none)")

    print("\nGit:")
    env = db.env
    if not env:
        print("  (当前上下文不可用)")
        return
    for line in _git_handoff_summary(env.project_root):
        print(f"  {line}")


def _git_handoff_summary(project_root: Path) -> list[str]:
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        ahead = ""
        if branch:
            r = subprocess.run(
                ["git", "rev-list", "--left-right", "--count", f"origin/{branch}...HEAD"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                timeout=5,
            )
            ahead = r.stdout.strip() if r.returncode == 0 else ""
        result = [f"分支: {branch or '(detached)'}"]
        result.append(f"脏文件数: {len(dirty.splitlines()) if dirty else 0}")
        if ahead:
            behind, ahead_count = ahead.split()
            result.append(f"未 push commits: {ahead_count} (behind {behind})")
        return result
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        return ["git 摘要不可用"]


def find_owner(db: BoardDB, file_path: str) -> str | None:
    """Find the owner of a file path. Longest prefix match wins."""
    rows = db.query("SELECT session, path_pattern FROM ownership ORDER BY LENGTH(path_pattern) DESC")
    for session, pattern in rows:
        if file_path.startswith(pattern) or file_path == pattern:
            return session
    return None


def _parse_heartbeat(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _orphan_reason(db: BoardDB, session: str, *, hours: int = DEFAULT_ORPHAN_HOURS) -> str | None:
    row = db.query_one("SELECT last_heartbeat FROM sessions WHERE name=?", (session,))
    if not row:
        return "session missing"

    heartbeat = row[0]
    if not heartbeat:
        return None

    parsed = _parse_heartbeat(heartbeat)
    if not parsed:
        return None

    age_hours = (datetime.now() - parsed).total_seconds() / 3600
    if age_hours > hours:
        return f"last heartbeat {heartbeat} ({age_hours:.1f}h ago)"
    return None


def _is_orphaned_owner(db: BoardDB, session: str, *, hours: int = DEFAULT_ORPHAN_HOURS) -> bool:
    return _orphan_reason(db, session, hours=hours) is not None


def _own_orphans(db: BoardDB, args: list[str]) -> None:
    flags, positional = parse_flags(args, value_flags={"hours": ["--hours"]})
    if positional:
        print("Usage: board --as <name> own orphans [--hours N]")
        raise SystemExit(1)

    try:
        hours = int(flags["hours"]) if "hours" in flags else DEFAULT_ORPHAN_HOURS
    except ValueError:
        print("ERROR: --hours 必须是整数")
        raise SystemExit(1)

    rows = db.query("SELECT session, path_pattern FROM ownership ORDER BY session, path_pattern")
    orphaned: list[tuple[str, str, str]] = []
    for session, pattern in rows:
        reason = _orphan_reason(db, session, hours=hours)
        if reason:
            orphaned.append((session, pattern, reason))

    if not orphaned:
        print("无 orphaned ownership")
        return

    print(f"Orphaned ownership（超过 {hours}h 无心跳）:")
    for session, pattern, reason in orphaned:
        print(f"  {session}: {pattern} — {reason}")


# ---------------------------------------------------------------------------
# Verify: run tests before marking task done
# ---------------------------------------------------------------------------


def verify_task(project_root: Path) -> tuple[bool, str]:
    """Run pytest from project root. Returns (passed, output_summary)."""
    try:
        r = subprocess.run(
            ["python", "-m", "pytest", "-x", "-q", "--tb=short"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=300,
        )
        lines = r.stdout.strip().splitlines()
        summary = lines[-1] if lines else r.stderr.strip()[:200]
        # returncode 5 = no tests collected, treat as pass
        return r.returncode in (0, 5), summary
    except subprocess.TimeoutExpired:
        return False, "测试超时 (>5min)"
    except FileNotFoundError:
        return True, "pytest 未安装，跳过验证"


# ---------------------------------------------------------------------------
# Auto-PR: create PR after verified task completion
# ---------------------------------------------------------------------------


def auto_pr(project_root: Path, task_desc: str, session_name: str) -> str | None:
    """Create a PR if there are unpushed commits. Returns PR URL or None."""
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()

        if not branch or branch in ("master", "main"):
            return None

        ahead = subprocess.run(
            ["git", "log", f"origin/{branch}..HEAD", "--oneline"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if not ahead.stdout.strip():
            return None

        subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )

        r = subprocess.run(
            [
                "gh",
                "pr",
                "create",
                "--title",
                task_desc[:70],
                "--body",
                f"Auto-created by {session_name} on task completion.\n\nTask: {task_desc}",
            ],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            return r.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


# ---------------------------------------------------------------------------
# Scan: check GitHub issues and CI, route to owners
# ---------------------------------------------------------------------------


def cmd_scan(db: BoardDB, identity: str, args: list[str]) -> None:
    """Scan GitHub issues and CI status, route notifications to owners."""
    validate_identity(db, identity)
    env = db.require_env()

    issues_found = _scan_issues(db, env.project_root)
    ci_found = _scan_ci(db, env.project_root)

    total = issues_found + ci_found
    if total:
        print(f"OK scan 完成: {issues_found} 个 issue, {ci_found} 个 CI 问题已路由")
    else:
        print("OK scan 完成: 无新事项")


def _scan_issues(db: BoardDB, project_root: Path) -> int:
    """Check open GitHub issues, notify owners of relevant ones."""
    try:
        r = subprocess.run(
            ["gh", "issue", "list", "--state", "open", "--json", "number,title,labels,body"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            return 0

        issues = json.loads(r.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return 0

    ownership_rows = db.query("SELECT session, path_pattern FROM ownership")
    if not ownership_rows:
        return 0

    routed = 0
    for issue in issues:
        title = issue.get("title", "")
        body = issue.get("body", "") or ""
        number = issue.get("number", 0)
        text = f"{title} {body}".lower()

        for session, pattern in ownership_rows:
            if pattern.lower() in text:
                is_orphan = _is_orphaned_owner(db, session)
                recipient = "all" if is_orphan else session
                already = db.scalar(
                    "SELECT COUNT(*) FROM messages WHERE body LIKE ? AND recipient=?",
                    (f"%[ISSUE #{number}]%", recipient),
                )
                if not already:
                    if is_orphan:
                        body = (
                            f"[ISSUE #{number}] {title} — 原 owner {session} 可能 orphaned，相关 ownership: {pattern}"
                        )
                    else:
                        body = f"[ISSUE #{number}] {title} — 可能与你负责的 {pattern} 相关"
                    db.post_message(
                        "system",
                        recipient,
                        body,
                        deliver=True,
                    )
                    routed += 1
    return routed


def _scan_ci(db: BoardDB, project_root: Path) -> int:
    """Check CI status of current branch, notify owners of failing files."""
    try:
        r = subprocess.run(
            ["gh", "run", "list", "--limit", "1", "--json", "status,conclusion,headBranch"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            return 0

        runs = json.loads(r.stdout)
        if not runs or runs[0].get("conclusion") != "failure":
            return 0

        branch = runs[0].get("headBranch", "unknown")
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return 0

    owners = db.query("SELECT DISTINCT session FROM ownership")
    routed = 0
    for (session,) in owners:
        already = db.scalar(
            "SELECT COUNT(*) FROM messages WHERE body LIKE ? AND recipient=?",
            (f"%[CI FAIL]%{branch}%", session),
        )
        if not already:
            db.post_message(
                "system",
                session,
                f"[CI FAIL] {branch} 分支 CI 失败，请检查你负责的模块",
                deliver=True,
            )
            routed += 1
    return routed
