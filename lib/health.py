#!/usr/bin/env python3
"""health.py -- Session health report with colored output.

Shows restart count, idle status, uptime for each session.

Usage:
    ./lib/health.py
"""

import re
import subprocess
import sys
import time
from pathlib import Path

# Try to import common; fall back gracefully for standalone use
try:
    from lib.common import ClaudesEnv, date_to_epoch
except ImportError:
    # Allow running from project root
    _here = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_here))
    from lib.common import ClaudesEnv, date_to_epoch

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------

G = "\033[0;32m"
R = "\033[0;31m"
Y = "\033[1;33m"
D = "\033[2m"
NC = "\033[0m"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tmux(*args: str) -> str | None:
    """Run a tmux command, return stdout or None on failure."""
    try:
        r = subprocess.run(
            ["tmux", *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def get_sessions(prefix: str, dispatcher: str = "dispatcher", lead: str = "lead") -> list:
    """List dev session names from tmux (excludes dispatcher & lead)."""
    raw = _tmux("list-sessions", "-F", "#{session_name}")
    if raw is None:
        return []
    names = []
    for line in sorted(raw.splitlines()):
        if line.startswith(f"{prefix}-"):
            name = line[len(prefix) + 1 :]
            if name not in (dispatcher, lead):
                names.append(name)
    return names


def is_claude_running(sess: str) -> bool:
    """Check if the pane's current command looks like an active Claude process."""
    if _tmux("has-session", "-t", sess) is None:
        return False
    cmd = _tmux("list-panes", "-t", sess, "-F", "#{pane_current_command}")
    if cmd is None:
        return False
    first = cmd.splitlines()[0] if cmd else ""
    return first not in ("zsh", "bash", "sh", "-zsh", "-bash", "")


def session_status(sess: str, idle_cache: Path) -> str:
    """Return status string: active, idle, exited, offline."""
    if _tmux("has-session", "-t", sess) is None:
        return "offline"

    cmd = _tmux("list-panes", "-t", sess, "-F", "#{pane_current_command}")
    first = (cmd or "").splitlines()[0] if cmd else ""
    if first in ("zsh", "bash", "sh", "-zsh", "-bash", ""):
        return "exited"

    # Check idle cache
    if idle_cache.exists():
        for line in idle_cache.read_text().splitlines():
            if line == f"{sess} idle":
                return "idle"
    return "active"


# ---------------------------------------------------------------------------
# Main report
# ---------------------------------------------------------------------------


def print_health_report() -> None:
    env = ClaudesEnv.load()
    prefix = env.prefix
    log_dir = env.project_root / ".swarm-logs"
    idle_cache = log_dir / "idle-cache"
    now = int(time.time())

    sessions = get_sessions(prefix)

    print()
    print("  Session\t\tStatus\t\tRestarts\tUptime\t\tAgent")
    print("  -------\t\t------\t\t--------\t------\t\t-----")

    total = 0
    alive = 0
    idle_count = 0

    for name in sessions:
        total += 1
        sess = f"{prefix}-{name}"

        status = session_status(sess, idle_cache)
        if status == "idle":
            idle_count += 1
            alive += 1
        elif status == "active":
            alive += 1

        # Restart count
        restarts = 0
        log_file = log_dir / f"{name}.log"
        if log_file.exists():
            restarts = sum(1 for _ in log_file.read_text().splitlines())

        # Uptime + agent
        uptime_str = "-"
        agent = "?"
        if log_file.exists():
            lines = log_file.read_text().splitlines()
            if lines:
                last_line = lines[-1]
                ts_match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", last_line)
                agent_match = re.search(r"agent: ([a-z]+)", last_line)
                if agent_match:
                    agent = agent_match.group(1)
                if ts_match:
                    start_epoch = date_to_epoch(ts_match.group(0))
                    if start_epoch > 0:
                        elapsed = now - start_epoch
                        hours = elapsed // 3600
                        mins = (elapsed % 3600) // 60
                        uptime_str = f"{hours}h{mins}m"

        # Color status
        if status == "active":
            status_col = f"{G}active{NC}"
        elif status == "idle":
            status_col = f"{Y}idle{NC}"
        elif status == "exited":
            status_col = f"{R}exited{NC}"
        else:
            status_col = f"{D}offline{NC}"

        # Color restarts
        if restarts > 5:
            restart_col = f"{R}{restarts}{NC}"
        elif restarts > 2:
            restart_col = f"{Y}{restarts}{NC}"
        else:
            restart_col = f"{G}{restarts}{NC}"

        print(f"  {name}\t\t{status_col}\t\t{restart_col}\t\t{uptime_str}\t\t{agent}")

    print()
    offline = total - alive
    print(f"  Total: {total} | Active: {G}{alive}{NC} | Idle: {Y}{idle_count}{NC} | Offline: {D}{offline}{NC}")
    print()


def main() -> None:
    print_health_report()


if __name__ == "__main__":
    main()
