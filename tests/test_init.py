"""Tests for the project initialization (bin/init).

Covers: directory structure creation, config.toml generation,
database initialization from schema, session .md file creation,
CLAUDE.md generation, idempotency, and session name validation.
"""

import re
import sqlite3

import pytest

from tests.conftest import DEFAULT_SESSIONS, SCHEMA_PATH


class TestDirectoryStructure:
    """Initialization creates the correct directory structure."""

    def test_claudes_dir_created(self, tmp_project):
        """The .claudes/ directory exists."""
        assert (tmp_project / ".claudes").is_dir()

    def test_sessions_dir_created(self, tmp_project):
        """The sessions/ subdirectory exists."""
        assert (tmp_project / ".claudes" / "sessions").is_dir()

    def test_files_dir_created(self, tmp_project):
        """The files/ subdirectory exists."""
        assert (tmp_project / ".claudes" / "files").is_dir()

    def test_logs_dir_created(self, tmp_project):
        """The logs/ subdirectory exists."""
        assert (tmp_project / ".claudes" / "logs").is_dir()

    def test_okr_dir_created(self, tmp_project):
        """The okr/ subdirectory exists."""
        assert (tmp_project / ".claudes" / "okr").is_dir()

    def test_cv_dir_created(self, tmp_project):
        """The cv/ subdirectory exists."""
        assert (tmp_project / ".claudes" / "cv").is_dir()


class TestConfigGeneration:
    """config.toml generation."""

    def test_config_file_exists(self, tmp_project):
        """config.toml is created."""
        assert (tmp_project / ".claudes" / "config.toml").is_file()

    def test_config_has_claudes_home(self, tmp_project):
        """config.toml contains claudes_home."""
        config = (tmp_project / ".claudes" / "config.toml").read_text()
        assert "claudes_home" in config

    def test_config_has_sessions_array(self, tmp_project):
        """config.toml contains the sessions array with all session names."""
        config = (tmp_project / ".claudes" / "config.toml").read_text()
        assert "sessions" in config
        for name in DEFAULT_SESSIONS:
            assert name in config

    def test_config_has_prefix(self, tmp_project):
        """config.toml contains a prefix variable."""
        config = (tmp_project / ".claudes" / "config.toml").read_text()
        assert "prefix" in config


class TestDatabaseInitialization:
    """Database initialization from schema.sql."""

    def test_database_file_exists(self, tmp_project):
        """board.db is created."""
        assert (tmp_project / ".claudes" / "board.db").is_file()

    def test_database_has_all_tables(self, tmp_project):
        """Database contains all tables defined in schema.sql."""
        db_path = tmp_project / ".claudes" / "board.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
        tables = {r["name"] for r in rows}
        conn.close()

        expected = {
            "sessions",
            "messages",
            "inbox",
            "proposals",
            "votes",
            "files",
            "bugs",
            "threads",
            "thread_replies",
            "kudos",
            "suspended",
            "tasks",
            "meta",
        }
        assert expected.issubset(tables)

    def test_sessions_are_inserted(self, tmp_project):
        """All configured sessions are inserted into the sessions table."""
        db_path = tmp_project / ".claudes" / "board.db"
        conn = sqlite3.connect(str(db_path))

        rows = conn.execute("SELECT name FROM sessions ORDER BY name").fetchall()
        conn.close()

        names = [r[0] for r in rows]
        assert names == sorted(DEFAULT_SESSIONS)

    def test_sessions_lowercase(self, tmp_project):
        """Session names are stored in lowercase."""
        db_path = tmp_project / ".claudes" / "board.db"
        conn = sqlite3.connect(str(db_path))

        rows = conn.execute("SELECT name FROM sessions").fetchall()
        conn.close()

        for row in rows:
            assert row[0] == row[0].lower()


class TestSessionFiles:
    """Session .md file creation."""

    def test_session_files_created(self, tmp_project):
        """A .md file is created for each session."""
        for name in DEFAULT_SESSIONS:
            path = tmp_project / ".claudes" / "sessions" / f"{name}.md"
            assert path.is_file(), f"Missing session file for {name}"

    def test_session_file_has_header(self, tmp_project):
        """Each session file starts with a header containing the session name."""
        for name in DEFAULT_SESSIONS:
            content = (tmp_project / ".claudes" / "sessions" / f"{name}.md").read_text()
            assert f"# {name}" in content

    def test_session_file_has_current_task_section(self, tmp_project):
        """Each session file has a Current task section."""
        for name in DEFAULT_SESSIONS:
            content = (tmp_project / ".claudes" / "sessions" / f"{name}.md").read_text()
            assert "## Current task" in content

    def test_session_file_has_inbox_section(self, tmp_project):
        """Each session file has an @inbox section."""
        for name in DEFAULT_SESSIONS:
            content = (tmp_project / ".claudes" / "sessions" / f"{name}.md").read_text()
            assert "## @inbox" in content


