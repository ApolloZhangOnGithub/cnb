"""Shared helper functions for dispatcher concerns (tmux, board, etc.)."""

import hashlib
import subprocess
import sys
import time
from pathlib import Path

from lib.board_db import BoardDB
from lib.tmux_utils import is_agent_running as is_claude_running  # noqa: F401 — re-export
from lib.tmux_utils import (
    tmux_ok,  # noqa: F401 — re-export for concerns
    tmux_run,
)
from lib.tmux_utils import tmux_send as _tmux_send_raw

from .config import DispatcherConfig

# ── logging ──


def log(msg: str) -> None:
    print(f"[dispatcher] {time.strftime('%H:%M:%S')} {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"[dispatcher] {time.strftime('%H:%M:%S')} WARN {msg}", flush=True, file=sys.stderr)


# ── tmux (thin wrappers that add dispatcher logging) ──


def tmux(*args: str) -> str | None:
    result = tmux_run(*args)
    if result is None and args:
        warn(f"tmux {' '.join(args)}: returned None")
    return result


def tmux_send(sess: str, text: str) -> bool:
    result = _tmux_send_raw(sess, text)
    if not result:
        warn(f"tmux_send {sess}: failed")
    return result


def get_dev_sessions(cfg: DispatcherConfig) -> list[str]:
    raw = tmux_run("list-sessions", "-F", "#{session_name}")
    if not raw:
        return []
    pfx = f"{cfg.prefix}-"
    protected = {"dispatcher", "lead"}
    return [line[len(pfx) :] for line in raw.splitlines() if line.startswith(pfx) and line[len(pfx) :] not in protected]


def pane_md5(sess: str) -> str:
    content = tmux_run("capture-pane", "-t", sess, "-p") or ""
    return hashlib.md5(content.encode()).hexdigest()


# ── board ──


def board_send(cfg: DispatcherConfig, target: str, msg: str) -> None:
    try:
        subprocess.run(
            [cfg.board_sh, "--as", "dispatcher", "send", target, msg],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        warn(f"board_send {target}: {e}")


_db_cache: dict[Path, BoardDB] = {}


def db(cfg: DispatcherConfig) -> BoardDB:
    if cfg.board_db not in _db_cache:
        _db_cache[cfg.board_db] = BoardDB(cfg.board_db)
    return _db_cache[cfg.board_db]


# ── process inspection ──


def has_tool_process(sess: str) -> bool:
    """Check if Claude has spawned transient child processes (not caffeinate/uv)."""
    pane_pid = tmux("display-message", "-t", sess, "-p", "#{pane_pid}")
    if not pane_pid:
        return False
    try:
        r = subprocess.run(
            ["pgrep", "-P", pane_pid],
            capture_output=True,
            text=True,
            timeout=3,
        )
        claude_pid = (r.stdout.strip().splitlines() or [""])[0]
        if not claude_pid:
            return False
        r2 = subprocess.run(
            ["pgrep", "-P", claude_pid],
            capture_output=True,
            text=True,
            timeout=3,
        )
        for cpid in r2.stdout.strip().splitlines():
            if not cpid:
                continue
            r3 = subprocess.run(
                ["ps", "-p", cpid, "-o", "comm="],
                capture_output=True,
                text=True,
                timeout=3,
            )
            name = r3.stdout.strip().rsplit("/", 1)[-1]
            if name and name not in ("caffeinate", "uv", ""):
                return True
    except (subprocess.TimeoutExpired, OSError) as e:
        warn(f"has_tool_process {sess}: {e}")
    return False


def is_pane_typing(sess: str) -> bool:
    """Check if a pane has an active prompt with typing."""
    content = tmux("capture-pane", "-t", sess, "-p") or ""
    return any(l.startswith("❯ ") and len(l) > 3 for l in content.splitlines())
