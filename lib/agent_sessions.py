"""Discover foreground agent sessions (Codex / Claude Code) on the local machine."""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

AGENT_PROCESS_RE = re.compile(r"(^|/|\s)(codex|claude)(\s|$)", re.IGNORECASE)


def describe_foreground_agent_sessions(*, limit: int = 6) -> str:
    sessions = foreground_agent_sessions(limit=limit)
    if not sessions:
        return "未发现用户前台操作的非 tmux Codex/Claude Code 会话。"
    lines = [_format_foreground_session(session) for session in sessions[:limit]]
    if len(sessions) > limit:
        lines.append(f"另有 {len(sessions) - limit} 个未展开")
    return "；".join(lines)


def foreground_agent_sessions(*, limit: int = 12) -> list[dict[str, str]]:
    rows = _process_rows()
    by_pid = {row["pid"]: row for row in rows}
    sessions: list[dict[str, str]] = []
    for row in rows:
        engine = _agent_engine(row)
        if not engine or _is_child_agent_process(row, by_pid) or _is_under_tmux(row, by_pid):
            continue
        tty = row.get("tty", "")
        if tty in {"", "?", "??"}:
            continue
        cwd = _extract_cd_path(row.get("args", "")) or _process_cwd(row["pid"])
        sessions.append(
            {
                "engine": engine,
                "pid": str(row["pid"]),
                "tty": tty,
                "cwd": cwd,
                "command": _short_agent_command(row.get("args", "")),
            }
        )
    return sessions[:limit]


def _process_rows() -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,tty=,stat=,comm=,args="],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, 5)
        if len(parts) < 6:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        rows.append({"pid": pid, "ppid": ppid, "tty": parts[2], "stat": parts[3], "comm": parts[4], "args": parts[5]})
    return rows


def _agent_engine(row: dict[str, Any]) -> str:
    comm = Path(str(row.get("comm", ""))).name.lower()
    args = str(row.get("args", ""))
    lowered = f"{comm} {args}".lower()
    if "codex computer use.app" in lowered:
        return ""
    if "rg -i" in lowered or "ps -axo" in lowered:
        return ""
    if "codex" in comm or re.search(r"(^|\s|/)codex(\s|$)", lowered):
        return "codex"
    if "claude" in comm or (AGENT_PROCESS_RE.search(lowered) and "codex" not in lowered):
        return "claude"
    return ""


def _is_child_agent_process(row: dict[str, Any], by_pid: dict[int, dict[str, Any]]) -> bool:
    engine = _agent_engine(row)
    parent = by_pid.get(int(row.get("ppid", 0)))
    return bool(engine and parent and _agent_engine(parent) == engine)


def _is_under_tmux(row: dict[str, Any], by_pid: dict[int, dict[str, Any]]) -> bool:
    ppid = int(row.get("ppid", 0))
    for _ in range(12):
        parent = by_pid.get(ppid)
        if not parent:
            return False
        comm = Path(str(parent.get("comm", ""))).name.lower()
        args = str(parent.get("args", "")).lower()
        if comm == "tmux" or args.startswith("tmux "):
            return True
        ppid = int(parent.get("ppid", 0))
    return False


def _extract_cd_path(args: str) -> str:
    try:
        parts = shlex.split(args)
    except ValueError:
        return ""
    for index, part in enumerate(parts[:-1]):
        if part == "--cd":
            return parts[index + 1]
    return ""


def _process_cwd(pid: int) -> str:
    if not shutil.which("lsof"):
        return ""
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=1,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    for line in result.stdout.splitlines():
        if line.startswith("n"):
            return line[1:]
    return ""


def _short_agent_command(args: str) -> str:
    text = " ".join(args.split())
    if " resume " in f" {text} ":
        return "resume"
    if " --cd " in f" {text} ":
        return "--cd"
    return _truncate_inline(text, 64)


def _format_foreground_session(session: dict[str, str]) -> str:
    cwd = session.get("cwd", "")
    cwd_bit = f" cwd={cwd}" if cwd else ""
    command = session.get("command", "")
    command_bit = f" {command}" if command else ""
    return f"{session.get('engine')} pid={session.get('pid')} tty={session.get('tty')}{cwd_bit}{command_bit}"


def _truncate_inline(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)] + "…"
