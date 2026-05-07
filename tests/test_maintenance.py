"""Tests for lib/board_maintenance.py — prune, backup, restore.

Covers: pruning old messages, dry-run mode, backup/restore with verification,
edge cases for empty databases and corrupt backups.
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.board_maintenance import _days_ago_ts, _parse_days, cmd_backup, cmd_prune, cmd_restore


@pytest.fixture
def maint_db(db):
    """BoardDB with some old and recent messages for prune testing."""
    old_ts = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d %H:%M:%S")
    recent_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with db.conn() as c:
        cur = c.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, 'alice', 'bob', 'old msg')", (old_ts,)
        )
        old_msg_id = cur.lastrowid
        cur = c.execute(
            "INSERT INTO messages(ts, sender, recipient, body) VALUES (?, 'alice', 'bob', 'new msg')", (recent_ts,)
        )
        new_msg_id = cur.lastrowid
        c.execute(
            "INSERT INTO inbox(session, message_id, delivered_at, read) VALUES ('bob', ?, ?, 1)", (old_msg_id, old_ts)
        )
        c.execute(
            "INSERT INTO inbox(session, message_id, delivered_at, read) VALUES ('bob', ?, ?, 0)",
            (new_msg_id, recent_ts),
        )

    return db


class TestParseDays:
    def test_integer_days(self):
        assert _parse_days("30") == 30

    def test_date_string(self):
        target = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        result = _parse_days(target)
        assert 9 <= result <= 11

    def test_invalid_input_exits(self):
        with pytest.raises(SystemExit):
            _parse_days("not-a-date")


class TestDaysAgoTs:
    def test_returns_timestamp_string(self):
        result = _days_ago_ts(30)
        datetime.strptime(result, "%Y-%m-%d %H:%M:%S")

    def test_is_in_the_past(self):
        result = _days_ago_ts(1)
        ts = datetime.strptime(result, "%Y-%m-%d %H:%M:%S")
        assert ts < datetime.now()


class TestPrune:
    def test_dry_run_shows_counts(self, maint_db, capsys):
        cmd_prune(maint_db, ["--dry-run"])
        output = capsys.readouterr().out
        assert "DRY RUN" in output

    def test_prune_removes_old_messages(self, maint_db, capsys):
        cmd_prune(maint_db, [])
        output = capsys.readouterr().out
        assert "pruned" in output

        remaining = maint_db.scalar("SELECT COUNT(*) FROM messages")
        assert remaining == 1

    def test_prune_nothing_to_prune(self, db, capsys):
        cmd_prune(db, [])
        output = capsys.readouterr().out
        assert "nothing to prune" in output

    def test_prune_with_before_days(self, maint_db, capsys):
        cmd_prune(maint_db, ["--before", "200"])
        output = capsys.readouterr().out
        assert "nothing to prune" in output

    def test_prune_rejects_positional_args(self, maint_db):
        with pytest.raises(SystemExit):
            cmd_prune(maint_db, ["extra-arg"])


class TestBackup:
    def test_creates_backup_file(self, db, capsys):
        cmd_backup(db, [])
        output = capsys.readouterr().out
        assert "OK backup saved" in output
        assert "bytes" in output

    def test_backup_with_custom_output(self, db, tmp_path, capsys):
        out_path = tmp_path / "custom-backup.db"
        cmd_backup(db, [f"--output={out_path}"])
        assert out_path.exists()
        output = capsys.readouterr().out
        assert "OK" in output

    def test_backup_is_valid_sqlite(self, db, tmp_path):
        out_path = tmp_path / "test-backup.db"
        cmd_backup(db, [f"--output={out_path}"])

        conn = sqlite3.connect(str(out_path))
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "sessions" in tables

    def test_backup_verification_failure_exits(self, db, tmp_path):
        out_path = tmp_path / "bad-backup.db"

        def write_garbage(src, dst):
            Path(dst).write_text("not a database")

        with patch("shutil.copy2", side_effect=write_garbage), pytest.raises(SystemExit):
            cmd_backup(db, [f"--output={out_path}"])
        assert not out_path.exists()


class TestRestore:
    def test_restore_with_force(self, db, tmp_path, capsys):
        backup_path = tmp_path / "backup.db"
        cmd_backup(db, [f"--output={backup_path}"])
        capsys.readouterr()

        cmd_restore(db, [str(backup_path), "--force"])
        output = capsys.readouterr().out
        assert "OK restored" in output

    def test_restore_missing_file_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_restore(db, ["/nonexistent/backup.db"])

    def test_restore_no_args_exits(self, db):
        with pytest.raises(SystemExit):
            cmd_restore(db, [])

    def test_restore_invalid_db_exits(self, db, tmp_path):
        bad_file = tmp_path / "corrupt.db"
        bad_file.write_text("not a database")
        with pytest.raises(SystemExit):
            cmd_restore(db, [str(bad_file), "--force"])

    def test_restore_empty_db_exits(self, db, tmp_path):
        empty_db = tmp_path / "empty.db"
        conn = sqlite3.connect(str(empty_db))
        conn.close()
        with pytest.raises(SystemExit):
            cmd_restore(db, [str(empty_db), "--force"])

    def test_restore_cancel(self, db, tmp_path, capsys):
        backup_path = tmp_path / "backup.db"
        cmd_backup(db, [f"--output={backup_path}"])
        capsys.readouterr()
        with patch("builtins.input", return_value="n"):
            cmd_restore(db, [str(backup_path)])
        out = capsys.readouterr().out
        assert "Cancelled" in out

    def test_restore_eof(self, db, tmp_path, capsys):
        backup_path = tmp_path / "backup.db"
        cmd_backup(db, [f"--output={backup_path}"])
        capsys.readouterr()
        with patch("builtins.input", side_effect=EOFError):
            cmd_restore(db, [str(backup_path)])
        out = capsys.readouterr().out
        assert "Cancelled" in out


class TestBackupHelp:
    def test_backup_help(self, db, capsys):
        cmd_backup(db, ["--help"])
        out = capsys.readouterr().out
        assert "Usage" in out

    def test_restore_help(self, db, capsys):
        cmd_restore(db, ["--help"])
        out = capsys.readouterr().out
        assert "Usage" in out


class TestPruneWithDate:
    def test_prune_with_date_string(self, maint_db, capsys):
        old_date = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
        cmd_prune(maint_db, ["--before", old_date])
        out = capsys.readouterr().out
        assert "nothing to prune" in out

    def test_prune_with_recent_date(self, maint_db, capsys):
        recent_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        cmd_prune(maint_db, ["--before", recent_date])
        out = capsys.readouterr().out
        assert "pruned" in out
