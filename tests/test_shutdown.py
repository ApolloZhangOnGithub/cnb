"""Tests for lib/shutdown — shutdown flow orchestration."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.board_db import BoardDB
from lib.shutdown import (
    _active_sessions,
    _unread_count,
    broadcast_shutdown,
    collect_reports,
    run_shutdown,
    save_shift,
    stop_dispatcher_session,
    wait_for_acks,
)


def _setup_db(tmp_path: Path) -> BoardDB:
    db_path = tmp_path / "board.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE sessions(name TEXT PRIMARY KEY, status TEXT DEFAULT '',
            persona TEXT DEFAULT '', updated_at TEXT DEFAULT '', last_heartbeat TEXT DEFAULT NULL);
        CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL, sender TEXT NOT NULL, recipient TEXT NOT NULL,
            body TEXT NOT NULL, attachment TEXT DEFAULT NULL);
        CREATE TABLE bugs(id TEXT PRIMARY KEY, severity TEXT NOT NULL, sla TEXT NOT NULL,
            reporter TEXT NOT NULL, assignee TEXT DEFAULT '', status TEXT DEFAULT 'OPEN',
            description TEXT NOT NULL,
            reported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
            fixed_at TEXT DEFAULT NULL, evidence TEXT DEFAULT NULL);
        CREATE TABLE tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,
            session TEXT NOT NULL, description TEXT NOT NULL,
            status TEXT DEFAULT 'pending', priority INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT '', done_at TEXT DEFAULT NULL);
        CREATE TABLE kudos(id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL, target TEXT NOT NULL, reason TEXT NOT NULL,
            evidence TEXT DEFAULT NULL, ts TEXT NOT NULL DEFAULT '');
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE inbox(id INTEGER PRIMARY KEY, session TEXT, message_id INTEGER,
            delivered_at TEXT DEFAULT '', read INTEGER DEFAULT 0);
        INSERT INTO sessions(name, status) VALUES ('alice', 'working');
        INSERT INTO sessions(name, status) VALUES ('bob', 'idle');
        INSERT INTO sessions(name, status) VALUES ('all', 'system');
        INSERT INTO sessions(name, status) VALUES ('dispatcher', 'running');
        """
    )
    conn.commit()
    conn.close()
    return BoardDB(db_path)


class TestActiveSessions:
    def test_excludes_system(self, tmp_path):
        board = _setup_db(tmp_path)
        result = _active_sessions(board)
        assert "all" not in result
        assert "dispatcher" not in result

    def test_includes_agents(self, tmp_path):
        board = _setup_db(tmp_path)
        result = _active_sessions(board)
        assert "alice" in result
        assert "bob" in result

    def test_sorted(self, tmp_path):
        board = _setup_db(tmp_path)
        result = _active_sessions(board)
        assert result == sorted(result)

    def test_roster_excludes_historical_sessions(self, tmp_path):
        board = _setup_db(tmp_path)
        board.execute("INSERT INTO sessions(name, status) VALUES ('ghost', 'old')")
        result = _active_sessions(board, ["bob", "alice"])
        assert result == ["bob", "alice"]

    def test_roster_excludes_unregistered_and_system_sessions(self, tmp_path):
        board = _setup_db(tmp_path)
        result = _active_sessions(board, ["alice", "dispatcher", "missing", "all", "alice"])
        assert result == ["alice"]


class TestUnreadCount:
    def test_empty(self, tmp_path):
        board = _setup_db(tmp_path)
        assert _unread_count(board, "alice") == 0

    def test_with_unread(self, tmp_path):
        board = _setup_db(tmp_path)
        with board.conn() as c:
            c.execute("INSERT INTO inbox(session, message_id, read) VALUES ('alice', 1, 0)")
            c.execute("INSERT INTO inbox(session, message_id, read) VALUES ('alice', 2, 0)")
            c.execute("INSERT INTO inbox(session, message_id, read) VALUES ('alice', 3, 1)")
        assert _unread_count(board, "alice") == 2

    def test_other_session(self, tmp_path):
        board = _setup_db(tmp_path)
        with board.conn() as c:
            c.execute("INSERT INTO inbox(session, message_id, read) VALUES ('alice', 1, 0)")
        assert _unread_count(board, "bob") == 0


class TestBroadcastShutdown:
    @patch("lib.shutdown.subprocess.run")
    def test_sends_to_current_sessions_only(self, mock_run, tmp_path):
        broadcast_shutdown("/bin/board", "dispatcher", ["alice", "bob"])
        assert mock_run.call_count == 2
        recipients = [call.args[0][4] for call in mock_run.call_args_list]
        assert recipients == ["alice", "bob"]
        assert "all" not in recipients

    @patch("lib.shutdown.subprocess.run", side_effect=OSError("fail"))
    def test_handles_error(self, mock_run, tmp_path):
        broadcast_shutdown("/bin/board", "dispatcher", ["alice"])


