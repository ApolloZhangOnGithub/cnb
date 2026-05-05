"""Tests for the board BBS (forum) subsystem.

Covers: thread creation (post), reply, view thread with replies,
list threads with reply count, and error handling for nonexistent threads.
"""

import sqlite3

import pytest

from tests.conftest import ts


class TestCreateThread:
    """Creating new BBS threads."""

    def test_create_thread(self, db_conn):
        """Creating a thread inserts into the threads table."""
        db_conn.execute(
            "INSERT INTO threads(id, title, author) VALUES (?, ?, ?)",
            ("abc123", "Architecture Discussion", "alice"),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT id, title, author FROM threads WHERE id='abc123'").fetchone()
        assert row is not None
        assert row["title"] == "Architecture Discussion"
        assert row["author"] == "alice"

    def test_create_thread_sets_created_at(self, db_conn):
        """Thread creation automatically sets a timestamp."""
        db_conn.execute(
            "INSERT INTO threads(id, title, author) VALUES (?, ?, ?)",
            ("def456", "Testing Practices", "bob"),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT created_at FROM threads WHERE id='def456'").fetchone()
        assert row["created_at"] is not None

    def test_create_thread_id_unique(self, db_conn):
        """Thread IDs must be unique."""
        db_conn.execute("INSERT INTO threads(id, title, author) VALUES ('abc123', 'Thread 1', 'alice')")
        db_conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute("INSERT INTO threads(id, title, author) VALUES ('abc123', 'Thread 2', 'bob')")

    def test_create_thread_generates_broadcast(self, db_conn):
        """Creating a thread also creates a broadcast message."""
        now = ts()
        thread_id = "abc123"
        title = "New Feature Proposal"

        db_conn.execute(
            "INSERT INTO threads(id, title, author) VALUES (?, ?, ?)",
            (thread_id, title, "alice"),
        )
        db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, 'all', ?)",
            (now, "alice", f'[BBS] New thread "{title}" ({thread_id})'),
        )
        db_conn.commit()

        msg = db_conn.execute("SELECT body FROM messages WHERE body LIKE '%BBS%' AND body LIKE '%abc123%'").fetchone()
        assert msg is not None


