"""Tests for the board messaging subsystem.

Covers: send, inbox, ack, log, broadcast (send to 'all'),
attachments, and the --mine filter.
"""

from tests.conftest import ts


class TestSendMessage:
    """Sending messages between sessions."""

    def test_send_creates_message_record(self, db_conn):
        """Sending a message inserts a row into the messages table."""
        now = ts()
        db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (now, "alice", "bob", "hello bob"),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT sender, recipient, body FROM messages WHERE sender='alice'").fetchone()
        assert row is not None
        assert row["sender"] == "alice"
        assert row["recipient"] == "bob"
        assert row["body"] == "hello bob"

    def test_send_delivers_to_inbox(self, db_conn):
        """A sent message creates an inbox entry for the recipient."""
        now = ts()
        cur = db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (now, "alice", "bob", "check this out"),
        )
        msg_id = cur.lastrowid
        db_conn.execute(
            "INSERT INTO inbox(session, message_id) VALUES (?, ?)",
            ("bob", msg_id),
        )
        db_conn.commit()

        count = db_conn.execute("SELECT COUNT(*) FROM inbox WHERE session='bob' AND read=0").fetchone()[0]
        assert count == 1

    def test_send_to_all_delivers_to_everyone_except_sender(self, db_conn):
        """Broadcast (to='all') creates inbox entries for all sessions except sender."""
        now = ts()
        cur = db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (now, "alice", "all", "team announcement"),
        )
        msg_id = cur.lastrowid

        # Deliver to all except alice
        sessions = db_conn.execute("SELECT name FROM sessions WHERE name != 'alice'").fetchall()
        for s in sessions:
            db_conn.execute(
                "INSERT INTO inbox(session, message_id) VALUES (?, ?)",
                (s["name"], msg_id),
            )
        db_conn.commit()

        # Bob and Charlie should have the message
        for name in ["bob", "charlie"]:
            count = db_conn.execute(
                "SELECT COUNT(*) FROM inbox WHERE session=? AND read=0",
                (name,),
            ).fetchone()[0]
            assert count == 1, f"{name} should have 1 unread message"

        # Alice should NOT have the message
        alice_count = db_conn.execute("SELECT COUNT(*) FROM inbox WHERE session='alice' AND read=0").fetchone()[0]
        assert alice_count == 0, "Sender should not receive their own broadcast"

    def test_send_with_empty_body_requires_content(self, db_conn):
        """Messages should have a non-empty body (enforced at application level)."""
        # The schema allows empty body, but the CLI enforces non-empty.
        # Test that the DB at least stores what we give it.
        now = ts()
        db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (now, "alice", "bob", ""),
        )
        db_conn.commit()
        row = db_conn.execute("SELECT body FROM messages WHERE sender='alice'").fetchone()
        assert row["body"] == ""

    def test_multiple_messages_ordered_by_id(self, db_conn):
        """Messages are retrievable in insertion order."""
        now = ts()
        for i in range(5):
            db_conn.execute(
                "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
                (now, "alice", "bob", f"msg {i}"),
            )
        db_conn.commit()

        rows = db_conn.execute("SELECT body FROM messages ORDER BY id ASC").fetchall()
        assert len(rows) == 5
        for i, row in enumerate(rows):
            assert row["body"] == f"msg {i}"


class TestInbox:
    """Inbox reading and unread counts."""

    def _send_msg(self, db_conn, sender, recipient, body):
        """Helper: insert a message and deliver to recipient's inbox."""
        now = ts()
        cur = db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (now, sender, recipient, body),
        )
        msg_id = cur.lastrowid
        db_conn.execute(
            "INSERT INTO inbox(session, message_id) VALUES (?, ?)",
            (recipient, msg_id),
        )
        db_conn.commit()
        return msg_id

    def test_inbox_shows_unread_count(self, db_conn):
        """Unread count reflects number of undelivered messages."""
        self._send_msg(db_conn, "alice", "bob", "message 1")
        self._send_msg(db_conn, "charlie", "bob", "message 2")

        count = db_conn.execute("SELECT COUNT(*) FROM inbox WHERE session='bob' AND read=0").fetchone()[0]
        assert count == 2

    def test_inbox_empty_when_no_messages(self, db_conn):
        """Empty inbox returns zero unread."""
        count = db_conn.execute("SELECT COUNT(*) FROM inbox WHERE session='bob' AND read=0").fetchone()[0]
        assert count == 0

    def test_inbox_shows_message_details(self, db_conn):
        """Inbox join retrieves message sender and body."""
        self._send_msg(db_conn, "alice", "bob", "important stuff")

        row = db_conn.execute(
            "SELECT m.sender, m.body FROM inbox i "
            "JOIN messages m ON i.message_id=m.id "
            "WHERE i.session='bob' AND i.read=0"
        ).fetchone()
        assert row is not None
        assert row["sender"] == "alice"
        assert row["body"] == "important stuff"


