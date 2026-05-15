"""Tests for lib/board_view.py — read-only views.

Covers: _heartbeat_status logic, cmd_p0 (ROADMAP.md parsing),
cmd_get (file retrieval), cmd_history (message history),
cmd_freshness, cmd_relations, cmd_files.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.board_files import cmd_files, cmd_get
from lib.board_msg import cmd_history
from lib.board_view import (
    _heartbeat_status,
    cmd_dashboard,
    cmd_dirty,
    cmd_freshness,
    cmd_overview,
    cmd_p0,
    cmd_prebuild,
    cmd_progress,
    cmd_relations,
    cmd_roster,
    cmd_view,
)


class TestHeartbeatStatus:
    def _hb(self, seconds_ago: int) -> str:
        return (datetime.now() - timedelta(seconds=seconds_ago)).strftime("%Y-%m-%d %H:%M:%S")

    @patch("lib.board_view.has_session", return_value=False)
    def test_active(self, _mock):
        status, _ago = _heartbeat_status(self._hb(30), "cc", "alice")
        assert "alive" in status

    @patch("lib.board_view.has_session", return_value=False)
    def test_thinking(self, _mock):
        status, _ago = _heartbeat_status(self._hb(150), "cc", "alice")
        assert "pulse lag" in status

    @patch("lib.board_view.has_session", return_value=False)
    def test_stale(self, _mock):
        status, _ago = _heartbeat_status(self._hb(300), "cc", "alice")
        assert "pulse stale" in status

    @patch("lib.board_view.has_session", return_value=False)
    def test_offline_old_heartbeat(self, _mock):
        status, ago = _heartbeat_status(self._hb(3600), "cc", "alice")
        assert "offline" in status
        assert "h ago" in ago

    @patch("lib.board_view.capture_pane", return_value="idle prompt\n❯ ")
    @patch("lib.board_view.pane_command", return_value="node")
    @patch("lib.board_view.has_session", return_value=True)
    def test_old_heartbeat_tmux_alive_idle(self, _has, _cmd, _pane):
        status, ago = _heartbeat_status(self._hb(3600), "cc", "alice")
        assert "alive idle" in status
        assert "h ago" in ago

    @patch("lib.board_view.has_session", return_value=False)
    def test_no_heartbeat_no_tmux(self, _mock):
        status, _ = _heartbeat_status(None, "cc", "alice")
        assert "offline" in status

    @patch("lib.board_view.capture_pane", return_value="normal output\n❯ ")
    @patch("lib.board_view.pane_command", return_value="node")
    @patch("lib.board_view.has_session", return_value=True)
    def test_no_heartbeat_tmux_alive_idle(self, _has, _cmd, _pane):
        status, _ = _heartbeat_status(None, "cc", "alice")
        assert "alive idle" in status

    @patch("lib.board_view.capture_pane", return_value="• Working (12s • esc to interrupt)")
    @patch("lib.board_view.pane_command", return_value="node")
    @patch("lib.board_view.has_session", return_value=True)
    def test_no_heartbeat_tmux_working(self, _has, _cmd, _pane):
        status, _ = _heartbeat_status(None, "cc", "alice")
        assert "working" in status

    @patch("lib.board_view.pane_command", return_value="zsh")
    @patch("lib.board_view.has_session", return_value=True)
    def test_no_heartbeat_tmux_dead(self, _has, _cmd):
        status, _ = _heartbeat_status(None, "cc", "alice")
        assert "shell" in status

    @patch("lib.board_view.has_session", return_value=False)
    def test_invalid_heartbeat_format(self, _mock):
        status, _ = _heartbeat_status("not-a-date", "cc", "alice")
        assert "offline" in status


class TestCmdP0:
    def test_no_roadmap(self, db):
        with pytest.raises(SystemExit):
            cmd_p0(db)

    def test_p0_locked(self, db, capsys):
        roadmap = db.env.project_root / "ROADMAP.md"
        roadmap.write_text("## Status\n端到端状态: 从未验证\n## END\n")
        cmd_p0(db)
        output = capsys.readouterr().out
        assert "P0 LOCKED" in output

    def test_p0_clear(self, db, capsys):
        roadmap = db.env.project_root / "ROADMAP.md"
        roadmap.write_text("## Status\n端到端状态: 已通过\n## END\n")
        cmd_p0(db)
        output = capsys.readouterr().out
        assert "P0 CLEAR" in output


class TestCmdGet:
    def test_no_args_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_get(db, [])

    def test_missing_file_exits(self, db, capsys):
        with pytest.raises(SystemExit):
            cmd_get(db, ["nonexistent"])
        output = capsys.readouterr().out
        assert "no file matching" in output

    def test_retrieves_file(self, db, capsys):
        files_dir = db.env.claudes_dir / "files"
        files_dir.mkdir(exist_ok=True)
        stored = files_dir / "abc123.txt"
        stored.write_text("file content here")
        db.execute(
            "INSERT INTO files(hash, original_name, sender, stored_path, extension) "
            "VALUES ('abc123', 'readme.txt', 'alice', 'files/abc123.txt', '.txt')"
        )
        cmd_get(db, ["abc123"])
        output = capsys.readouterr().out
        assert "readme.txt" in output
        assert "alice" in output
        assert "file content here" in output

    def test_retrieves_by_name(self, db, capsys):
        files_dir = db.env.claudes_dir / "files"
        files_dir.mkdir(exist_ok=True)
        stored = files_dir / "xyz789.txt"
        stored.write_text("by name")
        db.execute(
            "INSERT INTO files(hash, original_name, sender, stored_path, extension) "
            "VALUES ('xyz789', 'notes.txt', 'bob', 'files/xyz789.txt', '.txt')"
        )
        cmd_get(db, ["notes.txt"])
        output = capsys.readouterr().out
        assert "notes.txt" in output


class TestCmdHistory:
    def test_no_args_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_history(db, [])

    def test_shows_messages(self, db, capsys):
        db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES ('2025-01-01 12:00', 'alice', 'bob', 'hello bob')"
        )
        cmd_history(db, ["alice"])
        output = capsys.readouterr().out
        assert "hello bob" in output

    def test_with_limit(self, db, capsys):
        for i in range(5):
            db.execute(
                "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, 'alice', 'bob', ?)",
                (f"2025-01-01 12:0{i}", f"msg{i}"),
            )
        cmd_history(db, ["alice", "2"])
        output = capsys.readouterr().out
        assert "last 2" in output

    def test_invalid_limit_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_history(db, ["alice", "notanumber"])


class TestCmdFreshness:
    def test_shows_sessions(self, db, capsys):
        cmd_freshness(db)
        output = capsys.readouterr().out
        assert "alice" in output
        assert "bob" in output

    def test_shows_unread_count(self, db, capsys):
        db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES ('2025-01-01 12:00', 'alice', 'bob', 'test')"
        )
        msg_id = db.scalar("SELECT id FROM messages ORDER BY id DESC LIMIT 1")
        db.execute("INSERT INTO inbox(session, message_id) VALUES ('bob', ?)", (msg_id,))
        cmd_freshness(db)
        output = capsys.readouterr().out
        assert "bob" in output


class TestCmdRelations:
    def test_empty(self, db, capsys):
        cmd_relations(db)
        output = capsys.readouterr().out
        assert "通信关系图" in output

    def test_shows_counts(self, db, capsys):
        for _ in range(3):
            db.execute("INSERT INTO messages(ts, sender, recipient, body) VALUES ('2025-01-01', 'alice', 'bob', 'hi')")
        cmd_relations(db)
        output = capsys.readouterr().out
        assert "alice → bob: 3" in output


class TestCmdPrebuild:
    def test_clean_tree_passes(self, db, capsys):
        with patch("lib.board_view._git", return_value="?? untracked.txt\n"):
            cmd_prebuild(db)
        out = capsys.readouterr().out
        assert "Ready to build" in out

    def test_dirty_tree_exits(self, db, capsys):
        with (
            patch(
                "lib.board_view._git",
                side_effect=lambda pr, *a: (
                    " M lib/something.py\n M lib/other.py" if "status" in a else "abc1234 Some commit"
                ),
            ),
            pytest.raises(SystemExit),
        ):
            cmd_prebuild(db)
        out = capsys.readouterr().out
        assert "FAIL" in out
        assert "NOT ready" in out

    def test_ignores_board_and_untracked(self, db, capsys):
        with patch(
            "lib.board_view._git",
            side_effect=lambda pr, *a: "?? newfile.py\n M board/something" if "status" in a else "abc1234 commit",
        ):
            cmd_prebuild(db)
        out = capsys.readouterr().out
        assert "Ready to build" in out


class TestCmdFiles:
    def test_empty(self, db, capsys):
        cmd_files(db)
        output = capsys.readouterr().out
        assert "(none)" in output

    def test_lists_files(self, db, capsys):
        db.execute(
            "INSERT INTO files(hash, original_name, sender, stored_path, extension) "
            "VALUES ('abc', 'test.txt', 'alice', 'files/abc.txt', '.txt')"
        )
        cmd_files(db)
        output = capsys.readouterr().out
        assert "test.txt" in output
        assert "alice" in output


class TestCmdOverview:
    @patch("lib.board_view.has_session", return_value=False)
    def test_shows_sessions(self, _mock, db, capsys):
        cmd_overview(db)
        output = capsys.readouterr().out
        assert "alice" in output
        assert "bob" in output

    @patch("lib.board_view.has_session", return_value=False)
    def test_shows_recent_messages(self, _mock, db, capsys):
        db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES ('2025-01-01', 'alice', 'bob', 'test msg')"
        )
        cmd_overview(db)
        output = capsys.readouterr().out
        assert "test msg" in output

    @patch("lib.board_view.has_session", return_value=False)
    def test_dispatcher_not_running(self, _mock, db, capsys):
        cmd_overview(db)
        output = capsys.readouterr().out
        assert "No sessions running" in output


class TestCmdView:
    @patch("lib.board_view.has_session", return_value=False)
    @patch("lib.board_view.pane_command", return_value="")
    def test_shows_board(self, _cmd, _has, db, capsys):
        cmd_view(db, "alice")
        output = capsys.readouterr().out
        assert "Board" in output
        assert "Alice" in output or "alice" in output

    @patch("lib.board_view.has_session", return_value=False)
    @patch("lib.board_view.pane_command", return_value="")
    def test_shows_inbox_count(self, _cmd, _has, db, capsys):
        db.execute("INSERT INTO messages(ts, sender, recipient, body) VALUES ('2025-01-01', 'bob', 'alice', 'hi')")
        msg_id = db.scalar("SELECT id FROM messages ORDER BY id DESC LIMIT 1")
        db.execute("INSERT INTO inbox(session, message_id) VALUES ('alice', ?)", (msg_id,))
        cmd_view(db, "alice")
        output = capsys.readouterr().out
        assert "1 条未读" in output


class TestCmdDashboard:
    @patch("lib.board_view.has_session", return_value=False)
    def test_shows_team_status(self, _mock, db, capsys):
        cmd_dashboard(db)
        output = capsys.readouterr().out
        assert "Team Dashboard" in output
        assert "alice" in output

    @patch("lib.board_view.has_session", return_value=False)
    def test_shows_dispatcher_status(self, _mock, db, capsys):
        cmd_dashboard(db)
        output = capsys.readouterr().out
        assert "dispatcher" in output


class TestCmdProgress:
    @patch("lib.board_view.has_session", return_value=False)
    def test_shows_tracked_tasks_and_summary(self, _mock, db, capsys):
        db.execute(
            "INSERT INTO tasks(session, description, status, priority) VALUES ('alice', 'ship queue fix', 'active', 5)"
        )
        db.execute(
            "INSERT INTO tasks(session, description, status, priority) VALUES ('bob', 'write tracker', 'pending', 1)"
        )
        db.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, assignee, description) VALUES "
            "('P1-1', 'P1', 'today', 'alice', 'bob', 'missing tracking')"
        )
        db.execute(
            "INSERT INTO pending_actions(type, command, reason, created_by) VALUES ('merge', 'gh pr merge', 'review', 'alice')"
        )

        cmd_progress(db)
        output = capsys.readouterr().out

        assert "Progress Tracking" in output
        assert "1 active tasks" in output
        assert "1 pending tasks" in output
        assert "ship queue fix" in output
        assert "write tracker" in output
        assert "missing tracking" in output
        assert "pending actions" in output


class TestCmdDirty:
    def test_no_git_repo(self, db, capsys):
        with patch("lib.board_view._git", return_value=""):
            cmd_dirty(db)
        output = capsys.readouterr().out
        assert "clean" in output.lower() or "无" in output or "干净" in output

    def test_shows_dirty_files(self, db, capsys):
        with patch("lib.board_view._git", return_value=" M lib/foo.py\n M lib/bar.py\n"):
            cmd_dirty(db)
        output = capsys.readouterr().out
        assert "foo.py" in output


class TestCmdRoster:
    @patch("lib.board_view.has_session", return_value=False)
    def test_shows_all_sessions(self, _mock, db, capsys):
        cmd_roster(db)
        output = capsys.readouterr().out
        assert "alice" in output
        assert "bob" in output
        assert "charlie" in output
        assert "offline" in output

    @patch("lib.board_view.has_session", return_value=True)
    def test_online_status(self, _mock, db, capsys):
        cmd_roster(db)
        output = capsys.readouterr().out
        assert "online" in output
