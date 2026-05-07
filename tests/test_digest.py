"""Tests for lib/digest — daily activity summary generation."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from lib.board_db import BoardDB
from lib.digest import generate_daily_digest, generate_weekly_report


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
        INSERT INTO sessions(name) VALUES ('alice');
        INSERT INTO sessions(name) VALUES ('bob');
        """
    )
    conn.commit()
    conn.close()
    return BoardDB(db_path)


class TestGenerateDailyDigest:
    def test_empty_activity(self, tmp_path):
        board = _setup_db(tmp_path)
        result = generate_daily_digest(board)
        assert "无活动" in result

    def test_includes_messages(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute("INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)", (now, "alice", "all", "hello"))
            c.execute("INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)", (now, "bob", "all", "hi"))
        result = generate_daily_digest(board)
        assert "消息: 2 条" in result
        assert "alice" in result

    def test_includes_new_bugs(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO bugs(id,severity,sla,reporter,description,reported_at) VALUES (?,?,?,?,?,?)",
                ("BUG-1", "P1", "1h", "alice", "crash on login", now),
            )
        result = generate_daily_digest(board)
        assert "新 Bug: 1 个" in result
        assert "crash on login" in result

    def test_includes_fixed_bugs(self, tmp_path):
        board = _setup_db(tmp_path)
        yesterday = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO bugs(id,severity,sla,reporter,assignee,description,reported_at,status,fixed_at) VALUES (?,?,?,?,?,?,?,?,?)",
                ("BUG-2", "P2", "4h", "alice", "bob", "nav broken", yesterday, "FIXED", now),
            )
        result = generate_daily_digest(board)
        assert "修复: 1 个" in result
        assert "bob" in result

    def test_includes_completed_tasks(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO tasks(session,description,status,created_at,done_at) VALUES (?,?,?,?,?)",
                ("alice", "implement feature X", "done", now, now),
            )
        result = generate_daily_digest(board)
        assert "完成任务: 1 个" in result
        assert "implement feature X" in result

    def test_includes_kudos(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO kudos(sender,target,reason,ts) VALUES (?,?,?,?)",
                ("alice", "bob", "great fix", now),
            )
        result = generate_daily_digest(board)
        assert "Kudos: 1 个" in result
        assert "alice" in result and "bob" in result

    def test_custom_since(self, tmp_path):
        board = _setup_db(tmp_path)
        old = (datetime.now() - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
        recent = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute("INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)", (old, "alice", "all", "old"))
            c.execute(
                "INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)", (recent, "bob", "all", "recent")
            )

        result_24h = generate_daily_digest(board)
        assert "消息: 1 条" in result_24h

        result_all = generate_daily_digest(board, since=datetime.now() - timedelta(hours=72))
        assert "消息: 2 条" in result_all

    def test_header_format(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute("INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)", (now, "alice", "all", "msg"))
        result = generate_daily_digest(board)
        assert result.startswith("[Daily Digest]")
        assert "活动摘要" in result

    def test_excludes_old_activity(self, tmp_path):
        board = _setup_db(tmp_path)
        old = (datetime.now() - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute("INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)", (old, "alice", "all", "old"))
        result = generate_daily_digest(board)
        assert "无活动" in result


class TestDigestEdgeCases:
    def test_top_senders_ranked(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            for _ in range(5):
                c.execute("INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)", (now, "alice", "all", "x"))
            for _ in range(2):
                c.execute("INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)", (now, "bob", "all", "y"))
        result = generate_daily_digest(board)
        assert "alice(5)" in result
        assert "bob(2)" in result
        alice_pos = result.index("alice(5)")
        bob_pos = result.index("bob(2)")
        assert alice_pos < bob_pos

    def test_pending_tasks_excluded(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO tasks(session,description,status,created_at) VALUES (?,?,?,?)",
                ("alice", "still working", "pending", now),
            )
            c.execute(
                "INSERT INTO tasks(session,description,status,created_at) VALUES (?,?,?,?)",
                ("bob", "in progress", "active", now),
            )
        result = generate_daily_digest(board)
        assert "完成任务" not in result

    def test_bug_description_truncated_at_40(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        long_desc = "X" * 80
        with board.conn() as c:
            c.execute(
                "INSERT INTO bugs(id,severity,sla,reporter,description,reported_at) VALUES (?,?,?,?,?,?)",
                ("BUG-T", "P1", "1h", "alice", long_desc, now),
            )
        result = generate_daily_digest(board)
        assert "X" * 40 in result
        assert "X" * 41 not in result

    def test_task_description_truncated_at_50(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        long_desc = "Y" * 80
        with board.conn() as c:
            c.execute(
                "INSERT INTO tasks(session,description,status,created_at,done_at) VALUES (?,?,?,?,?)",
                ("alice", long_desc, "done", now, now),
            )
        result = generate_daily_digest(board)
        assert "Y" * 50 in result
        assert "Y" * 51 not in result

    def test_kudos_reason_truncated_at_40(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        long_reason = "Z" * 80
        with board.conn() as c:
            c.execute(
                "INSERT INTO kudos(sender,target,reason,ts) VALUES (?,?,?,?)",
                ("alice", "bob", long_reason, now),
            )
        result = generate_daily_digest(board)
        assert "Z" * 40 in result
        assert "Z" * 41 not in result

    def test_all_sections_present(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute("INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)", (now, "alice", "bob", "hi"))
            c.execute(
                "INSERT INTO bugs(id,severity,sla,reporter,description,reported_at) VALUES (?,?,?,?,?,?)",
                ("B-ALL", "P1", "1h", "alice", "bug", now),
            )
            c.execute(
                "INSERT INTO bugs(id,severity,sla,reporter,assignee,description,reported_at,status,fixed_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                ("B-FIX", "P2", "4h", "bob", "alice", "fixed bug", now, "FIXED", now),
            )
            c.execute(
                "INSERT INTO tasks(session,description,status,created_at,done_at) VALUES (?,?,?,?,?)",
                ("alice", "done task", "done", now, now),
            )
            c.execute("INSERT INTO kudos(sender,target,reason,ts) VALUES (?,?,?,?)", ("bob", "alice", "nice", now))
        result = generate_daily_digest(board)
        assert "消息:" in result
        assert "新 Bug:" in result
        assert "修复:" in result
        assert "完成任务:" in result
        assert "Kudos:" in result

    def test_closed_bugs_not_in_new_bugs(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO bugs(id,severity,sla,reporter,description,reported_at,status,fixed_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                ("B-CLOSED", "P1", "1h", "alice", "already fixed", now, "FIXED", now),
            )
        result = generate_daily_digest(board)
        assert "新 Bug" not in result
        assert "修复: 1 个" in result


class TestGenerateWeeklyReport:
    def test_empty_activity(self, tmp_path):
        board = _setup_db(tmp_path)
        result = generate_weekly_report(board)
        assert "[Weekly Report]" in result
        assert "无活动" in result

    def test_includes_message_count(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            for i in range(10):
                c.execute(
                    "INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)",
                    (now, "alice", "all", f"msg{i}"),
                )
        result = generate_weekly_report(board)
        assert "消息总计: 10 条" in result
        assert "alice(10)" in result

    def test_includes_bug_summary(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO bugs(id,severity,sla,reporter,description,reported_at) VALUES (?,?,?,?,?,?)",
                ("BUG-W1", "P1", "1h", "alice", "new bug", now),
            )
            c.execute(
                "INSERT INTO bugs(id,severity,sla,reporter,assignee,description,reported_at,status,fixed_at) VALUES (?,?,?,?,?,?,?,?,?)",
                ("BUG-W2", "P2", "4h", "bob", "alice", "fixed", now, "FIXED", now),
            )
        result = generate_weekly_report(board)
        assert "Bug: 新增 1, 修复 1" in result

    def test_includes_task_summary(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute(
                "INSERT INTO tasks(session,description,status,created_at,done_at) VALUES (?,?,?,?,?)",
                ("alice", "done task", "done", now, now),
            )
            c.execute(
                "INSERT INTO tasks(session,description,status,created_at) VALUES (?,?,?,?)",
                ("bob", "pending task", "pending", now),
            )
        result = generate_weekly_report(board)
        assert "任务: 完成 1, 待办 1" in result

    def test_includes_top_completers(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            for i in range(3):
                c.execute(
                    "INSERT INTO tasks(session,description,status,created_at,done_at) VALUES (?,?,?,?,?)",
                    ("alice", f"task{i}", "done", now, now),
                )
            c.execute(
                "INSERT INTO tasks(session,description,status,created_at,done_at) VALUES (?,?,?,?,?)",
                ("bob", "task", "done", now, now),
            )
        result = generate_weekly_report(board)
        assert "完成排行:" in result
        assert "alice(3)" in result
        assert "bob(1)" in result

    def test_includes_kudos_summary(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute("INSERT INTO kudos(sender,target,reason,ts) VALUES (?,?,?,?)", ("alice", "bob", "great", now))
            c.execute("INSERT INTO kudos(sender,target,reason,ts) VALUES (?,?,?,?)", ("bob", "alice", "nice", now))
        result = generate_weekly_report(board)
        assert "Kudos: 2 个" in result

    def test_custom_since(self, tmp_path):
        board = _setup_db(tmp_path)
        old = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        recent = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute("INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)", (old, "alice", "all", "old"))
            c.execute("INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)", (recent, "bob", "all", "new"))
        result_7d = generate_weekly_report(board)
        assert "消息总计: 1 条" in result_7d
        result_all = generate_weekly_report(board, since=datetime.now() - timedelta(days=30))
        assert "消息总计: 2 条" in result_all

    def test_header_format(self, tmp_path):
        board = _setup_db(tmp_path)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with board.conn() as c:
            c.execute("INSERT INTO messages(ts,sender,recipient,body) VALUES (?,?,?,?)", (now, "alice", "all", "msg"))
        result = generate_weekly_report(board)
        assert result.startswith("[Weekly Report]")
        assert "周报" in result