class TestIdempotency:
    """Running initialization twice does not break things."""

    def test_reinit_does_not_duplicate_sessions(self, tmp_project):
        """Re-initializing the database does not create duplicate sessions."""
        db_path = tmp_project / ".claudes" / "board.db"

        # Simulate re-init: try inserting sessions again with INSERT OR IGNORE
        conn = sqlite3.connect(str(db_path))
        for name in DEFAULT_SESSIONS:
            conn.execute("INSERT OR IGNORE INTO sessions(name) VALUES (?)", (name,))
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        conn.close()

        assert count == len(DEFAULT_SESSIONS)

    def test_reinit_preserves_existing_data(self, tmp_project):
        """Re-initialization preserves messages and other data."""
        db_path = tmp_project / ".claudes" / "board.db"
        conn = sqlite3.connect(str(db_path))

        # Add some data
        conn.execute(
            "INSERT INTO messages(ts, sender, recipient, body) "
            "VALUES ('2025-01-01 10:00', 'alice', 'bob', 'important message')"
        )
        conn.commit()

        # Re-apply schema (CREATE TABLE IF NOT EXISTS)
        conn.executescript(SCHEMA_PATH.read_text())
        conn.commit()

        # Data should still be there
        count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        conn.close()
        assert count == 1

    def test_reinit_session_files_overwritable(self, tmp_project):
        """Session files can be safely overwritten."""
        path = tmp_project / ".claudes" / "sessions" / "alice.md"

        # Modify the file
        path.write_text("# alice\n\n## Current task\nworking on something\n")

        # Re-create (simulating init)
        path.write_text("# alice\n\n## Current task\n(none)\n\n## @inbox\n")

        content = path.read_text()
        assert "(none)" in content


class TestSchemaApplication:
    """Applying schema.sql to the database."""

    def test_schema_file_exists(self):
        """schema.sql exists in the project root."""
        assert SCHEMA_PATH.is_file()

    def test_schema_is_valid_sql(self):
        """schema.sql can be executed without errors."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_PATH.read_text())

        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()

        assert len(tables) > 0

    def test_schema_creates_indexes(self):
        """schema.sql creates the expected indexes."""
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA_PATH.read_text())

        indexes = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        conn.close()

        index_names = {r[0] for r in indexes}
        assert "idx_msg_ts" in index_names
        assert "idx_inbox" in index_names


# ── session name validation (bin/init) ──

VALID_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,62}[a-z0-9])?$")
RESERVED = frozenset({"all", "dispatcher", "lead", "system"})


def _validate(name: str) -> str:
    """Replicate the validation logic from bin/init for testing."""
    clean = name.strip().lower()
    if not clean:
        raise ValueError("empty")
    if len(clean) > 64:
        raise ValueError("too long")
    if clean in RESERVED:
        raise ValueError(f"reserved: {clean}")
    if not VALID_NAME.match(clean):
        raise ValueError(f"invalid chars: {name}")
    return clean


class TestSessionNameValidation:
    """Session name validation rejects dangerous or reserved names."""

    @pytest.mark.parametrize("name", [
        "alice",
        "bob",
        "charlie",
        "a",            # single char
        "zz",           # two chars
        "my-agent",     # hyphen
        "agent_42",     # underscore + digits
        "a-b-c_d",      # mixed
        "x" * 64,        # max length
    ])
    def test_valid_names_pass(self, name):
        """Valid session names are accepted."""
        result = _validate(name)
        assert result == name.lower()

    @pytest.mark.parametrize("name", [
        "",             # empty
        "   ",          # whitespace only
    ])
    def test_empty_name_rejected(self, name):
        """Empty or whitespace-only names raise an error."""
        with pytest.raises(ValueError):
            _validate(name)

    @pytest.mark.parametrize("name", [
        "all",
        "dispatcher",
        "lead",
        "system",
        "ALL",          # case-insensitive
        "Dispatcher",
    ])
    def test_reserved_names_rejected(self, name):
        """Reserved names are rejected."""
        with pytest.raises(ValueError):
            _validate(name)

    @pytest.mark.parametrize("name", [
        "<dicksuck>",
        "a/b",
        "hello world",
        "../evil",
        "name;rm",
        "a|b",
        "user@host",
        "name!yes",
        "a..b",
        "-leading",     # starts with hyphen
        "trailing-",    # ends with hyphen
        "_leading",     # starts with underscore
        "trailing_",    # ends with underscore

    ])
    def test_invalid_chars_rejected(self, name):
        """Names with dangerous characters are rejected."""
        with pytest.raises(ValueError):
            _validate(name)

    def test_too_long_name_rejected(self):
        """Names over 64 chars are rejected."""
        with pytest.raises(ValueError):
            _validate("a" * 65)
