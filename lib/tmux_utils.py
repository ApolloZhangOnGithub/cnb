"""tmux_utils — shared tmux subprocess wrappers for board_* and dispatcher concerns."""

import os
import subprocess

TMUX_TIMEOUT = 8


def tmux_run(*args: str) -> str | None:
    try:
        r = subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=TMUX_TIMEOUT)
        return r.stdout.strip() if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def tmux_ok(*args: str) -> bool:
    try:
        return subprocess.run(["tmux", *args], capture_output=True, timeout=TMUX_TIMEOUT).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def tmux_send(sess: str, text: str) -> bool:
    try:
        if text:
            buffer_name = f"cnb-send-{os.getpid()}"
            subprocess.run(
                ["tmux", "load-buffer", "-b", buffer_name, "-"],
                input=text,
                text=True,
                timeout=TMUX_TIMEOUT,
                check=True,
            )
            subprocess.run(
                ["tmux", "paste-buffer", "-d", "-p", "-r", "-b", buffer_name, "-t", sess],
                timeout=TMUX_TIMEOUT,
                check=True,
            )
        subprocess.run(["tmux", "send-keys", "-t", sess, "Enter"], timeout=TMUX_TIMEOUT, check=True)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


def has_session(name: str) -> bool:
    return tmux_ok("has-session", "-t", name)


def pane_command(name: str) -> str:
    result = tmux_run("list-panes", "-t", name, "-F", "#{pane_current_command}")
    return result.splitlines()[0] if result else ""


def capture_pane(sess: str, lines: int = 0) -> str:
    args = ["capture-pane", "-t", sess, "-p"]
    if lines:
        args.extend(["-S", str(-lines)])
    return tmux_run(*args) or ""


def is_agent_running(sess: str) -> bool:
    if not has_session(sess):
        return False
    cmd = pane_command(sess)
    return cmd not in ("zsh", "bash", "sh", "-zsh", "-bash", "")