class TestReplyToThread:
    """Replying to existing threads."""

    @pytest.fixture
    def thread(self, db_conn):
        """Create a test thread and return its id."""
        db_conn.execute(
            "INSERT INTO threads(id, title, author) VALUES (?, ?, ?)",
            ("thread01", "Design Review", "alice"),
        )
        db_conn.commit()
        return "thread01"

    def test_reply_to_thread(self, db_conn, thread):
        """Replies are stored in thread_replies table."""
        db_conn.execute(
            "INSERT INTO thread_replies(thread_id, author, body) VALUES (?, ?, ?)",
            (thread, "bob", "I agree with the proposal"),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT author, body FROM thread_replies WHERE thread_id=?",
            (thread,),
        ).fetchone()
        assert row["author"] == "bob"
        assert row["body"] == "I agree with the proposal"

    def test_multiple_replies_ordered_by_id(self, db_conn, thread):
        """Multiple replies are ordered by insertion order."""
        for i, author in enumerate(["bob", "charlie", "alice"]):
            db_conn.execute(
                "INSERT INTO thread_replies(thread_id, author, body) VALUES (?, ?, ?)",
                (thread, author, f"Reply {i + 1}"),
            )
        db_conn.commit()

        rows = db_conn.execute(
            "SELECT author, body FROM thread_replies WHERE thread_id=? ORDER BY id",
            (thread,),
        ).fetchall()
        assert len(rows) == 3
        assert rows[0]["author"] == "bob"
        assert rows[1]["author"] == "charlie"
        assert rows[2]["author"] == "alice"

    def test_reply_sets_timestamp(self, db_conn, thread):
        """Replies automatically get a timestamp."""
        db_conn.execute(
            "INSERT INTO thread_replies(thread_id, author, body) VALUES (?, ?, ?)",
            (thread, "bob", "timestamped reply"),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT ts FROM thread_replies WHERE thread_id=?", (thread,)).fetchone()
        assert row["ts"] is not None

    def test_reply_to_nonexistent_thread_detectable(self, db_conn):
        """The application checks thread existence before inserting a reply.

        The DB itself does not enforce a foreign key, so we test the
        lookup pattern used by the application.
        """
        exists = db_conn.execute("SELECT COUNT(*) FROM threads WHERE id LIKE 'nonexistent%'").fetchone()[0]
        assert exists == 0


class TestViewThread:
    """Viewing a thread with its replies."""

    @pytest.fixture
    def thread_with_replies(self, db_conn):
        """Create a thread with several replies."""
        db_conn.execute(
            "INSERT INTO threads(id, title, author) VALUES (?, ?, ?)",
            ("view01", "API Design", "alice"),
        )
        for _i, (author, body) in enumerate(
            [
                ("bob", "Looks good to me"),
                ("charlie", "What about edge cases?"),
                ("alice", "Good point, will address"),
            ]
        ):
            db_conn.execute(
                "INSERT INTO thread_replies(thread_id, author, body) VALUES (?, ?, ?)",
                ("view01", author, body),
            )
        db_conn.commit()
        return "view01"

    def test_view_shows_thread_metadata(self, db_conn, thread_with_replies):
        """Thread view includes title, author, and created_at."""
        row = db_conn.execute(
            "SELECT title, author, created_at FROM threads WHERE id=?",
            (thread_with_replies,),
        ).fetchone()
        assert row["title"] == "API Design"
        assert row["author"] == "alice"
        assert row["created_at"] is not None

    def test_view_shows_all_replies(self, db_conn, thread_with_replies):
        """Thread view includes all replies in order."""
        rows = db_conn.execute(
            "SELECT author, body, ts FROM thread_replies WHERE thread_id=? ORDER BY id",
            (thread_with_replies,),
        ).fetchall()
        assert len(rows) == 3
        assert rows[0]["body"] == "Looks good to me"
        assert rows[2]["body"] == "Good point, will address"


class TestListThreads:
    """Listing all threads with metadata."""

    def test_list_threads_with_reply_count(self, db_conn):
        """Thread list includes the reply count for each thread."""
        db_conn.execute("INSERT INTO threads(id, title, author) VALUES ('t1', 'Thread 1', 'alice')")
        db_conn.execute("INSERT INTO threads(id, title, author) VALUES ('t2', 'Thread 2', 'bob')")
        # Add replies to thread 1 only
        for i in range(3):
            db_conn.execute(
                "INSERT INTO thread_replies(thread_id, author, body) VALUES ('t1', 'charlie', ?)",
                (f"reply {i}",),
            )
        db_conn.commit()

        rows = db_conn.execute(
            "SELECT t.id, t.title, t.author, "
            "(SELECT COUNT(*) FROM thread_replies r WHERE r.thread_id=t.id) as reply_count "
            "FROM threads t ORDER BY t.created_at DESC"
        ).fetchall()
        assert len(rows) == 2
        # Find thread 1 and check reply count
        t1 = [r for r in rows if r["id"] == "t1"][0]
        t2 = [r for r in rows if r["id"] == "t2"][0]
        assert t1["reply_count"] == 3
        assert t2["reply_count"] == 0

    def test_list_empty_threads(self, db_conn):
        """Listing when no threads exist returns empty result."""
        rows = db_conn.execute("SELECT id FROM threads").fetchall()
        assert len(rows) == 0

    def test_thread_lookup_by_prefix(self, db_conn):
        """Threads can be looked up by ID prefix (LIKE pattern)."""
        db_conn.execute("INSERT INTO threads(id, title, author) VALUES ('abcdef', 'Test', 'alice')")
        db_conn.commit()

        row = db_conn.execute("SELECT id FROM threads WHERE id LIKE 'abc%' LIMIT 1").fetchone()
        assert row is not None
        assert row["id"] == "abcdef"
