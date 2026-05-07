"""Tests for board_vote — governance: propose, vote, tally."""

import pytest

from lib.board_vote import cmd_propose, cmd_tally, cmd_vote


@pytest.fixture(autouse=True)
def _set_dispatcher_meta(db):
    """Ensure meta.dispatcher_session is set so eligible-voter count works."""
    db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('dispatcher_session', 'dispatcher')")
    db.ensure_session("dispatcher")


class TestPropose:
    def test_creates_proposal(self, db, capsys):
        cmd_propose(db, "alice", ["should we use tabs or spaces?"])

        row = db.query_one("SELECT * FROM proposals WHERE number='001'")
        assert row is not None
        assert row["content"] == "should we use tabs or spaces?"
        assert row["type"] == "A"
        assert row["status"] == "OPEN"
        assert "OK 提案 #001" in capsys.readouterr().out

    def test_type_s_proposal(self, db, capsys):
        cmd_propose(db, "alice", ["--type", "S", "major refactor"])

        row = db.query_one("SELECT type FROM proposals WHERE number='001'")
        assert row["type"] == "S"

    def test_sequential_numbers(self, db, capsys):
        cmd_propose(db, "alice", ["first proposal"])
        cmd_propose(db, "bob", ["second proposal"])

        nums = [r["number"] for r in db.query("SELECT number FROM proposals ORDER BY number")]
        assert nums == ["001", "002"]

    def test_broadcasts_message(self, db, capsys):
        cmd_propose(db, "alice", ["test proposal"])

        msg = db.query_one("SELECT * FROM messages WHERE body LIKE '%PROPOSAL%'")
        assert msg is not None
        assert msg["recipient"] == "all"
        assert "#001" in msg["body"]

    def test_empty_content_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_propose(db, "alice", [])

    def test_invalid_type_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_propose(db, "alice", ["--type", "X", "bad type"])

    def test_slug_generated(self, db, capsys):
        cmd_propose(db, "alice", ["add dark mode support"])

        row = db.query_one("SELECT slug FROM proposals WHERE number='001'")
        assert "add-dark-mode" in row["slug"]


class TestVote:
    def _create_proposal(self, db, capsys):
        cmd_propose(db, "alice", ["test proposal"])
        capsys.readouterr()

    def test_vote_support(self, db, capsys):
        self._create_proposal(db, capsys)

        cmd_vote(db, "alice", ["1", "SUPPORT", "looks good"])

        vote = db.query_one("SELECT * FROM votes WHERE voter='alice'")
        assert vote["decision"] == "SUPPORT"
        assert vote["reason"] == "looks good"
        out = capsys.readouterr().out
        assert "OK voted SUPPORT" in out

    def test_vote_object(self, db, capsys):
        self._create_proposal(db, capsys)

        cmd_vote(db, "alice", ["1", "OBJECT", "too risky"])

        vote = db.query_one("SELECT * FROM votes WHERE voter='alice'")
        assert vote["decision"] == "OBJECT"

    def test_case_insensitive_decision(self, db, capsys):
        self._create_proposal(db, capsys)

        cmd_vote(db, "alice", ["1", "support", "ok"])

        vote = db.query_one("SELECT * FROM votes WHERE voter='alice'")
        assert vote["decision"] == "SUPPORT"

    def test_privileged_role_cannot_vote(self, db, capsys):
        self._create_proposal(db, capsys)

        with pytest.raises(SystemExit):
            cmd_vote(db, "lead", ["1", "SUPPORT", "reason"])

    def test_invalid_decision_exits(self, db, capsys):
        self._create_proposal(db, capsys)

        with pytest.raises(SystemExit):
            cmd_vote(db, "alice", ["1", "ABSTAIN", "reason"])

    def test_proposal_not_found_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_vote(db, "alice", ["999", "SUPPORT", "reason"])

    def test_vote_on_closed_proposal_exits(self, db, capsys):
        self._create_proposal(db, capsys)
        db.execute("UPDATE proposals SET status='PASSED' WHERE number='001'")

        with pytest.raises(SystemExit):
            cmd_vote(db, "alice", ["1", "SUPPORT", "reason"])

    def test_change_vote_replaces(self, db, capsys):
        self._create_proposal(db, capsys)

        cmd_vote(db, "alice", ["1", "SUPPORT", "yes"])
        capsys.readouterr()
        cmd_vote(db, "alice", ["1", "OBJECT", "changed mind"])

        votes = db.query("SELECT * FROM votes WHERE voter='alice'")
        assert len(votes) == 1
        assert votes[0]["decision"] == "OBJECT"

    def test_missing_args_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_vote(db, "alice", ["1", "SUPPORT"])

    def test_padded_number_lookup(self, db, capsys):
        self._create_proposal(db, capsys)
        cmd_vote(db, "alice", ["001", "SUPPORT", "padded"])

        vote = db.query_one("SELECT * FROM votes WHERE voter='alice'")
        assert vote is not None

    def test_shows_tally_after_vote(self, db, capsys):
        self._create_proposal(db, capsys)
        cmd_vote(db, "alice", ["1", "SUPPORT", "good idea"])

        out = capsys.readouterr().out
        assert "Tally:" in out
        assert "alice: SUPPORT" in out


