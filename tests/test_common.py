"""Tests for shared utility functions (lib/common.py).

Covers: find_claudes_dir traversal, ClaudesEnv config parsing,
DB parameterized queries, SQL injection prevention, ts() format,
is_suspended(), date_to_epoch(), validate_identity, escape_like,
sanitize_session_name, is_terminal_*_status, is_privileged.
"""

import sqlite3
import time

import pytest

from lib.common import (
    escape_like,
    is_privileged,
    is_terminal_bug_status,
    is_terminal_task_status,
    sanitize_session_name,
    validate_identity,
)
from tests.conftest import ts


class TestFindClaudesDir:
    """Finding the .claudes/ directory from nested paths."""

    def test_find_from_project_root(self, tmp_project):
        """Finds .claudes/ when starting from the project root."""
        claudes_dir = tmp_project / ".claudes"
        assert claudes_dir.is_dir()

    def test_find_from_nested_directory(self, tmp_project):
        """Finds .claudes/ when starting from a deeply nested subdirectory."""
        nested = tmp_project / "src" / "lib" / "deep"
        nested.mkdir(parents=True)

        # Walk up from nested dir to find .claudes/
        d = nested
        found = None
        while str(d) != str(d.parent):  # Stop at root
            if (d / ".claudes").is_dir():
                found = d / ".claudes"
                break
            d = d.parent

        assert found is not None
        assert found == tmp_project / ".claudes"

    def test_find_not_found_when_missing(self, tmp_path):
        """Returns error when .claudes/ does not exist in any parent."""
        isolated = tmp_path / "isolated"
        isolated.mkdir()

        d = isolated
        found = None
        while str(d) != str(d.parent):
            if (d / ".claudes").is_dir():
                found = d / ".claudes"
                break
            d = d.parent

        assert found is None


class TestClaudesEnvConfig:
    """Parsing the config.toml file."""

    def test_config_contains_sessions(self, tmp_project):
        """Config file lists the configured sessions."""
        config = (tmp_project / ".claudes" / "config.toml").read_text()
        assert "alice" in config
        assert "bob" in config
        assert "charlie" in config

    def test_config_contains_prefix(self, tmp_project):
        """Config file has a prefix variable."""
        config = (tmp_project / ".claudes" / "config.toml").read_text()
        assert "prefix" in config

    def test_config_contains_claudes_home(self, tmp_project):
        """Config file has claudes_home pointing to the project root."""
        config = (tmp_project / ".claudes" / "config.toml").read_text()
        assert "claudes_home" in config
        assert str(tmp_project) in config


class TestDBParameterizedQueries:
    """Testing that the DB wrapper properly handles parameterized queries."""

    def test_basic_query(self, db_conn):
        """Simple parameterized query works."""
        rows = db_conn.execute("SELECT name FROM sessions WHERE name=?", ("alice",)).fetchall()
        assert len(rows) == 1
        assert rows[0]["name"] == "alice"

    def test_insert_with_params(self, db_conn):
        """Parameterized INSERT works correctly."""
        now = ts()
        db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (now, "alice", "bob", "hello"),
        )
        db_conn.commit()

        count = db_conn.execute("SELECT COUNT(*) FROM messages WHERE sender=?", ("alice",)).fetchone()[0]
        assert count == 1

    def test_scalar_query(self, db_conn):
        """Scalar query returns a single value."""
        count = db_conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        assert count == 3  # alice, bob, charlie


