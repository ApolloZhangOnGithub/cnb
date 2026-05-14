"""shift_report — auto-generate per-agent shift reports and shift metadata.

Collects status, messages sent, tasks completed, bugs reported/fixed,
kudos received, and git commits for each session within a time window.
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from lib.board_db import BoardDB


def _git_commits_by_author(project_root: Path, since: str, author: str) -> list[str]:
    """Get commit onelines by a co-author or committer since a timestamp."""
    try:
        r = subprocess.run(
            ["git", "-C", str(project_root), "log", f"--since={since}", "--oneline", f"--author={author}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return []


def _git_commits_all(project_root: Path, since: str) -> list[str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(project_root), "log", f"--since={since}", "--oneline"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().splitlines()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return []


def generate_agent_report(
    board: BoardDB,
    session_name: str,
    since: datetime | None = None,
    project_root: Path | None = None,
) -> str:
    """Generate a shift report for a single agent."""
    if since is None:
        since = datetime.now()
    since_str = since.strftime("%Y-%m-%d %H:%M:%S")
    date_str = datetime.now().strftime("%Y-%m-%d")

    sections: list[str] = []

    status_row = board.query_one("SELECT status FROM sessions WHERE name=?", (session_name,))
    current_status = status_row[0] if status_row and status_row[0] else "(none)"
    sections.append(f"## 状态\n{current_status}")

    tasks_done = board.query(
        "SELECT description FROM tasks WHERE session=? AND done_at > ? AND status='done'",
        (session_name, since_str),
    )
    if tasks_done:
        lines = [f"- {r[0][:80]}" for r in tasks_done]
        sections.append("## 完成任务\n" + "\n".join(lines))

    tasks_active = board.query(
        "SELECT description FROM tasks WHERE session=? AND status IN ('active', 'pending')",
        (session_name,),
    )
    if tasks_active:
        lines = [f"- {r[0][:80]}" for r in tasks_active]
        sections.append("## 待办\n" + "\n".join(lines))

    bugs_reported = board.query(
        "SELECT id, severity, description FROM bugs WHERE reporter=? AND reported_at > ?",
        (session_name, since_str),
    )
    if bugs_reported:
        lines = [f"- {r[0]} [{r[1]}] {r[2][:60]}" for r in bugs_reported]
        sections.append("## 报告 Bug\n" + "\n".join(lines))

    bugs_fixed = board.query(
        "SELECT id, severity, description FROM bugs WHERE assignee=? AND fixed_at > ?",
        (session_name, since_str),
    )
    if bugs_fixed:
        lines = [f"- {r[0]} [{r[1]}] {r[2][:60]}" for r in bugs_fixed]
        sections.append("## 修复 Bug\n" + "\n".join(lines))

    msg_count = (
        board.scalar(
            "SELECT COUNT(*) FROM messages WHERE sender=? AND ts > ?",
            (session_name, since_str),
        )
        or 0
    )
    if msg_count:
        sections.append(f"## 消息\n发送 {msg_count} 条")

    kudos_received = board.query(
        "SELECT sender, reason FROM kudos WHERE target=? AND ts > ?",
        (session_name, since_str),
    )
    if kudos_received:
        lines = [f"- {r[0]}: {r[1][:60]}" for r in kudos_received]
        sections.append("## 获得 Kudos\n" + "\n".join(lines))

    if project_root:
        commits = _git_commits_by_author(project_root, since_str, session_name)
        if commits:
            lines = [f"- {c}" for c in commits[:20]]
            sections.append(f"## Git Commits ({len(commits)})\n" + "\n".join(lines))

    header = f"# 日报 — {session_name} — {date_str}"
    if not sections:
        return header + "\n\n(本轮无活动)"
    return header + "\n\n" + "\n\n".join(sections)


def generate_shift_meta(
    board: BoardDB,
    shift_number: int,
    started: datetime,
    ended: datetime | None = None,
    participants: list[str] | None = None,
    project_root: Path | None = None,
) -> str:
    """Generate _meta.md for a shift."""
    if ended is None:
        ended = datetime.now()
    since_str = started.strftime("%Y-%m-%d %H:%M:%S")
    end_str = ended.strftime("%Y-%m-%dT%H:%M")
    start_str = started.strftime("%Y-%m-%dT%H:%M")

    if participants is None:
        rows = board.query("SELECT name FROM sessions WHERE name != 'all' ORDER BY name")
        participants = [r[0] for r in (rows or [])]

    lines = [
        "---",
        f"shift: {shift_number}",
        f"started: {start_str}",
        f"ended: {end_str}",
        "---",
        "",
        f"# Shift {shift_number:03d}",
        "",
        "## 参与同学",
        "",
        "| 同学 | commits | tasks done |",
        "|------|---------|------------|",
    ]

    for name in participants:
        task_count = (
            board.scalar(
                "SELECT COUNT(*) FROM tasks WHERE session=? AND done_at > ? AND status='done'",
                (name, since_str),
            )
            or 0
        )
        commit_count = 0
        if project_root:
            commits = _git_commits_by_author(project_root, since_str, name)
            commit_count = len(commits)
        lines.append(f"| {name} | {commit_count} | {task_count} |")

    bugs_opened = board.query(
        "SELECT id, severity, reporter, description FROM bugs WHERE reported_at > ?",
        (since_str,),
    )
    bugs_fixed = board.query(
        "SELECT id, severity, assignee FROM bugs WHERE fixed_at > ?",
        (since_str,),
    )

    if bugs_opened or bugs_fixed:
        lines.append("")
        lines.append("## Bug")
        if bugs_opened:
            lines.append(f"\n新增: {len(bugs_opened)}")
            for r in bugs_opened:
                lines.append(f"- {r[0]} [{r[1]}] {r[3][:50]}")
        if bugs_fixed:
            lines.append(f"\n修复: {len(bugs_fixed)}")
            for r in bugs_fixed:
                lines.append(f"- {r[0]} [{r[1]}] by {r[2]}")

    total_commits = 0
    if project_root:
        total_commits = len(_git_commits_all(project_root, since_str))
    if total_commits:
        lines.append("")
        lines.append(f"## 总 Commits: {total_commits}")

    return "\n".join(lines) + "\n"


def next_shift_number(dailies_dir: Path) -> int:
    """Read the next shift number from .next_shift file, defaulting to 1."""
    marker = dailies_dir / ".next_shift"
    if marker.exists():
        try:
            return int(marker.read_text().strip())
        except (ValueError, OSError):
            pass
    existing = [d.name for d in dailies_dir.iterdir() if d.is_dir() and d.name.isdigit()]
    if existing:
        return max(int(d) for d in existing) + 1
    return 1


def save_shift_number(dailies_dir: Path, number: int) -> None:
    """Save the next shift number."""
    marker = dailies_dir / ".next_shift"
    marker.write_text(str(number + 1) + "\n")
