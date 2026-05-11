"""Tests for bin/doctor — system health checks.

Covers: check_db, check_foreign_keys, check_orphans, check_schema_version,
check_config, check_python, check_disk. Focuses on database and config checks
since they're the most important for reliability.
"""

import importlib.machinery
import importlib.util
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.conftest import SCHEMA_VERSION

SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"
DOCTOR_PATH = Path(__file__).parent.parent / "bin" / "doctor"

# Load bin/doctor as a module (no .py extension — need explicit SourceFileLoader)
_loader = importlib.machinery.SourceFileLoader("doctor", str(DOCTOR_PATH))
_spec = importlib.util.spec_from_loader("doctor", _loader, origin=str(DOCTOR_PATH))
assert _spec is not None
_doctor = importlib.util.module_from_spec(_spec)
_doctor.__file__ = str(DOCTOR_PATH)
assert _spec.loader is not None
_spec.loader.exec_module(_doctor)

check_db = _doctor.check_db
check_foreign_keys = _doctor.check_foreign_keys
check_orphans = _doctor.check_orphans
check_schema_version = _doctor.check_schema_version
check_config = _doctor.check_config
check_python = _doctor.check_python
check_disk = _doctor.check_disk


@pytest.fixture
def doctor_db(tmp_path):
    """Create a test database from schema.sql with test sessions."""
    db_path = tmp_path / "board.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_PATH.read_text())
    conn.execute("INSERT INTO sessions(name) VALUES ('alice')")
    conn.execute("INSERT INTO sessions(name) VALUES ('bob')")
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
    conn.commit()
    conn.close()
    return db_path


class TestCheckDb:
    def test_existing_db(self, doctor_db, capsys):
        assert check_db(doctor_db) is True
        output = capsys.readouterr().out
        assert "board.db found" in output

    def test_missing_db(self, tmp_path, capsys):
        assert check_db(tmp_path / "missing.db") is False
        output = capsys.readouterr().out
        assert "not found" in output


class TestCheckForeignKeys:
    def test_has_foreign_keys(self, doctor_db, capsys):
        assert check_foreign_keys(doctor_db) is True
        output = capsys.readouterr().out
        assert "Foreign keys defined" in output

    def test_no_foreign_keys(self, tmp_path, capsys):
        db_path = tmp_path / "bare.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, val TEXT)")
        conn.commit()
        conn.close()
        assert check_foreign_keys(db_path) is False
        output = capsys.readouterr().out
        assert "No foreign key" in output

    def test_corrupt_db(self, tmp_path, capsys):
        bad = tmp_path / "corrupt.db"
        bad.write_text("not sqlite")
        assert check_foreign_keys(bad) is False
        output = capsys.readouterr().out
        assert "failed" in output


class TestCheckOrphans:
    def test_clean_db(self, doctor_db, capsys):
        assert check_orphans(doctor_db) is True
        output = capsys.readouterr().out
        assert "No orphaned" in output

    def test_orphaned_inbox_session(self, doctor_db, capsys):
        conn = sqlite3.connect(str(doctor_db))
        conn.execute("INSERT INTO messages(ts, sender, recipient, body) VALUES ('2025-01-01', 'alice', 'bob', 'hi')")
        conn.execute("INSERT INTO inbox(session, message_id) VALUES ('ghost', 1)")
        conn.commit()
        conn.close()
        assert check_orphans(doctor_db) is False
        output = capsys.readouterr().out
        assert "inbox rows reference missing sessions" in output

    def test_orphaned_inbox_message(self, doctor_db, capsys):
        conn = sqlite3.connect(str(doctor_db))
        conn.execute("INSERT INTO inbox(session, message_id) VALUES ('alice', 9999)")
        conn.commit()
        conn.close()
        assert check_orphans(doctor_db) is False
        output = capsys.readouterr().out
        assert "inbox rows reference missing messages" in output

    def test_orphaned_tasks(self, doctor_db, capsys):
        conn = sqlite3.connect(str(doctor_db))
        conn.execute("INSERT INTO tasks(session, description) VALUES ('phantom', 'orphan task')")
        conn.commit()
        conn.close()
        assert check_orphans(doctor_db) is False
        output = capsys.readouterr().out
        assert "tasks reference missing sessions" in output

    def test_orphaned_votes(self, doctor_db, capsys):
        conn = sqlite3.connect(str(doctor_db))
        conn.execute("INSERT INTO votes(proposal_id, voter, decision) VALUES (9999, 'alice', 'approve')")
        conn.commit()
        conn.close()
        assert check_orphans(doctor_db) is False
        output = capsys.readouterr().out
        assert "votes reference missing proposals" in output

    def test_orphaned_thread_replies(self, doctor_db, capsys):
        conn = sqlite3.connect(str(doctor_db))
        conn.execute("INSERT INTO thread_replies(thread_id, author, body) VALUES ('gone', 'alice', 'orphan reply')")
        conn.commit()
        conn.close()
        assert check_orphans(doctor_db) is False
        output = capsys.readouterr().out
        assert "replies reference missing threads" in output

    def test_multiple_orphan_types(self, doctor_db, capsys):
        conn = sqlite3.connect(str(doctor_db))
        conn.execute("INSERT INTO tasks(session, description) VALUES ('phantom', 'orphan')")
        conn.execute("INSERT INTO thread_replies(thread_id, author, body) VALUES ('gone', 'alice', 'orphan')")
        conn.commit()
        conn.close()
        assert check_orphans(doctor_db) is False
        output = capsys.readouterr().out
        assert "tasks" in output
        assert "replies" in output