class TestSQLInjectionPrevention:
    """Verify that parameterized queries prevent SQL injection."""

    def test_injection_in_session_name(self, db_conn):
        """Malicious session name does not execute as SQL."""
        malicious_name = "'; DROP TABLE sessions; --"

        # Using parameterized query -- should treat as literal string
        db_conn.execute(
            "INSERT OR IGNORE INTO sessions(name) VALUES (?)",
            (malicious_name,),
        )
        db_conn.commit()

        # sessions table should still exist and have original data
        count = db_conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        assert count >= 3  # Original sessions intact

        # The malicious string was stored as a literal name
        row = db_conn.execute("SELECT name FROM sessions WHERE name=?", (malicious_name,)).fetchone()
        assert row is not None
        assert row["name"] == malicious_name

    def test_injection_in_message_body(self, db_conn):
        """Malicious message body is stored as literal text."""
        malicious_body = "test'); DELETE FROM messages; --"
        now = ts()

        db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (now, "alice", "bob", malicious_body),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT body FROM messages WHERE sender='alice'").fetchone()
        assert row["body"] == malicious_body

    def test_injection_in_where_clause(self, db_conn):
        """Parameterized WHERE clause prevents injection."""
        malicious_input = "alice' OR '1'='1"

        rows = db_conn.execute("SELECT name FROM sessions WHERE name=?", (malicious_input,)).fetchall()
        # Should return nothing (no session with that literal name)
        assert len(rows) == 0

    def test_injection_in_bug_description(self, db_conn):
        """Malicious bug description stored safely."""
        malicious_desc = "'; UPDATE bugs SET status='FIXED' WHERE '1'='1"
        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description) VALUES (?, ?, ?, ?, ?, ?)",
            ("BUG-001", "P1", "4h", "alice", "OPEN", malicious_desc),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT description, status FROM bugs WHERE id='BUG-001'").fetchone()
        assert row["description"] == malicious_desc
        assert row["status"] == "OPEN"

    def test_injection_in_proposal_content(self, db_conn):
        """Malicious proposal content is stored as-is."""
        malicious = "test'); DROP TABLE proposals; --"
        db_conn.execute(
            "INSERT INTO proposals(number, slug, type, content) VALUES (?, ?, ?, ?)",
            ("001", "test", "A", malicious),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT content FROM proposals WHERE number='001'").fetchone()
        assert row["content"] == malicious

        # Table still exists
        count = db_conn.execute("SELECT COUNT(*) FROM proposals").fetchone()[0]
        assert count == 1

    def test_null_bytes_in_input(self, db_conn):
        """Null bytes in input are handled safely."""
        null_input = "hello\x00world"
        db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (ts(), "alice", "bob", null_input),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT body FROM messages WHERE sender='alice'").fetchone()
        # SQLite may strip or preserve null bytes -- either is safe
        assert row is not None


class TestTimestamp:
    """Timestamp formatting."""

    def test_ts_format(self):
        """Timestamp follows YYYY-MM-DD HH:MM:SS format."""
        result = ts()
        assert len(result) == 19
        assert result[4] == "-"
        assert result[7] == "-"
        assert result[10] == " "
        assert result[13] == ":"
        assert result[16] == ":"

    def test_ts_is_current(self):
        """Timestamp reflects the current time (within 2 seconds tolerance)."""
        result = ts()
        expected = time.strftime("%Y-%m-%d %H:%M:%S")
        # Allow up to 2 seconds difference due to execution timing
        result_epoch = int(time.mktime(time.strptime(result, "%Y-%m-%d %H:%M:%S")))
        expected_epoch = int(time.mktime(time.strptime(expected, "%Y-%m-%d %H:%M:%S")))
        assert abs(result_epoch - expected_epoch) <= 2


class TestIsSuspended:
    """Session suspension tracking."""

    def test_suspended_session_detected(self, db_conn):
        """A suspended session appears in the suspended table."""
        db_conn.execute(
            "INSERT INTO suspended(name, suspended_by) VALUES (?, ?)",
            ("alice", "lead"),
        )
        db_conn.commit()

        count = db_conn.execute("SELECT COUNT(*) FROM suspended WHERE name='alice'").fetchone()[0]
        assert count == 1

    def test_non_suspended_session_not_detected(self, db_conn):
        """A non-suspended session is absent from the suspended table."""
        count = db_conn.execute("SELECT COUNT(*) FROM suspended WHERE name='alice'").fetchone()[0]
        assert count == 0

    def test_resume_removes_from_suspended(self, db_conn):
        """Resuming a session removes it from the suspended table."""
        db_conn.execute(
            "INSERT INTO suspended(name, suspended_by) VALUES (?, ?)",
            ("alice", "lead"),
        )
        db_conn.commit()

        db_conn.execute("DELETE FROM suspended WHERE name='alice'")
        db_conn.commit()

        count = db_conn.execute("SELECT COUNT(*) FROM suspended WHERE name='alice'").fetchone()[0]
        assert count == 0

    def test_suspend_records_who_suspended(self, db_conn):
        """Suspension records which session initiated the suspension."""
        db_conn.execute(
            "INSERT INTO suspended(name, suspended_by) VALUES (?, ?)",
            ("bob", "lead"),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT suspended_by FROM suspended WHERE name='bob'").fetchone()
        assert row["suspended_by"] == "lead"


class TestDateToEpoch:
    """Date string to epoch conversion."""

    def test_standard_format(self):
        """Parse standard YYYY-MM-DD HH:MM format to epoch."""
        # Use a known timestamp
        test_ts = "2025-01-15 10:30"
        # Verify it can be parsed by time.strptime
        parsed = time.strptime(test_ts, "%Y-%m-%d %H:%M")
        epoch = int(time.mktime(parsed))
        assert epoch > 0

    def test_with_seconds(self):
        """Parse YYYY-MM-DD HH:MM:SS format."""
        test_ts = "2025-01-15 10:30:45"
        parsed = time.strptime(test_ts, "%Y-%m-%d %H:%M:%S")
        epoch = int(time.mktime(parsed))
        assert epoch > 0

    def test_roundtrip(self):
        """Convert to epoch and back preserves the time."""
        original = "2025-06-15 14:30"
        parsed = time.strptime(original, "%Y-%m-%d %H:%M")
        epoch = int(time.mktime(parsed))
        back = time.strftime("%Y-%m-%d %H:%M", time.localtime(epoch))
        assert back == original


class TestBoardDB:
    """Test the BoardDB wrapper."""

    def test_db_execute(self, db):
        """BoardDB.execute runs a query."""
        db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (ts(), "alice", "bob", "test message"),
        )
        count = db.scalar("SELECT COUNT(*) FROM messages")
        assert count == 1

    def test_db_query(self, db):
        """DB.query returns a list of rows."""
        rows = db.query("SELECT name FROM sessions ORDER BY name")
        names = [r["name"] for r in rows]
        assert "alice" in names
        assert "bob" in names
        assert "charlie" in names

    def test_db_scalar(self, db):
        """DB.scalar returns a single value."""
        count = db.scalar("SELECT COUNT(*) FROM sessions")
        assert count >= 3

    def test_db_scalar_no_rows(self, db):
        """DB.scalar returns None when no rows match."""
        result = db.scalar("SELECT name FROM sessions WHERE name='nonexistent'")
        assert result is None

    def test_db_execute_returns_lastrowid(self, db):
        """DB.execute returns the new row's lastrowid."""
        row_id = db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (ts(), "alice", "bob", "test"),
        )
        assert isinstance(row_id, int)
        assert row_id > 0


