"""Tests for foreground agent process discovery."""

from lib import agent_sessions


def test_foreground_agent_sessions_excludes_tmux_and_child_processes(monkeypatch):
    rows = [
        {"pid": 10, "ppid": 1, "tty": "??", "stat": "Ss", "comm": "tmux", "args": "tmux new-session"},
        {
            "pid": 20,
            "ppid": 10,
            "tty": "ttys005",
            "stat": "S+",
            "comm": "node",
            "args": "node /opt/homebrew/bin/codex --cd /repo",
        },
        {
            "pid": 21,
            "ppid": 20,
            "tty": "ttys005",
            "stat": "S+",
            "comm": "codex",
            "args": "/vendor/codex --cd /repo",
        },
        {
            "pid": 30,
            "ppid": 2,
            "tty": "ttys010",
            "stat": "S+",
            "comm": "node",
            "args": "node /opt/homebrew/bin/codex resume abc",
        },
        {
            "pid": 31,
            "ppid": 30,
            "tty": "ttys010",
            "stat": "S+",
            "comm": "codex",
            "args": "/vendor/codex resume abc",
        },
    ]

    monkeypatch.setattr(agent_sessions, "_process_rows", lambda: rows)
    monkeypatch.setattr(agent_sessions, "_process_cwd", lambda pid: "/manual")

    sessions = agent_sessions.foreground_agent_sessions()

    assert sessions == [
        {
            "engine": "codex",
            "pid": "30",
            "tty": "ttys010",
            "cwd": "/manual",
            "command": "resume",
        }
    ]
