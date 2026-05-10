"""Tests for lib/board_own.py — ownership registry, verify, auto-PR, scan."""

import json
import os
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lib.board_db import BoardDB
from lib.board_own import auto_pr, cmd_own, cmd_scan, find_owner, verify_task


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "board.db"
    schema = (Path(__file__).parent.parent / "schema.sql").read_text()
    conn = sqlite3.connect(str(db_path))
    conn.executescript(schema)
    conn.execute("INSERT INTO sessions(name) VALUES ('alice')")
    conn.execute("INSERT INTO sessions(name) VALUES ('bob')")
    conn.execute("INSERT INTO sessions(name) VALUES ('system')")
    conn.commit()
    conn.close()
    return BoardDB(db_path)


# ---------------------------------------------------------------------------
# Ownership CRUD
# ---------------------------------------------------------------------------


class TestOwnClaim:
    def test_claim_single(self, db, capsys):
        cmd_own(db, "alice", ["claim", "lib/board_own.py"])
        out = capsys.readouterr().out
        assert "OK alice owns lib/board_own.py" in out

    def test_claim_multiple(self, db, capsys):
        cmd_own(db, "alice", ["claim", "lib/", "tests/"])
        out = capsys.readouterr().out
        assert "OK alice owns lib/" in out
        assert "OK alice owns tests/" in out

    def test_claim_already_owned_by_other(self, db, capsys):
        cmd_own(db, "alice", ["claim", "lib/"])
        cmd_own(db, "bob", ["claim", "lib/"])
        out = capsys.readouterr().out
        assert "已被 alice 认领" in out

    def test_claim_idempotent(self, db, capsys):
        cmd_own(db, "alice", ["claim", "lib/"])
        cmd_own(db, "alice", ["claim", "lib/"])
        out = capsys.readouterr().out
        assert "OK alice owns lib/" in out

    def test_claim_no_args(self, db):
        with pytest.raises(SystemExit):
            cmd_own(db, "alice", ["claim"])


class TestOwnDisown:
    def test_disown(self, db, capsys):
        cmd_own(db, "alice", ["claim", "lib/"])
        cmd_own(db, "alice", ["disown", "lib/"])
        out = capsys.readouterr().out
        assert "released" in out

    def test_disown_not_owned(self, db, capsys):
        cmd_own(db, "alice", ["disown", "lib/"])
        out = capsys.readouterr().out
        assert "不拥有" in out

    def test_disown_no_args(self, db):
        with pytest.raises(SystemExit):
            cmd_own(db, "alice", ["disown"])


class TestOwnList:
    def test_list_own(self, db, capsys):
        cmd_own(db, "alice", ["claim", "lib/", "bin/"])
        capsys.readouterr()
        cmd_own(db, "alice", ["list"])
        out = capsys.readouterr().out
        assert "bin/" in out
        assert "lib/" in out

    def test_list_empty(self, db, capsys):
        cmd_own(db, "alice", ["list"])
        out = capsys.readouterr().out
        assert "无 ownership" in out

    def test_list_other_session(self, db, capsys):
        cmd_own(db, "alice", ["claim", "lib/"])
        capsys.readouterr()
        cmd_own(db, "bob", ["list", "alice"])
        out = capsys.readouterr().out
        assert "lib/" in out


class TestOwnMap:
    def test_map_shows_all(self, db, capsys):
        cmd_own(db, "alice", ["claim", "lib/"])
        cmd_own(db, "bob", ["claim", "bin/"])
        capsys.readouterr()
        cmd_own(db, "alice", ["map"])
        out = capsys.readouterr().out
        assert "alice" in out
        assert "bob" in out
        assert "lib/" in out
        assert "bin/" in out

    def test_map_empty(self, db, capsys):
        cmd_own(db, "alice", ["map"])
        out = capsys.readouterr().out
        assert "无 ownership" in out


