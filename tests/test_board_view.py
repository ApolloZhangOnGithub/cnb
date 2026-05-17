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
    _format_age,
    _git,
    _heartbeat_status,
    _pane_work_state,
    _parse_board_time,
    _stall_reason,
    _tmux_status,
    cmd_checkpoint,
    cmd_dashboard,
    cmd_dirty,
    cmd_freshness,
    cmd_overview,
    cmd_p0,
    cmd_prebuild,
    cmd_progress,
    cmd_relations,
    cmd_roster,
    cmd_stalls,
    cmd_view,
)


class TestGit:
    def test_returns_stdout_on_success(self, tmp_path):
        from unittest.mock import MagicMock

        completed = MagicMock(stdout="branch info\n", returncode=0)
        with patch("lib.board_view.subprocess.run", return_value=completed):
            assert _git(tmp_path, "status") == "branch info\n"

    def test_returns_empty_on_timeout(self, tmp_path):
        import subprocess as sp

        with patch("lib.board_view.subprocess.run", side_effect=sp.TimeoutExpired("git", 5)):
            assert _git(tmp_path, "status") == ""

    def test_returns_empty_on_oserror(self, tmp_path):
        with patch("lib.board_view.subprocess.run", side_effect=OSError("git not installed")):
            assert _git(tmp_path, "status") == ""


class TestPaneWorkState:
    @patch("lib.board_view.capture_pane", return_value="some output\nbypass permissions to continue\n❯ ")
    def test_blocked_when_bypass_permissions_prompt(self, _pane):
        assert _pane_work_state("cc-test-alice") == "blocked"

    @patch("lib.board_view.capture_pane", return_value="• Working on something\n")
    def test_working_when_work_label(self, _pane):
        assert _pane_work_state("cc-test-alice") == "working"

    @patch("lib.board_view.capture_pane", return_value="just sitting at the prompt\n❯ ")
    def test_idle_otherwise(self, _pane):
        assert _pane_work_state("cc-test-alice") == "idle"


class TestTmuxStatus:
    @patch("lib.board_view.capture_pane", return_value="bypass permissions\n")
    @patch("lib.board_view.pane_command", return_value="node")
    @patch("lib.board_view.has_session", return_value=True)
    def test_blocked_branch(self, _has, _cmd, _pane):
        status, _ago = _tmux_status("cc", "alice")
        assert status == "● alive blocked"


class TestParseBoardTime:
    def test_parses_with_seconds_format(self):
        assert _parse_board_time("2026-05-17 12:00:00") == datetime(2026, 5, 17, 12, 0, 0)

    def test_falls_back_to_minute_format(self):
        assert _parse_board_time("2026-05-17 12:00") == datetime(2026, 5, 17, 12, 0)

    def test_returns_none_on_invalid(self):
        assert _parse_board_time("not a date") is None

    def test_returns_none_on_empty(self):
        assert _parse_board_time(None) is None
        assert _parse_board_time("") is None


class TestFormatAge:
    def test_unknown_for_none(self):
        assert _format_age(None) == "unknown"

    def test_seconds_under_a_minute(self):
        assert _format_age(45) == "45s"

    def test_minutes_under_an_hour(self):
        assert _format_age(125) == "2m"

    def test_hours_above(self):
        assert _format_age(3660) == "1h"


class TestStallReason:
    def test_returns_none_when_no_unread(self):
        assert _stall_reason("● working", heartbeat_age=999, unread=0, latest_unread_age=999) is None

    def test_working_pane_with_stale_heartbeat_and_old_unread(self):
        reason = _stall_reason("● working", heartbeat_age=999, unread=1, latest_unread_age=999)
        assert reason == "working pane has unread inbox and stale heartbeat"

    def test_alive_pane_with_stale_heartbeat_and_old_unread(self):
        reason = _stall_reason("● alive idle", heartbeat_age=999, unread=1, latest_unread_age=999)
        assert reason == "live pane has unread inbox and stale heartbeat"

    def test_pulse_stale_with_old_unread(self):
        reason = _stall_reason("○ pulse stale", heartbeat_age=999, unread=1, latest_unread_age=999)
        assert reason == "stale heartbeat with unread inbox"

    def test_returns_none_when_heartbeat_fresh(self):
        assert _stall_reason("● working", heartbeat_age=10, unread=1, latest_unread_age=120) is None


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


