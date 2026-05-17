"""Tests for lib/board_hint — proactive association hint plumbing (#158 phase 1)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.board_hint import (
    SCOPE_SENDER,
    SCOPE_TOPIC,
    STATUS_DROPPED_RATE,
    STATUS_EXPIRED,
    STATUS_MUTED,
    STATUS_PENDING,
    _is_muted,
    _rate_capped,
    clear_hints,
    cmd_hint,
    emit_hint,
    list_hints,
    mute,
    unmute,
)


@pytest.fixture
def hint_db(db):
    """BoardDB with the hint tables ensured (migration 010 already applied via _auto_migrate)."""
    return db


class TestSchema:
    def test_hints_table_exists(self, hint_db):
        rows = hint_db.query("SELECT name FROM sqlite_master WHERE type='table' AND name='hints'")
        assert rows

    def test_hint_events_table_exists(self, hint_db):
        rows = hint_db.query("SELECT name FROM sqlite_master WHERE type='table' AND name='hint_events'")
        assert rows

    def test_hint_mutes_table_exists(self, hint_db):
        rows = hint_db.query("SELECT name FROM sqlite_master WHERE type='table' AND name='hint_mutes'")
        assert rows


class TestEmitHint:
    def test_basic_emit(self, hint_db):
        hint_id = emit_hint(hint_db, "alice", "bob", "you might want to look at #42", confidence=0.8)
        assert hint_id > 0
        row = hint_db.query_one("SELECT status, confidence, body FROM hints WHERE id=?", (hint_id,))
        assert row["status"] == STATUS_PENDING
        assert row["confidence"] == pytest.approx(0.8)
        assert "#42" in row["body"]

    def test_emit_logs_event(self, hint_db):
        hint_id = emit_hint(hint_db, "alice", "bob", "test", confidence=0.7)
        events = hint_db.query("SELECT event FROM hint_events WHERE hint_id=?", (hint_id,))
        assert len(events) == 1
        assert events[0]["event"] == "emit"

    def test_emit_stores_refs_as_json(self, hint_db):
        refs = {"issues": [42, 153], "paths": ["lib/foo.py"]}
        hint_id = emit_hint(hint_db, "alice", "bob", "test", confidence=0.7, refs=refs)
        row = hint_db.query_one("SELECT refs FROM hints WHERE id=?", (hint_id,))
        assert json.loads(row["refs"]) == refs

    def test_below_threshold_still_pending(self, hint_db):
        """v1 plumbing: below-threshold hints enter pending; surface (phase 3) won't pick them up."""
        hint_id = emit_hint(hint_db, "alice", "bob", "test", confidence=0.1)
        row = hint_db.query_one("SELECT status FROM hints WHERE id=?", (hint_id,))
        assert row["status"] == STATUS_PENDING


class TestRateCap:
    def test_under_cap_passes(self, hint_db):
        for _ in range(2):
            hid = emit_hint(hint_db, "alice", "bob", "test", confidence=0.8)
            row = hint_db.query_one("SELECT status FROM hints WHERE id=?", (hid,))
            assert row["status"] == STATUS_PENDING

    def test_exceeds_cap_drops_to_dropped_rate(self, hint_db):
        # default rate limit is 3/hour
        for _ in range(3):
            emit_hint(hint_db, "alice", "bob", "test", confidence=0.8)
        hid = emit_hint(hint_db, "alice", "bob", "test4", confidence=0.8)
        row = hint_db.query_one("SELECT status FROM hints WHERE id=?", (hid,))
        assert row["status"] == STATUS_DROPPED_RATE

    def test_rate_cap_per_recipient(self, hint_db):
        """Cap is per sender+recipient, so different recipients are independent."""
        for _ in range(3):
            emit_hint(hint_db, "alice", "bob", "test", confidence=0.8)
        # Same sender, different recipient: should still pass
        hid = emit_hint(hint_db, "alice", "charlie", "test", confidence=0.8)
        row = hint_db.query_one("SELECT status FROM hints WHERE id=?", (hid,))
        assert row["status"] == STATUS_PENDING


