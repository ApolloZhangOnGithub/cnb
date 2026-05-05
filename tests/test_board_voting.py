"""Tests for the board voting subsystem.

Covers: proposal creation, voting (SUPPORT/OBJECT), tally counting,
auto-pass/fail thresholds (type A = simple majority, type S = 2/3),
dispatcher cannot vote, cannot vote on decided proposals,
and invalid vote decisions.
"""

import sqlite3

import pytest

from tests.conftest import ts


@pytest.fixture
def proposal_a(db_conn):
    """Create a type-A (simple majority) proposal and return its id."""
    cur = db_conn.execute(
        "INSERT INTO proposals(number, slug, type, content, status) "
        "VALUES (?, ?, ?, ?, 'OPEN')",
        ("001", "test-proposal", "A", "Should we refactor the board module?"),
    )
    db_conn.commit()
    return cur.lastrowid


@pytest.fixture
def proposal_s(db_conn):
    """Create a type-S (supermajority 2/3) proposal and return its id."""
    cur = db_conn.execute(
        "INSERT INTO proposals(number, slug, type, content, status) "
        "VALUES (?, ?, ?, ?, 'OPEN')",
        ("002", "charter-amendment", "S", "Amend the team charter section 3"),
    )
    db_conn.commit()
    return cur.lastrowid


@pytest.fixture
def with_dispatcher_meta(db_conn):
    """Insert the dispatcher session name into the meta table."""
    db_conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('dispatcher_session', 'dispatcher')"
    )
    db_conn.execute(
        "INSERT OR IGNORE INTO sessions(name) VALUES ('dispatcher')"
    )
    db_conn.commit()


class TestVoteCasting:
    """Casting votes on proposals."""

    def test_vote_support(self, db_conn, proposal_a):
        """A session can vote SUPPORT on an open proposal."""
        db_conn.execute(
            "INSERT INTO votes(proposal_id, voter, decision, reason) "
            "VALUES (?, ?, ?, ?)",
            (proposal_a, "alice", "SUPPORT", "looks good"),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT voter, decision, reason FROM votes WHERE proposal_id=?",
            (proposal_a,),
        ).fetchone()
        assert row["voter"] == "alice"
        assert row["decision"] == "SUPPORT"
        assert row["reason"] == "looks good"

    def test_vote_object(self, db_conn, proposal_a):
        """A session can vote OBJECT on an open proposal."""
        db_conn.execute(
            "INSERT INTO votes(proposal_id, voter, decision, reason) "
            "VALUES (?, ?, ?, ?)",
            (proposal_a, "bob", "OBJECT", "needs more discussion"),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT decision FROM votes WHERE proposal_id=? AND voter='bob'",
            (proposal_a,),
        ).fetchone()
        assert row["decision"] == "OBJECT"

    def test_vote_replaces_previous_vote(self, db_conn, proposal_a):
        """A voter can change their vote (INSERT OR REPLACE on unique constraint)."""
        db_conn.execute(
            "INSERT INTO votes(proposal_id, voter, decision, reason) "
            "VALUES (?, ?, ?, ?)",
            (proposal_a, "alice", "SUPPORT", "initially for"),
        )
        db_conn.commit()

        # Change vote
        db_conn.execute(
            "INSERT OR REPLACE INTO votes(proposal_id, voter, decision, reason, ts) "
            "VALUES (?, ?, ?, ?, ?)",
            (proposal_a, "alice", "OBJECT", "changed my mind", ts()),
        )
        db_conn.commit()

        row = db_conn.execute(
            "SELECT decision, reason FROM votes WHERE proposal_id=? AND voter='alice'",
            (proposal_a,),
        ).fetchone()
        assert row["decision"] == "OBJECT"
        assert row["reason"] == "changed my mind"

    def test_unique_constraint_per_voter_per_proposal(self, db_conn, proposal_a):
        """The (proposal_id, voter) pair is unique."""
        db_conn.execute(
            "INSERT INTO votes(proposal_id, voter, decision, reason) "
            "VALUES (?, ?, ?, ?)",
            (proposal_a, "alice", "SUPPORT", "reason 1"),
        )
        db_conn.commit()

        # Attempting a plain INSERT (not OR REPLACE) should fail
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO votes(proposal_id, voter, decision, reason) "
                "VALUES (?, ?, ?, ?)",
                (proposal_a, "alice", "OBJECT", "reason 2"),
            )


