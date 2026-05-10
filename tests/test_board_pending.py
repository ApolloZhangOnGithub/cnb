"""Tests for lib/board_pending — pending actions queue."""

import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.board_db import BoardDB
from lib.board_pending import cmd_pending
from tests.conftest import SCHEMA_VERSION


def _setup_db(tmp_path: Path) -> BoardDB:
    db_path = tmp_path / "board.db"
    schema = Path(__file__).parent.parent / "schema.sql"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(schema.read_text())
    conn.execute("INSERT INTO sessions(name) VALUES ('alice')")
    conn.execute("INSERT INTO sessions(name) VALUES ('bob')")
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
    conn.commit()
    conn.close()
    return BoardDB(db_path)


def _add_action(db: BoardDB, **kwargs) -> int:
    defaults = {
        "type": "auth",
        "command": "gcloud auth login",
        "reason": "need credentials",
        "verify_command": "gcloud auth print-access-token",
        "retry_command": None,
        "created_by": "alice",
    }
    defaults.update(kwargs)
    from lib.board_db import ts

    now = ts()
    return db.execute(
        "INSERT INTO pending_actions(type, command, reason, verify_command, retry_command, created_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            defaults["type"],
            defaults["command"],
            defaults["reason"],
            defaults["verify_command"],
            defaults["retry_command"],
            defaults["created_by"],
            now,
        ),
    )


