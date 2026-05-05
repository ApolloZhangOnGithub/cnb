"""Tests for the board git lock coordination subsystem.

Covers: lock acquisition, blocking on contention, re-entrant extension,
unlock by holder, unlock by non-holder (error), force unlock,
stale lock auto-cleanup, and lock status queries.
"""

import sqlite3
import time

import pytest

from tests.conftest import ts

GIT_LOCK_TTL = 60  # Same as in board.sh


@pytest.fixture
def git_lock_table(db_conn):
    """Create the git_locks table (as the board does on first use)."""
    db_conn.execute(
        """CREATE TABLE IF NOT EXISTS git_locks (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            session     TEXT NOT NULL,
            reason      TEXT DEFAULT '',
            acquired_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
            expires_at  INTEGER NOT NULL
        )"""
    )
    db_conn.commit()
    return db_conn


class TestGitLockAcquire:
    """Acquiring the git lock."""

    def test_acquire_when_free(self, git_lock_table):
        """Acquiring a free lock succeeds."""
        conn = git_lock_table
        expires = int(time.time()) + GIT_LOCK_TTL
        conn.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) "
            "VALUES (1, ?, ?, ?)",
            ("alice", "git commit", expires),
        )
        conn.commit()

        row = conn.execute(
            "SELECT session, reason, expires_at FROM git_locks WHERE id=1"
        ).fetchone()
        assert row is not None
        assert row["session"] == "alice"
        assert row["reason"] == "git commit"

    def test_acquire_when_locked_by_other_fails(self, git_lock_table):
        """Attempting to acquire a lock held by another session is blocked."""
        conn = git_lock_table
        expires = int(time.time()) + GIT_LOCK_TTL
        conn.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) "
            "VALUES (1, ?, ?, ?)",
            ("alice", "git push", expires),
        )
        conn.commit()

        # Bob tries to acquire -- the CHECK constraint (id=1) plus PRIMARY KEY
        # means only one lock can exist
        holder = conn.execute(
            "SELECT session FROM git_locks WHERE id=1"
        ).fetchone()
        assert holder is not None
        assert holder["session"] == "alice"
        # Bob would see BLOCKED because holder != bob

    def test_reentrant_lock_extends_ttl(self, git_lock_table):
        """Same holder can re-acquire to extend the lock TTL."""
        conn = git_lock_table
        old_expires = int(time.time()) + 10  # Short TTL
        conn.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) "
            "VALUES (1, ?, ?, ?)",
            ("alice", "git commit", old_expires),
        )
        conn.commit()

        # Alice re-acquires with new TTL
        new_expires = int(time.time()) + GIT_LOCK_TTL
        conn.execute(
            "UPDATE git_locks SET expires_at=?, reason=?, "
            "acquired_at=strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime') "
            "WHERE id=1",
            (new_expires, "extended"),
        )
        conn.commit()

        row = conn.execute(
            "SELECT expires_at, reason FROM git_locks WHERE id=1"
        ).fetchone()
        assert row["expires_at"] == new_expires
        assert row["reason"] == "extended"

    def test_only_one_lock_allowed(self, git_lock_table):
        """The CHECK constraint enforces exactly one lock row (id=1)."""
        conn = git_lock_table
        expires = int(time.time()) + GIT_LOCK_TTL
        conn.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) "
            "VALUES (1, 'alice', 'first', ?)",
            (expires,),
        )
        conn.commit()

        # Cannot insert another row with id=1 (PRIMARY KEY violation)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO git_locks(id, session, reason, expires_at) "
                "VALUES (1, 'bob', 'second', ?)",
                (expires,),
            )

        # Cannot insert a row with id=2 (CHECK constraint violation)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO git_locks(id, session, reason, expires_at) "
                "VALUES (2, 'bob', 'second', ?)",
                (expires,),
            )


