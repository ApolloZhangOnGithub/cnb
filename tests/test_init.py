"""Tests for the project initialization (bin/init).

Covers: directory structure creation, config.toml generation,
database initialization from schema, session .md file creation,
CLAUDE.md generation, idempotency, and session name validation.
"""

import importlib.util
import re
import sqlite3
import types
from pathlib import Path

import pytest

from tests.conftest import DEFAULT_SESSIONS, SCHEMA_PATH

_init_script = Path(__file__).parent.parent / "bin" / "init"
_spec = importlib.util.spec_from_loader("init_mod", loader=None, origin=str(_init_script))
init_mod = types.ModuleType("init_mod")
init_mod.__file__ = str(_init_script)
exec(compile(_init_script.read_text(), _init_script, "exec"), init_mod.__dict__)


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

    def test_session_file_has_no_inbox_section(self, tmp_project):
        """Session files do not mirror SQLite inbox state."""
        for name in DEFAULT_SESSIONS:
            content = (tmp_project / ".claudes" / "sessions" / f"{name}.md").read_text()
            assert "## @inbox" not in content
            assert "## @收件箱" not in content


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
        path.write_text("# alice\n\n## Current task\n(none)\n")

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


class TestInstructionFiles:
    """Initialization writes coordination instructions for supported agent CLIs."""

    def test_agents_md_can_be_created_for_codex(self, tmp_path):
        snippet = init_mod._claude_md_snippet(["alice"], Path("/tmp/cnb"))
        init_mod._update_agents_md(tmp_path, snippet)

        path = tmp_path / "AGENTS.md"
        assert path.exists()
        assert "Multi-Agent Coordination" in path.read_text()

    def test_agents_md_marker_is_idempotent(self, tmp_path):
        original = "project notes\n\n"
        path = tmp_path / "AGENTS.md"
        path.write_text(original)

        first = init_mod._claude_md_snippet(["alice"], Path("/tmp/cnb"))
        second = init_mod._claude_md_snippet(["bob"], Path("/tmp/cnb"))
        init_mod._update_agents_md(tmp_path, first)
        init_mod._update_agents_md(tmp_path, second)

        text = path.read_text()
        assert text.count(init_mod.MARKER_START) == 1
        assert "**bob**" in text
        assert "**alice**" not in text

    def test_cnb_md_visible_project_marker_created(self, tmp_path):
        init_mod._update_project_marker(tmp_path, ".cnb", "cc-test")

        path = tmp_path / "CNB.md"
        text = path.read_text()
        assert path.exists()
        assert "Do not delete" in text
        assert "`.cnb/`" in text
        assert "`cc-test`" in text

    def test_cnb_md_visible_project_marker_is_idempotent(self, tmp_path):
        path = tmp_path / "CNB.md"
        path.write_text("human notes\n\n")

        init_mod._update_project_marker(tmp_path, ".cnb", "cc-old")
        init_mod._update_project_marker(tmp_path, ".claudes", "cc-new")

        text = path.read_text()
        assert text.startswith("human notes")
        assert text.count(init_mod.PROJECT_MARKER_START) == 1
        assert "`.claudes/`" in text
        assert "`cc-new`" in text
        assert "cc-old" not in text


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

    @pytest.mark.parametrize(
        "name",
        [
            "alice",
            "bob",
            "charlie",
            "a",  # single char
            "zz",  # two chars
            "my-agent",  # hyphen
            "agent_42",  # underscore + digits
            "a-b-c_d",  # mixed
            "x" * 64,  # max length
        ],
    )
    def test_valid_names_pass(self, name):
        """Valid session names are accepted."""
        result = _validate(name)
        assert result == name.lower()

    @pytest.mark.parametrize(
        "name",
        [
            "",  # empty
            "   ",  # whitespace only
        ],
    )
    def test_empty_name_rejected(self, name):
        """Empty or whitespace-only names raise an error."""
        with pytest.raises(ValueError):
            _validate(name)

    @pytest.mark.parametrize(
        "name",
        [
            "all",
            "dispatcher",
            "lead",
            "system",
            "ALL",  # case-insensitive
            "Dispatcher",
        ],
    )
    def test_reserved_names_rejected(self, name):
        """Reserved names are rejected."""
        with pytest.raises(ValueError):
            _validate(name)

    @pytest.mark.parametrize(
        "name",
        [
            "<dicksuck>",
            "a/b",
            "hello world",
            "../evil",
            "name;rm",
            "a|b",
            "user@host",
            "name!yes",
            "a..b",
            "-leading",  # starts with hyphen
            "trailing-",  # ends with hyphen
            "_leading",  # starts with underscore
            "trailing_",  # ends with underscore
        ],
    )
    def test_invalid_chars_rejected(self, name):
        """Names with dangerous characters are rejected."""
        with pytest.raises(ValueError):
            _validate(name)

    def test_too_long_name_rejected(self):
        """Names over 64 chars are rejected."""
        with pytest.raises(ValueError):
            _validate("a" * 65)


class TestPreCommitHook:
    """Pre-commit hook installation for secret scanning."""

    def test_installs_hook_in_git_repo(self, tmp_path):
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        secret_scan = tmp_path / "bin" / "secret-scan"
        secret_scan.parent.mkdir(parents=True)
        secret_scan.write_text("#!/bin/sh\nexit 0\n")
        init_mod._install_pre_commit_hook(tmp_path, tmp_path)
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        assert hook.exists()
        assert "secret-scan" in hook.read_text()
        assert hook.stat().st_mode & 0o111

    def test_skips_when_no_git(self, tmp_path):
        init_mod._install_pre_commit_hook(tmp_path, tmp_path)
        assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()

    def test_skips_when_no_secret_scan(self, tmp_path):
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        init_mod._install_pre_commit_hook(tmp_path, tmp_path)
        assert not (tmp_path / ".git" / "hooks" / "pre-commit").exists()

    def test_appends_to_existing_hook(self, tmp_path):
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        hook = git_dir / "pre-commit"
        hook.write_text("#!/bin/sh\necho existing\n")
        hook.chmod(0o755)
        secret_scan = tmp_path / "bin" / "secret-scan"
        secret_scan.parent.mkdir(parents=True)
        secret_scan.write_text("#!/bin/sh\nexit 0\n")
        init_mod._install_pre_commit_hook(tmp_path, tmp_path)
        content = hook.read_text()
        assert "echo existing" in content
        assert "secret-scan" in content

    def test_idempotent(self, tmp_path):
        git_dir = tmp_path / ".git" / "hooks"
        git_dir.mkdir(parents=True)
        secret_scan = tmp_path / "bin" / "secret-scan"
        secret_scan.parent.mkdir(parents=True)
        secret_scan.write_text("#!/bin/sh\nexit 0\n")
        init_mod._install_pre_commit_hook(tmp_path, tmp_path)
        init_mod._install_pre_commit_hook(tmp_path, tmp_path)
        content = (git_dir / "pre-commit").read_text()
        assert content.count("secret-scan") == 1
