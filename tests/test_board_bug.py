"""Tests for board_bug — bug tracker: report, assign, fix, list, overdue."""

from unittest.mock import patch

import pytest

from lib.board_bug import _bug_assign, _bug_fix, _bug_list, _bug_overdue, _bug_report, cmd_bug


class TestBugReport:
    def test_creates_bug_with_correct_fields(self, db, capsys):
        _bug_report(db, "alice", ["P1", "login page crashes"])

        row = db.query_one("SELECT * FROM bugs WHERE id='BUG-001'")
        assert row["severity"] == "P1"
        assert row["sla"] == "4h"
        assert row["reporter"] == "alice"
        assert row["status"] == "OPEN"
        assert row["description"] == "login page crashes"
        assert "OK BUG-001" in capsys.readouterr().out

    def test_p0_has_immediate_sla(self, db, capsys):
        _bug_report(db, "alice", ["P0", "total outage"])
        row = db.query_one("SELECT sla FROM bugs WHERE id='BUG-001'")
        assert row["sla"] == "immediate"

    def test_p2_has_24h_sla(self, db, capsys):
        _bug_report(db, "alice", ["P2", "minor typo"])
        row = db.query_one("SELECT sla FROM bugs WHERE id='BUG-001'")
        assert row["sla"] == "24h"

    def test_sequential_ids(self, db, capsys):
        _bug_report(db, "alice", ["P1", "bug one"])
        _bug_report(db, "bob", ["P2", "bug two"])
        ids = [r["id"] for r in db.query("SELECT id FROM bugs ORDER BY id")]
        assert ids == ["BUG-001", "BUG-002"]

    def test_broadcasts_message(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash on save"])
        msg = db.query_one("SELECT * FROM messages WHERE body LIKE '%BUG-001%'")
        assert msg is not None
        assert msg["recipient"] == "all"
        assert "P1" in msg["body"]

    def test_delivers_to_inbox(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        inbox = db.query("SELECT * FROM inbox WHERE session != 'alice'")
        assert len(inbox) > 0

    def test_invalid_severity_exits(self, db):
        with pytest.raises(SystemExit):
            _bug_report(db, "alice", ["P3", "not valid"])

    def test_missing_args_exits(self, db):
        with pytest.raises(SystemExit):
            _bug_report(db, "alice", ["P1"])

    def test_multi_word_description(self, db, capsys):
        _bug_report(db, "alice", ["P1", "this", "is", "a", "long", "description"])
        row = db.query_one("SELECT description FROM bugs WHERE id='BUG-001'")
        assert row["description"] == "this is a long description"


class TestBugAssign:
    def test_assigns_bug(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        capsys.readouterr()

        _bug_assign(db, "alice", ["BUG-001", "bob"])

        row = db.query_one("SELECT assignee, status FROM bugs WHERE id='BUG-001'")
        assert row["assignee"] == "bob"
        assert row["status"] == "ASSIGNED"
        assert "OK BUG-001 assigned to bob" in capsys.readouterr().out

    def test_auto_prefixes_bug_id(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        capsys.readouterr()

        _bug_assign(db, "alice", ["001", "bob"])
        row = db.query_one("SELECT assignee FROM bugs WHERE id='BUG-001'")
        assert row["assignee"] == "bob"

    def test_sends_notification(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        _bug_assign(db, "alice", ["BUG-001", "bob"])

        msgs = db.query("SELECT * FROM messages WHERE recipient='bob'")
        assert len(msgs) == 1
        assert "BUG-001" in msgs[0]["body"]

    def test_nonexistent_bug_exits(self, db):
        with pytest.raises(SystemExit):
            _bug_assign(db, "alice", ["BUG-999", "bob"])

    def test_missing_args_exits(self, db):
        with pytest.raises(SystemExit):
            _bug_assign(db, "alice", ["BUG-001"])

    def test_nonexistent_assignee_exits(self, db):
        _bug_report(db, "alice", ["P1", "crash"])
        with pytest.raises(SystemExit):
            _bug_assign(db, "alice", ["BUG-001", "ghost"])


class TestBugFix:
    def test_fixes_bug(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        capsys.readouterr()

        _bug_fix(db, "bob", ["BUG-001", "fixed in commit abc123"])

        row = db.query_one("SELECT status, evidence, fixed_at FROM bugs WHERE id='BUG-001'")
        assert row["status"] == "FIXED"
        assert row["evidence"] == "fixed in commit abc123"
        assert row["fixed_at"] is not None
        assert "OK BUG-001 marked FIXED" in capsys.readouterr().out

    def test_broadcasts_fix_message(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        _bug_fix(db, "bob", ["BUG-001", "resolved"])

        msgs = db.query("SELECT * FROM messages WHERE body LIKE '%FIXED%'")
        assert len(msgs) == 1
        assert msgs[0]["recipient"] == "all"

    def test_already_fixed_is_noop(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        _bug_fix(db, "bob", ["BUG-001", "first fix"])
        capsys.readouterr()

        _bug_fix(db, "bob", ["BUG-001", "second fix"])
        out = capsys.readouterr().out
        assert "already FIXED" in out

    def test_auto_prefixes_bug_id(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        capsys.readouterr()

        _bug_fix(db, "bob", ["001", "fixed"])
        row = db.query_one("SELECT status FROM bugs WHERE id='BUG-001'")
        assert row["status"] == "FIXED"

    def test_nonexistent_bug_exits(self, db):
        with pytest.raises(SystemExit):
            _bug_fix(db, "bob", ["BUG-999", "evidence"])

    def test_missing_args_exits(self, db):
        with pytest.raises(SystemExit):
            _bug_fix(db, "bob", ["BUG-001"])


class TestBugList:
    def test_list_open_bugs(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        _bug_report(db, "alice", ["P2", "typo"])
        capsys.readouterr()

        _bug_list(db, [])
        out = capsys.readouterr().out
        assert "BUG-001" in out
        assert "BUG-002" in out

    def test_list_excludes_fixed(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        _bug_fix(db, "bob", ["BUG-001", "fixed"])
        capsys.readouterr()

        _bug_list(db, [])
        out = capsys.readouterr().out
        assert "BUG-001" not in out or "no bugs" in out.lower()

    def test_list_all_includes_fixed(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        _bug_fix(db, "bob", ["BUG-001", "fixed"])
        capsys.readouterr()

        _bug_list(db, ["all"])
        out = capsys.readouterr().out
        assert "BUG-001" in out

    def test_list_by_status_filter(self, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        _bug_assign(db, "alice", ["BUG-001", "bob"])
        capsys.readouterr()

        _bug_list(db, ["ASSIGNED"])
        out = capsys.readouterr().out
        assert "BUG-001" in out

    def test_empty_list(self, db, capsys):
        _bug_list(db, [])
        out = capsys.readouterr().out
        assert "no bugs" in out.lower()


class TestBugOverdue:
    def test_no_overdue_bugs(self, db, capsys):
        _bug_overdue(db)
        assert "No overdue" in capsys.readouterr().out

    def test_p0_always_overdue(self, db, capsys):
        _bug_report(db, "alice", ["P0", "total outage"])
        capsys.readouterr()

        _bug_overdue(db)
        out = capsys.readouterr().out
        assert "OVERDUE" in out
        assert "BUG-001" in out

    @patch("lib.board_bug.time.time")
    def test_p1_overdue_after_4h(self, mock_time, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        capsys.readouterr()

        reported = db.scalar("SELECT reported_at FROM bugs WHERE id='BUG-001'")
        from datetime import datetime

        rep_epoch = int(datetime.strptime(reported, "%Y-%m-%d %H:%M").timestamp())
        mock_time.return_value = rep_epoch + 14401

        _bug_overdue(db)
        out = capsys.readouterr().out
        assert "OVERDUE" in out

    @patch("lib.board_bug.time.time")
    def test_p1_not_overdue_within_4h(self, mock_time, db, capsys):
        _bug_report(db, "alice", ["P1", "crash"])
        capsys.readouterr()

        reported = db.scalar("SELECT reported_at FROM bugs WHERE id='BUG-001'")
        from datetime import datetime

        rep_epoch = int(datetime.strptime(reported, "%Y-%m-%d %H:%M").timestamp())
        mock_time.return_value = rep_epoch + 100

        _bug_overdue(db)
        assert "No overdue" in capsys.readouterr().out

    def test_fixed_bugs_not_overdue(self, db, capsys):
        _bug_report(db, "alice", ["P0", "outage"])
        _bug_fix(db, "bob", ["BUG-001", "fixed"])
        capsys.readouterr()

        _bug_overdue(db)
        assert "No overdue" in capsys.readouterr().out


class TestCmdBugDispatch:
    def test_unknown_subcommand_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_bug(db, "alice", ["unknown"])

    def test_default_is_list(self, db, capsys):
        cmd_bug(db, "alice", [])
        out = capsys.readouterr().out
        assert "Bug Tracker" in out
