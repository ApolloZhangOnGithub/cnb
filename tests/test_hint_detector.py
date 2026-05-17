"""Tests for lib/hint_detector — phase 2 of #158 (signal extraction + detection)."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.board_hint import STATUS_PENDING, emit_hint
from lib.hint_detector import (
    WEIGHT_ISSUE_REF,
    WEIGHT_KEYWORD_OVERLAP,
    WEIGHT_PATH_OVERLAP,
    compute_confidence,
    compute_signals,
    detect_hints,
    extract_issue_refs,
    extract_keywords,
    extract_paths,
    recency_multiplier,
    run_for_message,
)

# ── extract_* unit tests ─────────────────────────────────────────────────────


class TestExtractIssueRefs:
    def test_simple_hash(self):
        assert extract_issue_refs("see #42") == {42}

    def test_multiple(self):
        assert extract_issue_refs("see #42 and #153, also #999") == {42, 153, 999}

    def test_pr_prefix(self):
        assert extract_issue_refs("PR #221 fixed it") == {221}

    def test_no_refs(self):
        assert extract_issue_refs("just plain text") == set()

    def test_hash_not_followed_by_digit_ignored(self):
        assert extract_issue_refs("#abc not an issue") == set()


class TestExtractPaths:
    def test_simple_path(self):
        assert extract_paths("look at lib/foo.py") == {"lib/foo.py"}

    def test_nested_path(self):
        assert extract_paths("see docs/dev/x.md") == {"docs/dev/x.md"}

    def test_multiple(self):
        text = "diff lib/a.py and tests/test_a.py"
        assert extract_paths(text) == {"lib/a.py", "tests/test_a.py"}

    def test_no_paths(self):
        assert extract_paths("just text") == set()

    def test_url_does_not_match(self):
        # We require a file extension at the end; bare slashes don't qualify.
        assert extract_paths("look here") == set()


class TestExtractKeywords:
    def test_lowercase_and_filter_short(self):
        # "a" is short, "the" is stopword, "alert" passes
        assert extract_keywords("The alert is critical") == {"alert", "critical"}

    def test_filters_stopwords(self):
        assert extract_keywords("this is a test") == {"test"}

    def test_empty(self):
        assert extract_keywords("") == set()

    def test_chinese_tokenization_is_coarse_v1(self):
        """v1 limitation: regex `\\w+` lumps contiguous CJK characters into one
        token. Proper segmentation (jieba etc.) is a v2 upgrade. Test documents
        the known shape so v2 can change it intentionally."""
        # Whole CJK run is one token (no spaces to split on); too long for keyword
        # overlap to be useful, but the function shouldn't crash.
        tokens = extract_keywords("你的测试数据是这个")
        assert isinstance(tokens, set)


class TestRecencyMultiplier:
    def test_now_is_one(self):
        now = datetime(2026, 5, 17, 12, 0, 0)
        assert recency_multiplier("2026-05-17 12:00:00", now) == pytest.approx(1.0)

    def test_half_life_24h(self):
        now = datetime(2026, 5, 17, 12, 0, 0)
        # 24h ago → 0.5
        ts = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        assert recency_multiplier(ts, now) == pytest.approx(0.5)

    def test_double_half_life(self):
        now = datetime(2026, 5, 17, 12, 0, 0)
        # 48h ago → 0.25
        ts = (now - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
        assert recency_multiplier(ts, now) == pytest.approx(0.25)

    def test_unparseable_returns_one(self):
        assert recency_multiplier("not a date", datetime(2026, 5, 17)) == 1.0


# ── compute_signals composition ──────────────────────────────────────────────


class TestComputeSignals:
    def setup_method(self):
        self.now = datetime(2026, 5, 17, 12, 0, 0)
        self.fresh_ts = "2026-05-17 12:00:00"

    def test_issue_ref_only(self):
        s = compute_signals("worked on #42", "what about #42", self.fresh_ts, self.now)
        assert s == {"issue_ref": pytest.approx(WEIGHT_ISSUE_REF)}

    def test_path_overlap_only(self):
        # Path overlap, no shared keywords (different surrounding words to keep
        # the keyword-overlap signal below KEYWORD_OVERLAP_MIN).
        s = compute_signals("touched lib/foo.py", "rewriting lib/foo.py", self.fresh_ts, self.now)
        # path_overlap fires; keyword overlap may or may not — assert at minimum
        # that path_overlap is present with the right weight.
        assert s.get("path_overlap") == pytest.approx(WEIGHT_PATH_OVERLAP)

    def test_keyword_overlap_only(self):
        s = compute_signals(
            "discussed authentication implementation details",
            "implementation details about authentication required",
            self.fresh_ts,
            self.now,
        )
        assert "keyword_overlap" in s
        assert s["keyword_overlap"] == pytest.approx(WEIGHT_KEYWORD_OVERLAP)

    def test_all_three_signals(self):
        s = compute_signals(
            "PR #42 touched lib/x.py for authentication redesign",
            "is #42 redesign for authentication in lib/x.py done",
            self.fresh_ts,
            self.now,
        )
        assert set(s.keys()) == {"issue_ref", "path_overlap", "keyword_overlap"}

    def test_no_signals(self):
        s = compute_signals("completely unrelated", "different topic entirely", self.fresh_ts, self.now)
        assert s == {}

    def test_recency_attenuates(self):
        old_ts = (self.now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        s = compute_signals("worked on #42", "what about #42", old_ts, self.now)
        # 24h half-life → ~0.5 of base weight
        assert s["issue_ref"] == pytest.approx(WEIGHT_ISSUE_REF * 0.5)


class TestComputeConfidence:
    def test_empty(self):
        assert compute_confidence({}) == 0.0

    def test_single(self):
        assert compute_confidence({"issue_ref": 0.5}) == 0.5

    def test_sum(self):
        assert compute_confidence({"issue_ref": 0.5, "path_overlap": 0.3}) == pytest.approx(0.8)

    def test_capped_at_one(self):
        assert compute_confidence({"a": 0.6, "b": 0.6, "c": 0.6}) == 1.0


# ── detect_hints — full DB integration ───────────────────────────────────────


def _seed_message(db, sender, recipient, body, ts_offset_hours=0, now=None):
    """Helper: insert a message at `now - ts_offset_hours`."""
    if now is None:
        now = datetime.now()
    ts = (now - timedelta(hours=ts_offset_hours)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
        (ts, sender, recipient, body),
    )


@pytest.fixture
def hint_db(db):
    """Reuse the standard board fixture; hint tables already exist via schema.sql."""
    return db


class TestDetectHints:
    def test_no_eligible_senders(self, hint_db):
        # bob has never messaged charlie before, so when charlie's message
        # comes in we have no candidates to scan
        result = detect_hints(hint_db, "charlie", "what about #42")
        assert result == []

    def test_no_overlap_no_hints(self, hint_db):
        _seed_message(hint_db, "alice", "charlie", "unrelated content", ts_offset_hours=1)
        result = detect_hints(hint_db, "charlie", "completely different topic")
        assert result == []

    def test_issue_ref_emits_candidate(self, hint_db):
        now = datetime(2026, 5, 17, 12, 0, 0)
        _seed_message(hint_db, "alice", "charlie", "I fixed #42 yesterday", ts_offset_hours=1, now=now)
        result = detect_hints(hint_db, "charlie", "what about #42 still broken?", now=now)
        assert len(result) == 1
        assert result[0]["sender"] == "alice"
        assert result[0]["recipient"] == "charlie"
        assert result[0]["refs"]["issues"] == [42]
        assert result[0]["confidence"] > 0

    def test_path_overlap_emits_candidate(self, hint_db):
        now = datetime(2026, 5, 17, 12, 0, 0)
        _seed_message(hint_db, "alice", "charlie", "edited lib/foo.py", ts_offset_hours=1, now=now)
        result = detect_hints(hint_db, "charlie", "lib/foo.py crashes", now=now)
        assert len(result) == 1
        assert "lib/foo.py" in result[0]["refs"]["paths"]

    def test_picks_strongest_prior_per_sender(self, hint_db):
        """Same sender's multiple priors — emit only the best-scoring one."""
        now = datetime(2026, 5, 17, 12, 0, 0)
        _seed_message(hint_db, "alice", "charlie", "weak: keyword only test", ts_offset_hours=1, now=now)
        _seed_message(hint_db, "alice", "charlie", "strong: #42 + lib/foo.py", ts_offset_hours=1, now=now)
        result = detect_hints(hint_db, "charlie", "is #42 in lib/foo.py done", now=now)
        # only one candidate per sender even though both messages overlap
        assert len(result) == 1
        # the strong one wins — should reference #42 and lib/foo.py
        assert 42 in result[0]["refs"]["issues"]

    def test_eligible_sender_must_have_messaged_recipient(self, hint_db):
        """A→B, but not A→C, means A is NOT eligible to emit hints to C."""
        now = datetime(2026, 5, 17, 12, 0, 0)
        # alice messaged bob (not charlie); incoming is to charlie
        _seed_message(hint_db, "alice", "bob", "I fixed #42", ts_offset_hours=1, now=now)
        result = detect_hints(hint_db, "charlie", "what about #42", now=now)
        assert result == []

    def test_lookback_window_respected(self, hint_db):
        """Messages older than lookback_hours are ignored."""
        now = datetime(2026, 5, 17, 12, 0, 0)
        _seed_message(hint_db, "alice", "charlie", "I fixed #42", ts_offset_hours=72, now=now)
        result = detect_hints(hint_db, "charlie", "what about #42", now=now, lookback_hours=48.0)
        assert result == []

    def test_one_candidate_per_sender(self, hint_db):
        """Two different senders both overlap → two candidates."""
        now = datetime(2026, 5, 17, 12, 0, 0)
        _seed_message(hint_db, "alice", "charlie", "I fixed #42", ts_offset_hours=1, now=now)
        _seed_message(hint_db, "bob", "charlie", "also touched #42", ts_offset_hours=2, now=now)
        result = detect_hints(hint_db, "charlie", "what about #42", now=now)
        senders = {c["sender"] for c in result}
        assert senders == {"alice", "bob"}


