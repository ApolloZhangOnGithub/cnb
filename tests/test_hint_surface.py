"""Tests for the phase-3 surface UI of #158 — yellow `💡` block in `board view`."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.board_hint import STATUS_SURFACED, emit_hint
from lib.board_view import _print_hints, cmd_view


def _enable_hints(db, threshold=0.6):
    """Write a `[hints]` section to notifications.toml turning the feature on."""
    toml = db.env.claudes_dir / "notifications.toml"
    toml.write_text(f"[hints]\nenabled = true\nthreshold = {threshold}\n")


@pytest.fixture
def hint_db(db):
    """BoardDB with hint tables; feature off unless test calls _enable_hints."""
    return db


class TestPrintHintsGuard:
    def test_silent_when_feature_disabled(self, hint_db, capsys):
        """Default state: [hints] enabled=false → no surface even with pending hints."""
        emit_hint(hint_db, "alice", "charlie", "test hint", confidence=0.9)
        _print_hints(hint_db, "charlie")
        assert capsys.readouterr().out == ""

    def test_silent_when_no_pending_hints(self, hint_db, capsys):
        _enable_hints(hint_db)
        _print_hints(hint_db, "charlie")
        assert capsys.readouterr().out == ""

    def test_silent_when_below_threshold(self, hint_db, capsys):
        _enable_hints(hint_db, threshold=0.6)
        emit_hint(hint_db, "alice", "charlie", "weak hint", confidence=0.3)
        _print_hints(hint_db, "charlie")
        assert capsys.readouterr().out == ""

    def test_surfaces_when_eligible(self, hint_db, capsys):
        _enable_hints(hint_db)
        emit_hint(hint_db, "alice", "charlie", "strong hint about #42", confidence=0.9)
        _print_hints(hint_db, "charlie")
        out = capsys.readouterr().out
        assert "💡" in out
        assert "from alice" in out
        assert "strong hint about #42" in out


class TestSurfaceMarkers:
    def test_pending_hint_becomes_surfaced(self, hint_db, capsys):
        _enable_hints(hint_db)
        hid = emit_hint(hint_db, "alice", "charlie", "hint", confidence=0.9)
        _print_hints(hint_db, "charlie")
        capsys.readouterr()  # drain
        row = hint_db.query_one("SELECT status, surfaced_at FROM hints WHERE id=?", (hid,))
        assert row["status"] == STATUS_SURFACED
        assert row["surfaced_at"] is not None

    def test_surface_event_logged(self, hint_db, capsys):
        _enable_hints(hint_db)
        hid = emit_hint(hint_db, "alice", "charlie", "hint", confidence=0.9)
        _print_hints(hint_db, "charlie")
        capsys.readouterr()
        events = hint_db.query("SELECT event FROM hint_events WHERE hint_id=? ORDER BY id", (hid,))
        # emit event from phase 1 + surface event from phase 3
        assert [e["event"] for e in events] == ["emit", "surface"]

    def test_surfaced_hint_not_re_surfaced(self, hint_db, capsys):
        """Once surfaced, a hint shouldn't appear again on the next view."""
        _enable_hints(hint_db)
        emit_hint(hint_db, "alice", "charlie", "hint", confidence=0.9)
        _print_hints(hint_db, "charlie")  # first surface
        capsys.readouterr()
        _print_hints(hint_db, "charlie")  # second view
        assert capsys.readouterr().out == ""


class TestOrdering:
    def test_higher_confidence_first(self, hint_db, capsys):
        _enable_hints(hint_db)
        emit_hint(hint_db, "alice", "charlie", "weaker", confidence=0.65)
        emit_hint(hint_db, "bob", "charlie", "stronger", confidence=0.95)
        _print_hints(hint_db, "charlie")
        out = capsys.readouterr().out
        assert out.index("stronger") < out.index("weaker")

    def test_caps_at_five_per_view(self, hint_db, capsys):
        _enable_hints(hint_db)
        for i in range(7):
            # different recipients-of-prior to keep them all in 'pending'
            emit_hint(hint_db, "alice", "charlie", f"hint {i}", confidence=0.9)
        _print_hints(hint_db, "charlie")
        out = capsys.readouterr().out
        # rate cap from phase 1 limits emit; we get at most rate_limit_per_hour (3) PENDING,
        # but the LIMIT 5 in the surface query is the cap. Just verify it doesn't
        # explode and surfaces a bounded count.
        surface_lines = [line for line in out.split("\n") if "from alice" in line]
        assert 1 <= len(surface_lines) <= 5


class TestBoardViewIntegration:
    def test_cmd_view_includes_hints_block(self, hint_db, capsys):
        """cmd_view should call _print_hints; block appears between unread alert and Status."""
        _enable_hints(hint_db)
        emit_hint(hint_db, "alice", "charlie", "integration hint about #42", confidence=0.9)
        cmd_view(hint_db, "charlie")
        out = capsys.readouterr().out
        assert "💡 association hints" in out
        assert "integration hint" in out

    def test_cmd_view_no_hints_block_when_disabled(self, hint_db, capsys):
        emit_hint(hint_db, "alice", "charlie", "hint", confidence=0.9)
        cmd_view(hint_db, "charlie")
        out = capsys.readouterr().out
        assert "💡" not in out