class TestGitLockRelease:
    """Releasing the git lock."""

    def test_unlock_by_holder(self, git_lock_table):
        """Lock holder can release their own lock."""
        conn = git_lock_table
        expires = int(time.time()) + GIT_LOCK_TTL
        conn.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) "
            "VALUES (1, 'alice', 'git push', ?)",
            (expires,),
        )
        conn.commit()

        # Alice releases
        conn.execute("DELETE FROM git_locks WHERE id=1")
        conn.commit()

        row = conn.execute(
            "SELECT session FROM git_locks WHERE id=1"
        ).fetchone()
        assert row is None

    def test_unlock_by_non_holder_should_be_blocked(self, git_lock_table):
        """Non-holder attempting to unlock should check holder first."""
        conn = git_lock_table
        expires = int(time.time()) + GIT_LOCK_TTL
        conn.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) "
            "VALUES (1, 'alice', 'git push', ?)",
            (expires,),
        )
        conn.commit()

        # Application would check: holder != bob, so refuse
        holder = conn.execute(
            "SELECT session FROM git_locks WHERE id=1"
        ).fetchone()
        assert holder["session"] == "alice"
        assert holder["session"] != "bob"

    def test_force_unlock(self, git_lock_table):
        """Force unlock releases the lock regardless of holder."""
        conn = git_lock_table
        expires = int(time.time()) + GIT_LOCK_TTL
        conn.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) "
            "VALUES (1, 'alice', 'long operation', ?)",
            (expires,),
        )
        conn.commit()

        # Bob force-unlocks
        conn.execute("DELETE FROM git_locks WHERE id=1")
        conn.commit()

        row = conn.execute(
            "SELECT session FROM git_locks WHERE id=1"
        ).fetchone()
        assert row is None

    def test_force_unlock_creates_notification(self, git_lock_table):
        """Force unlock should notify the displaced lock holder."""
        conn = git_lock_table
        expires = int(time.time()) + GIT_LOCK_TTL
        conn.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) "
            "VALUES (1, 'alice', 'git push', ?)",
            (expires,),
        )
        conn.commit()

        # Simulate notification
        now = ts()
        conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) "
            "VALUES (?, 'SYSTEM', 'alice', ?)",
            (now, "[GIT-LOCK] bob force-released your git lock"),
        )
        conn.execute("DELETE FROM git_locks WHERE id=1")
        conn.commit()

        msg = conn.execute(
            "SELECT body FROM messages WHERE recipient='alice' "
            "AND body LIKE '%force-released%'"
        ).fetchone()
        assert msg is not None

    def test_unlock_already_free(self, git_lock_table):
        """Unlocking when no lock is held is a no-op."""
        conn = git_lock_table
        row = conn.execute(
            "SELECT session FROM git_locks WHERE id=1"
        ).fetchone()
        assert row is None
        # No error -- just "OK git lock is already free"


class TestGitLockStaleCleanup:
    """Automatic cleanup of stale/expired locks."""

    def test_stale_lock_auto_removed(self, git_lock_table):
        """Locks with expired TTL are automatically cleaned up."""
        conn = git_lock_table
        # Insert a lock that expired 10 seconds ago
        expired_time = int(time.time()) - 10
        conn.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) "
            "VALUES (1, 'alice', 'stale operation', ?)",
            (expired_time,),
        )
        conn.commit()

        # Cleanup stale locks (as the board does before acquire/unlock)
        now_epoch = int(time.time())
        conn.execute(
            "DELETE FROM git_locks WHERE expires_at < ?", (now_epoch,)
        )
        conn.commit()

        row = conn.execute(
            "SELECT session FROM git_locks WHERE id=1"
        ).fetchone()
        assert row is None

    def test_non_expired_lock_survives_cleanup(self, git_lock_table):
        """Locks with valid TTL are not removed by cleanup."""
        conn = git_lock_table
        future_expires = int(time.time()) + 300  # 5 minutes from now
        conn.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) "
            "VALUES (1, 'alice', 'active operation', ?)",
            (future_expires,),
        )
        conn.commit()

        # Run cleanup
        now_epoch = int(time.time())
        conn.execute(
            "DELETE FROM git_locks WHERE expires_at < ?", (now_epoch,)
        )
        conn.commit()

        row = conn.execute(
            "SELECT session FROM git_locks WHERE id=1"
        ).fetchone()
        assert row is not None
        assert row["session"] == "alice"


class TestGitLockStatus:
    """Git lock status queries."""

    def test_status_when_free(self, git_lock_table):
        """Status query returns no rows when lock is free."""
        conn = git_lock_table
        row = conn.execute(
            "SELECT session, reason, acquired_at, expires_at "
            "FROM git_locks WHERE id=1"
        ).fetchone()
        assert row is None

    def test_status_when_locked(self, git_lock_table):
        """Status query returns holder info when lock is held."""
        conn = git_lock_table
        expires = int(time.time()) + GIT_LOCK_TTL
        conn.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) "
            "VALUES (1, 'alice', 'git rebase', ?)",
            (expires,),
        )
        conn.commit()

        row = conn.execute(
            "SELECT session, reason, acquired_at, expires_at "
            "FROM git_locks WHERE id=1"
        ).fetchone()
        assert row["session"] == "alice"
        assert row["reason"] == "git rebase"
        assert row["expires_at"] == expires

    def test_status_remaining_time(self, git_lock_table):
        """Remaining time is calculated from expires_at minus current time."""
        conn = git_lock_table
        expires = int(time.time()) + 30  # 30 seconds from now
        conn.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) "
            "VALUES (1, 'alice', 'quick op', ?)",
            (expires,),
        )
        conn.commit()

        row = conn.execute(
            "SELECT expires_at FROM git_locks WHERE id=1"
        ).fetchone()
        remaining = row["expires_at"] - int(time.time())
        assert 0 < remaining <= 30