class TestCmdViewPrompts:
    def test_p0_locked_prompt_uses_absolute_board_path(self, db, capsys):
        roadmap = db.env.project_root / "ROADMAP.md"
        roadmap.write_text("## Status\n端到端状态: 从未验证\n## END\n")

        cmd_view(db, "alice")
        output = capsys.readouterr().out

        assert f"{db.env.install_home}/bin/board p0" in output
        assert "./board" not in output

    def test_unread_prompt_uses_absolute_board_path(self, db, capsys):
        msg_id = db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            ("2026-05-16 08:00:00", "bob", "alice", "ping"),
        )
        db.execute(
            "INSERT INTO inbox(session, message_id, delivered_at, read) VALUES (?, ?, ?, 0)", ("alice", msg_id, "")
        )

        cmd_view(db, "alice")
        output = capsys.readouterr().out

        assert f"{db.env.install_home}/bin/board --as alice inbox" in output
        assert "./board" not in output


class TestCmdStalls:
    def test_no_suspects_when_inbox_empty(self, db, capsys):
        db.execute(
            "UPDATE sessions SET last_heartbeat=?, status='watching' WHERE name='alice'",
            ((datetime.now() - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S"),),
        )

        cmd_stalls(db)

        output = capsys.readouterr().out
        assert "No supervisor stall suspects" in output

    @patch("lib.board_view.capture_pane", return_value="• Working (12m • esc to interrupt)")
    @patch("lib.board_view.pane_command", return_value="node")
    @patch("lib.board_view.has_session", return_value=True)
    def test_flags_live_working_session_with_stale_heartbeat_and_unread(self, _has, _cmd, _pane, db, capsys):
        stale = (datetime.now() - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
        msg_ts = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "UPDATE sessions SET last_heartbeat=?, status='handling Feishu inbound' WHERE name='alice'", (stale,)
        )
        msg_id = db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, 'user', 'alice', 'reply now')",
            (msg_ts,),
        )
        db.execute("INSERT INTO inbox(session, message_id, read) VALUES ('alice', ?, 0)", (msg_id,))

        cmd_stalls(db)

        output = capsys.readouterr().out
        assert "alice" in output
        assert "working pane has unread inbox and stale heartbeat" in output
        assert "restart/replace supervisor" in output

    @patch("lib.board_view.capture_pane", return_value="• Working (12m • esc to interrupt)")
    @patch("lib.board_view.pane_command", return_value="node")
    @patch("lib.board_view.has_session", return_value=True)
    def test_ignores_recent_unread_message(self, _has, _cmd, _pane, db, capsys):
        stale = (datetime.now() - timedelta(minutes=20)).strftime("%Y-%m-%d %H:%M:%S")
        msg_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE sessions SET last_heartbeat=? WHERE name='alice'", (stale,))
        msg_id = db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, 'user', 'alice', 'new')",
            (msg_ts,),
        )
        db.execute("INSERT INTO inbox(session, message_id, read) VALUES ('alice', ?, 0)", (msg_id,))

        cmd_stalls(db)

        output = capsys.readouterr().out
        assert "No supervisor stall suspects" in output


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

    @patch("lib.board_view.has_session", return_value=False)
    def test_truncates_long_status(self, _mock, db, capsys):
        long_status = "x" * 200
        db.execute("UPDATE sessions SET status=? WHERE name='alice'", (long_status,))
        cmd_overview(db)
        output = capsys.readouterr().out
        # Truncated at 60 chars in cmd_overview
        assert "x" * 60 in output
        assert "x" * 70 not in output

    @patch("lib.board_view.has_session", return_value=False)
    def test_shows_unread_count_when_present(self, _mock, db, capsys):
        db.execute("INSERT INTO messages(ts, sender, recipient, body) VALUES ('2025-01-01', 'bob', 'alice', 'hi')")
        msg_id = db.scalar("SELECT id FROM messages ORDER BY id DESC LIMIT 1")
        db.execute("INSERT INTO inbox(session, message_id) VALUES ('alice', ?)", (msg_id,))
        cmd_overview(db)
        output = capsys.readouterr().out
        assert "[1 msg]" in output

    @patch("lib.board_view.has_session", return_value=False)
    def test_shows_heartbeat_ago_when_known(self, _mock, db, capsys):
        recent = (datetime.now() - timedelta(seconds=20)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE sessions SET last_heartbeat=? WHERE name='alice'", (recent,))
        cmd_overview(db)
        output = capsys.readouterr().out
        assert "s ago" in output

    @patch("lib.board_view.has_session", return_value=False)
    def test_shows_open_proposals(self, _mock, db, capsys):
        db.execute(
            "INSERT INTO proposals(number, slug, content, status) VALUES (?, ?, ?, 'OPEN')",
            ("1", "test", "Test proposal"),
        )
        cmd_overview(db)
        output = capsys.readouterr().out
        assert "Open proposals: 1" in output

    def test_dispatcher_running_when_session_present(self, db, capsys):
        prefix = db.env.prefix

        def has_session_mock(sess):
            return sess == f"{prefix}-dispatcher"

        with patch("lib.board_view.has_session", side_effect=has_session_mock):
            cmd_overview(db)
        output = capsys.readouterr().out
        assert "dispatcher: running" in output

    def test_dispatcher_not_running_with_active_sessions(self, db, capsys):
        prefix = db.env.prefix

        def has_session_mock(sess):
            # dispatcher off but alice on
            return sess == f"{prefix}-alice"

        with (
            patch("lib.board_view.has_session", side_effect=has_session_mock),
            patch("lib.board_view.pane_command", return_value="zsh"),
        ):
            cmd_overview(db)
        output = capsys.readouterr().out
        assert "dispatcher: NOT RUNNING" in output


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

    @patch("lib.board_view.has_session", return_value=False)
    @patch("lib.board_view.pane_command", return_value="")
    def test_truncates_long_session_status(self, _cmd, _has, db, capsys):
        long_status = "y" * 200
        db.execute("UPDATE sessions SET status=? WHERE name='alice'", (long_status,))
        cmd_view(db, "alice")
        output = capsys.readouterr().out
        # cmd_view truncates >60 chars to 57 + "..."
        assert "..." in output
        assert "y" * 70 not in output

    @patch("lib.board_view.has_session", return_value=False)
    @patch("lib.board_view.pane_command", return_value="")
    def test_lists_open_proposals(self, _cmd, _has, db, capsys):
        db.execute(
            "INSERT INTO proposals(number, slug, content, status) VALUES (?, ?, ?, 'OPEN')",
            ("7", "feature", "Add feature"),
        )
        cmd_view(db, "alice")
        output = capsys.readouterr().out
        assert "7-feature" in output
        assert "[OPEN]" in output


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

    def test_dispatcher_running_branch(self, db, capsys):
        prefix = db.env.prefix

        def has_session_mock(sess):
            return sess == f"{prefix}-dispatcher"

        with patch("lib.board_view.has_session", side_effect=has_session_mock):
            cmd_dashboard(db)
        output = capsys.readouterr().out
        assert "dispatcher: running" in output


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

    @patch("lib.board_view.has_session", return_value=False)
    def test_empty_lists_show_placeholders(self, _mock, db, capsys):
        db.execute("DELETE FROM sessions WHERE name != 'all'")
        cmd_progress(db)
        output = capsys.readouterr().out
        assert "(no sessions)" in output
        # Active tasks, pending queue and open bugs all empty.
        # Each section prints "  (none)" — assert it appears at least 3 times.
        assert output.count("(none)") >= 3


class TestCmdDirty:
    def test_no_git_repo(self, db, capsys):
        with patch("lib.worktree_checkpoint._git", return_value=None):
            cmd_dirty(db)
        output = capsys.readouterr().out
        assert "Not a git worktree" in output

    def test_shows_dirty_files(self, db, capsys):
        def fake_git(_root, *args):
            if args == ("rev-parse", "--show-toplevel"):
                return str(db.env.project_root)
            if args == ("status", "--porcelain"):
                return " M lib/foo.py\n M lib/bar.py\n"
            return ""

        with patch("lib.worktree_checkpoint._git", side_effect=fake_git):
            cmd_dirty(db)
        output = capsys.readouterr().out
        assert "foo.py" in output
        assert "code/docs change" in output


class TestCmdCheckpoint:
    def test_exits_when_guard_finds_dirty_tree(self, db, capsys):
        def fake_git(_root, *args):
            if args == ("rev-parse", "--show-toplevel"):
                return str(db.env.project_root)
            if args == ("status", "--porcelain"):
                return "?? .env\n"
            return ""

        with patch("lib.worktree_checkpoint._git", side_effect=fake_git), pytest.raises(SystemExit):
            cmd_checkpoint(db)
        output = capsys.readouterr().out
        assert "secret/config risk" in output
        assert "Guard mode" in output

    def test_clean_checkpoint_passes(self, db, capsys):
        def fake_git(_root, *args):
            if args == ("rev-parse", "--show-toplevel"):
                return str(db.env.project_root)
            if args == ("status", "--porcelain"):
                return ""
            return ""

        with patch("lib.worktree_checkpoint._git", side_effect=fake_git):
            cmd_checkpoint(db)
        output = capsys.readouterr().out
        assert "Working tree clean" in output

    def test_shows_board_files_separately(self, db, capsys):
        def git_mock(_root, *args):
            if args == ("rev-parse", "--show-toplevel"):
                return str(db.env.project_root)
            if args == ("status", "--porcelain"):
                return " M lib/foo.py\n M board/things.md\n M board/other.md\n"
            return ""

        with patch("lib.worktree_checkpoint._git", side_effect=git_mock):
            cmd_dirty(db)
        output = capsys.readouterr().out
        assert "board/runtime churn: 2" in output
        assert "foo.py" in output
        assert "code/docs change" in output


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