class TestMute:
    def test_mute_sender(self, hint_db):
        mute(hint_db, "bob", sender="alice")
        rows = hint_db.query("SELECT scope, value FROM hint_mutes WHERE recipient='bob'")
        assert (rows[0]["scope"], rows[0]["value"]) == (SCOPE_SENDER, "alice")

    def test_mute_topic_issue(self, hint_db):
        mute(hint_db, "bob", topic="issue:42")
        rows = hint_db.query("SELECT scope, value FROM hint_mutes WHERE recipient='bob'")
        assert (rows[0]["scope"], rows[0]["value"]) == (SCOPE_TOPIC, "issue:42")

    def test_mute_topic_path(self, hint_db):
        mute(hint_db, "bob", topic="path:lib/foo.py")
        rows = hint_db.query("SELECT scope, value FROM hint_mutes WHERE recipient='bob'")
        assert rows[0]["value"] == "path:lib/foo.py"

    def test_unmute_removes_row(self, hint_db):
        mute(hint_db, "bob", sender="alice")
        n = unmute(hint_db, "bob", sender="alice")
        assert n == 1
        rows = hint_db.query("SELECT * FROM hint_mutes WHERE recipient='bob'")
        assert rows == []

    def test_mute_without_args_raises(self, hint_db):
        with pytest.raises(SystemExit):
            mute(hint_db, "bob")

    def test_mute_with_both_args_raises(self, hint_db):
        with pytest.raises(SystemExit):
            mute(hint_db, "bob", sender="alice", topic="issue:42")

    def test_muted_sender_hint_marked_muted(self, hint_db):
        mute(hint_db, "bob", sender="alice")
        hid = emit_hint(hint_db, "alice", "bob", "test", confidence=0.8)
        row = hint_db.query_one("SELECT status FROM hints WHERE id=?", (hid,))
        assert row["status"] == STATUS_MUTED

    def test_muted_topic_hint_marked_muted(self, hint_db):
        mute(hint_db, "bob", topic="issue:42")
        hid = emit_hint(
            hint_db,
            "alice",
            "bob",
            "test",
            confidence=0.8,
            refs={"issues": [42], "paths": []},
        )
        row = hint_db.query_one("SELECT status FROM hints WHERE id=?", (hid,))
        assert row["status"] == STATUS_MUTED


class TestIsMuted:
    def test_sender_match(self, hint_db):
        mute(hint_db, "bob", sender="alice")
        assert _is_muted(hint_db, "bob", "alice", {}) is True

    def test_sender_no_match(self, hint_db):
        mute(hint_db, "bob", sender="alice")
        assert _is_muted(hint_db, "bob", "charlie", {}) is False

    def test_topic_issue_match(self, hint_db):
        mute(hint_db, "bob", topic="issue:42")
        assert _is_muted(hint_db, "bob", "alice", {"issues": [42]}) is True

    def test_topic_path_match(self, hint_db):
        mute(hint_db, "bob", topic="path:lib/foo.py")
        assert _is_muted(hint_db, "bob", "alice", {"paths": ["lib/foo.py"]}) is True


class TestListHints:
    def test_filters_by_recipient(self, hint_db):
        emit_hint(hint_db, "alice", "bob", "to bob", confidence=0.8)
        emit_hint(hint_db, "alice", "charlie", "to lisa", confidence=0.8)
        hints = list_hints(hint_db, recipient="bob")
        assert len(hints) == 1
        assert hints[0]["recipient"] == "bob"

    def test_filters_by_sender(self, hint_db):
        emit_hint(hint_db, "alice", "bob", "from alice", confidence=0.8)
        emit_hint(hint_db, "charlie", "bob", "from charlie", confidence=0.8)
        hints = list_hints(hint_db, sender="alice")
        assert len(hints) == 1
        assert hints[0]["sender"] == "alice"

    def test_excludes_expired_by_default(self, hint_db):
        hid = emit_hint(hint_db, "alice", "bob", "test", confidence=0.8)
        hint_db.execute("UPDATE hints SET status=? WHERE id=?", (STATUS_EXPIRED, hid))
        hints = list_hints(hint_db, recipient="bob")
        assert hints == []

    def test_include_expired_when_requested(self, hint_db):
        hid = emit_hint(hint_db, "alice", "bob", "test", confidence=0.8)
        hint_db.execute("UPDATE hints SET status=? WHERE id=?", (STATUS_EXPIRED, hid))
        hints = list_hints(hint_db, recipient="bob", include_expired=True)
        assert len(hints) == 1


