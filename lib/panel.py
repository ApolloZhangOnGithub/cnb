#!/usr/bin/env python3
"""panel.py -- Auto-refreshing team status panel.

Usage:
    ./lib/panel.py [interval_seconds]
"""

import re
import select
import subprocess
import sys
import time
from pathlib import Path

# Try to import common; fall back gracefully for standalone use
try:
    from lib.common import ClaudesEnv
except ImportError:
    _here = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(_here))
    from lib.common import ClaudesEnv


def _tmux(*args: str) -> str | None:
    try:
        r = subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def status_icon(prefix: str, name: str) -> str:
    """Return a 2-char status icon for the session."""
    sess = f"{prefix}-{name}"
    if _tmux("has-session", "-t", sess) is None:
        return "  "

    cmd = _tmux("list-panes", "-t", sess, "-F", "#{pane_current_command}")
    first = (cmd or "").splitlines()[0] if cmd else ""
    if first in ("zsh", "bash", "sh", "-zsh", "-bash", ""):
        return "!!"

    output = _tmux("capture-pane", "-t", sess, "-p")
    if output is None:
        return "~~"

    tail = "\n".join(output.splitlines()[-8:])
    if "bypass permissions" in tail:
        return ".."
    if re.search(r"^\s*(⠋|⠙|⠹|⠸|⠼|⠴|⠦|⠧|⠇|⠏|●)", tail, re.MULTILINE):
        return ">>"
    return "~~"


def render(env: ClaudesEnv, interval: int) -> None:
    """Clear screen and print the team panel."""
    # Clear screen
    print("\033[2J\033[H", end="")
    now = time.strftime("%H:%M:%S")
    print(f"\033[1m  TEAM PANEL\033[0m  {now}")
    print()

    for name in env.sessions:
        sf = env.sessions_dir / f"{name}.md"
        icon = status_icon(env.prefix, name)

        task = "-"
        if sf.exists():
            lines = sf.read_text().splitlines()
            for i, line in enumerate(lines):
                if line.startswith("## Status"):
                    if i + 1 < len(lines) and lines[i + 1].strip():
                        task = lines[i + 1].strip()
                    break

        # Color by icon
        color = "\033[90m"  # dim
        if icon == ">>":
            color = "\033[32m"  # green
        elif icon == "..":
            color = "\033[33m"  # yellow
        elif icon == "!!":
            color = "\033[31m"  # red

        print(f"  {color}{icon} {name:<6}\033[0m {task}")

    print(f"\n  \033[90m{interval} 秒刷新  q 退出\033[0m")


def main() -> None:
    env = ClaudesEnv.load()
    try:
        interval = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    except ValueError:
        print(f"ERROR: 无效的刷新间隔: {sys.argv[1]}")
        raise SystemExit(1)

    # Hide cursor
    print("\033[?25l", end="", flush=True)

    import signal

    def _restore(*_):
        print("\033[?25h", end="", flush=True)  # show cursor
        raise SystemExit(0)

    signal.signal(signal.SIGINT, _restore)
    signal.signal(signal.SIGTERM, _restore)

    try:
        while True:
            render(env, interval)

            # Wait for interval, checking for 'q' key
            deadline = time.time() + interval
            while time.time() < deadline:
                # Non-blocking stdin read (Unix only)
                import termios
                import tty

                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setcbreak(sys.stdin.fileno())
                    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
                    if rlist:
                        ch = sys.stdin.read(1)
                        if ch == "q":
                            _restore()
                except Exception:
                    time.sleep(0.1)
                finally:
                    try:
                        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                    except Exception:
                        pass
    finally:
        print("\033[?25h", end="", flush=True)


if __name__ == "__main__":
    main()
