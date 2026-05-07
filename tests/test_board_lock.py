"""Tests for lib/board_lock.py — git lock coordination.

Covers: acquiring locks, extending own locks, blocking on held locks,
releasing locks, force-unlock with notification, stale cleanup, lock status.
"""

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.board_lock import GIT_LOCK_TTL, _cleanup_stale, cmd_git_lock, cmd_git_lock_status, cmd_git_unlock


class TestCleanupStale:
    def test_removes_expired_locks(self, db):
        expired = int(time.time()) - 10
        db.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) VALUES (1, 'alice', 'test', ?)",
            (expired,),
        )
        _cleanup_stale(db)
        count = db.scalar("SELECT COUNT(*) FROM git_locks")
        assert count == 0

    def test_keeps_valid_locks(self, db):
        future = int(time.time()) + 100
        db.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) VALUES (1, 'alice', 'test', ?)",
            (future,),
        )
        _cleanup_stale(db)
        count = db.scalar("SELECT COUNT(*) FROM git_locks")
        assert count == 1

    def test_noop_when_empty(self, db):
        _cleanup_stale(db)
        count = db.scalar("SELECT COUNT(*) FROM git_locks")
        assert count == 0


class TestGitLock:
    def test_acquires_free_lock(self, db, capsys):
        cmd_git_lock(db, "alice", ["commit changes"])
        output = capsys.readouterr().out
        assert "OK" in output
        assert "alice" in output
        holder = db.scalar("SELECT session FROM git_locks WHERE id=1")
        assert holder == "alice"

    def test_stores_reason(self, db):
        cmd_git_lock(db, "alice", ["rebase", "main"])
        reason = db.scalar("SELECT reason FROM git_locks WHERE id=1")
        assert reason == "rebase main"

    def test_default_reason(self, db):
        cmd_git_lock(db, "alice", [])
        reason = db.scalar("SELECT reason FROM git_locks WHERE id=1")
        assert reason == "git operation"

    def test_extends_own_lock(self, db, capsys):
        cmd_git_lock(db, "alice", ["first"])
        capsys.readouterr()
        cmd_git_lock(db, "alice", ["extended"])
        output = capsys.readouterr().out
        assert "extended" in output
        reason = db.scalar("SELECT reason FROM git_locks WHERE id=1")
        assert reason == "extended"

    def test_blocks_when_held_by_other(self, db, capsys):
        cmd_git_lock(db, "alice", ["mine"])
        capsys.readouterr()
        with pytest.raises(SystemExit):
            cmd_git_lock(db, "bob", ["want lock"])
        output = capsys.readouterr().out
        assert "BLOCKED" in output
        assert "alice" in output

    def test_acquires_after_stale_expiry(self, db, capsys):
        expired = int(time.time()) - 10
        db.execute(
            "INSERT INTO git_locks(id, session, reason, expires_at) VALUES (1, 'alice', 'old', ?)",
            (expired,),
        )
        cmd_git_lock(db, "bob", ["new"])
        output = capsys.readouterr().out
        assert "OK" in output
        holder = db.scalar("SELECT session FROM git_locks WHERE id=1")
        assert holder == "bob"

    def test_case_insensitive_identity(self, db):
        cmd_git_lock(db, "Alice", ["test"])
        holder = db.scalar("SELECT session FROM git_locks WHERE id=1")
        assert holder == "alice"

    def test_lock_sets_ttl(self, db):
        now = int(time.time())
        cmd_git_lock(db, "alice", [])
        expires = db.scalar("SELECT expires_at FROM git_locks WHERE id=1")
        assert expires >= now + GIT_LOCK_TTL - 1
        assert expires <= now + GIT_LOCK_TTL + 2


class TestGitUnlock:
    def test_releases_own_lock(self, db, capsys):
        cmd_git_lock(db, "alice", ["test"])
        capsys.readouterr()
        cmd_git_unlock(db, "alice", [])
        output = capsys.readouterr().out
        assert "OK" in output
        count = db.scalar("SELECT COUNT(*) FROM git_locks")
        assert count == 0

    def test_already_free(self, db, capsys):
        cmd_git_unlock(db, "alice", [])
        output = capsys.readouterr().out
        assert "already free" in output

    def test_cannot_release_others_lock(self, db, capsys):
        cmd_git_lock(db, "alice", ["mine"])
        capsys.readouterr()
        with pytest.raises(SystemExit):
            cmd_git_unlock(db, "bob", [])
        output = capsys.readouterr().out
        assert "ERROR" in output
        assert "alice" in output

    def test_force_releases_others_lock(self, db, capsys):
        cmd_git_lock(db, "alice", ["mine"])
        capsys.readouterr()
        cmd_git_unlock(db, "bob", ["--force"])
        output = capsys.readouterr().out
        assert "force-releasing" in output
        count = db.scalar("SELECT COUNT(*) FROM git_locks")
        assert count == 0

    def test_force_unlock_notifies_holder(self, db):
        cmd_git_lock(db, "alice", ["mine"])
        cmd_git_unlock(db, "bob", ["--force"])
        msg = db.scalar(
            "SELECT body FROM messages WHERE sender='SYSTEM' AND recipient='alice' ORDER BY id DESC LIMIT 1"
        )
        assert "GIT-LOCK" in msg
        assert "bob" in msg

    def test_force_unlock_delivers_to_inbox(self, db):
        cmd_git_lock(db, "alice", ["mine"])
        cmd_git_unlock(db, "bob", ["--force"])
        inbox_count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session='alice'")
        assert inbox_count >= 1

    def test_removes_stale_index_lock(self, db):
        git_dir = db.env.project_root / ".git"
        git_dir.mkdir(exist_ok=True)
        index_lock = git_dir / "index.lock"
        index_lock.write_text("")
        cmd_git_lock(db, "alice", ["test"])
        with patch("lib.board_lock.subprocess") as mock_sub:
            mock_sub.run.return_value = type("R", (), {"returncode": 1})()
            cmd_git_unlock(db, "alice", [])
        assert not index_lock.exists()

    def test_keeps_index_lock_when_git_running(self, db):
        git_dir = db.env.project_root / ".git"
        git_dir.mkdir(exist_ok=True)
        index_lock = git_dir / "index.lock"
        index_lock.write_text("")
        cmd_git_lock(db, "alice", ["test"])
        with patch("lib.board_lock.subprocess") as mock_sub:
            mock_sub.run.return_value = type("R", (), {"returncode": 0})()
            cmd_git_unlock(db, "alice", [])
        assert index_lock.exists()


class TestGitLockStatus:
    def test_free_status(self, db, capsys):
        cmd_git_lock_status(db)
        output = capsys.readouterr().out
        assert "FREE" in output

    def test_locked_status(self, db, capsys):
        cmd_git_lock(db, "alice", ["pushing"])
        capsys.readouterr()
        cmd_git_lock_status(db)
        output = capsys.readouterr().out
        assert "LOCKED" in output
        assert "alice" in output
        assert "pushing" in output

    def test_shows_index_lock_warning(self, db, capsys):
        git_dir = db.env.project_root / ".git"
        git_dir.mkdir(exist_ok=True)
        index_lock = git_dir / "index.lock"
        index_lock.write_text("")
        cmd_git_lock_status(db)
        output = capsys.readouterr().out
        assert "index.lock" in output

    def test_no_index_lock_warning_when_absent(self, db, capsys):
        cmd_git_lock_status(db)
        output = capsys.readouterr().out
        assert "index.lock" not in output
