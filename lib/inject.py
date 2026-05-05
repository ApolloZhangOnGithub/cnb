#!/usr/bin/env python3
"""inject.py -- Force-inject a message into another Claude Code session.

Auto-detects tmux or screen. Override with SWARM_MODE=tmux|screen.

Usage:
    ./lib/inject.py <target> <message>
    ./lib/inject.py all "everyone check inbox"
"""

import os
import shutil
import subprocess
import sys
from typing import Optional

# Try to import common; fall back gracefully for standalone use
try:
    from lib.common import ClaudesEnv
except ImportError:
    _here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(_here))
    from lib.common import ClaudesEnv


def detect_mode(prefix: str) -> str:
    """Auto-detect session multiplexer: tmux, screen, or none."""
    swarm_mode = os.environ.get("SWARM_MODE", "")
    if swarm_mode:
        return swarm_mode

    # Check tmux
    try:
        r = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if line.startswith(f"{prefix}-"):
                    return "tmux"
    except Exception:
        pass

    # Check screen
    try:
        r = subprocess.run(
            ["screen", "-list"], capture_output=True, text=True, timeout=5,
        )
        if f".{prefix}-" in (r.stdout + r.stderr):
            return "screen"
    except Exception:
        pass

    if shutil.which("tmux"):
        return "tmux"
    elif shutil.which("screen"):
        return "screen"
    return "none"


def send_tmux(prefix: str, name: str, message: str) -> bool:
    """Inject message into a tmux session. Returns True on success."""
    sess = f"{prefix}-{name}"
    try:
        r = subprocess.run(
            ["tmux", "has-session", "-t", sess],
            capture_output=True, timeout=5,
        )
        if r.returncode != 0:
            print(f"  {name}: not running")
            return False
    except Exception:
        print(f"  {name}: not running")
        return False

    oneline = message.replace("\n", " ")
    subprocess.run(["tmux", "send-keys", "-t", sess, "-l", oneline], timeout=5)
    subprocess.run(["tmux", "send-keys", "-t", sess, "Enter"], timeout=5)
    print(f"  {name}: injected (tmux)")
    return True


def send_screen(prefix: str, name: str, message: str) -> bool:
    """Inject message into a screen session. Returns True on success."""
    sess = f"{prefix}-{name}"
    try:
        r = subprocess.run(
            ["screen", "-list"], capture_output=True, text=True, timeout=5,
        )
        if f".{sess}" not in (r.stdout + r.stderr):
            print(f"  {name}: not running")
            return False
    except Exception:
        print(f"  {name}: not running")
        return False

    oneline = message.replace("\n", " ")
    subprocess.run(
        ["screen", "-S", sess, "-p", "0", "-X", "stuff", oneline], timeout=5,
    )
    import time
    time.sleep(0.3)
    subprocess.run(
        ["screen", "-S", sess, "-p", "0", "-X", "stuff", "\r"], timeout=5,
    )
    print(f"  {name}: injected (screen)")
    return True


def inject(target: str, message: str, prefix: Optional[str] = None, sessions: Optional[list] = None) -> None:
    """Inject a message to *target* (a session name or 'all')."""
    if prefix is None or sessions is None:
        env = ClaudesEnv.load()
        prefix = prefix or env.prefix
        sessions = sessions if sessions is not None else env.sessions

    mode = detect_mode(prefix)
    if mode == "none":
        print("ERROR: neither tmux nor screen found", file=sys.stderr)
        sys.exit(1)

    send_fn = send_tmux if mode == "tmux" else send_screen
    target_lower = target.lower()

    if target_lower == "all":
        print(f"Injecting to all ({mode}):")
        for name in sessions:
            send_fn(prefix, name, message)
    else:
        send_fn(prefix, target_lower, message)


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "Usage: ./inject.py <target> <message>\n"
            "\n"
            "  target: session name or 'all'\n"
            "\n"
            "Examples:\n"
            '  ./inject.py alice "what\'s blocking P0?"\n'
            '  ./inject.py all "everyone check inbox"',
        )
        sys.exit(1)

    target = sys.argv[1]
    message = " ".join(sys.argv[2:])
    inject(target, message)


if __name__ == "__main__":
    main()
