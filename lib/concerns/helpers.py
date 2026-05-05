"""Shared helper functions for dispatcher concerns (tmux, board, etc.)."""

import hashlib
import re
import subprocess
import sys
import time
from pathlib import Path

from lib.board_db import BoardDB

from .config import DispatcherConfig

# ── logging ──


def log(msg: str) -> None:
    print(f"[dispatcher] {time.strftime('%H:%M:%S')} {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"[dispatcher] {time.strftime('%H:%M:%S')} WARN {msg}", flush=True, file=sys.stderr)


# ── tmux ──

TMUX_TIMEOUT = 8  # seconds


def tmux(*args: str) -> str | None:
    try:
        r = subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=TMUX_TIMEOUT)
        return r.stdout.strip() if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError) as e:
        warn(f"tmux {' '.join(args)}: {e}")
        return None


def tmux_ok(*args: str) -> bool:
    try:
        return subprocess.run(["tmux", *args], capture_output=True, timeout=TMUX_TIMEOUT).returncode == 0
    except (subprocess.TimeoutExpired, OSError) as e:
        warn(f"tmux_ok {' '.join(args)}: {e}")
        return False


def tmux_send(sess: str, text: str) -> bool:
    """Send keys to a tmux session. Returns True on success."""
    try:
        subprocess.run(["tmux", "send-keys", "-t", sess, "-l", text], timeout=TMUX_TIMEOUT, check=True)
        subprocess.run(["tmux", "send-keys", "-t", sess, "Enter"], timeout=TMUX_TIMEOUT, check=True)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        warn(f"tmux_send {sess}: {e}")
        return False


def is_claude_running(sess: str) -> bool:
    if not tmux_ok("has-session", "-t", sess):
        return False
    cmd = tmux("list-panes", "-t", sess, "-F", "#{pane_current_command}")
    if not cmd:
        return False
    first = cmd.splitlines()[0] if cmd else ""
    return first not in ("zsh", "bash", "sh", "-zsh", "-bash", "")


def get_dev_sessions(cfg: DispatcherConfig) -> list[str]:
    raw = tmux("list-sessions", "-F", "#{session_name}")
    if not raw:
        return []
    pfx = f"{cfg.prefix}-"
    protected = {"dispatcher", "lead"}
    return [
        line[len(pfx) :]
        for line in raw.splitlines()
        if line.startswith(pfx) and line[len(pfx) :] not in protected
    ]


def pane_md5(sess: str) -> str:
    content = tmux("capture-pane", "-t", sess, "-p") or ""
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
