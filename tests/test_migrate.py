"""Tests for lib/migrate.py — schema migration runner.

Covers: migration discovery, version tracking, applying pending migrations,
skipping already-applied migrations, and error handling.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.migrate import _applied_versions, _discover_migrations, _record_version, run_migrations

SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"


@pytest.fixture
def migration_env(tmp_path):
    """Create a minimal environment with DB and migrations dir."""
    db_path = tmp_path / "board.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_PATH.read_text())
    conn.execute("INSERT INTO sessions(name) VALUES ('alice')")
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '0')")
    conn.commit()
    conn.close()

    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()

    return db_path, tmp_path


class TestDiscoverMigrations:
    def test_finds_numbered_sql_files(self, tmp_path):
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "001_first.sql").write_text("SELECT 1;")
        (mig_dir / "002_second.sql").write_text("SELECT 2;")
        (mig_dir / "readme.txt").write_text("not a migration")

        result = _discover_migrations(mig_dir)
        assert len(result) == 2
        assert result[0][0] == 1
        assert result[1][0] == 2

    def test_sorts_by_version_number(self, tmp_path):
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "003_third.sql").write_text("SELECT 3;")
        (mig_dir / "001_first.sql").write_text("SELECT 1;")

        result = _discover_migrations(mig_dir)
        assert [v for v, _ in result] == [1, 3]

    def test_empty_directory(self, tmp_path):
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()

        result = _discover_migrations(mig_dir)
        assert result == []

    def test_ignores_non_numeric_prefixes(self, tmp_path):
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        (mig_dir / "abc_nope.sql").write_text("SELECT 1;")
        (mig_dir / "001_yes.sql").write_text("SELECT 2;")

        result = _discover_migrations(mig_dir)
        assert len(result) == 1


class TestAppliedVersions:
    def test_returns_empty_when_no_meta(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        result = _applied_versions(conn)
        conn.close()
        assert result == set()

    def test_returns_range_up_to_version(self, migration_env):
        db_path, _ = migration_env
        conn = sqlite3.connect(str(db_path))
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '3')")
        conn.commit()
        result = _applied_versions(conn)
        conn.close()
        assert result == {1, 2, 3}

    def test_version_zero_returns_empty(self, migration_env):
        db_path, _ = migration_env
        conn = sqlite3.connect(str(db_path))
        result = _applied_versions(conn)
        conn.close()
        assert result == set()


class TestRecordVersion:
    def test_records_version_in_meta(self, migration_env):
        db_path, _ = migration_env
        conn = sqlite3.connect(str(db_path))
        _record_version(conn, 5)
        conn.commit()
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        conn.close()
        assert row[0] == "5"

    def test_upserts_existing_version(self, migration_env):
        db_path, _ = migration_env
        conn = sqlite3.connect(str(db_path))
        _record_version(conn, 3)
        conn.commit()
        _record_version(conn, 5)
        conn.commit()
        row = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        conn.close()
        assert row[0] == "5"


class TestRunMigrations:
    def test_applies_pending_migration(self, migration_env):
        db_path, claudes_home = migration_env
        mig_dir = claudes_home / "migrations"
        (mig_dir / "001_add_col.sql").write_text("ALTER TABLE sessions ADD COLUMN test_col TEXT DEFAULT 'ok';")

        applied = run_migrations(db_path, claudes_home)
        assert applied == 1

        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT test_col FROM sessions WHERE name='alice'").fetchone()
        ver = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
        conn.close()
        assert row[0] == "ok"
        assert ver[0] == "1"

    def test_skips_already_applied(self, migration_env):
        db_path, claudes_home = migration_env
        mig_dir = claudes_home / "migrations"
        (mig_dir / "001_add_col.sql").write_text("ALTER TABLE sessions ADD COLUMN test_col TEXT DEFAULT 'ok';")

        conn = sqlite3.connect(str(db_path))
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '1')")
        conn.commit()
        conn.close()

        applied = run_migrations(db_path, claudes_home)
        assert applied == 0

    def test_applies_multiple_in_order(self, migration_env):
        db_path, claudes_home = migration_env
        mig_dir = claudes_home / "migrations"
        (mig_dir / "001_col_a.sql").write_text("ALTER TABLE sessions ADD COLUMN col_a TEXT DEFAULT 'a';")
        (mig_dir / "002_col_b.sql").write_text("ALTER TABLE sessions ADD COLUMN col_b TEXT DEFAULT 'b';")

        applied = run_migrations(db_path, claudes_home)
        assert applied == 2

        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT col_a, col_b FROM sessions WHERE name='alice'").fetchone()
        conn.close()
        assert row == ("a", "b")

    def test_no_migrations_returns_zero(self, migration_env):
        db_path, claudes_home = migration_env
        applied = run_migrations(db_path, claudes_home)
        assert applied == 0

    def test_failed_migration_exits(self, migration_env):
        db_path, claudes_home = migration_env
        mig_dir = claudes_home / "migrations"
        (mig_dir / "001_bad.sql").write_text("INVALID SQL SYNTAX HERE !!!")

        with pytest.raises(SystemExit):
            run_migrations(db_path, claudes_home)

    def test_missing_migrations_dir_exits(self, tmp_path):
        db_path = tmp_path / "board.db"
        sqlite3.connect(str(db_path)).close()
        no_mig_home = tmp_path / "empty"
        no_mig_home.mkdir()

        with pytest.raises(SystemExit):
            run_migrations(db_path, no_mig_home)