class TestAutoDecision:
    def _setup_proposal_with_sessions(self, db, capsys, n_sessions=5):
        """Create a proposal and add extra sessions to meet thresholds."""
        for i in range(n_sessions):
            db.execute("INSERT OR IGNORE INTO sessions(name) VALUES (?)", (f"voter{i}",))
        cmd_propose(db, "alice", ["test proposal"])
        capsys.readouterr()

    def test_type_a_passes_at_majority(self, db, capsys):
        self._setup_proposal_with_sessions(db, capsys)

        eligible = (
            db.scalar(
                "SELECT COUNT(*) FROM sessions WHERE name != (SELECT value FROM meta WHERE key='dispatcher_session')"
            )
            or 0
        )
        threshold = eligible // 2 + 1

        for i in range(threshold):
            name = f"voter{i}"
            cmd_vote(db, name, ["1", "SUPPORT", "yes"])
            capsys.readouterr()

        status = db.scalar("SELECT status FROM proposals WHERE number='001'")
        assert status == "PASSED"

    def test_type_a_fails_when_impossible(self, db, capsys):
        self._setup_proposal_with_sessions(db, capsys)

        eligible = (
            db.scalar(
                "SELECT COUNT(*) FROM sessions WHERE name != (SELECT value FROM meta WHERE key='dispatcher_session')"
            )
            or 0
        )
        threshold = eligible // 2 + 1
        needed_objects = eligible - threshold + 1

        for i in range(needed_objects):
            name = f"voter{i}"
            cmd_vote(db, name, ["1", "OBJECT", "no"])
            capsys.readouterr()

        status = db.scalar("SELECT status FROM proposals WHERE number='001'")
        assert status == "FAILED"

    def test_pass_creates_system_message(self, db, capsys):
        self._setup_proposal_with_sessions(db, capsys)

        eligible = (
            db.scalar(
                "SELECT COUNT(*) FROM sessions WHERE name != (SELECT value FROM meta WHERE key='dispatcher_session')"
            )
            or 0
        )
        threshold = eligible // 2 + 1

        for i in range(threshold):
            cmd_vote(db, f"voter{i}", ["1", "SUPPORT", "yes"])
            capsys.readouterr()

        msg = db.query_one("SELECT * FROM messages WHERE sender='SYSTEM' AND body LIKE '%PASSED%'")
        assert msg is not None


class TestTally:
    def test_shows_votes(self, db, capsys):
        cmd_propose(db, "alice", ["test"])
        capsys.readouterr()

        cmd_vote(db, "alice", ["1", "SUPPORT", "good"])
        cmd_vote(db, "bob", ["1", "OBJECT", "bad"])
        capsys.readouterr()

        cmd_tally(db, ["1"])
        out = capsys.readouterr().out
        assert "alice: SUPPORT" in out
        assert "bob: OBJECT" in out
        assert "SUPPORT=" in out

    def test_tally_already_decided(self, db, capsys):
        cmd_propose(db, "alice", ["test"])
        db.execute("UPDATE proposals SET status='PASSED', decided_at='2026-05-08 10:00'")
        capsys.readouterr()

        cmd_tally(db, ["1"])
        out = capsys.readouterr().out
        assert "Already PASSED" in out

    def test_tally_not_found_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_tally(db, ["999"])

    def test_tally_no_args_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_tally(db, [])

    def test_tally_padded_lookup(self, db, capsys):
        cmd_propose(db, "alice", ["test"])
        capsys.readouterr()

        cmd_tally(db, ["001"])
        out = capsys.readouterr().out
        assert "SUPPORT=" in out


class TestMissingDispatcherMeta:
    """Verify voting works when meta.dispatcher_session is not set."""

    def test_eligible_counts_all_sessions_when_no_dispatcher_meta(self, db, capsys):
        db.execute("DELETE FROM meta WHERE key='dispatcher_session'")
        cmd_propose(db, "alice", ["test proposal"])
        capsys.readouterr()

        cmd_vote(db, "alice", ["1", "SUPPORT", "yes"])
        out = capsys.readouterr().out

        total_sessions = db.scalar("SELECT COUNT(*) FROM sessions")
        assert f"/{total_sessions}" in out

    def test_single_vote_does_not_auto_pass_without_meta(self, db, capsys):
        db.execute("DELETE FROM meta WHERE key='dispatcher_session'")
        for i in range(4):
            db.execute("INSERT OR IGNORE INTO sessions(name) VALUES (?)", (f"extra{i}",))
        cmd_propose(db, "alice", ["test"])
        capsys.readouterr()

        cmd_vote(db, "alice", ["1", "SUPPORT", "yes"])

        status = db.scalar("SELECT status FROM proposals WHERE number='001'")
        assert status == "OPEN"