class TestClearHints:
    def test_clears_pending_and_surfaced(self, hint_db):
        emit_hint(hint_db, "alice", "bob", "p1", confidence=0.8)
        emit_hint(hint_db, "alice", "bob", "p2", confidence=0.8)
        n = clear_hints(hint_db, "bob")
        assert n == 2
        rows = hint_db.query("SELECT status FROM hints WHERE recipient='bob'")
        assert all(r["status"] == STATUS_EXPIRED for r in rows)

    def test_clear_logs_ignore_event(self, hint_db):
        hid = emit_hint(hint_db, "alice", "bob", "p1", confidence=0.8)
        clear_hints(hint_db, "bob")
        events = hint_db.query("SELECT event FROM hint_events WHERE hint_id=? ORDER BY id", (hid,))
        assert [e["event"] for e in events] == ["emit", "ignore"]

    def test_clear_does_not_touch_inbox(self, hint_db):
        """Critical guarantee: clearing hints must not affect inbox state."""
        # seed an unread message in the inbox
        msg_id = hint_db.execute(
            "INSERT INTO messages(sender, recipient, body) VALUES (?, ?, ?)",
            ("alice", "bob", "real message"),
        )
        hint_db.execute(
            "INSERT INTO inbox(session, message_id, read) VALUES (?, ?, 0)",
            ("bob", msg_id),
        )
        # emit and clear a hint
        emit_hint(hint_db, "alice", "bob", "hint", confidence=0.8)
        clear_hints(hint_db, "bob")
        # inbox unread count unchanged
        unread = hint_db.scalar("SELECT COUNT(*) FROM inbox WHERE session='bob' AND read=0")
        assert unread == 1


class TestCmdHint:
    def test_emit_command(self, hint_db, capsys):
        cmd_hint(hint_db, "alice", ["emit", "bob", "你看一下 #42 跟你 lib/foo.py 相关"])
        out = capsys.readouterr().out
        assert "OK hint #1 emitted to bob" in out
        rows = hint_db.query("SELECT body FROM hints WHERE id=1")
        assert "#42" in rows[0]["body"]

    def test_emit_with_refs_and_confidence(self, hint_db):
        cmd_hint(
            hint_db,
            "alice",
            ["emit", "bob", "test", "--confidence", "0.9", "--refs", "issues:42,paths:lib/foo.py"],
        )
        row = hint_db.query_one("SELECT confidence, refs FROM hints WHERE id=1")
        assert row["confidence"] == pytest.approx(0.9)
        assert json.loads(row["refs"]) == {"issues": [42], "paths": ["lib/foo.py"]}

    def test_list_command(self, hint_db, capsys):
        emit_hint(hint_db, "alice", "bob", "test 1", confidence=0.8)
        cmd_hint(hint_db, "bob", ["list"])
        out = capsys.readouterr().out
        assert "from alice" in out
        assert "test 1" in out

    def test_list_empty(self, hint_db, capsys):
        cmd_hint(hint_db, "bob", ["list"])
        out = capsys.readouterr().out
        assert "没有 hint" in out

    def test_mute_command(self, hint_db, capsys):
        cmd_hint(hint_db, "bob", ["mute", "alice"])
        out = capsys.readouterr().out
        assert "muted sender 'alice'" in out
        rows = hint_db.query("SELECT * FROM hint_mutes WHERE recipient='bob'")
        assert len(rows) == 1

    def test_unmute_command(self, hint_db, capsys):
        mute(hint_db, "bob", sender="alice")
        cmd_hint(hint_db, "bob", ["unmute", "alice"])
        out = capsys.readouterr().out
        assert "unmuted sender 'alice' (1 row)" in out

    def test_clear_command(self, hint_db, capsys):
        emit_hint(hint_db, "alice", "bob", "test", confidence=0.8)
        cmd_hint(hint_db, "bob", ["clear"])
        out = capsys.readouterr().out
        assert "清空 1 条 hint" in out

    def test_unknown_subcommand(self, hint_db, capsys):
        with pytest.raises(SystemExit):
            cmd_hint(hint_db, "bob", ["bogus"])
        out = capsys.readouterr().out
        assert "unknown hint subcommand" in out

    def test_no_args(self, hint_db, capsys):
        with pytest.raises(SystemExit):
            cmd_hint(hint_db, "bob", [])
        out = capsys.readouterr().out
        assert "Usage:" in out


class TestRateCapHelper:
    def test_returns_false_under_cap(self, hint_db):
        assert _rate_capped(hint_db, "alice", "bob", 3) is False

    def test_returns_true_at_cap(self, hint_db):
        for _ in range(3):
            emit_hint(hint_db, "alice", "bob", "test", confidence=0.8)
        assert _rate_capped(hint_db, "alice", "bob", 3) is True
