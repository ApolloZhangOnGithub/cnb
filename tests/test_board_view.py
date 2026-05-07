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

from lib.board_view import (
    _heartbeat_status,
    cmd_files,
    cmd_freshness,
    cmd_get,
    cmd_history,
    cmd_p0,
    cmd_prebuild,
    cmd_relations,
)


class TestHeartbeatStatus:
    def _hb(self, seconds_ago: int) -> str:
        return (datetime.now() - timedelta(seconds=seconds_ago)).strftime("%Y-%m-%d %H:%M:%S")

    @patch("lib.board_view.has_session", return_value=False)
    def test_active(self, _mock):
        status, _ago = _heartbeat_status(self._hb(30), "cc", "alice")
        assert "active" in status

    @patch("lib.board_view.has_session", return_value=False)
    def test_thinking(self, _mock):
        status, _ago = _heartbeat_status(self._hb(150), "cc", "alice")
        assert "thinking" in status

    @patch("lib.board_view.has_session", return_value=False)
    def test_stale(self, _mock):
        status, _ago = _heartbeat_status(self._hb(300), "cc", "alice")
        assert "stale" in status

    @patch("lib.board_view.has_session", return_value=False)
    def test_offline_old_heartbeat(self, _mock):
        status, ago = _heartbeat_status(self._hb(3600), "cc", "alice")
        assert "offline" in status
        assert "h ago" in ago

    @patch("lib.board_view.has_session", return_value=False)
    def test_no_heartbeat_no_tmux(self, _mock):
        status, _ = _heartbeat_status(None, "cc", "alice")
        assert "offline" in status

    @patch("lib.board_view.pane_command", return_value="node")
    @patch("lib.board_view.has_session", return_value=True)
    def test_no_heartbeat_tmux_running(self, _has, _cmd):
        status, _ = _heartbeat_status(None, "cc", "alice")
        assert "running" in status

    @patch("lib.board_view.pane_command", return_value="zsh")
    @patch("lib.board_view.has_session", return_value=True)
    def test_no_heartbeat_tmux_dead(self, _has, _cmd):
        status, _ = _heartbeat_status(None, "cc", "alice")
        assert "dead" in status

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
