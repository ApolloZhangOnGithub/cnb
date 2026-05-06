"""board_tui — tmux-native team UI with mouse support.

Opens a single terminal window with tmux. Each worker is a window (tab).
Mouse click on the tab bar to switch. That's it.
"""

import os
import subprocess
import sys

from lib.board_db import BoardDB

UI_SESSION = "cnb-ui"


def _tmux(*args: str) -> int:
    return subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=5).returncode


def _tmux_out(*args: str) -> str:
    r = subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=5)
    return r.stdout.strip() if r.returncode == 0 else ""


def _session_exists(name: str) -> bool:
    return _tmux("has-session", "-t", name) == 0


def cmd_tui(db: BoardDB) -> None:
    """Open team UI: one tmux window per worker, mouse-clickable tabs."""
    if not db.env:
        print("ERROR: 需要完整环境才能启动 TUI")
        raise SystemExit(1)

    prefix = db.env.prefix
    workers = [r[0] for r in db.query("SELECT name FROM sessions WHERE name != 'all' ORDER BY name")]

    if not workers:
        print("ERROR: 没有注册的 session")
        raise SystemExit(1)

    online = [w for w in workers if _session_exists(f"{prefix}-{w}")]
    if not online:
        print("ERROR: 没有在线的 worker，先运行 cnb swarm start")
        raise SystemExit(1)

    # Kill old UI session if exists
    if _session_exists(UI_SESSION):
        _tmux("kill-session", "-t", UI_SESSION)

    # Create session grouped with first worker
    _tmux("new-session", "-d", "-s", UI_SESSION, "-t", f"{prefix}-{online[0]}")

    # Link remaining workers as windows
    for name in online[1:]:
        _tmux("link-window", "-s", f"{prefix}-{name}", "-t", UI_SESSION, "-a")

    # Rename windows
    win_indices = _tmux_out("list-windows", "-t", UI_SESSION, "-F", "#{window_index}").split("\n")
    for i, name in enumerate(online):
        if i < len(win_indices):
            _tmux("rename-window", "-t", f"{UI_SESSION}:{win_indices[i]}", name)

    # Mouse + visual config
    _tmux("set-option", "-t", UI_SESSION, "mouse", "on")
    _tmux("set-option", "-t", UI_SESSION, "status", "on")
    _tmux("set-option", "-t", UI_SESSION, "status-position", "top")
    _tmux("set-option", "-t", UI_SESSION, "status-style", "bg=#1a1a2e,fg=#e0e0e0")
    _tmux("set-option", "-t", UI_SESSION, "status-left", " ◆ cnb  ")
    _tmux("set-option", "-t", UI_SESSION, "status-left-style", "fg=#00d4aa,bold")
    _tmux("set-option", "-t", UI_SESSION, "status-left-length", "10")
    _tmux("set-option", "-t", UI_SESSION, "status-right", f" {len(online)} workers ")
    _tmux("set-option", "-t", UI_SESSION, "status-right-style", "fg=#888888")
    _tmux("set-option", "-t", UI_SESSION, "window-status-format", " #W ")
    _tmux("set-option", "-t", UI_SESSION, "window-status-current-format", " #W ")
    _tmux("set-option", "-t", UI_SESSION, "window-status-style", "fg=#888888")
    _tmux("set-option", "-t", UI_SESSION, "window-status-current-style", "fg=#ffffff,bg=#4a4a6a,bold")

    # Open in new terminal window
    _open_terminal()


def _open_terminal() -> None:
    """Open a new terminal window attached to cnb-ui."""
    attach_cmd = f"tmux attach -t {UI_SESSION}"

    if sys.platform == "darwin":
        if os.path.isdir("/Applications/iTerm.app"):
            script = (
                'tell application "iTerm"\n'
                "  activate\n"
                f'  create window with default profile command "{attach_cmd}"\n'
                "end tell"
            )
        else:
            script = f'tell application "Terminal"\n  do script "{attach_cmd}"\n  activate\nend tell'
        subprocess.run(["osascript", "-e", script], capture_output=True)
        print("OK 已打开 — 点击顶部 tab 切换同学")
    else:
        import shutil

        for term in ("gnome-terminal", "xterm", "konsole", "alacritty"):
            if shutil.which(term):
                subprocess.Popen([term, "--", "bash", "-c", attach_cmd])
                print("OK 已打开 — 点击顶部 tab 切换同学")
                return
        print(f"运行: {attach_cmd}")