class TestAck:
    """Acknowledging (clearing) inbox."""

    def _send_msg(self, db_conn, sender, recipient, body):
        now = ts()
        cur = db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (now, sender, recipient, body),
        )
        msg_id = cur.lastrowid
        db_conn.execute(
            "INSERT INTO inbox(session, message_id) VALUES (?, ?)",
            (recipient, msg_id),
        )
        db_conn.commit()
        return msg_id

    def test_ack_clears_inbox(self, db_conn):
        """Ack marks all unread messages as read for a session."""
        self._send_msg(db_conn, "alice", "bob", "msg 1")
        self._send_msg(db_conn, "charlie", "bob", "msg 2")

        # Ack
        db_conn.execute("UPDATE inbox SET read=1 WHERE session='bob' AND read=0")
        db_conn.commit()

        count = db_conn.execute("SELECT COUNT(*) FROM inbox WHERE session='bob' AND read=0").fetchone()[0]
        assert count == 0

    def test_ack_idempotent(self, db_conn):
        """Acking an already-empty inbox does not error."""
        # No messages sent to bob
        db_conn.execute("UPDATE inbox SET read=1 WHERE session='bob' AND read=0")
        db_conn.commit()
        count = db_conn.execute("SELECT COUNT(*) FROM inbox WHERE session='bob' AND read=0").fetchone()[0]
        assert count == 0

    def test_ack_only_affects_target_session(self, db_conn):
        """Acking bob's inbox does not affect alice's inbox."""
        self._send_msg(db_conn, "charlie", "bob", "for bob")
        self._send_msg(db_conn, "charlie", "alice", "for alice")

        # Ack only bob
        db_conn.execute("UPDATE inbox SET read=1 WHERE session='bob' AND read=0")
        db_conn.commit()

        bob_count = db_conn.execute("SELECT COUNT(*) FROM inbox WHERE session='bob' AND read=0").fetchone()[0]
        alice_count = db_conn.execute("SELECT COUNT(*) FROM inbox WHERE session='alice' AND read=0").fetchone()[0]
        assert bob_count == 0
        assert alice_count == 1


class TestMessageLog:
    """Message log/history queries."""

    def _send_msg(self, db_conn, sender, recipient, body):
        now = ts()
        db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (now, sender, recipient, body),
        )
        db_conn.commit()

    def test_log_returns_recent_messages(self, db_conn):
        """Log query returns messages in chronological order."""
        for i in range(5):
            self._send_msg(db_conn, "alice", "bob", f"msg {i}")

        rows = db_conn.execute("SELECT body FROM messages ORDER BY id DESC LIMIT 20").fetchall()
        assert len(rows) == 5

    def test_log_mine_filter(self, db_conn):
        """--mine filter shows only messages involving the specified session."""
        self._send_msg(db_conn, "alice", "bob", "alice to bob")
        self._send_msg(db_conn, "charlie", "bob", "charlie to bob")
        self._send_msg(db_conn, "bob", "alice", "bob to alice")

        rows = db_conn.execute(
            "SELECT body FROM messages "
            "WHERE sender='alice' OR recipient='alice' OR recipient='all' "
            "ORDER BY id DESC LIMIT 20"
        ).fetchall()
        # Should include "alice to bob" and "bob to alice"
        assert len(rows) == 2

    def test_log_limit(self, db_conn):
        """Log respects the limit parameter."""
        for i in range(30):
            self._send_msg(db_conn, "alice", "bob", f"msg {i}")

        rows = db_conn.execute("SELECT body FROM messages ORDER BY id DESC LIMIT 10").fetchall()
        assert len(rows) == 10


class TestMessageAttachment:
    """Message attachments and file storage."""

    def test_file_record_created(self, db_conn):
        """Inserting a file record into the files table works."""
        db_conn.execute(
            "INSERT INTO files(hash, original_name, extension, sender, stored_path) VALUES (?, ?, ?, ?, ?)",
            ("abc123def456", "report.pdf", "pdf", "alice", "files/abc123def456.pdf"),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT original_name, sender FROM files WHERE hash='abc123def456'").fetchone()
        assert row is not None
        assert row["original_name"] == "report.pdf"
        assert row["sender"] == "alice"

    def test_file_hash_is_primary_key(self, db_conn):
        """Duplicate file hash is rejected (INSERT OR IGNORE)."""
        db_conn.execute(
            "INSERT INTO files(hash, original_name, extension, sender, stored_path) VALUES (?, ?, ?, ?, ?)",
            ("abc123def456", "report.pdf", "pdf", "alice", "files/abc123def456.pdf"),
        )
        db_conn.commit()

        # Insert again with IGNORE
        db_conn.execute(
            "INSERT OR IGNORE INTO files(hash, original_name, extension, sender, stored_path) VALUES (?, ?, ?, ?, ?)",
            ("abc123def456", "different.pdf", "pdf", "bob", "files/abc123def456.pdf"),
        )
        db_conn.commit()

        # Original record should be unchanged
        row = db_conn.execute("SELECT original_name, sender FROM files WHERE hash='abc123def456'").fetchone()
        assert row["original_name"] == "report.pdf"
        assert row["sender"] == "alice"

    def test_message_with_attachment_reference(self, db_conn):
        """Messages can reference an attachment hash."""
        now = ts()
        db_conn.execute(
            "INSERT INTO files(hash, original_name, extension, sender, stored_path) VALUES (?, ?, ?, ?, ?)",
            ("abc123def456", "data.csv", "csv", "alice", "files/abc123def456.csv"),
        )
        db_conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body, attachment) VALUES (?, ?, ?, ?, ?)",
            (now, "alice", "bob", "Here is the data", "abc123def456"),
        )
        db_conn.commit()

        row = db_conn.execute("SELECT body, attachment FROM messages WHERE attachment IS NOT NULL").fetchone()
        assert row is not None
        assert row["attachment"] == "abc123def456"