class TestStopDispatcherSession:
    def test_skips_when_not_running(self, tmp_path):
        class Backend:
            def is_running(self, prefix, name):
                return False

        cfg = type(
            "Cfg",
            (),
            {"env": type("Env", (), {"prefix": "cc-test"})(), "install_home": tmp_path, "backend": Backend()},
        )()
        assert stop_dispatcher_session(cfg) is False

    def test_stops_dispatcher_session(self, tmp_path):
        calls = []

        class Backend:
            def is_running(self, prefix, name):
                return True

            def stop_session(self, prefix, name, save_cmd):
                calls.append((prefix, name, save_cmd))

        cfg = type(
            "Cfg",
            (),
            {"env": type("Env", (), {"prefix": "cc-test"})(), "install_home": tmp_path, "backend": Backend()},
        )()
        assert stop_dispatcher_session(cfg) is True
        assert calls == [
            (
                "cc-test",
                "dispatcher",
                f"'{tmp_path / 'bin' / 'board'}' --as dispatcher status 'shutdown: dispatcher stopped'",
            )
        ]


class TestWaitForAcks:
    def test_all_already_acked(self, tmp_path):
        board = _setup_db(tmp_path)
        acked, timed_out = wait_for_acks(board, ["alice", "bob"], timeout=1, poll_interval=1)
        assert set(acked) == {"alice", "bob"}
        assert timed_out == []

    def test_timeout_with_unread(self, tmp_path):
        board = _setup_db(tmp_path)
        with board.conn() as c:
            c.execute("INSERT INTO inbox(session, message_id, read) VALUES ('bob', 1, 0)")
        acked, timed_out = wait_for_acks(board, ["alice", "bob"], timeout=1, poll_interval=1)
        assert "alice" in acked
        assert "bob" in timed_out


class TestCollectReports:
    def test_generates_for_all(self, tmp_path):
        board = _setup_db(tmp_path)
        reports = collect_reports(board, ["alice", "bob"], since=datetime.now() - timedelta(hours=1))
        assert "alice" in reports
        assert "bob" in reports
        assert "# 日报 — alice" in reports["alice"]
        assert "# 日报 — bob" in reports["bob"]

    def test_with_project_root(self, tmp_path):
        board = _setup_db(tmp_path)
        with patch("lib.shift_report._git_commits_by_author", return_value=["abc fix"]):
            reports = collect_reports(
                board, ["alice"], since=datetime.now() - timedelta(hours=1), project_root=tmp_path
            )
        assert "Git Commits" in reports["alice"]


class TestSaveShift:
    def test_creates_directory(self, tmp_path):
        dailies = tmp_path / "dailies"
        dailies.mkdir()
        reports = {"alice": "# alice report", "bob": "# bob report"}
        meta = "# meta"
        shift_dir = save_shift(dailies, 1, reports, meta)
        assert shift_dir.exists()
        assert (shift_dir / "_meta.md").read_text() == "# meta"
        assert (shift_dir / "alice.md").read_text() == "# alice report"
        assert (shift_dir / "bob.md").read_text() == "# bob report"

    def test_zero_padded_name(self, tmp_path):
        dailies = tmp_path / "dailies"
        dailies.mkdir()
        shift_dir = save_shift(dailies, 5, {}, "meta")
        assert shift_dir.name == "005"

    def test_overwrites_existing(self, tmp_path):
        dailies = tmp_path / "dailies"
        (dailies / "001").mkdir(parents=True)
        (dailies / "001" / "_meta.md").write_text("old")
        shift_dir = save_shift(dailies, 1, {}, "new meta")
        assert (shift_dir / "_meta.md").read_text() == "new meta"


