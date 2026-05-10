"""shutdown — orchestrate the cnb shutdown flow.

Broadcast shutdown notice → wait for acks → collect per-agent reports →
generate _meta.md → save to dailies/{shift}/ → stop sessions.
"""

from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.board_db import BoardDB
from lib.common import ClaudesEnv
from lib.shift_report import (
    generate_agent_report,
    generate_shift_meta,
    next_shift_number,
    save_shift_number,
)


def _board_send(board_sh: str, sender: str, recipient: str, msg: str) -> bool:
    try:
        subprocess.run(
            [board_sh, "--as", sender, "send", recipient, msg],
            capture_output=True,
            timeout=10,
        )
        return True
    except (subprocess.TimeoutExpired, OSError):
        return False


SYSTEM_SESSIONS: frozenset[str] = frozenset({"all", "dispatcher"})


def _active_sessions(board: BoardDB, roster: list[str] | None = None) -> list[str]:
    """Return the shutdown roster.

    If config.toml provides a roster, it is the authority for the current team.
    The database may contain historical/offboarded sessions, and shutdown must
    not broadcast to or wait on those stale identities.
    """
    if roster is not None:
        registered = {r[0] for r in board.query("SELECT name FROM sessions")}
        seen: set[str] = set()
        active: list[str] = []
        for raw_name in roster:
            name = raw_name.lower()
            if name in SYSTEM_SESSIONS or name in seen or name not in registered:
                continue
            seen.add(name)
            active.append(name)
        return active

    rows = board.query("SELECT name FROM sessions WHERE name NOT IN ('all', 'dispatcher') ORDER BY name")
    return [r[0] for r in (rows or [])]


def _unread_count(board: BoardDB, session: str) -> int:
    return (
        board.scalar(
            "SELECT COUNT(*) FROM inbox WHERE session=? AND read=0",
            (session,),
        )
        or 0
    )


def broadcast_shutdown(board_sh: str, sender: str, sessions: list[str]) -> None:
    msg = "收工通知：请保存当前工作，ack 你的收件箱。系统将自动收集日报并关停 session。"
    for session in sessions:
        _board_send(board_sh, sender, session, msg)


def stop_dispatcher_session(cfg: Any) -> bool:
    """Stop the dispatcher UI session as part of shutdown."""
    prefix = cfg.env.prefix
    if not cfg.backend.is_running(prefix, "dispatcher"):
        return False

    board = cfg.install_home / "bin" / "board"
    save_cmd = f"'{board}' --as dispatcher status 'shutdown: dispatcher stopped'"
    cfg.backend.stop_session(prefix, "dispatcher", save_cmd)
    return True


def wait_for_acks(
    board: BoardDB,
    sessions: list[str],
    timeout: int = 120,
    poll_interval: int = 5,
) -> tuple[list[str], list[str]]:
    """Wait for sessions to ack (clear their inbox).

    Returns (acked, timed_out) lists.
    """
    pending = set(sessions)
    acked: list[str] = []
    deadline = time.monotonic() + timeout

    while pending and time.monotonic() < deadline:
        for name in list(pending):
            if _unread_count(board, name) == 0:
                pending.discard(name)
                acked.append(name)
        if pending:
            time.sleep(poll_interval)

    return acked, sorted(pending)


def collect_reports(
    board: BoardDB,
    sessions: list[str],
    since: datetime,
    project_root: Path | None = None,
) -> dict[str, str]:
    """Generate per-agent shift reports."""
    reports: dict[str, str] = {}
    for name in sessions:
        reports[name] = generate_agent_report(board, name, since=since, project_root=project_root)
    return reports


def save_shift(
    dailies_dir: Path,
    shift_number: int,
    reports: dict[str, str],
    meta: str,
) -> Path:
    """Save reports and _meta.md to dailies/{shift_number}/."""
    shift_dir = dailies_dir / f"{shift_number:03d}"
    shift_dir.mkdir(parents=True, exist_ok=True)

    (shift_dir / "_meta.md").write_text(meta)

    for name, content in reports.items():
        (shift_dir / f"{name}.md").write_text(content)

    return shift_dir


def run_shutdown(
    env: ClaudesEnv,
    *,
    timeout: int = 120,
    skip_broadcast: bool = False,
    skip_stop: bool = False,
    dry_run: bool = False,
) -> Path | None:
    """Execute the full shutdown flow. Returns the shift directory path."""
    board_sh = str(env.install_home / "bin" / "board")
    db_path = env.board_db
    if not db_path.exists():
        print("ERROR: board.db 不存在")
        raise SystemExit(1)

    board = BoardDB(db_path)
    sessions = _active_sessions(board, env.sessions if env.sessions else None)
    if not sessions:
        print("无活跃 session")
        return None

    dailies_dir = env.claudes_dir / "dailies"
    dailies_dir.mkdir(exist_ok=True)
    shift_number = next_shift_number(dailies_dir)
    started = datetime.now()

    print(f"=== Shift {shift_number:03d} 收工流程 ===")
    print(f"活跃同学: {', '.join(sessions)}")

    if dry_run:
        print("[DRY RUN] 不会实际发送或停止")

    if not skip_broadcast and not dry_run:
        print("\n[1/5] 广播收工通知...")
        broadcast_shutdown(board_sh, "dispatcher", sessions)
        print("OK 已广播")
    else:
        print("\n[1/5] 跳过广播")

    if not skip_broadcast and not dry_run:
        print(f"\n[2/5] 等待 ack（超时 {timeout}s）...")
        acked, timed_out = wait_for_acks(board, sessions, timeout=timeout)
        if acked:
            print(f"  已 ack: {', '.join(acked)}")
        if timed_out:
            print(f"  超时未 ack: {', '.join(timed_out)}（继续收集）")
    else:
        print("\n[2/5] 跳过等待 ack")

    print("\n[3/5] 收集同学日报...")
    reports = collect_reports(board, sessions, since=started, project_root=env.project_root)
    for name in sessions:
        print(f"  {name}: OK")

    print("\n[4/5] 生成轮次汇总...")
    ended = datetime.now()
    meta = generate_shift_meta(
        board,
        shift_number,
        started,
        ended,
        participants=sessions,
        project_root=env.project_root,
    )

    if dry_run:
        print(f"\n[DRY RUN] 将保存到 dailies/{shift_number:03d}/")
        print(f"  _meta.md + {len(reports)} 份个人日报")
        return None

    shift_dir = save_shift(dailies_dir, shift_number, reports, meta)
    save_shift_number(dailies_dir, shift_number)
    print(f"OK 已保存到 {shift_dir}")

    if not skip_stop:
        print("\n[5/5] 关停 session...")
        from lib.swarm import SwarmConfig, SwarmManager

        cfg = SwarmConfig.load()
        mgr = SwarmManager(cfg)
        mgr.stop([], force=True)
        if stop_dispatcher_session(cfg):
            print("  dispatcher: stopped")
        print("OK 全部关停")
    else:
        print("\n[5/5] 跳过关停（--no-stop）")

    print(f"\n=== Shift {shift_number:03d} 收工完成 ===")
    return shift_dir
