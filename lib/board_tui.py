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
    try:
        return subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=5).returncode
    except (subprocess.TimeoutExpired, OSError):
        return 1


def _tmux_out(*args: str) -> str:
    try:
        r = subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (subprocess.TimeoutExpired, OSError):
        return ""


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

    # Rebuild base UI session (shared window group)
    if _session_exists(UI_SESSION):
        _tmux("kill-session", "-t", UI_SESSION)

    _tmux("new-session", "-d", "-s", UI_SESSION)
    for name in online:
        _tmux("link-window", "-s", f"{prefix}-{name}:0", "-t", UI_SESSION, "-a")
    _tmux("kill-window", "-t", f"{UI_SESSION}:0")

    win_indices = _tmux_out("list-windows", "-t", UI_SESSION, "-F", "#{window_index}").split("\n")
    for i, name in enumerate(online):
        if i < len(win_indices):
            _tmux("rename-window", "-t", f"{UI_SESSION}:{win_indices[i]}", name)

    _apply_style(len(online), win_indices)
    _open_terminal()


def _apply_style(n_online: int, win_indices: list[str]) -> None:
    session_opts = {
        "mouse": "on",
        "status": "on",
        "status-position": "top",
        "status-style": "bg=default,fg=white",
        "status-left": " cnb ",
        "status-left-style": "bold",
        "status-left-length": "6",
        "status-right": f" {n_online} online ",
        "status-right-style": "dim",
    }
    for k, v in session_opts.items():
        _tmux("set-option", "-t", UI_SESSION, k, v)

    window_opts = {
        "window-status-format": " #W ",
        "window-status-current-format": " #W ",
        "window-status-style": "dim",
        "window-status-current-style": "bold,underscore",
        "window-status-separator": "",
    }
    for idx in win_indices:
        for k, v in window_opts.items():
            _tmux("set-option", "-w", "-t", f"{UI_SESSION}:{idx}", k, v)


def _open_terminal() -> None:
    """Open a new terminal attached to cnb-ui."""
    attach_cmd = f"tmux attach -t {UI_SESSION} ';' set-option destroy-unattached on"

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
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            print(f"ERROR: 无法打开终端: {r.stderr.strip()}")
            raise SystemExit(1)
        print("OK 已打开 — 点击顶部 tab 切换同学")
    else:
        import shutil

        for term in ("gnome-terminal", "xterm", "konsole", "alacritty"):
            if shutil.which(term):
                subprocess.Popen([term, "--", "bash", "-c", attach_cmd])
                print("OK 已打开 — 点击顶部 tab 切换同学")
                return
        print(f"ERROR: 找不到终端模拟器，手动运行: {attach_cmd}")
        raise SystemExit(1)
