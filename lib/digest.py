"""digest — generate daily/weekly activity summaries from board data."""

from __future__ import annotations

from datetime import datetime, timedelta

from lib.board_db import BoardDB


def generate_daily_digest(board: BoardDB, since: datetime | None = None) -> str:
    if since is None:
        since = datetime.now() - timedelta(hours=24)
    since_str = since.strftime("%Y-%m-%d %H:%M:%S")

    sections: list[str] = []

    msg_count = board.scalar("SELECT COUNT(*) FROM messages WHERE ts > ?", (since_str,)) or 0
    if msg_count:
        top_senders = board.query(
            "SELECT sender, COUNT(*) as cnt FROM messages WHERE ts > ? GROUP BY sender ORDER BY cnt DESC LIMIT 5",
            (since_str,),
        )
        sender_str = ", ".join(f"{r[0]}({r[1]})" for r in (top_senders or []))
        sections.append(f"消息: {msg_count} 条 — {sender_str}")

    bugs_opened = board.query(
        "SELECT id, severity, reporter, description FROM bugs WHERE reported_at > ? AND status='OPEN'",
        (since_str,),
    )
    if bugs_opened:
        bug_lines = [f"  {r[0]} [{r[1]}] {r[3][:40]}" for r in bugs_opened]
        sections.append(f"新 Bug: {len(bugs_opened)} 个\n" + "\n".join(bug_lines))

    bugs_fixed = board.query(
        "SELECT id, severity, assignee FROM bugs WHERE fixed_at > ?",
        (since_str,),
    )
    if bugs_fixed:
        fix_lines = [f"  {r[0]} [{r[1]}] by {r[2]}" for r in bugs_fixed]
        sections.append(f"修复: {len(bugs_fixed)} 个\n" + "\n".join(fix_lines))

    tasks_done = board.query(
        "SELECT session, description FROM tasks WHERE done_at > ? AND status='done'",
        (since_str,),
    )
    if tasks_done:
        task_lines = [f"  {r[0]}: {r[1][:50]}" for r in tasks_done]
        sections.append(f"完成任务: {len(tasks_done)} 个\n" + "\n".join(task_lines))

    kudos_list = board.query(
        "SELECT sender, target, reason FROM kudos WHERE ts > ?",
        (since_str,),
    )
    if kudos_list:
        kudos_lines = [f"  {r[0]} → {r[1]}: {r[2][:40]}" for r in kudos_list]
        sections.append(f"Kudos: {len(kudos_list)} 个\n" + "\n".join(kudos_lines))

    if not sections:
        return "[Daily Digest] 过去 24h 无活动。"

    header = f"[Daily Digest] {datetime.now().strftime('%Y-%m-%d')} 活动摘要"
    return header + "\n" + "\n".join(sections)
