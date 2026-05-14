#!/usr/bin/env python3
"""Export compact terminal-supervisor state for the CNB Live Activity."""

from __future__ import annotations

import json
import os
import socket
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

CNB_HOME = Path.home() / ".cnb"
PROJECTS_FILE = CNB_HOME / "projects.json"
LIVE_STATE_FILE = CNB_HOME / "live_state.json"


def _locale() -> str:
    return os.environ.get("CNB_LIVE_STATE_LOCALE", "zh-Hans").lower()


def _english() -> bool:
    return _locale().startswith("en")


def _read_projects() -> list[dict]:
    try:
        data = json.loads(PROJECTS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    projects = data.get("projects", [])
    return projects if isinstance(projects, list) else []


def _board_path(project_path: Path) -> Path | None:
    for candidate in (project_path / ".cnb" / "board.db", project_path / ".claudes" / "board.db"):
        if candidate.exists():
            return candidate
    return None


def _count(conn: sqlite3.Connection, table: str, where: str = "") -> int:
    try:
        suffix = f" WHERE {where}" if where else ""
        row = conn.execute(f"SELECT COUNT(*) FROM {table}{suffix}").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.Error:
        return 0


def _tables(conn: sqlite3.Connection) -> set[str]:
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    except sqlite3.Error:
        return set()
    return {str(row[0]) for row in rows}


def _inspect_project(entry: dict) -> dict | None:
    raw_path = entry.get("path", "")
    if not isinstance(raw_path, str) or not raw_path:
        return None

    project_path = Path(raw_path).expanduser()
    if not project_path.exists():
        return None

    board = _board_path(project_path)
    if not board:
        return None

    try:
        conn = sqlite3.connect(f"file:{board}?mode=ro", uri=True)
    except sqlite3.Error:
        return None

    try:
        tables = _tables(conn)
        pending = (
            _count(conn, "pending_actions", "status IN ('pending', 'reminded')") if "pending_actions" in tables else 0
        )
        active_tasks = _count(conn, "tasks", "status='active'") if "tasks" in tables else 0
        queued_tasks = _count(conn, "tasks", "status='pending'") if "tasks" in tables else 0
        unread = _count(conn, "inbox", "read=0") if "inbox" in tables else 0
        sessions = _count(conn, "sessions", "name NOT IN ('all', 'dispatcher')") if "sessions" in tables else 0
    finally:
        conn.close()

    return {
        "name": entry.get("name") or project_path.name,
        "path": str(project_path),
        "pending": pending,
        "active_tasks": active_tasks,
        "queued_tasks": queued_tasks,
        "unread": unread,
        "sessions": sessions,
    }


def _status(projects: list[dict]) -> str:
    if any(project["pending"] > 0 for project in projects):
        return "attention"
    if any(project["active_tasks"] > 0 or project["queued_tasks"] > 0 for project in projects):
        return "working"
    return "quiet"


def _count_summary(pending: int, tasks: int) -> str:
    parts: list[str] = []
    if pending > 0:
        parts.append(f"{pending} pending" if _english() else f"{pending} 个待处理")
    if tasks > 0:
        parts.append(f"{tasks} tasks" if _english() else f"{tasks} 个任务")
    if parts:
        return ", ".join(parts) if _english() else "，".join(parts)
    return "No active project needs attention" if _english() else "没有需要处理的活跃项目"


def build_state() -> dict:
    projects = [p for p in (_inspect_project(entry) for entry in _read_projects()) if p]

    active_projects = [p for p in projects if p["pending"] or p["active_tasks"] or p["queued_tasks"]]
    top = max(
        active_projects,
        key=lambda p: (p["pending"] * 100) + p["active_tasks"] + p["queued_tasks"],
        default=None,
    )

    pending = sum(p["pending"] for p in projects)
    active_tasks = sum(p["active_tasks"] for p in projects)
    queued_tasks = sum(p["queued_tasks"] for p in projects)
    unread = sum(p["unread"] for p in projects)
    status = _status(projects)
    task_count = active_tasks + queued_tasks

    if top:
        if _english():
            title = f"{top['name']} needs attention" if status == "attention" else f"{top['name']} active"
        else:
            title = f"{top['name']} 需要处理" if status == "attention" else f"{top['name']} 运行中"
        detail = _count_summary(pending, task_count)
    else:
        if _english():
            title = "CNB quiet"
        else:
            title = "CNB 空闲"
        detail = _count_summary(pending, task_count)

    return {
        "supervisorName": os.environ.get("CNB_SUPERVISOR", "terminal-supervisor"),
        "machineName": socket.gethostname(),
        "title": title,
        "detail": detail,
        "status": status,
        "activeProjects": len(active_projects),
        "pendingActions": pending,
        "activeTasks": task_count,
        "unreadMessages": unread,
        "updatedAt": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def main() -> None:
    CNB_HOME.mkdir(parents=True, exist_ok=True)
    state = build_state()
    LIVE_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    print(f"OK wrote {LIVE_STATE_FILE}")
    print(f"{state['title']}: {state['detail']}")


if __name__ == "__main__":
    main()