class TestOwnTransfer:
    def test_transfer_single(self, db, capsys):
        cmd_own(db, "alice", ["claim", "lib/"])
        capsys.readouterr()

        cmd_own(db, "alice", ["transfer", "bob", "lib/"])
        out = capsys.readouterr().out
        assert "alice -> bob" in out

        assert find_owner(db, "lib/board_own.py") == "bob"
        assert db.scalar("SELECT COUNT(*) FROM ownership WHERE session='alice'") == 0

    def test_transfer_unowned_warns(self, db, capsys):
        cmd_own(db, "alice", ["transfer", "bob", "lib/"])
        out = capsys.readouterr().out
        assert "不拥有" in out
        assert "0 条 ownership" in out

    def test_transfer_to_self_rejected(self, db):
        cmd_own(db, "alice", ["claim", "lib/"])
        with pytest.raises(SystemExit):
            cmd_own(db, "alice", ["transfer", "alice", "lib/"])

    def test_transfer_all(self, db, capsys):
        cmd_own(db, "alice", ["claim", "lib/", "bin/"])
        capsys.readouterr()

        cmd_own(db, "alice", ["transfer-all", "bob"])
        out = capsys.readouterr().out
        assert "全部 ownership 交接给 bob" in out
        assert find_owner(db, "lib/board_own.py") == "bob"
        assert find_owner(db, "bin/board") == "bob"

    def test_transfer_all_empty(self, db, capsys):
        cmd_own(db, "alice", ["transfer-all", "bob"])
        out = capsys.readouterr().out
        assert "无 ownership 可交接" in out


class TestOwnOffboard:
    def test_offboard_lists_ownership_and_tasks(self, db, capsys):
        cmd_own(db, "alice", ["claim", "lib/"])
        db.execute(
            "INSERT INTO tasks(session, description, status, priority) VALUES (?, ?, ?, ?)",
            ("alice", "finish handoff", "active", 2),
        )
        capsys.readouterr()

        cmd_own(db, "alice", ["offboard"])
        out = capsys.readouterr().out
        assert "离职清单: alice" in out
        assert "lib/" in out
        assert "finish handoff" in out
        assert "当前上下文不可用" in out

    def test_other_session_offboard_requires_privilege(self, db):
        with pytest.raises(SystemExit):
            cmd_own(db, "bob", ["offboard", "alice"])

    def test_dispatcher_can_view_other_session_offboard(self, db, capsys):
        cmd_own(db, "dispatcher", ["offboard", "alice"])
        out = capsys.readouterr().out
        assert "离职清单: alice" in out