class TestCmdRouting:
    def test_unknown_subcmd_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_pending(db, "alice", ["bogus"])
        assert exc.value.code == 1

    def test_default_is_list(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        cmd_pending(db, "alice", [])
        out = capsys.readouterr().out
        assert "无待处理操作" in out


class TestPendingAdd:
    def test_adds_action(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        cmd_pending(
            db,
            "alice",
            [
                "add",
                "--type",
                "auth",
                "--command",
                "gcloud auth login",
                "--reason",
                "need GCP credentials",
            ],
        )
        out = capsys.readouterr().out
        assert "OK pending #1 added" in out

    def test_with_verify_and_retry(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        cmd_pending(
            db,
            "alice",
            [
                "add",
                "--type",
                "approve",
                "--command",
                "npm login",
                "--reason",
                "publish access",
                "--verify",
                "npm whoami",
                "--retry",
                "npm publish",
            ],
        )
        out = capsys.readouterr().out
        assert "OK pending #1 added" in out
        assert "approve" in out

    def test_missing_required_fields_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_pending(db, "alice", ["add", "--type", "auth"])
        assert exc.value.code == 1

    def test_invalid_type_exits(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_pending(
                db,
                "alice",
                [
                    "add",
                    "--type",
                    "invalid",
                    "--command",
                    "x",
                    "--reason",
                    "y",
                ],
            )
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "类型必须是" in out

    def test_stored_in_db(self, tmp_path):
        db = _setup_db(tmp_path)
        cmd_pending(
            db,
            "alice",
            [
                "add",
                "--type",
                "confirm",
                "--command",
                "do-thing",
                "--reason",
                "testing",
            ],
        )
        row = db.query_one("SELECT type, command, reason, status, created_by FROM pending_actions WHERE id=1")
        assert row is not None
        assert row[0] == "confirm"
        assert row[1] == "do-thing"
        assert row[3] == "pending"
        assert row[4] == "alice"


class TestPendingList:
    def test_empty_list(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        cmd_pending(db, "alice", ["list"])
        out = capsys.readouterr().out
        assert "无待处理操作" in out

    def test_shows_pending_actions(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _add_action(db)
        cmd_pending(db, "alice", ["list"])
        out = capsys.readouterr().out
        assert "待处理操作" in out
        assert "gcloud auth login" in out
        assert "need credentials" in out

    def test_all_flag_shows_resolved(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        aid = _add_action(db)
        db.execute("UPDATE pending_actions SET status='done' WHERE id=?", (aid,))
        cmd_pending(db, "alice", ["list"])
        out1 = capsys.readouterr().out
        assert "无待处理操作" in out1

        cmd_pending(db, "alice", ["list", "--all"])
        out2 = capsys.readouterr().out
        assert "所有操作" in out2
        assert "gcloud auth login" in out2

    def test_shows_verify_and_retry_commands(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _add_action(db, retry_command="gcloud auth login --force")
        cmd_pending(db, "alice", ["list"])
        out = capsys.readouterr().out
        assert "验证命令" in out
        assert "重试命令" in out

    def test_status_icons(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _add_action(db)
        cmd_pending(db, "alice", ["list"])
        out = capsys.readouterr().out
        assert "⏳" in out


class TestPendingVerify:
    def test_no_verifiable_actions(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        cmd_pending(db, "alice", ["verify"])
        out = capsys.readouterr().out
        assert "无可验证的操作" in out

    @patch("lib.board_pending.subprocess.run")
    def test_verify_success(self, mock_run, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _add_action(db)
        mock_run.return_value.returncode = 0
        cmd_pending(db, "alice", ["verify"])
        out = capsys.readouterr().out
        assert "验证通过" in out
        assert "1 通过" in out

        row = db.query_one("SELECT status FROM pending_actions WHERE id=1")
        assert row[0] == "done"

    @patch("lib.board_pending.subprocess.run")
    def test_verify_with_retry_success(self, mock_run, tmp_path, capsys):
        db = _setup_db(tmp_path)
        aid = _add_action(db, retry_command="npm publish")
        mock_run.side_effect = [
            subprocess.CompletedProcess(["verify"], 0, stdout="", stderr=""),
            subprocess.CompletedProcess(["retry"], 0, stdout="", stderr=""),
        ]

        cmd_pending(db, "alice", ["verify", "--retry"])
        out = capsys.readouterr().out
        assert "验证通过" in out
        assert "重试成功" in out
        assert "重试结果: 1 成功, 0 失败, 0 跳过" in out

        row = db.query_one("SELECT status FROM pending_actions WHERE id=?", (aid,))
        assert row[0] == "retried"
        assert mock_run.call_args_list[0].args[0] == ["gcloud", "auth", "print-access-token"]
        assert mock_run.call_args_list[1].args[0] == ["npm", "publish"]

    @patch("lib.board_pending.subprocess.run")
    def test_verify_with_retry_failure(self, mock_run, tmp_path, capsys):
        db = _setup_db(tmp_path)
        aid = _add_action(db, retry_command="npm publish")
        mock_run.side_effect = [
            subprocess.CompletedProcess(["verify"], 0, stdout="", stderr=""),
            subprocess.CompletedProcess(["retry"], 1, stdout="", stderr="publish denied"),
        ]

        cmd_pending(db, "alice", ["verify", "#1", "--retry"])
        out = capsys.readouterr().out
        assert "验证通过" in out
        assert "重试失败" in out
        assert "publish denied" in out

        row = db.query_one("SELECT status FROM pending_actions WHERE id=?", (aid,))
        assert row[0] == "failed"

    @patch("lib.board_pending.subprocess.run")
    def test_verify_failure(self, mock_run, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _add_action(db)
        mock_run.return_value.returncode = 1
        cmd_pending(db, "alice", ["verify"])
        out = capsys.readouterr().out
        assert "验证失败" in out

        row = db.query_one("SELECT status FROM pending_actions WHERE id=1")
        assert row[0] == "reminded"

    @patch("lib.board_pending.subprocess.run")
    def test_verify_specific_id(self, mock_run, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _add_action(db)
        _add_action(db, command="other-cmd", verify_command="other-verify")
        mock_run.return_value.returncode = 0
        cmd_pending(db, "alice", ["verify", "#1"])
        out = capsys.readouterr().out
        assert "#1" in out

        row1 = db.query_one("SELECT status FROM pending_actions WHERE id=1")
        row2 = db.query_one("SELECT status FROM pending_actions WHERE id=2")
        assert row1[0] == "done"
        assert row2[0] == "pending"

    @patch("lib.board_pending.subprocess.run", side_effect=TimeoutError)
    def test_verify_timeout(self, mock_run, tmp_path, capsys):
        import subprocess as sp

        with patch("lib.board_pending.subprocess.run", side_effect=sp.TimeoutExpired("cmd", 30)):
            db = _setup_db(tmp_path)
            _add_action(db)
            cmd_pending(db, "alice", ["verify"])
            out = capsys.readouterr().out
            assert "超时" in out
            row = db.query_one("SELECT status FROM pending_actions WHERE id=1")
            assert row[0] == "reminded"

    def test_verify_invalid_id_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_pending(db, "alice", ["verify", "notanumber"])
        assert exc.value.code == 1


class TestPendingRetry:
    def test_no_retryable_actions(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        cmd_pending(db, "alice", ["retry"])
        out = capsys.readouterr().out
        assert "无可重试的操作" in out

    @patch("lib.board_pending.subprocess.run")
    def test_retry_success(self, mock_run, tmp_path, capsys):
        db = _setup_db(tmp_path)
        aid = _add_action(db, retry_command="npm publish")
        db.execute("UPDATE pending_actions SET status='done' WHERE id=?", (aid,))

        mock_run.return_value.returncode = 0
        cmd_pending(db, "alice", ["retry"])
        out = capsys.readouterr().out
        assert "重试成功" in out

        row = db.query_one("SELECT status FROM pending_actions WHERE id=?", (aid,))
        assert row[0] == "retried"

    @patch("lib.board_pending.subprocess.run")
    def test_retry_failure(self, mock_run, tmp_path, capsys):
        db = _setup_db(tmp_path)
        aid = _add_action(db, retry_command="npm publish")
        db.execute("UPDATE pending_actions SET status='done' WHERE id=?", (aid,))

        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "auth failed"
        mock_run.return_value.stdout = ""
        cmd_pending(db, "alice", ["retry"])
        out = capsys.readouterr().out
        assert "重试失败" in out

        row = db.query_one("SELECT status FROM pending_actions WHERE id=?", (aid,))
        assert row[0] == "failed"

    @patch("lib.board_pending.subprocess.run")
    def test_retry_can_rerun_failed_action(self, mock_run, tmp_path, capsys):
        db = _setup_db(tmp_path)
        aid = _add_action(db, retry_command="npm publish")
        db.execute("UPDATE pending_actions SET status='failed' WHERE id=?", (aid,))

        mock_run.return_value.returncode = 0
        cmd_pending(db, "alice", ["retry"])
        out = capsys.readouterr().out
        assert "重试成功" in out

        row = db.query_one("SELECT status FROM pending_actions WHERE id=?", (aid,))
        assert row[0] == "retried"

    def test_retry_invalid_id_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_pending(db, "alice", ["retry", "xyz"])
        assert exc.value.code == 1


class TestPendingResolve:
    def test_resolves_pending(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        _add_action(db)
        cmd_pending(db, "alice", ["resolve", "1"])
        out = capsys.readouterr().out
        assert "已手动标记为完成" in out

        row = db.query_one("SELECT status FROM pending_actions WHERE id=1")
        assert row[0] == "done"

    def test_resolves_reminded(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        aid = _add_action(db)
        db.execute("UPDATE pending_actions SET status='reminded' WHERE id=?", (aid,))
        cmd_pending(db, "alice", ["resolve", "#1"])
        out = capsys.readouterr().out
        assert "已手动标记为完成" in out

    def test_already_done_noop(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        aid = _add_action(db)
        db.execute("UPDATE pending_actions SET status='done' WHERE id=?", (aid,))
        cmd_pending(db, "alice", ["resolve", "1"])
        out = capsys.readouterr().out
        assert "已是 done 状态" in out

    def test_nonexistent_id_exits(self, tmp_path, capsys):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_pending(db, "alice", ["resolve", "999"])
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "不存在" in out

    def test_no_args_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_pending(db, "alice", ["resolve"])
        assert exc.value.code == 1

    def test_invalid_id_exits(self, tmp_path):
        db = _setup_db(tmp_path)
        with pytest.raises(SystemExit) as exc:
            cmd_pending(db, "alice", ["resolve", "abc"])
        assert exc.value.code == 1