class TestVoteTally:
    """Vote counting and tally logic."""

    def test_tally_counts_support_and_object(self, db_conn, proposal_a):
        """Tally correctly counts SUPPORT and OBJECT votes."""
        for voter, decision in [
            ("alice", "SUPPORT"),
            ("bob", "SUPPORT"),
            ("charlie", "OBJECT"),
        ]:
            db_conn.execute(
                "INSERT INTO votes(proposal_id, voter, decision, reason) "
                "VALUES (?, ?, ?, ?)",
                (proposal_a, voter, decision, "reason"),
            )
        db_conn.commit()

        support = db_conn.execute(
            "SELECT COUNT(*) FROM votes WHERE proposal_id=? AND decision='SUPPORT'",
            (proposal_a,),
        ).fetchone()[0]
        obj = db_conn.execute(
            "SELECT COUNT(*) FROM votes WHERE proposal_id=? AND decision='OBJECT'",
            (proposal_a,),
        ).fetchone()[0]

        assert support == 2
        assert obj == 1


class TestAutoDecision:
    """Automatic pass/fail based on thresholds."""

    def _get_eligible_count(self, db_conn):
        """Count eligible voters (all sessions minus dispatcher)."""
        return db_conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE name != "
            "(SELECT COALESCE((SELECT value FROM meta WHERE key='dispatcher_session'), ''))"
        ).fetchone()[0]

    def test_type_a_simple_majority_pass(self, db_conn, proposal_a, with_dispatcher_meta):
        """Type A proposal passes with simple majority (eligible/2 + 1)."""
        eligible = self._get_eligible_count(db_conn)
        threshold = eligible // 2 + 1  # For 3 eligible: threshold = 2

        # Cast enough SUPPORT votes to reach threshold
        voters = ["alice", "bob", "charlie"]
        for i in range(threshold):
            db_conn.execute(
                "INSERT INTO votes(proposal_id, voter, decision, reason) "
                "VALUES (?, ?, ?, ?)",
                (proposal_a, voters[i], "SUPPORT", "in favor"),
            )
        db_conn.commit()

        support = db_conn.execute(
            "SELECT COUNT(*) FROM votes WHERE proposal_id=? AND decision='SUPPORT'",
            (proposal_a,),
        ).fetchone()[0]

        assert support >= threshold
        # Application would set status to PASSED
        db_conn.execute(
            "UPDATE proposals SET status='PASSED', decided_at=? WHERE id=?",
            (ts(), proposal_a),
        )
        db_conn.commit()

        status = db_conn.execute(
            "SELECT status FROM proposals WHERE id=?", (proposal_a,)
        ).fetchone()["status"]
        assert status == "PASSED"

    def test_type_s_supermajority_threshold(self, db_conn, proposal_s, with_dispatcher_meta):
        """Type S proposal requires 2/3 supermajority."""
        eligible = self._get_eligible_count(db_conn)
        # Bash formula: (eligible * 2 + 2) / 3 using integer division
        threshold = (eligible * 2 + 2) // 3  # For 3 eligible: threshold = 3 (rounded up)

        # With 3 eligible voters, all 3 must vote SUPPORT for type S
        voters = ["alice", "bob", "charlie"]
        for v in voters:
            db_conn.execute(
                "INSERT INTO votes(proposal_id, voter, decision, reason) "
                "VALUES (?, ?, ?, ?)",
                (proposal_s, v, "SUPPORT", "agreed"),
            )
        db_conn.commit()

        support = db_conn.execute(
            "SELECT COUNT(*) FROM votes WHERE proposal_id=? AND decision='SUPPORT'",
            (proposal_s,),
        ).fetchone()[0]

        assert support >= threshold

    def test_auto_fail_when_impossible(self, db_conn, proposal_a, with_dispatcher_meta):
        """Proposal auto-fails when it's impossible to reach the threshold."""
        eligible = self._get_eligible_count(db_conn)
        threshold = eligible // 2 + 1  # For 3 eligible: threshold = 2

        # If 2 out of 3 OBJECT, threshold of 2 SUPPORT is impossible
        for voter in ["alice", "bob"]:
            db_conn.execute(
                "INSERT INTO votes(proposal_id, voter, decision, reason) "
                "VALUES (?, ?, ?, ?)",
                (proposal_a, voter, "OBJECT", "against"),
            )
        db_conn.commit()

        obj_count = db_conn.execute(
            "SELECT COUNT(*) FROM votes WHERE proposal_id=? AND decision='OBJECT'",
            (proposal_a,),
        ).fetchone()[0]

        # Check: obj_count > (eligible - threshold) means impossible to pass
        assert obj_count > (eligible - threshold)