class TestRunShutdown:
    def _make_env(self, tmp_path):
        from lib.common import ClaudesEnv

        cd = tmp_path / ".claudes"
        cd.mkdir(exist_ok=True)
        (cd / "sessions").mkdir(exist_ok=True)
        (cd / "cv").mkdir(exist_ok=True)
        (cd / "logs").mkdir(exist_ok=True)

        return ClaudesEnv(
            claudes_dir=cd,
            project_root=tmp_path,
            install_home=Path(__file__).parent.parent,
            board_db=cd / "board.db",
            sessions_dir=cd / "sessions",
            cv_dir=cd / "cv",
            log_dir=cd / "logs",
            prefix="test",
            sessions=["alice", "bob"],
            suspended_file=cd / "suspended",
            attendance_log=cd / "logs" / "attendance.log",
        )

    def test_missing_db_exits(self, tmp_path):
        env = self._make_env(tmp_path)
        with pytest.raises(SystemExit) as exc:
            run_shutdown(env)
        assert exc.value.code == 1

    def test_no_sessions_returns_none(self, tmp_path):
        env = self._make_env(tmp_path)
        db_path = env.board_db
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            """
            CREATE TABLE sessions(name TEXT PRIMARY KEY, status TEXT DEFAULT '',
                persona TEXT DEFAULT '', updated_at TEXT DEFAULT '', last_heartbeat TEXT DEFAULT NULL);
            CREATE TABLE inbox(id INTEGER PRIMARY KEY, session TEXT, message_id INTEGER,
                delivered_at TEXT DEFAULT '', read INTEGER DEFAULT 0);
            INSERT INTO sessions(name) VALUES ('all');
            INSERT INTO sessions(name) VALUES ('dispatcher');
            """
        )
        conn.commit()
        conn.close()
        result = run_shutdown(env, skip_broadcast=True, skip_stop=True)
        assert result is None

    def test_dry_run(self, tmp_path, capsys):
        env = self._make_env(tmp_path)
        _setup_db_at(env.board_db)
        result = run_shutdown(env, dry_run=True)
        assert result is None
        out = capsys.readouterr().out
        assert "DRY RUN" in out
        assert "alice" in out

    @patch("lib.shutdown.subprocess.run")
    def test_full_flow_skip_stop(self, mock_run, tmp_path, capsys):
        env = self._make_env(tmp_path)
        _setup_db_at(env.board_db)
        shift_dir = run_shutdown(env, skip_broadcast=True, skip_stop=True, timeout=1)
        assert shift_dir is not None
        assert shift_dir.exists()
        assert (shift_dir / "_meta.md").exists()
        assert (shift_dir / "alice.md").exists()
        assert (shift_dir / "bob.md").exists()
        out = capsys.readouterr().out
        assert "收工完成" in out

    def test_uses_config_roster_for_reports(self, tmp_path):
        env = self._make_env(tmp_path)
        _setup_db_at(env.board_db)
        conn = sqlite3.connect(str(env.board_db))
        conn.execute("INSERT INTO sessions(name, status) VALUES ('legacy', 'old')")
        conn.commit()
        conn.close()

        shift_dir = run_shutdown(env, skip_broadcast=True, skip_stop=True, timeout=1)
        assert shift_dir is not None
        assert (shift_dir / "alice.md").exists()
        assert (shift_dir / "bob.md").exists()
        assert not (shift_dir / "legacy.md").exists()

    @patch("lib.shutdown.subprocess.run")
    def test_increments_shift_number(self, mock_run, tmp_path):
        env = self._make_env(tmp_path)
        _setup_db_at(env.board_db)
        dailies = env.claudes_dir / "dailies"
        dailies.mkdir(exist_ok=True)
        run_shutdown(env, skip_broadcast=True, skip_stop=True, timeout=1)
        marker = dailies / ".next_shift"
        assert marker.exists()
        assert marker.read_text().strip() == "2"


def _setup_db_at(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE sessions(name TEXT PRIMARY KEY, status TEXT DEFAULT '',
            persona TEXT DEFAULT '', updated_at TEXT DEFAULT '', last_heartbeat TEXT DEFAULT NULL);
        CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL, sender TEXT NOT NULL, recipient TEXT NOT NULL,
            body TEXT NOT NULL, attachment TEXT DEFAULT NULL);
        CREATE TABLE bugs(id TEXT PRIMARY KEY, severity TEXT NOT NULL, sla TEXT NOT NULL,
            reporter TEXT NOT NULL, assignee TEXT DEFAULT '', status TEXT DEFAULT 'OPEN',
            description TEXT NOT NULL,
            reported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
            fixed_at TEXT DEFAULT NULL, evidence TEXT DEFAULT NULL);
        CREATE TABLE tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,
            session TEXT NOT NULL, description TEXT NOT NULL,
            status TEXT DEFAULT 'pending', priority INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT '', done_at TEXT DEFAULT NULL);
        CREATE TABLE kudos(id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL, target TEXT NOT NULL, reason TEXT NOT NULL,
            evidence TEXT DEFAULT NULL, ts TEXT NOT NULL DEFAULT '');
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE inbox(id INTEGER PRIMARY KEY, session TEXT, message_id INTEGER,
            delivered_at TEXT DEFAULT '', read INTEGER DEFAULT 0);
        INSERT INTO sessions(name, status) VALUES ('alice', 'working');
        INSERT INTO sessions(name, status) VALUES ('bob', 'idle');
        INSERT INTO sessions(name, status) VALUES ('all', 'system');
        INSERT INTO sessions(name, status) VALUES ('dispatcher', 'running');
        """
    )
    conn.commit()
    conn.close()