class TestCheckSchemaVersion:
    def test_version_present(self, doctor_db, capsys):
        assert check_schema_version(doctor_db) is True
        output = capsys.readouterr().out
        assert "Schema version:" in output

    def test_no_meta_table(self, tmp_path, capsys):
        db_path = tmp_path / "bare.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        assert check_schema_version(db_path) is False
        output = capsys.readouterr().out
        assert "failed" in output


class TestCheckConfig:
    def test_valid_config(self, capsys):
        from lib.common import ClaudesEnv

        env = ClaudesEnv(
            claudes_dir=Path(__file__).parent.parent,
            project_root=Path(__file__).parent.parent,
            install_home=Path(__file__).parent.parent,
            board_db=Path(__file__).parent.parent / "board.db",
            sessions_dir=Path(__file__).parent.parent / "sessions",
            cv_dir=Path(__file__).parent.parent / "cv",
            log_dir=Path(__file__).parent.parent / "logs",
            prefix="cc-test",
            sessions=["alice", "bob"],
            suspended_file=Path(__file__).parent.parent / "suspended",
            attendance_log=Path(__file__).parent.parent / "attendance.log",
        )
        assert check_config(env) is True
        output = capsys.readouterr().out
        assert "Sessions: alice, bob" in output
        assert "Prefix: cc-test" in output

    def test_no_sessions(self, tmp_path, capsys):
        from lib.common import ClaudesEnv

        env = ClaudesEnv(
            claudes_dir=tmp_path,
            project_root=tmp_path,
            install_home=tmp_path,
            board_db=tmp_path / "board.db",
            sessions_dir=tmp_path / "sessions",
            cv_dir=tmp_path / "cv",
            log_dir=tmp_path / "logs",
            prefix="cc-test",
            sessions=[],
            suspended_file=tmp_path / "suspended",
            attendance_log=tmp_path / "attendance.log",
        )
        assert check_config(env) is False
        output = capsys.readouterr().out
        assert "No sessions configured" in output

    def test_no_prefix(self, tmp_path, capsys):
        from lib.common import ClaudesEnv

        env = ClaudesEnv(
            claudes_dir=tmp_path,
            project_root=tmp_path,
            install_home=tmp_path,
            board_db=tmp_path / "board.db",
            sessions_dir=tmp_path / "sessions",
            cv_dir=tmp_path / "cv",
            log_dir=tmp_path / "logs",
            prefix="",
            sessions=["alice"],
            suspended_file=tmp_path / "suspended",
            attendance_log=tmp_path / "attendance.log",
        )
        assert check_config(env) is False
        output = capsys.readouterr().out
        assert "No prefix" in output

    def test_missing_install_home(self, tmp_path, capsys):
        from lib.common import ClaudesEnv

        env = ClaudesEnv(
            claudes_dir=tmp_path,
            project_root=tmp_path,
            install_home=tmp_path / "nonexistent",
            board_db=tmp_path / "board.db",
            sessions_dir=tmp_path / "sessions",
            cv_dir=tmp_path / "cv",
            log_dir=tmp_path / "logs",
            prefix="cc-test",
            sessions=["alice"],
            suspended_file=tmp_path / "suspended",
            attendance_log=tmp_path / "attendance.log",
        )
        assert check_config(env) is False
        output = capsys.readouterr().out
        assert "Install home not found" in output


class TestCheckPython:
    def test_current_python_passes(self, capsys):
        assert check_python() is True
        output = capsys.readouterr().out
        assert "Python" in output

    def test_old_python_fails(self, capsys):
        from collections import namedtuple

        FakeVI = namedtuple("version_info", ["major", "minor", "micro", "releaselevel", "serial"])  # type: ignore[name-match]
        fake_info = FakeVI(3, 9, 0, "final", 0)
        with patch.object(_doctor.sys, "version_info", fake_info):
            assert check_python() is False
        output = capsys.readouterr().out
        assert "3.11 required" in output


class TestCheckDisk:
    def test_sufficient_space(self, tmp_path, capsys):
        assert check_disk(tmp_path) is True
        output = capsys.readouterr().out
        assert "Disk free" in output

    def test_low_space(self, tmp_path, capsys):
        fake_stat = os.statvfs_result((4096, 4096, 100, 50, 50, 100, 50, 50, 0, 255))
        with patch.object(_doctor.os, "statvfs", return_value=fake_stat):
            assert check_disk(tmp_path) is False
        output = capsys.readouterr().out
        assert "Low disk" in output

    def test_os_error(self, tmp_path, capsys):
        with patch.object(_doctor.os, "statvfs", side_effect=OSError("fail")):
            assert check_disk(tmp_path) is False
        output = capsys.readouterr().out
        assert "Cannot check" in output