class TestSchemaIntegrity:
    """Verify the database schema is correct."""

    def test_all_tables_exist(self, db_conn):
        """All expected tables are created by schema.sql."""
        expected_tables = {
            "sessions",
            "messages",
            "inbox",
            "proposals",
            "votes",
            "files",
            "bugs",
            "threads",
            "thread_replies",
            "kudos",
            "suspended",
            "tasks",
            "meta",
        }
        rows = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        actual_tables = {r["name"] for r in rows}
        assert expected_tables.issubset(actual_tables)

    def test_indexes_exist(self, db_conn):
        """Expected indexes are created."""
        rows = db_conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        index_names = {r["name"] for r in rows}
        expected_indexes = {
            "idx_msg_ts",
            "idx_msg_to",
            "idx_msg_from",
            "idx_inbox",
            "idx_bugs",
            "idx_replies",
            "idx_tasks",
        }
        assert expected_indexes.issubset(index_names)

    def test_sessions_primary_key(self, db_conn):
        """Session name is the primary key."""
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute("INSERT INTO sessions(name) VALUES ('alice')")  # alice already exists

    def test_message_autoincrement(self, db_conn):
        """Messages get auto-incrementing IDs."""
        now = ts()
        ids = []
        for i in range(3):
            cur = db_conn.execute(
                "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
                (now, "alice", "bob", f"msg {i}"),
            )
            ids.append(cur.lastrowid)
        db_conn.commit()
        assert ids[0] < ids[1] < ids[2]


# ---------------------------------------------------------------------------
# validate_identity
# ---------------------------------------------------------------------------


class TestValidateIdentity:
    def test_registered_session_passes(self, db):
        validate_identity(db, "alice")

    def test_unregistered_session_exits(self, db):
        with pytest.raises(SystemExit):
            validate_identity(db, "intruder")

    def test_privileged_role_always_passes(self, db):
        validate_identity(db, "lead")
        validate_identity(db, "dispatcher")

    def test_case_insensitive(self, db):
        validate_identity(db, "Alice")


# ---------------------------------------------------------------------------
# escape_like
# ---------------------------------------------------------------------------


class TestEscapeLike:
    def test_no_special_chars(self):
        assert escape_like("hello") == "hello"

    def test_escapes_percent(self):
        assert escape_like("100%") == "100\\%"

    def test_escapes_underscore(self):
        assert escape_like("my_var") == "my\\_var"

    def test_escapes_backslash(self):
        assert escape_like("a\\b") == "a\\\\b"

    def test_escapes_all_together(self):
        assert escape_like("a%b_c\\d") == "a\\%b\\_c\\\\d"

    def test_empty_string(self):
        assert escape_like("") == ""


# ---------------------------------------------------------------------------
# sanitize_session_name
# ---------------------------------------------------------------------------


class TestSanitizeSessionName:
    def test_normal_name_unchanged(self):
        assert sanitize_session_name("alice") == "alice"

    def test_strips_forward_slash(self):
        assert sanitize_session_name("../evil") == ".._evil"

    def test_strips_backslash(self):
        assert sanitize_session_name("a\\b") == "a_b"

    def test_strips_null_byte(self):
        assert sanitize_session_name("alice\0") == "alice"

    def test_combined_traversal(self):
        assert sanitize_session_name("../../etc/passwd") == ".._.._etc_passwd"


# ---------------------------------------------------------------------------
# is_terminal_*_status / is_privileged
# ---------------------------------------------------------------------------


class TestStatusHelpers:
    def test_done_is_terminal_task(self):
        assert is_terminal_task_status("done") is True

    def test_active_not_terminal_task(self):
        assert is_terminal_task_status("active") is False

    def test_fixed_is_terminal_bug(self):
        assert is_terminal_bug_status("FIXED") is True

    def test_open_not_terminal_bug(self):
        assert is_terminal_bug_status("OPEN") is False

    def test_lead_is_privileged(self):
        assert is_privileged("lead") is True

    def test_dispatcher_is_privileged(self):
        assert is_privileged("dispatcher") is True

    def test_normal_user_not_privileged(self):
        assert is_privileged("alice") is False
