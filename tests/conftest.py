"""Shared fixtures for claudes-code tests.

Provides temporary project directories with initialized .claudes/ structure,
database connections, and helper utilities used across all test modules.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from lib.common import ts  # noqa: F401 — re-export for tests

# ---------------------------------------------------------------------------
# Schema path (relative to this file's location)
# ---------------------------------------------------------------------------
SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"

# Default test sessions
DEFAULT_SESSIONS = ["alice", "bob", "charlie"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_module_state():
    """Clear module-level caches and signals to prevent cross-test leaks."""
    yield
    try:
        from lib.concerns.helpers import _db_cache

        _db_cache.clear()
    except ImportError:
        pass
    try:
        from lib.board_db import inbox_delivered

        inbox_delivered.clear()
    except ImportError:
        pass


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project with .claudes/ directory structure.

    Initializes the database from schema.sql, inserts test sessions,
    and creates the supporting file structure.

    Returns the root project path (parent of .claudes/).
    """
    claudes = tmp_path / ".claudes"
    claudes.mkdir()
    (claudes / "sessions").mkdir()
    (claudes / "files").mkdir()
    (claudes / "logs").mkdir()
    (claudes / "okr").mkdir()
    (claudes / "cv").mkdir()

    # Create config.toml (primary config format)
    sessions_toml = ", ".join(f'"{s}"' for s in DEFAULT_SESSIONS)
    (claudes / "config.toml").write_text(
        f'claudes_home = "{tmp_path}"\nsessions = [{sessions_toml}]\nprefix = "cc-test"\n'
    )

    # Initialize database from schema
    db_path = claudes / "board.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_PATH.read_text())
    # Insert test sessions
    for name in DEFAULT_SESSIONS:
        conn.execute("INSERT INTO sessions(name) VALUES (?)", (name,))
    # Mark schema as fully up-to-date so auto-migrate won't re-apply
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', '7')")
    conn.commit()
    conn.close()

    # Create session .md files
    for name in DEFAULT_SESSIONS:
        (claudes / "sessions" / f"{name}.md").write_text(f"# {name}\n\n## Current task\n(none)\n\n## @inbox\n")

    return tmp_path


@pytest.fixture
def db_path(tmp_project):
    """Return the path to the SQLite database file."""
    return tmp_project / ".claudes" / "board.db"


@pytest.fixture
def db_conn(db_path):
    """Return an open sqlite3 connection to the test database.

    The connection is closed automatically after the test.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    yield conn
    conn.close()


@pytest.fixture
def db(tmp_project):
    """Return a BoardDB instance backed by a full ClaudesEnv (not bare path).

    This ensures db.env is populated, so commands that access the filesystem
    (attachments, .md sync) work correctly in tests.
    """
    from lib.board_db import BoardDB
    from lib.common import ClaudesEnv

    cd = tmp_project / ".claudes"
    env = ClaudesEnv(
        claudes_dir=cd,
        project_root=tmp_project,
        install_home=Path(__file__).parent.parent,
        board_db=cd / "board.db",
        sessions_dir=cd / "sessions",
        cv_dir=cd / "cv",
        log_dir=cd / "logs",
        prefix="cc-test",
        sessions=DEFAULT_SESSIONS,
        suspended_file=cd / "suspended",
        attendance_log=cd / "logs" / "attendance.log",
    )
    return BoardDB(env)


@pytest.fixture
def sessions_dir(tmp_project):
    """Return the sessions directory path."""
    return tmp_project / ".claudes" / "sessions"


@pytest.fixture
def files_dir(tmp_project):
    """Return the shared files directory path."""
    return tmp_project / ".claudes" / "files"