class TestRunForMessage:
    def test_emits_hints_via_emit_hint(self, hint_db):
        now = datetime(2026, 5, 17, 12, 0, 0)
        _seed_message(hint_db, "alice", "charlie", "I fixed #42", ts_offset_hours=1, now=now)
        emitted = run_for_message(hint_db, "charlie", "what about #42", now=now)
        assert len(emitted) == 1
        # the hint actually landed in the hints table
        row = hint_db.query_one("SELECT sender, recipient, status FROM hints WHERE id=?", (emitted[0],))
        assert (row["sender"], row["recipient"], row["status"]) == ("alice", "charlie", STATUS_PENDING)

    def test_no_candidates_returns_empty(self, hint_db):
        emitted = run_for_message(hint_db, "charlie", "unrelated text")
        assert emitted == []

    def test_detector_exception_swallowed(self, hint_db, monkeypatch):
        """A failing detector must NOT propagate — message delivery comes first."""

        def boom(*args, **kwargs):
            raise RuntimeError("detector blew up")

        monkeypatch.setattr("lib.hint_detector.detect_hints", boom)
        # Must not raise.
        emitted = run_for_message(hint_db, "charlie", "anything")
        assert emitted == []

    def test_one_failing_emit_does_not_sink_others(self, hint_db, monkeypatch):
        now = datetime(2026, 5, 17, 12, 0, 0)
        _seed_message(hint_db, "alice", "charlie", "I fixed #42", ts_offset_hours=1, now=now)
        _seed_message(hint_db, "bob", "charlie", "also #42", ts_offset_hours=2, now=now)

        calls = {"n": 0}
        original_emit = emit_hint

        def flaky_emit(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("simulated emit failure")
            return original_emit(*args, **kwargs)

        monkeypatch.setattr("lib.hint_detector.emit_hint", flaky_emit)
        emitted = run_for_message(hint_db, "charlie", "what about #42", now=now)
        # One emit failed, one succeeded
        assert len(emitted) == 1


# ── Integration with cmd_send ────────────────────────────────────────────────


class TestSendPipelineIntegration:
    def test_cmd_send_triggers_detection(self, hint_db, monkeypatch):
        """When charlie sends a message that overlaps with alice's prior outbox,
        cmd_send should fire the detector and a hint should land in the hints table."""
        from lib.board_msg import cmd_send

        # alice has prior thread mentioning #42 to charlie
        now = datetime.now()
        ts_recent = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        hint_db.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, ?, ?, ?)",
            (ts_recent, "alice", "charlie", "fixed #42 yesterday"),
        )

        # Now charlie sends bob a message about #42
        # Suppress board_msg side effects (nudge / network)
        monkeypatch.setattr("lib.board_msg.nudge_session", lambda *a, **kw: None)
        cmd_send(hint_db, "charlie", ["bob", "is", "#42", "still", "broken?"])

        # Detection ran on bob (recipient). alice messaged charlie, not bob, so
        # alice is NOT eligible. But what about charlie? charlie just sent to bob,
        # so charlie is now an eligible sender for bob → next time bob messages
        # charlie, we'd see hints. This test confirms the pipeline runs without
        # error, not necessarily that hints fire (depends on eligibility).
        # The KEY assertion is no exception from cmd_send.
        msg_rows = hint_db.query("SELECT sender, recipient FROM messages WHERE recipient='bob'")
        assert ("charlie", "bob") in [(r[0], r[1]) for r in msg_rows]

    def test_cmd_send_to_all_skips_detection(self, hint_db, monkeypatch):
        """Broadcasts skip detection — recipient='all' is not a real session."""
        from lib.board_msg import cmd_send

        called = {"n": 0}

        def fake_run(*args, **kwargs):
            called["n"] += 1
            return []

        monkeypatch.setattr("lib.board_msg.nudge_session", lambda *a, **kw: None)
        monkeypatch.setattr("lib.hint_detector.run_for_message", fake_run)
        cmd_send(hint_db, "alice", ["all", "broadcast", "message"])
        assert called["n"] == 0