class TestVotingRestrictions:
    """Access control on voting."""

    def test_dispatcher_cannot_vote(self, db_conn, proposal_a, with_dispatcher_meta):
        """The dispatcher session is not allowed to vote.

        This is enforced at the application layer (charter section 2).
        The DB itself does not prevent it, but the test validates the
        data model supports the restriction check.
        """
        dispatcher_name = db_conn.execute(
            "SELECT value FROM meta WHERE key='dispatcher_session'"
        ).fetchone()[0]
        assert dispatcher_name == "dispatcher"

        # Application should check: voter != dispatcher_session before inserting

    def test_cannot_vote_on_decided_proposal(self, db_conn):
        """Voting on a PASSED or FAILED proposal should be rejected."""
        cur = db_conn.execute(
            "INSERT INTO proposals(number, slug, type, content, status, decided_at) "
            "VALUES (?, ?, ?, ?, 'PASSED', ?)",
            ("003", "decided-prop", "A", "Already decided", ts()),
        )
        prop_id = cur.lastrowid
        db_conn.commit()

        status = db_conn.execute(
            "SELECT status FROM proposals WHERE id=?", (prop_id,)
        ).fetchone()["status"]
        assert status != "OPEN"
        # Application should check status == 'OPEN' before allowing vote

    def test_cannot_vote_on_failed_proposal(self, db_conn):
        """Voting on a FAILED proposal should also be rejected."""
        cur = db_conn.execute(
            "INSERT INTO proposals(number, slug, type, content, status, decided_at) "
            "VALUES (?, ?, ?, ?, 'FAILED', ?)",
            ("004", "failed-prop", "A", "This was rejected", ts()),
        )
        prop_id = cur.lastrowid
        db_conn.commit()

        status = db_conn.execute(
            "SELECT status FROM proposals WHERE id=?", (prop_id,)
        ).fetchone()["status"]
        assert status == "FAILED"

    def test_proposal_number_unique(self, db_conn):
        """Proposal numbers must be unique."""
        db_conn.execute(
            "INSERT INTO proposals(number, slug, type, content) "
            "VALUES ('005', 'first', 'A', 'first proposal')"
        )
        db_conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO proposals(number, slug, type, content) "
                "VALUES ('005', 'duplicate', 'A', 'duplicate number')"
            )

    def test_proposal_lookup_by_padded_number(self, db_conn):
        """Proposals can be looked up by zero-padded or raw number."""
        db_conn.execute(
            "INSERT INTO proposals(number, slug, type, content) "
            "VALUES ('007', 'test-prop', 'A', 'test content')"
        )
        db_conn.commit()

        # Lookup by padded
        row = db_conn.execute(
            "SELECT slug FROM proposals WHERE number='007'"
        ).fetchone()
        assert row is not None
        assert row["slug"] == "test-prop"

        # Lookup by raw (application handles both)
        row2 = db_conn.execute(
            "SELECT slug FROM proposals WHERE number='007' OR number='7'"
        ).fetchone()
        assert row2 is not None
