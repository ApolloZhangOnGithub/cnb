"""Global project registry for cross-project discovery and shared credentials.

Registry lives at ~/.cnb/ and tracks:
- projects.json: all cnb projects on this machine
- shared/credentials.json: credential status (valid/expired/unknown)
"""

import json
import os
import sqlite3
import subprocess
import sys
import tomllib
from argparse import ArgumentParser
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CNB_HOME = Path.home() / ".cnb"
PROJECTS_FILE = CNB_HOME / "projects.json"
CREDENTIALS_FILE = CNB_HOME / "shared" / "credentials.json"

VALID_CREDENTIAL_STATUSES = frozenset({"valid", "expired", "unknown"})
PROJECT_MARKER_DIRS = (".cnb", ".claudes")
SCAN_SKIP_DIRS = frozenset(
    {
        ".cache",
        ".codex",
        ".git",
        ".hg",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".venv",
        "__pycache__",
        "Library",
        "Applications",
        "Desktop Pictures",
        "DerivedData",
        "Movies",
        "Music",
        "Pictures",
        "Trash",
        "build",
        "dist",
        "node_modules",
        "target",
        "venv",
    }
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ensure_dirs() -> None:
    """Create ~/.cnb/ and ~/.cnb/shared/ if they don't exist."""
    CNB_HOME.mkdir(parents=True, exist_ok=True)
    (CNB_HOME / "shared").mkdir(exist_ok=True)


def _now_iso() -> str:
    """Current UTC timestamp in ISO 8601 format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_projects(path: Path | None = None) -> dict:
    """Read projects.json, returning {'projects': [...]}."""
    p = path or PROJECTS_FILE
    if not p.exists():
        return {"projects": []}
    try:
        data = json.loads(p.read_text())
        if not isinstance(data, dict) or "projects" not in data:
            return {"projects": []}
        return data
    except (json.JSONDecodeError, OSError):
        return {"projects": []}


def _write_projects(data: dict, path: Path | None = None) -> None:
    """Write projects.json atomically."""
    p = path or PROJECTS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _looks_like_transient_project(path: Path) -> bool:
    """Return True for temporary test projects that should not enter ~/.cnb."""
    if any(part.startswith("pytest-of-") or part.startswith("pytest-") for part in path.parts):
        return True
    return any(part.startswith("cnb-codex-smoke.") for part in path.parts)


def _read_credentials(path: Path | None = None) -> dict:
    """Read credentials.json, returning {name: {status, updated, updated_by}}."""
    p = path or CREDENTIALS_FILE
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def _write_credentials(data: dict, path: Path | None = None) -> None:
    """Write credentials.json."""
    p = path or CREDENTIALS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _default_scan_roots() -> list[Path]:
    """Return bounded local roots for machine-level project discovery."""
    raw = os.environ.get("CNB_SCAN_ROOTS", "")
    if raw.strip():
        return [Path(item).expanduser() for item in raw.split(os.pathsep) if item.strip()]
    home = Path.home()
    return [home / "Desktop" / "Toolbase_Skills", home / "Desktop"]


def _is_under(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_same_or_under(child: Path, parent: Path) -> bool:
    return child == parent or _is_under(child, parent)


def _normalize_roots(roots: list[str | Path] | None = None) -> list[Path]:
    candidates = [Path(r).expanduser() for r in (roots or _default_scan_roots())]
    existing: list[Path] = []
    for root in candidates:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if resolved.is_dir() and resolved not in existing:
            existing.append(resolved)

    # Prefer narrower roots first, then skip descendants already covered by an earlier root.
    existing.sort(key=lambda p: len(p.parts), reverse=True)
    normalized: list[Path] = []
    for root in existing:
        if any(_is_under(root, kept) for kept in normalized):
            continue
        normalized.append(root)
    return normalized


def _iter_scan_dirs(root: Path, max_depth: int, *, excluded_roots: list[Path] | None = None) -> list[Path]:
    """Depth-limited directory walk with heavy dependency/cache folders pruned."""
    excluded = excluded_roots or []
    found: list[Path] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        found.append(current)
        if depth >= max_depth:
            continue
        try:
            children = list(current.iterdir())
        except OSError:
            continue
        for child in reversed(children):
            name = child.name
            if name in PROJECT_MARKER_DIRS or name in SCAN_SKIP_DIRS:
                continue
            if name.startswith(".") and name not in {".config"}:
                continue
            try:
                if child.is_dir() and not child.is_symlink():
                    resolved_child = child.resolve()
                    if any(_is_same_or_under(resolved_child, excluded_root) for excluded_root in excluded):
                        continue
                    stack.append((child, depth + 1))
            except OSError:
                continue
    return found


def _read_project_config(config_dir: Path) -> dict:
    path = config_dir / "config.toml"
    if not path.exists():
        return {}
    try:
        data = tomllib.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _count(conn: sqlite3.Connection, table: str, where: str = "") -> int:
    try:
        suffix = f" WHERE {where}" if where else ""
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}{suffix}").fetchone()[0])
    except sqlite3.Error:
        return 0


def _empty_board_summary() -> dict:
    return {
        "sessions": 0,
        "messages": 0,
        "unread": 0,
        "tasks_total": 0,
        "tasks_active": 0,
        "tasks_pending": 0,
        "tasks_done": 0,
        "latest_message": "",
        "status_summary": [],
    }


def _inspect_board(board_db: Path) -> dict:
    summary = _empty_board_summary()
    try:
        conn = sqlite3.connect(str(board_db))
        conn.row_factory = sqlite3.Row
    except sqlite3.Error:
        return summary
    try:
        session_cols = _table_columns(conn, "sessions")
        if session_cols:
            summary["sessions"] = _count(conn, "sessions", "name NOT IN ('all', 'dispatcher')")
            if {"name", "status"} <= session_cols:
                rows = conn.execute(
                    "SELECT name, status FROM sessions WHERE name NOT IN ('all', 'dispatcher') ORDER BY name"
                ).fetchall()
                active = [
                    f"{row['name']}:{str(row['status'] or '')[:60]}"
                    for row in rows
                    if row["status"] and not str(row["status"]).startswith("shutdown")
                ]
                summary["status_summary"] = active[:6]

        message_cols = _table_columns(conn, "messages")
        if message_cols:
            summary["messages"] = _count(conn, "messages")
            if {"ts", "sender", "recipient", "body"} <= message_cols:
                row = conn.execute(
                    "SELECT ts, sender, recipient, body FROM messages ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if row:
                    summary["latest_message"] = f"{row['ts']} {row['sender']}->{row['recipient']}: {row['body'][:80]}"
            elif {"created_at", "from_session", "to_session", "content"} <= message_cols:
                row = conn.execute(
                    "SELECT created_at, from_session, to_session, content FROM messages ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if row:
                    summary["latest_message"] = (
                        f"{row['created_at']} {row['from_session']}->{row['to_session']}: {row['content'][:80]}"
                    )

        inbox_cols = _table_columns(conn, "inbox")
        if inbox_cols:
            summary["unread"] = _count(conn, "inbox", "read=0") if "read" in inbox_cols else _count(conn, "inbox")

        task_cols = _table_columns(conn, "tasks")
        if task_cols:
            summary["tasks_total"] = _count(conn, "tasks")
            summary["tasks_active"] = _count(conn, "tasks", "status='active'")
            summary["tasks_pending"] = _count(conn, "tasks", "status='pending'")
            summary["tasks_done"] = _count(conn, "tasks", "status='done'")
    finally:
        conn.close()
    return summary


def _tmux_sessions() -> set[str]:
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _git_summary(project_root: Path) -> dict:
    summary = {"root": "", "branch": "", "head": "", "dirty": 0}
    try:
        root = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return summary
    if root.returncode != 0:
        return summary

    git_root = root.stdout.strip()
    summary["root"] = git_root
    for key, cmd in (
        ("branch", ["git", "-C", git_root, "branch", "--show-current"]),
        ("head", ["git", "-C", git_root, "log", "--oneline", "-1"]),
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            summary[key] = result.stdout.strip()

    try:
        status = subprocess.run(["git", "-C", git_root, "status", "--short"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return summary
    if status.returncode == 0:
        summary["dirty"] = len([line for line in status.stdout.splitlines() if line.strip()])
    return summary


def discover_projects(
    *,
    roots: list[str | Path] | None = None,
    max_depth: int = 5,
    include_legacy: bool = True,
    mode: str = "board",
) -> list[dict]:
    """Discover local cnb projects by scanning bounded roots.

    mode="board" keeps the project definition strict: marker directory plus board.db.
    mode="marker" audits marker directories even when board.db is missing.
    """
    if mode not in {"board", "marker"}:
        raise ValueError("mode must be 'board' or 'marker'")
    discovered: list[dict] = []
    seen_roots: set[str] = set()
    tmux = _tmux_sessions()
    scan_roots = _normalize_roots(roots)

    for index, scan_root in enumerate(scan_roots):
        for directory in _iter_scan_dirs(scan_root, max_depth, excluded_roots=scan_roots[:index]):
            candidates = [directory / ".cnb"]
            if include_legacy:
                candidates.append(directory / ".claudes")

            # Prefer .cnb over legacy .claudes for the same project root.
            for config_dir in candidates:
                board_db = config_dir / "board.db"
                has_board = board_db.exists()
                if mode == "board" and not has_board:
                    continue
                if not config_dir.exists():
                    continue
                project_root = directory.resolve()
                key = str(project_root)
                if key in seen_roots:
                    break
                seen_roots.add(key)

                config = _read_project_config(config_dir)
                prefix = str(config.get("prefix") or "")
                configured_sessions = [str(s) for s in config.get("sessions", []) if isinstance(s, str)]
                running_sessions = sorted(s for s in tmux if prefix and s.startswith(f"{prefix}-"))
                summary = _inspect_board(board_db) if has_board else _empty_board_summary()
                discovered.append(
                    {
                        "name": project_root.name,
                        "path": str(project_root),
                        "config_dir": config_dir.name,
                        "board_db": str(board_db) if has_board else "",
                        "has_board": has_board,
                        "discovery": "board" if has_board else "marker",
                        "prefix": prefix,
                        "configured_sessions": configured_sessions,
                        "running_sessions": running_sessions,
                        "summary": summary,
                        "git": _git_summary(project_root),
                    }
                )
                break

    discovered.sort(key=lambda item: item["path"])
    return discovered


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def register_project(project_path: str | Path, name: str, *, registry_path: Path | None = None) -> bool:
    """Add or update a project in the global registry.

    If the project path already exists, updates name and last_active.
    """
    path = Path(project_path).resolve()
    if registry_path is None and _looks_like_transient_project(path):
        return False

    _ensure_dirs()
    path_str = str(path)
    data = _read_projects(registry_path)

    # Update existing or append new
    for entry in data["projects"]:
        if entry.get("path") == path_str:
            entry["name"] = name
            entry["last_active"] = _now_iso()
            _write_projects(data, registry_path)
            return True

    data["projects"].append(
        {
            "path": path_str,
            "name": name,
            "last_active": _now_iso(),
        }
    )
    _write_projects(data, registry_path)
    return True


def list_projects(*, registry_path: Path | None = None) -> list[dict[str, str]]:
    """Return the list of registered project dicts."""
    projects: list[dict[str, str]] = _read_projects(registry_path).get("projects", [])
    return projects


def remove_project(project_path: str | Path, *, registry_path: Path | None = None) -> bool:
    """Remove a project by path. Returns True if found and removed."""
    path_str = str(Path(project_path).resolve())
    data = _read_projects(registry_path)
    original_len = len(data["projects"])
    data["projects"] = [e for e in data["projects"] if e.get("path") != path_str]
    if len(data["projects"]) < original_len:
        _write_projects(data, registry_path)
        return True
    return False


def update_credential(
    name: str,
    status: str,
    *,
    updated_by: str | Path | None = None,
    credentials_path: Path | None = None,
) -> None:
    """Set credential status (valid/expired/unknown).

    Args:
        name: credential name (e.g. 'npm', 'lark')
        status: one of 'valid', 'expired', 'unknown'
        updated_by: project path that updated the credential
        credentials_path: override path for testing
    """
    if status not in VALID_CREDENTIAL_STATUSES:
        print(f"ERROR: 无效的凭证状态 '{status}'，有效值: {', '.join(sorted(VALID_CREDENTIAL_STATUSES))}")
        raise SystemExit(1)

    _ensure_dirs()
    data = _read_credentials(credentials_path)
    data[name] = {
        "status": status,
        "updated": _now_iso(),
        "updated_by": str(updated_by) if updated_by else "",
    }
    _write_credentials(data, credentials_path)


def check_credential(name: str, *, credentials_path: Path | None = None) -> dict | None:
    """Check credential status. Returns status dict or None if not tracked."""
    data = _read_credentials(credentials_path)
    return data.get(name)


def cleanup(*, registry_path: Path | None = None) -> list[str]:
    """Remove projects whose paths no longer exist on disk.

    Returns list of removed project paths.
    """
    data = _read_projects(registry_path)
    removed = []
    surviving = []
    for entry in data["projects"]:
        p = Path(entry.get("path", ""))
        if p.exists():
            surviving.append(entry)
        else:
            removed.append(entry.get("path", ""))
    if removed:
        data["projects"] = surviving
        _write_projects(data, registry_path)
    return removed


def register_discovered_projects(projects: list[dict], *, registry_path: Path | None = None) -> int:
    """Register board-backed discovered projects in the global registry. Returns count."""
    count = 0
    for project in projects:
        if not project.get("has_board", True):
            continue
        if register_project(project["path"], project["name"], registry_path=registry_path):
            count += 1
    return count


def _format_project_line(project: dict) -> str:
    summary = project.get("summary", {})
    running = len(project.get("running_sessions", []))
    sessions = summary.get("sessions", 0)
    tasks_active = summary.get("tasks_active", 0)
    tasks_pending = summary.get("tasks_pending", 0)
    unread = summary.get("unread", 0)
    marker = project.get("config_dir", "")
    state = "" if project.get("has_board", True) else " marker-only"
    git = project.get("git", {})
    git_bits = ""
    if git.get("root"):
        branch = git.get("branch") or "(detached)"
        dirty = git.get("dirty", 0)
        git_bits = f" git={branch} dirty={dirty}"
    return (
        f"  {project['name']:32s} {marker:8s} "
        f"sessions={sessions:<2} running={running:<2} "
        f"tasks={tasks_active} active/{tasks_pending} pending unread={unread:<3} "
        f"{project['path']}{state}{git_bits}"
    )


def cmd_projects_scan(argv: list[str] | None = None) -> None:
    """CLI for bounded local cnb project discovery."""
    parser = ArgumentParser(prog="cnb projects scan")
    parser.add_argument("--root", action="append", default=[], help="root directory to scan; can be repeated")
    parser.add_argument("--max-depth", type=int, default=5, help="maximum directory depth below each root")
    parser.add_argument(
        "--mode",
        choices=("board", "marker"),
        default="board",
        help="board=only real board-backed projects; marker=audit .cnb/.claudes markers too",
    )
    parser.add_argument("--no-legacy", action="store_true", help="ignore legacy .claudes/ projects")
    parser.add_argument("--register", action="store_true", help="upsert discovered projects into ~/.cnb/projects.json")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)

    roots: list[str | Path] | None = [Path(root).expanduser() for root in args.root] if args.root else None
    projects = discover_projects(
        roots=roots, max_depth=args.max_depth, include_legacy=not args.no_legacy, mode=args.mode
    )
    registered = 0
    if args.register:
        registered = register_discovered_projects(projects)

    if args.json:
        print(json.dumps({"projects": projects}, indent=2, ensure_ascii=False))
        return

    scan_roots = _normalize_roots(roots)
    print("扫描根目录:")
    for root in scan_roots:
        print(f"  {root}")
    print(f"最大深度: {args.max_depth}")
    print(f"扫描模式: {args.mode}")
    print()
    if not projects:
        print("没有发现 cnb 项目")
        return

    noun = "cnb 项目" if args.mode == "board" else "cnb marker"
    print(f"发现 {len(projects)} 个 {noun}:")
    for project in projects:
        print(_format_project_line(project))
        latest = project.get("summary", {}).get("latest_message")
        statuses = project.get("summary", {}).get("status_summary") or []
        if statuses:
            print(f"    active status: {'; '.join(statuses)}")
        if latest:
            print(f"    latest: {latest}")
    if args.register:
        print(f"\nOK 已注册/更新 {registered} 个 board-backed 项目")


if __name__ == "__main__":
    cmd_projects_scan(sys.argv[1:])