class TestOwnOrphans:
    def test_missing_heartbeat_is_not_orphan(self, db, capsys):
        cmd_own(db, "alice", ["claim", "lib/"])
        capsys.readouterr()

        cmd_own(db, "alice", ["orphans"])
        out = capsys.readouterr().out
        assert "无 orphaned ownership" in out

    def test_stale_heartbeat_is_orphan(self, db, capsys):
        old = (datetime.now() - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE sessions SET last_heartbeat=? WHERE name='alice'", (old,))
        cmd_own(db, "alice", ["claim", "lib/"])
        capsys.readouterr()

        cmd_own(db, "alice", ["orphans"])
        out = capsys.readouterr().out
        assert "alice" in out
        assert "lib/" in out


class TestFindOwner:
    def test_exact_match(self, db):
        cmd_own(db, "alice", ["claim", "lib/board_own.py"])
        assert find_owner(db, "lib/board_own.py") == "alice"

    def test_prefix_match(self, db):
        cmd_own(db, "alice", ["claim", "lib/"])
        assert find_owner(db, "lib/board_own.py") == "alice"

    def test_longest_prefix_wins(self, db):
        cmd_own(db, "alice", ["claim", "lib/"])
        cmd_own(db, "bob", ["claim", "lib/board_own.py"])
        assert find_owner(db, "lib/board_own.py") == "bob"

    def test_no_match(self, db):
        cmd_own(db, "alice", ["claim", "lib/"])
        assert find_owner(db, "bin/board") is None


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------


class TestVerifyTask:
    @patch("lib.board_own.subprocess.run")
    def test_pass(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="5 passed\n", stderr="")
        passed, summary = verify_task(tmp_path)
        assert passed is True
        assert "passed" in summary

    @patch("lib.board_own.subprocess.run")
    def test_fail(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=1, stdout="1 failed\n", stderr="")
        passed, _summary = verify_task(tmp_path)
        assert passed is False

    @patch("lib.board_own.subprocess.run")
    def test_timeout(self, mock_run, tmp_path):
        mock_run.side_effect = subprocess.TimeoutExpired("pytest", 300)
        passed, summary = verify_task(tmp_path)
        assert passed is False
        assert "超时" in summary

    @patch("lib.board_own.subprocess.run")
    def test_pytest_not_found(self, mock_run, tmp_path):
        mock_run.side_effect = FileNotFoundError
        passed, _summary = verify_task(tmp_path)
        assert passed is True


# ---------------------------------------------------------------------------
# Auto-PR
# ---------------------------------------------------------------------------


class TestAutoPR:
    def _write_cnb_config(self, tmp_path, sessions: list[str], extra: str = "") -> None:
        cnb = tmp_path / ".cnb"
        cnb.mkdir()
        sessions_toml = ", ".join(f'"{name}"' for name in sessions)
        cnb.joinpath("config.toml").write_text(
            f'claudes_home = "{tmp_path}"\nsessions = [{sessions_toml}]\nprefix = "test"\n{extra}'
        )

    @patch("lib.board_own.subprocess.run")
    def test_on_main_branch_skips(self, mock_run, tmp_path):
        mock_run.return_value = MagicMock(returncode=0, stdout="main\n", stderr="")
        assert auto_pr(tmp_path, "fix bug", "alice") is None

    @patch("lib.board_own.subprocess.run")
    def test_no_unpushed_skips(self, mock_run, tmp_path):
        def side_effect(cmd, **kwargs):
            if "branch" in cmd:
                return MagicMock(returncode=0, stdout="feature-x\n")
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = side_effect
        assert auto_pr(tmp_path, "fix bug", "alice") is None

    @patch("lib.board_own.subprocess.run")
    def test_creates_pr(self, mock_run, tmp_path):
        call_count = [0]

        def side_effect(cmd, **kwargs):
            call_count[0] += 1
            if "branch" in cmd:
                return MagicMock(returncode=0, stdout="feature-x\n")
            if "log" in cmd:
                return MagicMock(returncode=0, stdout="abc123 some commit\n")
            if "push" in cmd:
                return MagicMock(returncode=0, stdout="")
            if "pr" in cmd:
                return MagicMock(returncode=0, stdout="https://github.com/test/pr/1\n")
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = side_effect
        url = auto_pr(tmp_path, "fix bug", "alice")
        assert url == "https://github.com/test/pr/1"

    @patch.dict(os.environ, {"CNB_GITHUB_APP_SLUG_MUSK": "cnb-workspace-musk"}, clear=False)
    @patch("lib.github_app_identity.resolve_repository_installation_id")
    @patch("lib.github_app_identity.create_repo_scoped_token")
    @patch("lib.board_own.subprocess.run")
    def test_creates_pr_with_github_app_token(self, mock_run, mock_token, mock_installation, tmp_path):
        self._write_cnb_config(tmp_path, ["musk", "bezos"])
        mock_installation.return_value = 130997703
        mock_token.return_value = {"token": "ghs_app_token"}
        calls = []

        def side_effect(cmd, **kwargs):
            calls.append((cmd, kwargs))
            if "branch" in cmd:
                return MagicMock(returncode=0, stdout="feature-x\n")
            if "log" in cmd:
                return MagicMock(returncode=0, stdout="abc123 some commit\n")
            if cmd[:3] == ["gh", "repo", "view"]:
                return MagicMock(returncode=0, stdout="ApolloZhangOnGithub/cnb\n")
            if "push" in cmd:
                return MagicMock(returncode=0, stdout="")
            if "pr" in cmd:
                return MagicMock(returncode=0, stdout="https://github.com/test/pr/1\n")
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = side_effect

        url = auto_pr(tmp_path, "fix bug", "musk")

        assert url == "https://github.com/test/pr/1"
        pr_call = next(kwargs for cmd, kwargs in calls if cmd[:3] == ["gh", "pr", "create"])
        assert pr_call["env"]["GH_TOKEN"] == "ghs_app_token"
        assert pr_call["env"]["GITHUB_TOKEN"] == "ghs_app_token"

    @patch.dict(os.environ, {"CNB_GITHUB_APP_SLUG": "cnb-workspace-shared"}, clear=False)
    @patch("lib.github_app_identity.create_repo_scoped_token")
    @patch("lib.board_own.subprocess.run")
    def test_shared_github_app_slug_skips_app_token(self, mock_run, mock_token, tmp_path, capsys):
        self._write_cnb_config(tmp_path, ["musk", "bezos"])
        calls = []

        def side_effect(cmd, **kwargs):
            calls.append((cmd, kwargs))
            if "branch" in cmd:
                return MagicMock(returncode=0, stdout="feature-x\n")
            if "log" in cmd:
                return MagicMock(returncode=0, stdout="abc123 some commit\n")
            if "push" in cmd:
                return MagicMock(returncode=0, stdout="")
            if "pr" in cmd:
                return MagicMock(returncode=0, stdout="https://github.com/test/pr/1\n")
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = side_effect

        url = auto_pr(tmp_path, "fix bug", "musk")

        assert url == "https://github.com/test/pr/1"
        mock_token.assert_not_called()
        pr_call = next(kwargs for cmd, kwargs in calls if cmd[:3] == ["gh", "pr", "create"])
        assert pr_call["env"] is None
        out = capsys.readouterr().out
        assert "GitHub App identity skipped" in out
        assert "musk" in out
        assert "bezos" in out

    @patch("lib.github_app_identity.resolve_repository_installation_id")
    @patch("lib.github_app_identity.create_repo_scoped_token")
    @patch("lib.board_own.subprocess.run")
    def test_config_github_app_binding_is_session_specific(self, mock_run, mock_token, mock_installation, tmp_path):
        self._write_cnb_config(
            tmp_path,
            ["musk", "bezos"],
            '\n[session.musk]\ngithub_app_slug = "cnb-workspace-musk"\n',
        )
        mock_installation.return_value = 130997703
        mock_token.return_value = {"token": "ghs_app_token"}
        calls = []

        def side_effect(cmd, **kwargs):
            calls.append((cmd, kwargs))
            if "branch" in cmd:
                return MagicMock(returncode=0, stdout="feature-x\n")
            if "log" in cmd:
                return MagicMock(returncode=0, stdout="abc123 some commit\n")
            if cmd[:3] == ["gh", "repo", "view"]:
                return MagicMock(returncode=0, stdout="ApolloZhangOnGithub/cnb\n")
            if "push" in cmd:
                return MagicMock(returncode=0, stdout="")
            if "pr" in cmd:
                return MagicMock(returncode=0, stdout="https://github.com/test/pr/1\n")
            return MagicMock(returncode=0, stdout="")

        mock_run.side_effect = side_effect

        assert auto_pr(tmp_path, "fix bug", "musk") == "https://github.com/test/pr/1"
        pr_call = next(kwargs for cmd, kwargs in calls if cmd[:3] == ["gh", "pr", "create"])
        assert pr_call["env"]["GH_TOKEN"] == "ghs_app_token"


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------


class TestScan:
    @patch("lib.board_own.subprocess.run")
    def test_scan_routes_issue(self, mock_run, db, capsys):
        env = MagicMock()
        env.project_root = Path("/tmp/fake")
        db.env = env

        cmd_own(db, "alice", ["claim", "lib/board_own"])
        capsys.readouterr()

        issues_json = json.dumps(
            [{"number": 99, "title": "bug in board_own", "labels": [], "body": "lib/board_own crash"}]
        )

        def side_effect(cmd, **kwargs):
            if "issue" in cmd:
                return MagicMock(returncode=0, stdout=issues_json)
            if "run" in cmd:
                return MagicMock(returncode=0, stdout="[]")
            return MagicMock(returncode=1, stdout="")

        mock_run.side_effect = side_effect

        cmd_scan(db, "alice", [])
        out = capsys.readouterr().out
        assert "1 个 issue" in out

        msgs = db.query("SELECT body FROM messages WHERE recipient='alice' AND body LIKE '%ISSUE%'")
        assert len(msgs) == 1
        assert "#99" in msgs[0][0]

    @patch("lib.board_own.subprocess.run")
    def test_scan_no_owners(self, mock_run, db, capsys):
        env = MagicMock()
        env.project_root = Path("/tmp/fake")
        db.env = env

        def side_effect(cmd, **kwargs):
            return MagicMock(returncode=0, stdout="[]")

        mock_run.side_effect = side_effect

        cmd_scan(db, "alice", [])
        out = capsys.readouterr().out
        assert "无新事项" in out

    @patch("lib.board_own.subprocess.run")
    def test_scan_dedup(self, mock_run, db, capsys):
        env = MagicMock()
        env.project_root = Path("/tmp/fake")
        db.env = env

        cmd_own(db, "alice", ["claim", "lib/"])
        capsys.readouterr()

        issues_json = json.dumps([{"number": 10, "title": "lib/ problem", "labels": [], "body": ""}])

        def side_effect(cmd, **kwargs):
            if "issue" in cmd:
                return MagicMock(returncode=0, stdout=issues_json)
            return MagicMock(returncode=0, stdout="[]")

        mock_run.side_effect = side_effect

        cmd_scan(db, "alice", [])
        cmd_scan(db, "alice", [])

        msgs = db.query("SELECT body FROM messages WHERE recipient='alice' AND body LIKE '%ISSUE #10%'")
        assert len(msgs) == 1

    @patch("lib.board_own.subprocess.run")
    def test_scan_broadcasts_issue_for_orphaned_owner(self, mock_run, db, capsys):
        env = MagicMock()
        env.project_root = Path("/tmp/fake")
        db.env = env

        old = (datetime.now() - timedelta(hours=25)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE sessions SET last_heartbeat=? WHERE name='alice'", (old,))
        cmd_own(db, "alice", ["claim", "lib/"])
        capsys.readouterr()

        issues_json = json.dumps([{"number": 11, "title": "lib/ needs owner", "labels": [], "body": ""}])

        def side_effect(cmd, **kwargs):
            if "issue" in cmd:
                return MagicMock(returncode=0, stdout=issues_json)
            return MagicMock(returncode=0, stdout="[]")

        mock_run.side_effect = side_effect

        cmd_scan(db, "alice", [])
        out = capsys.readouterr().out
        assert "1 个 issue" in out

        msgs = db.query("SELECT body FROM messages WHERE recipient='all' AND body LIKE '%ISSUE #11%'")
        assert len(msgs) == 1
        assert "orphaned" in msgs[0][0]
        assert "alice" in msgs[0][0]

    @patch("lib.board_own.subprocess.run")
    def test_scan_ci_failure(self, mock_run, db, capsys):
        env = MagicMock()
        env.project_root = Path("/tmp/fake")
        db.env = env

        cmd_own(db, "alice", ["claim", "lib/"])
        capsys.readouterr()

        def side_effect(cmd, **kwargs):
            if "issue" in cmd:
                return MagicMock(returncode=0, stdout="[]")
            if "run" in cmd:
                return MagicMock(
                    returncode=0,
                    stdout=json.dumps([{"status": "completed", "conclusion": "failure", "headBranch": "feature-x"}]),
                )
            return MagicMock(returncode=1, stdout="")

        mock_run.side_effect = side_effect

        cmd_scan(db, "alice", [])
        out = capsys.readouterr().out
        assert "CI" in out

        msgs = db.query("SELECT body FROM messages WHERE recipient='alice' AND body LIKE '%CI FAIL%'")
        assert len(msgs) == 1
