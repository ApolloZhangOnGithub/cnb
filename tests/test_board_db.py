"""Tests for lib/board_db.py — BoardDB wrapper and deliver_to_inbox."""

import sqlite3
from pathlib import Path

import pytest

from lib.board_db import BoardDB, inbox_delivered

SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"


def _init_db(tmp_path: Path, sessions: list[str] | None = None) -> Path:
    """Create a board.db with schema + sessions. Returns db path."""
    sessions = sessions or ["alice", "bob", "charlie"]
    db_path = tmp_path / "board.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_PATH.read_text())
    for name in sessions:
        conn.execute("INSERT INTO sessions(name) VALUES (?)", (name,))
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '6')")
    conn.commit()
    conn.close()
    return db_path


# ===========================================================================
# Construction
# ===========================================================================


class TestBoardDBInit:
    def test_accepts_path(self, tmp_path):
        db_path = _init_db(tmp_path)
        db = BoardDB(db_path)
        assert db.db_path == db_path
        assert db.env is None

    def test_accepts_string_path(self, tmp_path):
        db_path = _init_db(tmp_path)
        db = BoardDB(str(db_path))
        assert db.db_path == db_path

    def test_missing_db_with_env_exits(self, tmp_path):
        from lib.common import ClaudesEnv

        cd = tmp_path / ".claudes"
        cd.mkdir()
        env = ClaudesEnv(
            claudes_dir=cd,
            project_root=tmp_path,
            install_home=Path(__file__).parent.parent,
            board_db=cd / "nonexistent.db",
            sessions_dir=cd / "sessions",
            cv_dir=cd / "cv",
            log_dir=cd / "logs",
            prefix="cc-test",
            sessions=["alice"],
            suspended_file=cd / "suspended",
            attendance_log=cd / "logs" / "attendance.log",
        )
        with pytest.raises(SystemExit):
            BoardDB(env)


# ===========================================================================
# Connection context manager
# ===========================================================================


class TestConn:
    def test_commits_on_success(self, tmp_path):
        db_path = _init_db(tmp_path)
        db = BoardDB(db_path)
        with db.conn() as c:
            c.execute("INSERT INTO sessions(name) VALUES ('dave')")

        result = db.scalar("SELECT COUNT(*) FROM sessions WHERE name='dave'")
        assert result == 1

    def test_rolls_back_on_exception(self, tmp_path):
        db_path = _init_db(tmp_path)
        db = BoardDB(db_path)
        with pytest.raises(ValueError), db.conn() as c:
            c.execute("INSERT INTO sessions(name) VALUES ('eve')")
            raise ValueError("test error")

        result = db.scalar("SELECT COUNT(*) FROM sessions WHERE name='eve'")
        assert result == 0

    def test_wal_mode_enabled(self, tmp_path):
        db_path = _init_db(tmp_path)
        db = BoardDB(db_path)
        with db.conn() as c:
            mode = c.execute("PRAGMA journal_mode").fetchone()[0]
            assert mode == "wal"

    def test_foreign_keys_enabled(self, tmp_path):
        db_path = _init_db(tmp_path)
        db = BoardDB(db_path)
        with db.conn() as c:
            fk = c.execute("PRAGMA foreign_keys").fetchone()[0]
            assert fk == 1

    def test_row_factory_is_row(self, tmp_path):
        db_path = _init_db(tmp_path)
        db = BoardDB(db_path)
        with db.conn() as c:
            assert c.row_factory == sqlite3.Row


# ===========================================================================
# query / query_one / scalar / execute / execute_changes
# ===========================================================================


