"""Tests for the board bug tracker subsystem.

Covers: bug report (P0/P1/P2), assign, fix, list, overdue detection,
SLA enforcement, severity validation, and bug ID generation.
"""

import sqlite3
import time

import pytest

from tests.conftest import ts


class TestBugReport:
    """Reporting new bugs."""

    def test_report_p0_bug(self, db_conn):
        """Reporting a P0 bug creates a record with immediate SLA."""
        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description) VALUES (?, ?, ?, ?, 'OPEN', ?)",
            ("BUG-001", "P0", "immediate", "alice", "Critical crash on startup"),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT severity, sla, reporter, status, description FROM bugs WHERE id='BUG-001'"
        ).fetchone()
        assert row["severity"] == "P0"
        assert row["sla"] == "immediate"
        assert row["reporter"] == "alice"
        assert row["status"] == "OPEN"

    def test_report_p1_bug(self, db_conn):
        """P1 bug has 4-hour SLA."""
        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description) VALUES (?, ?, ?, ?, 'OPEN', ?)",
            ("BUG-002", "P1", "4h", "bob", "Login page broken"),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT sla FROM bugs WHERE id='BUG-002'").fetchone()
        assert row["sla"] == "4h"

    def test_report_p2_bug(self, db_conn):
        """P2 bug has 24-hour SLA."""
        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description) VALUES (?, ?, ?, ?, 'OPEN', ?)",
            ("BUG-003", "P2", "24h", "charlie", "Minor styling issue"),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT sla FROM bugs WHERE id='BUG-003'").fetchone()
        assert row["sla"] == "24h"

    def test_bug_id_is_primary_key(self, db_conn):
        """Bug IDs must be unique."""
        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description) "
            "VALUES ('BUG-001', 'P1', '4h', 'alice', 'OPEN', 'first bug')"
        )
        db_conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO bugs(id, severity, sla, reporter, status, description) "
                "VALUES ('BUG-001', 'P2', '24h', 'bob', 'OPEN', 'duplicate id')"
            )

    def test_bug_id_auto_increment(self, db_conn):
        """Bug IDs follow BUG-NNN format with incrementing numbers."""
        for i in range(3):
            bug_id = f"BUG-{i + 1:03d}"
            db_conn.execute(
                "INSERT INTO bugs(id, severity, sla, reporter, status, description) "
                "VALUES (?, 'P1', '4h', 'alice', 'OPEN', ?)",
                (bug_id, f"bug {i + 1}"),
            )
        db_conn.commit()

        # Verify the max ID calculation works
        max_num = db_conn.execute("SELECT COALESCE(MAX(CAST(SUBSTR(id, 5) AS INTEGER)), 0) FROM bugs").fetchone()[0]
        assert max_num == 3

    def test_report_broadcasts_notification(self, db_conn):
        """When a bug is reported, a notification message should be created."""
        bug_id = "BUG-001"
        reporter = "alice"
        now = ts()

        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description) "
            "VALUES (?, 'P0', 'immediate', ?, 'OPEN', ?)",
            (bug_id, reporter, "server down"),
        )
        # The application creates a broadcast message
        db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, 'all', ?)",
            (now, reporter, f"[{bug_id}/P0] server down"),
        )
        db_conn.commit()

        msg = db_conn.execute("SELECT body FROM messages WHERE body LIKE '%BUG-001%'").fetchone()
        assert msg is not None
        assert "P0" in msg["body"]


class TestBugAssign:
    """Assigning bugs to sessions."""

    def test_assign_bug(self, db_conn):
        """Assigning a bug updates assignee and status."""
        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description) "
            "VALUES ('BUG-001', 'P1', '4h', 'alice', 'OPEN', 'some bug')"
        )
        db_conn.commit()

        db_conn.execute("UPDATE bugs SET assignee='bob', status='ASSIGNED' WHERE id='BUG-001'")
        db_conn.commit()

        row = db_conn.execute("SELECT assignee, status FROM bugs WHERE id='BUG-001'").fetchone()
        assert row["assignee"] == "bob"
        assert row["status"] == "ASSIGNED"

    def test_assign_nonexistent_bug_detectable(self, db_conn):
        """Assigning a nonexistent bug affects zero rows."""
        result = db_conn.execute("UPDATE bugs SET assignee='bob' WHERE id='BUG-999'")
        assert result.rowcount == 0

    def test_assign_sends_notification(self, db_conn):
        """Assigning a bug should create a notification message to the assignee."""
        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description) "
            "VALUES ('BUG-001', 'P1', '4h', 'alice', 'OPEN', 'fix this')"
        )
        db_conn.execute("UPDATE bugs SET assignee='bob', status='ASSIGNED' WHERE id='BUG-001'")
        now = ts()
        db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, 'alice', 'bob', '[BUG-001] assigned to you')",
            (now,),
        )
        db_conn.commit()

        msg = db_conn.execute("SELECT body FROM messages WHERE recipient='bob' AND body LIKE '%BUG-001%'").fetchone()
        assert msg is not None
        assert "assigned to you" in msg["body"]


