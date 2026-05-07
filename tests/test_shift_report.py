"""Tests for lib/shift_report — per-agent shift reports and shift metadata."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from lib.board_db import BoardDB
from lib.shift_report import (
    generate_agent_report,
    generate_shift_meta,
    next_shift_number,
    save_shift_number,
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
        INSERT INTO sessions(name, status) VALUES ('alice', 'working on feature X');
        INSERT INTO sessions(name, status) VALUES ('bob', 'idle');
        INSERT INTO sessions(name, status) VALUES ('all', 'system');
        """
    )
    conn.commit()
    conn.close()
    return BoardDB(db_path)


class TestGenerateAgentReport:
    def test_empty_activity(self, tmp_path):
        board = _setup_db(tmp_path)
        result = generate_agent_report(board, "alice")
        assert "# 日报 — alice" in result
        assert "状态" in result
        assert "working on feature X" in result

    def test_no_activity_message(self, tmp_path):
        board = _setup_db(tmp_path)
        result = generate_agent_report(board, "bob", since=datetime.now() - timedelta(hours=1))
        assert "# 日报 — bob" in result
        assert "idle" in result

    def test_includes_completed_tasks(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO tasks(session,description,status,created_at,done_at) VALUES (?,?,?,?,?)",
                ("alice", "implement notification system", "done", now, now),
            )
        result = generate_agent_report(board, "alice", since=datetime.now() - timedelta(hours=1))
        assert "完成任务" in result
        assert "implement notification system" in result

    def test_includes_pending_tasks(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO tasks(session,description,status,created_at) VALUES (?,?,?,?)",
                ("alice", "review PR #42", "active", now),
            )
        result = generate_agent_report(board, "alice", since=datetime.now() - timedelta(hours=1))
        assert "待办" in result
        assert "review PR #42" in result

    def test_includes_reported_bugs(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO bugs(id,severity,sla,reporter,description,reported_at) VALUES (?,?,?,?,?,?)",
                ("BUG-010", "P1", "1h", "alice", "crash on startup", now),
            )
        result = generate_agent_report(board, "alice", since=datetime.now() - timedelta(hours=1))
        assert "报告 Bug" in result
        assert "BUG-010" in result

    def test_includes_fixed_bugs(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO bugs(id,severity,sla,reporter,assignee,description,reported_at,status,fixed_at) VALUES (?,?,?,?,?,?,?,?,?)",
                ("BUG-011", "P2", "4h", "bob", "alice", "nav broken", now, "FIXED", now),
            )
        result = generate_agent_report(board, "alice", since=datetime.now() - timedelta(hours=1))
        assert "修复 Bug" in result
        assert "BUG-011" in result

    def test_includes_message_count(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            for i in range(5):
                c.execute(
                    "INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)",
                    (now, "alice", "all", f"msg{i}"),
                )
        result = generate_agent_report(board, "alice", since=datetime.now() - timedelta(hours=1))
        assert "消息" in result
        assert "发送 5 条" in result

    def test_includes_kudos_received(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO kudos(sender,target,reason,ts) VALUES (?,?,?,?)", ("bob", "alice", "great work", now)
            )
        result = generate_agent_report(board, "alice", since=datetime.now() - timedelta(hours=1))
        assert "获得 Kudos" in result
        assert "bob" in result
        assert "great work" in result

    @patch("lib.shift_report._git_commits_by_author", return_value=["abc1234 fix bug", "def5678 add test"])
    def test_includes_git_commits(self, mock_git, tmp_path):
        board = _setup_db(tmp_path)
        result = generate_agent_report(board, "alice", since=datetime.now() - timedelta(hours=1), project_root=tmp_path)
        assert "Git Commits (2)" in result
        assert "fix bug" in result

    def test_header_format(self, tmp_path):
        board = _setup_db(tmp_path)
        result = generate_agent_report(board, "alice")
        assert result.startswith("# 日报 — alice —")
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in result

    def test_excludes_other_sessions_tasks(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO tasks(session,description,status,created_at,done_at) VALUES (?,?,?,?,?)",
                ("bob", "bob task", "done", now, now),
            )
        result = generate_agent_report(board, "alice", since=datetime.now() - timedelta(hours=1))
        assert "bob task" not in result


class TestGenerateShiftMeta:
    def test_basic_structure(self, tmp_path):
        board = _setup_db(tmp_path)
        started = datetime.now() - timedelta(hours=3)
        ended = datetime.now()
        result = generate_shift_meta(board, 1, started, ended, participants=["alice", "bob"])
        assert "shift: 1" in result
        assert "# Shift 001" in result
        assert "alice" in result
        assert "bob" in result

    def test_includes_frontmatter(self, tmp_path):
        board = _setup_db(tmp_path)
        started = datetime.now() - timedelta(hours=3)
        ended = datetime.now()
        result = generate_shift_meta(board, 2, started, ended, participants=["alice"])
        assert result.startswith("---\n")
        assert "shift: 2" in result
        assert "started:" in result
        assert "ended:" in result

    def test_includes_task_counts(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO tasks(session,description,status,created_at,done_at) VALUES (?,?,?,?,?)",
                ("alice", "done task", "done", now, now),
            )
        started = datetime.now() - timedelta(hours=1)
        result = generate_shift_meta(board, 1, started, participants=["alice", "bob"])
        assert "| alice |" in result

    def test_includes_bugs(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO bugs(id,severity,sla,reporter,description,reported_at) VALUES (?,?,?,?,?,?)",
                ("BUG-M1", "P1", "1h", "alice", "crash", now),
            )
        started = datetime.now() - timedelta(hours=1)
        result = generate_shift_meta(board, 1, started, participants=["alice"])
        assert "Bug" in result
        assert "新增: 1" in result

    def test_auto_discovers_participants(self, tmp_path):
        board = _setup_db(tmp_path)
        started = datetime.now() - timedelta(hours=1)
        result = generate_shift_meta(board, 1, started)
        assert "alice" in result
        assert "bob" in result

    @patch("lib.shift_report._git_commits_all", return_value=["abc fix", "def add"])
    def test_includes_total_commits(self, mock_git, tmp_path):
        board = _setup_db(tmp_path)
        started = datetime.now() - timedelta(hours=1)
        result = generate_shift_meta(board, 1, started, participants=["alice"], project_root=tmp_path)
        assert "总 Commits: 2" in result


class TestShiftNumber:
    def test_default_is_one(self, tmp_path):
        assert next_shift_number(tmp_path) == 1

    def test_reads_from_file(self, tmp_path):
        (tmp_path / ".next_shift").write_text("5\n")
        assert next_shift_number(tmp_path) == 5

    def test_falls_back_to_dirs(self, tmp_path):
        (tmp_path / "001").mkdir()
        (tmp_path / "003").mkdir()
        assert next_shift_number(tmp_path) == 4

    def test_save_increments(self, tmp_path):
        save_shift_number(tmp_path, 3)
        assert (tmp_path / ".next_shift").read_text().strip() == "4"

    def test_invalid_file_content(self, tmp_path):
        (tmp_path / ".next_shift").write_text("not a number\n")
        assert next_shift_number(tmp_path) == 1

    def test_roundtrip(self, tmp_path):
        save_shift_number(tmp_path, 7)
        assert next_shift_number(tmp_path) == 8
