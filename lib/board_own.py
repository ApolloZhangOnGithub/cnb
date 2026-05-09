"""board_own — ownership registry, task verification, auto-PR, and issue scan."""

import json
import subprocess
from pathlib import Path

from lib.board_db import BoardDB
from lib.common import validate_identity


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
    elif subcmd == "map":
        _own_map(db)
    else:
        print("Usage: board --as <name> own {claim|list|disown|map}")
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


def find_owner(db: BoardDB, file_path: str) -> str | None:
    """Find the owner of a file path. Longest prefix match wins."""
    rows = db.query("SELECT session, path_pattern FROM ownership ORDER BY LENGTH(path_pattern) DESC")
    for session, pattern in rows:
        if file_path.startswith(pattern) or file_path == pattern:
            return str(session)
    return None


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
                already = db.scalar(
                    "SELECT COUNT(*) FROM messages WHERE body LIKE ? AND recipient=?",
                    (f"%[ISSUE #{number}]%", session),
                )
                if not already:
                    db.post_message(
                        "system",
                        session,
                        f"[ISSUE #{number}] {title} — 可能与你负责的 {pattern} 相关",
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