class TestQueryMethods:
    def test_query_returns_list(self, tmp_path):
        db_path = _init_db(tmp_path, ["alice", "bob"])
        db = BoardDB(db_path)
        rows = db.query("SELECT name FROM sessions ORDER BY name")
        names = [r["name"] for r in rows]
        assert "alice" in names
        assert "bob" in names

    def test_query_with_params(self, tmp_path):
        db_path = _init_db(tmp_path, ["alice", "bob"])
        db = BoardDB(db_path)
        rows = db.query("SELECT name FROM sessions WHERE name=?", ("alice",))
        assert len(rows) == 1
        assert rows[0]["name"] == "alice"

    def test_query_with_connection(self, tmp_path):
        db_path = _init_db(tmp_path, ["alice"])
        db = BoardDB(db_path)
        with db.conn() as c:
            rows = db.query("SELECT name FROM sessions", c=c)
            assert len(rows) >= 1

    def test_query_one_returns_row(self, tmp_path):
        db_path = _init_db(tmp_path, ["alice"])
        db = BoardDB(db_path)
        row = db.query_one("SELECT name FROM sessions WHERE name=?", ("alice",))
        assert row is not None
        assert row["name"] == "alice"

    def test_query_one_returns_none(self, tmp_path):
        db_path = _init_db(tmp_path)
        db = BoardDB(db_path)
        row = db.query_one("SELECT name FROM sessions WHERE name=?", ("nonexistent",))
        assert row is None

    def test_scalar_returns_value(self, tmp_path):
        db_path = _init_db(tmp_path, ["alice", "bob"])
        db = BoardDB(db_path)
        count = db.scalar("SELECT COUNT(*) FROM sessions")
        assert count == 2

    def test_scalar_returns_none_when_empty(self, tmp_path):
        db_path = _init_db(tmp_path)
        db = BoardDB(db_path)
        result = db.scalar("SELECT name FROM sessions WHERE name=?", ("nonexistent",))
        assert result is None

    def test_execute_returns_lastrowid(self, tmp_path):
        db_path = _init_db(tmp_path)
        db = BoardDB(db_path)
        rowid = db.execute("INSERT INTO sessions(name) VALUES (?)", ("dave",))
        assert isinstance(rowid, int)
        assert rowid > 0

    def test_execute_with_connection(self, tmp_path):
        db_path = _init_db(tmp_path)
        db = BoardDB(db_path)
        with db.conn() as c:
            rowid = db.execute("INSERT INTO sessions(name) VALUES (?)", ("eve",), c=c)
            assert rowid > 0

    def test_execute_changes(self, tmp_path):
        db_path = _init_db(tmp_path, ["alice", "bob"])
        db = BoardDB(db_path)
        # Insert a message first
        with db.conn() as c:
            c.execute(
                "INSERT INTO messages(sender, recipient, body, ts) VALUES (?, ?, ?, datetime('now'))",
                ("alice", "bob", "hello"),
            )
            msg_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.execute("INSERT INTO inbox(session, message_id) VALUES (?, ?)", ("bob", msg_id))
            c.execute("INSERT INTO inbox(session, message_id) VALUES (?, ?)", ("bob", msg_id))

        changed = db.execute_changes("UPDATE inbox SET read=1 WHERE session=?", ("bob",))
        assert changed == 2

    def test_execute_changes_zero(self, tmp_path):
        db_path = _init_db(tmp_path)
        db = BoardDB(db_path)
        changed = db.execute_changes("UPDATE inbox SET read=1 WHERE session=?", ("nonexistent",))
        assert changed == 0


# ===========================================================================
# ensure_session
# ===========================================================================


class TestEnsureSession:
    def test_creates_new_session(self, tmp_path):
        db_path = _init_db(tmp_path, [])
        db = BoardDB(db_path)
        db.ensure_session("newuser")
        count = db.scalar("SELECT COUNT(*) FROM sessions WHERE name='newuser'")
        assert count == 1

    def test_idempotent(self, tmp_path):
        db_path = _init_db(tmp_path, ["alice"])
        db = BoardDB(db_path)
        db.ensure_session("alice")
        db.ensure_session("alice")
        count = db.scalar("SELECT COUNT(*) FROM sessions WHERE name='alice'")
        assert count == 1

    def test_lowercases_name(self, tmp_path):
        db_path = _init_db(tmp_path, [])
        db = BoardDB(db_path)
        db.ensure_session("Alice")
        count = db.scalar("SELECT COUNT(*) FROM sessions WHERE name='alice'")
        assert count == 1