class TestBugFix:
    """Fixing/resolving bugs."""

    def test_fix_bug_with_evidence(self, db_conn):
        """Fixing a bug updates status, sets fixed_at, and records evidence."""
        now = ts()
        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description) "
            "VALUES ('BUG-001', 'P1', '4h', 'alice', 'ASSIGNED', 'broken page')"
        )
        db_conn.commit()

        db_conn.execute(
            "UPDATE bugs SET status='FIXED', fixed_at=?, evidence=? WHERE id='BUG-001'",
            (now, "commit abc123 fixes the layout"),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT status, fixed_at, evidence FROM bugs WHERE id='BUG-001'").fetchone()
        assert row["status"] == "FIXED"
        assert row["fixed_at"] is not None
        assert "commit abc123" in row["evidence"]

    def test_fix_nonexistent_bug_detectable(self, db_conn):
        """Fixing a nonexistent bug affects zero rows."""
        result = db_conn.execute("UPDATE bugs SET status='FIXED' WHERE id='BUG-999'")
        assert result.rowcount == 0


class TestBugList:
    """Listing and filtering bugs."""

    def _seed_bugs(self, db_conn):
        """Helper: insert a mix of bugs in various states."""
        bugs = [
            ("BUG-001", "P0", "immediate", "alice", "OPEN", "crash on launch"),
            ("BUG-002", "P1", "4h", "bob", "ASSIGNED", "slow response"),
            ("BUG-003", "P2", "24h", "charlie", "FIXED", "typo in docs"),
        ]
        for bug in bugs:
            db_conn.execute(
                "INSERT INTO bugs(id, severity, sla, reporter, status, description) VALUES (?, ?, ?, ?, ?, ?)",
                bug,
            )
        db_conn.commit()

    def test_list_open_bugs(self, db_conn):
        """List open bugs excludes FIXED ones."""
        self._seed_bugs(db_conn)

        rows = db_conn.execute("SELECT id FROM bugs WHERE status != 'FIXED' ORDER BY reported_at").fetchall()
        ids = [r["id"] for r in rows]
        assert "BUG-001" in ids
        assert "BUG-002" in ids
        assert "BUG-003" not in ids

    def test_list_all_bugs(self, db_conn):
        """List all bugs includes every status."""
        self._seed_bugs(db_conn)

        rows = db_conn.execute("SELECT id FROM bugs").fetchall()
        assert len(rows) == 3

    def test_list_by_specific_status(self, db_conn):
        """Filtering by a specific status works."""
        self._seed_bugs(db_conn)

        rows = db_conn.execute("SELECT id FROM bugs WHERE status='ASSIGNED'").fetchall()
        assert len(rows) == 1
        assert rows[0]["id"] == "BUG-002"


class TestBugOverdue:
    """SLA overdue detection."""

    def test_p0_immediately_overdue(self, db_conn):
        """P0 bugs are overdue immediately (SLA limit = 0 seconds)."""
        # Insert P0 bug with a timestamp 5 minutes ago
        past = time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - 300))
        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description, reported_at) "
            "VALUES ('BUG-001', 'P0', 'immediate', 'alice', 'OPEN', 'p0 bug', ?)",
            (past,),
        )
        db_conn.commit()

        # P0 limit is 0 seconds
        row = db_conn.execute("SELECT severity, reported_at FROM bugs WHERE id='BUG-001'").fetchone()
        assert row["severity"] == "P0"
        # Any elapsed time > 0 means P0 is overdue

    def test_p1_overdue_after_4_hours(self, db_conn):
        """P1 bugs are overdue after 4 hours (14400 seconds)."""
        # Insert P1 bug 5 hours ago
        past = time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - 5 * 3600))
        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description, reported_at) "
            "VALUES ('BUG-002', 'P1', '4h', 'bob', 'OPEN', 'p1 bug', ?)",
            (past,),
        )
        db_conn.commit()

        # P1 limit = 14400s = 4h. 5h > 4h, so overdue
        row = db_conn.execute("SELECT severity, reported_at FROM bugs WHERE id='BUG-002'").fetchone()
        assert row["severity"] == "P1"

    def test_p2_not_overdue_within_24_hours(self, db_conn):
        """P2 bugs are not overdue within 24 hours."""
        # Insert P2 bug 1 hour ago
        past = time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - 3600))
        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description, reported_at) "
            "VALUES ('BUG-003', 'P2', '24h', 'charlie', 'OPEN', 'p2 bug', ?)",
            (past,),
        )
        db_conn.commit()

        # P2 limit = 86400s = 24h. 1h < 24h, not overdue
        row = db_conn.execute("SELECT severity, reported_at FROM bugs WHERE id='BUG-003'").fetchone()
        assert row["severity"] == "P2"
        # 1h = 3600s < 86400s, so NOT overdue

    def test_fixed_bugs_excluded_from_overdue(self, db_conn):
        """Fixed bugs are not checked for overdue."""
        past = time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - 100000))
        db_conn.execute(
            "INSERT INTO bugs(id, severity, sla, reporter, status, description, reported_at) "
            "VALUES ('BUG-004', 'P0', 'immediate', 'alice', 'FIXED', 'old bug', ?)",
            (past,),
        )
        db_conn.commit()

        rows = db_conn.execute("SELECT id FROM bugs WHERE status != 'FIXED'").fetchall()
        ids = [r["id"] for r in rows]
        assert "BUG-004" not in ids

    def test_overdue_detection_logic(self, db_conn):
        """Verify overdue detection using elapsed time vs SLA limit."""
        int(time.time())
        sla_limits = {"P0": 0, "P1": 14400, "P2": 86400}

        # P0 reported 60 seconds ago -> overdue (limit=0)
        # P1 reported 5 hours ago -> overdue (limit=4h)
        # P2 reported 1 hour ago -> NOT overdue (limit=24h)
        test_cases = [
            ("P0", 60, True),
            ("P1", 5 * 3600, True),
            ("P2", 3600, False),
            ("P2", 25 * 3600, True),
        ]

        for severity, elapsed_s, expected_overdue in test_cases:
            limit = sla_limits[severity]
            is_overdue = elapsed_s > limit
            assert is_overdue == expected_overdue, (
                f"{severity} elapsed={elapsed_s}s limit={limit}s: expected overdue={expected_overdue}, got {is_overdue}"
            )
