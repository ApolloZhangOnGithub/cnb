"""Tests for #87 L1 ownership routing: 3-tier priority + per-file CI + audit log.

See `lib/board_own.py::_route_issue` and `lib/board_own._scan_ci`. The matrix
covers the acceptance criteria defined in the design comment on #87:

- Issue routing: assignee > label > path > substring > no-match fallback
- Multi-owner matches escalate to lead/all fallback (no broadcast pings)
- Orphaned owner re-routes to "all" with the original owner mentioned
- CI routing: per-file owner notification, fallback to lead/all when files
  cannot be determined
- routing_log audit table records every decision
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.board_own import (
    RouteDecision,
    _route_issue,
    cmd_own,
    cmd_scan,
)

# ---------------------------------------------------------------------------
# Tier 1: assignee
# ---------------------------------------------------------------------------


class TestRouteByAssignee:
    def test_assignee_matches_known_session(self, db):
        cmd_own(db, "alice", ["claim", "docs/"])
        ownership_rows = [("alice", "docs/")]
        issue = {
            "number": 1,
            "title": "anything",
            "body": "",
            "labels": [],
            "assignees": [{"login": "bob"}],
        }
        decision = _route_issue(db, issue, ownership_rows)
        assert decision.recipient == "bob"
        assert decision.evidence == "assigned:bob"
        assert decision.confidence == "high"

    def test_assignee_wins_over_label_and_path(self, db):
        cmd_own(db, "alice", ["claim", "lib/foo/"])
        ownership_rows = [("alice", "lib/foo/")]
        issue = {
            "number": 2,
            "title": "touches lib/foo/bar.py and label proj:foo",
            "body": "see lib/foo/bar.py",
            "labels": [{"name": "proj:foo"}],
            "assignees": [{"login": "charlie"}],
        }
        decision = _route_issue(db, issue, ownership_rows)
        assert decision.recipient == "charlie"
        assert decision.evidence == "assigned:charlie"

    def test_unknown_assignee_falls_through(self, db):
        cmd_own(db, "alice", ["claim", "docs/"])
        ownership_rows = [("alice", "docs/")]
        issue = {
            "number": 3,
            "title": "docs",
            "body": "in docs/",
            "labels": [],
            "assignees": [{"login": "stranger"}],  # not in sessions
        }
        decision = _route_issue(db, issue, ownership_rows)
        # falls through to substring tier (docs/ matches alice's pattern)
        assert decision.recipient == "alice"


# ---------------------------------------------------------------------------
# Tier 2: label
# ---------------------------------------------------------------------------


class TestRouteByLabel:
    def test_proj_label_maps_to_owner_via_path_tail(self, db):
        cmd_own(db, "alice", ["claim", "lib/fetch_bilibili/"])
        ownership_rows = [("alice", "lib/fetch_bilibili/")]
        issue = {
            "number": 4,
            "title": "anything",
            "body": "",
            "labels": [{"name": "proj:fetch_bilibili"}],
            "assignees": [],
        }
        decision = _route_issue(db, issue, ownership_rows)
        assert decision.recipient == "alice"
        assert decision.evidence == "label:proj:fetch_bilibili"
        assert decision.confidence == "high"

    def test_area_label_also_supported(self, db):
        cmd_own(db, "bob", ["claim", "lib/board_own/"])
        ownership_rows = [("bob", "lib/board_own/")]
        issue = {
            "number": 5,
            "title": "anything",
            "body": "",
            "labels": [{"name": "area:board_own"}],
            "assignees": [],
        }
        decision = _route_issue(db, issue, ownership_rows)
        assert decision.recipient == "bob"
        assert decision.evidence == "label:area:board_own"

    def test_unknown_label_tag_falls_through(self, db):
        cmd_own(db, "alice", ["claim", "lib/foo/"])
        ownership_rows = [("alice", "lib/foo/")]
        issue = {
            "number": 6,
            "title": "lib/foo/bar.py issue",
            "body": "",
            "labels": [{"name": "proj:nonexistent"}],
            "assignees": [],
        }
        decision = _route_issue(db, issue, ownership_rows)
        # falls through to path tier
        assert decision.recipient == "alice"
        assert decision.evidence.startswith("path:")

    def test_label_wins_over_path(self, db):
        cmd_own(db, "alice", ["claim", "lib/foo/"])
        cmd_own(db, "bob", ["claim", "lib/bar/"])
        ownership_rows = [("alice", "lib/foo/"), ("bob", "lib/bar/")]
        issue = {
            "number": 7,
            "title": "touches lib/bar/x.py but tagged foo",
            "body": "lib/bar/x.py",
            "labels": [{"name": "proj:foo"}],
            "assignees": [],
        }
        decision = _route_issue(db, issue, ownership_rows)
        assert decision.recipient == "alice"
        assert decision.evidence == "label:proj:foo"


# ---------------------------------------------------------------------------
# Tier 3: path references
# ---------------------------------------------------------------------------


class TestRouteByPath:
    def test_single_path_match(self, db):
        cmd_own(db, "alice", ["claim", "lib/"])
        ownership_rows = [("alice", "lib/")]
        issue = {
            "number": 8,
            "title": "bug in lib/board_view.py",
            "body": "see lib/board_view.py:123",
            "labels": [],
            "assignees": [],
        }
        decision = _route_issue(db, issue, ownership_rows)
        assert decision.recipient == "alice"
        assert decision.evidence == "path:lib/board_view.py"
        assert decision.confidence == "medium"

    def test_multi_owner_path_match_escalates_to_fallback(self, db):
        cmd_own(db, "alice", ["claim", "lib/"])
        cmd_own(db, "bob", ["claim", "tests/"])
        ownership_rows = [("alice", "lib/"), ("bob", "tests/")]
        issue = {
            "number": 9,
            "title": "lib/x.py + tests/test_x.py both broken",
            "body": "lib/x.py at line 5\ntests/test_x.py:9",
            "labels": [],
            "assignees": [],
        }
        decision = _route_issue(db, issue, ownership_rows)
        # No lead session in default fixture → fallback is "all"
        assert decision.recipient == "all"
        assert decision.evidence.startswith("ambiguous:")
        assert "alice" in decision.evidence and "bob" in decision.evidence
        assert decision.confidence == "fallback"


# ---------------------------------------------------------------------------
# Substring fallback (legacy behavior preserved)
# ---------------------------------------------------------------------------


class TestRouteBySubstring:
    def test_substring_match_low_confidence(self, db):
        cmd_own(db, "alice", ["claim", "lib/"])
        ownership_rows = [("alice", "lib/")]
        issue = {
            "number": 10,
            "title": "lib/ improvements",
            "body": "various lib/ cleanups",
            "labels": [],
            "assignees": [],
        }
        decision = _route_issue(db, issue, ownership_rows)
        assert decision.recipient == "alice"
        assert decision.evidence == "substring:lib/"
        assert decision.confidence == "low"

    def test_ambiguous_substring_escalates(self, db):
        cmd_own(db, "alice", ["claim", "lib/"])
        cmd_own(db, "bob", ["claim", "tests/"])
        ownership_rows = [("alice", "lib/"), ("bob", "tests/")]
        issue = {
            "number": 11,
            "title": "lib/ and tests/ mention",
            "body": "",
            "labels": [],
            "assignees": [],
        }
        decision = _route_issue(db, issue, ownership_rows)
        assert decision.recipient == "all"
        assert decision.evidence.startswith("ambiguous:")


# ---------------------------------------------------------------------------
# No match fallback
# ---------------------------------------------------------------------------


class TestRouteFallback:
    def test_no_match_routes_to_fallback(self, db):
        cmd_own(db, "alice", ["claim", "lib/zoo/"])
        ownership_rows = [("alice", "lib/zoo/")]
        issue = {
            "number": 12,
            "title": "totally unrelated",
            "body": "no path no label no assignee",
            "labels": [],
            "assignees": [],
        }
        decision = _route_issue(db, issue, ownership_rows)
        # No lead session in fixture → fallback to "all"
        assert decision.recipient == "all"
        assert decision.evidence == "no_match"
        assert decision.confidence == "fallback"

    def test_lead_session_preferred_as_fallback(self, db):
        # Add a lead session so fallback prefers it over "all"
        db.execute("INSERT OR IGNORE INTO sessions(name) VALUES ('lead')")
        cmd_own(db, "alice", ["claim", "lib/zoo/"])
        ownership_rows = [("alice", "lib/zoo/")]
        issue = {
            "number": 13,
            "title": "no match",
            "body": "",
            "labels": [],
            "assignees": [],
        }
        decision = _route_issue(db, issue, ownership_rows)
        assert decision.recipient == "lead"


# ---------------------------------------------------------------------------
# Scan end-to-end: routing decision becomes a posted message + audit row
# ---------------------------------------------------------------------------


class TestScanIntegration:
    @patch("lib.board_own.subprocess.run")
    def test_scan_writes_evidence_to_message_body(self, mock_run, db, capsys):
        env = MagicMock()
        env.project_root = Path("/tmp/fake")
        db.env = env
        cmd_own(db, "alice", ["claim", "lib/"])
        capsys.readouterr()

        issue = {
            "number": 99,
            "title": "lib/board_view.py bug",
            "body": "lib/board_view.py crashes",
            "labels": [],
            "assignees": [],
        }
        mock_run.side_effect = lambda cmd, **_: (
            MagicMock(returncode=0, stdout=json.dumps([issue]))
            if "issue" in cmd
            else MagicMock(returncode=0, stdout="[]")
        )

        cmd_scan(db, "alice", [])
        capsys.readouterr()

        row = db.query_one("SELECT body FROM messages WHERE recipient='alice' AND body LIKE '%ISSUE #99%'")
        assert row is not None
        body = row[0]
        assert "matched-via: path:lib/board_view.py" in body
        assert "confidence: medium" in body

    @patch("lib.board_own.subprocess.run")
    def test_scan_records_routing_log(self, mock_run, db, capsys):
        env = MagicMock()
        env.project_root = Path("/tmp/fake")
        db.env = env
        cmd_own(db, "alice", ["claim", "lib/"])
        capsys.readouterr()

        issue = {
            "number": 100,
            "title": "lib/x.py issue",
            "body": "",
            "labels": [],
            "assignees": [],
        }
        mock_run.side_effect = lambda cmd, **_: (
            MagicMock(returncode=0, stdout=json.dumps([issue]))
            if "issue" in cmd
            else MagicMock(returncode=0, stdout="[]")
        )

        cmd_scan(db, "alice", [])
        capsys.readouterr()

        row = db.query_one("SELECT kind, ref, recipient, evidence, confidence FROM routing_log WHERE ref='#100'")
        assert row is not None
        kind, _ref, recipient, evidence, confidence = row
        assert kind == "issue"
        assert recipient == "alice"
        assert evidence == "path:lib/x.py"
        assert confidence == "medium"


# ---------------------------------------------------------------------------
# CI routing (per-file)
# ---------------------------------------------------------------------------


class TestCiPerFileRouting:
    @patch("lib.board_own.subprocess.run")
    def test_files_route_to_their_owner_only(self, mock_run, db, capsys):
        env = MagicMock()
        env.project_root = Path("/tmp/fake")
        db.env = env
        cmd_own(db, "alice", ["claim", "lib/"])
        cmd_own(db, "bob", ["claim", "tests/"])
        capsys.readouterr()

        def side_effect(cmd, **_):
            if "issue" in cmd:
                return MagicMock(returncode=0, stdout="[]")
            if "run" in cmd and "list" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps(
                        [{"status": "completed", "conclusion": "failure", "headBranch": "f1", "databaseId": 1}]
                    ),
                )
            if "run" in cmd and "view" in cmd:
                # only lib/ files touched — alice should get the ping, bob should not
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps({"files": [{"path": "lib/foo.py"}]}),
                )
            return MagicMock(returncode=1, stdout="")

        mock_run.side_effect = side_effect

        cmd_scan(db, "alice", [])
        capsys.readouterr()

        alice_msgs = db.query("SELECT body FROM messages WHERE recipient='alice' AND body LIKE '%CI FAIL%'")
        bob_msgs = db.query("SELECT body FROM messages WHERE recipient='bob' AND body LIKE '%CI FAIL%'")
        assert len(alice_msgs) == 1
        assert len(bob_msgs) == 0
        assert "lib/foo.py" in alice_msgs[0][0]

    @patch("lib.board_own.subprocess.run")
    def test_no_files_falls_back_to_all_not_broadcast(self, mock_run, db, capsys):
        env = MagicMock()
        env.project_root = Path("/tmp/fake")
        db.env = env
        cmd_own(db, "alice", ["claim", "lib/"])
        cmd_own(db, "bob", ["claim", "tests/"])
        capsys.readouterr()

        def side_effect(cmd, **_):
            if "issue" in cmd:
                return MagicMock(returncode=0, stdout="[]")
            if "run" in cmd and "list" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps(
                        [{"status": "completed", "conclusion": "failure", "headBranch": "f2", "databaseId": 2}]
                    ),
                )
            if "run" in cmd and "view" in cmd:
                # No files → fallback path
                return MagicMock(returncode=0, stdout=json.dumps({"files": []}))
            return MagicMock(returncode=1, stdout="")

        mock_run.side_effect = side_effect

        cmd_scan(db, "alice", [])
        capsys.readouterr()

        # ONE fallback message, not one per owner (the old broadcast was the bug)
        all_msgs = db.query("SELECT body FROM messages WHERE body LIKE '%CI FAIL%'")
        assert len(all_msgs) == 1
        assert "无法定位 owner" in all_msgs[0][0]

    @patch("lib.board_own.subprocess.run")
    def test_gh_run_view_timeout_uses_fallback(self, mock_run, db, capsys):
        env = MagicMock()
        env.project_root = Path("/tmp/fake")
        db.env = env
        cmd_own(db, "alice", ["claim", "lib/"])
        capsys.readouterr()

        import subprocess as sp

        def side_effect(cmd, **_):
            if "issue" in cmd:
                return MagicMock(returncode=0, stdout="[]")
            if "run" in cmd and "list" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps(
                        [{"status": "completed", "conclusion": "failure", "headBranch": "f3", "databaseId": 3}]
                    ),
                )
            if "run" in cmd and "view" in cmd:
                raise sp.TimeoutExpired(cmd, 15)
            return MagicMock(returncode=1, stdout="")

        mock_run.side_effect = side_effect

        cmd_scan(db, "alice", [])
        capsys.readouterr()
        msgs = db.query("SELECT recipient, body FROM messages WHERE body LIKE '%CI FAIL%'")
        assert len(msgs) == 1
        # fallback recipient is "all" (no lead in fixture)
        assert msgs[0][0] == "all"
        assert "无法定位 owner" in msgs[0][1]


# ---------------------------------------------------------------------------
# Audit subcommand
# ---------------------------------------------------------------------------


class TestOwnAudit:
    def test_audit_shows_recent_entries(self, db, capsys):
        from lib.board_own import _record_routing

        _record_routing(db, "issue", "#1", RouteDecision("alice", "assigned:alice", "high"))
        _record_routing(db, "ci", "branch:99", RouteDecision("bob", "files:lib/x.py", "high"))

        cmd_own(db, "alice", ["audit"])
        out = capsys.readouterr().out
        assert "alice" in out
        assert "assigned:alice" in out
        assert "bob" in out
        assert "files:lib/x.py" in out

    def test_audit_empty(self, db, capsys):
        cmd_own(db, "alice", ["audit"])
        out = capsys.readouterr().out
        assert "为空" in out

    def test_audit_limit_flag(self, db, capsys):
        from lib.board_own import _record_routing

        for i in range(5):
            _record_routing(db, "issue", f"#{i}", RouteDecision("alice", "assigned:alice", "high"))

        cmd_own(db, "alice", ["audit", "--limit", "2"])
        out = capsys.readouterr().out
        # Header says "最近 2 条", and 2 entry lines (each starts with "  [")
        assert "最近 2 条" in out
        assert out.count("\n  [") == 2

    def test_audit_invalid_limit_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_own(db, "alice", ["audit", "--limit", "abc"])