# ===========================================================================
# deliver_to_inbox
# ===========================================================================


class TestDeliverToInbox:
    def test_deliver_to_specific_recipient(self, tmp_path):
        db_path = _init_db(tmp_path, ["alice", "bob"])
        db = BoardDB(db_path)

        with db.conn() as c:
            c.execute(
                "INSERT INTO messages(sender, recipient, body, ts) VALUES (?, ?, ?, datetime('now'))",
                ("alice", "bob", "hello bob"),
            )
            msg_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.deliver_to_inbox("alice", "bob", msg_id, c=c)

        rows = db.query("SELECT * FROM inbox WHERE session='bob'")
        assert len(rows) == 1
        assert rows[0]["message_id"] == msg_id

    def test_deliver_to_all(self, tmp_path):
        db_path = _init_db(tmp_path, ["alice", "bob", "charlie"])
        db = BoardDB(db_path)

        with db.conn() as c:
            c.execute(
                "INSERT INTO messages(sender, recipient, body, ts) VALUES (?, ?, ?, datetime('now'))",
                ("alice", "all", "broadcast"),
            )
            msg_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.deliver_to_inbox("alice", "all", msg_id, c=c)

        bob_inbox = db.query("SELECT * FROM inbox WHERE session='bob'")
        charlie_inbox = db.query("SELECT * FROM inbox WHERE session='charlie'")
        alice_inbox = db.query("SELECT * FROM inbox WHERE session='alice'")
        assert len(bob_inbox) == 1
        assert len(charlie_inbox) == 1
        assert len(alice_inbox) == 0, "sender should not receive own broadcast"

    def test_deliver_auto_registers_recipient(self, tmp_path):
        db_path = _init_db(tmp_path, ["alice"])
        db = BoardDB(db_path)

        with db.conn() as c:
            c.execute(
                "INSERT INTO messages(sender, recipient, body, ts) VALUES (?, ?, ?, datetime('now'))",
                ("alice", "newuser", "hello"),
            )
            msg_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            db.deliver_to_inbox("alice", "newuser", msg_id, c=c)

        count = db.scalar("SELECT COUNT(*) FROM sessions WHERE name='newuser'")
        assert count == 1

    def test_deliver_emits_signal(self, tmp_path):
        db_path = _init_db(tmp_path, ["alice", "bob"])
        db = BoardDB(db_path)
        received: list[str] = []
        unsub = inbox_delivered.subscribe(lambda name: received.append(name))

        try:
            with db.conn() as c:
                c.execute(
                    "INSERT INTO messages(sender, recipient, body, ts) VALUES (?, ?, ?, datetime('now'))",
                    ("alice", "bob", "hello"),
                )
                msg_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                db.deliver_to_inbox("alice", "bob", msg_id, c=c)

            assert "bob" in received
        finally:
            unsub()

    def test_broadcast_emits_signal_for_each(self, tmp_path):
        db_path = _init_db(tmp_path, ["alice", "bob", "charlie"])
        db = BoardDB(db_path)
        received: list[str] = []
        unsub = inbox_delivered.subscribe(lambda name: received.append(name))

        try:
            with db.conn() as c:
                c.execute(
                    "INSERT INTO messages(sender, recipient, body, ts) VALUES (?, ?, ?, datetime('now'))",
                    ("alice", "all", "broadcast"),
                )
                msg_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
                db.deliver_to_inbox("alice", "all", msg_id, c=c)

            assert "bob" in received
            assert "charlie" in received
            assert "alice" not in received
        finally:
            unsub()
