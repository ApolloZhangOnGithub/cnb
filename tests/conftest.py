"""Shared fixtures for claudes-code tests.

Provides temporary project directories with initialized .claudes/ structure,
database connections, and helper utilities used across all test modules.
"""

import pytest
import sqlite3
import tempfile
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Schema path (relative to this file's location)
# ---------------------------------------------------------------------------
SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"

# Default test sessions
DEFAULT_SESSIONS = ["alice", "bob", "charlie"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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

    # Create config.sh
    sessions_str = " ".join(DEFAULT_SESSIONS)
    (claudes / "config.sh").write_text(
        f'CLAUDES_HOME="{tmp_path}"\n'
        f"SESSIONS=({sessions_str})\n"
        f'PREFIX="cc-test"\n'
    )

    # Initialize database from schema
    db_path = claudes / "board.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_PATH.read_text())
    # Insert test sessions
    for name in DEFAULT_SESSIONS:
        conn.execute("INSERT INTO sessions(name) VALUES (?)", (name,))
    conn.commit()
    conn.close()

    # Create session .md files
    for name in DEFAULT_SESSIONS:
        (claudes / "sessions" / f"{name}.md").write_text(
            f"# {name}\n\n## Current task\n(none)\n\n## @inbox\n"
        )

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
def db(db_path):
    """Return a DB helper instance for the temp project.

    This fixture attempts to import the Python rewrite's DB class.
    If not yet available, it provides a lightweight shim that offers
    the same interface so tests can run before the rewrite lands.
    """
    try:
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))
        from lib.common import DB

        return DB(db_path)
    except ImportError:
        # Provide a lightweight shim for testing before lib/common.py exists
        return _DBShim(db_path)


class _DBShim:
    """Minimal DB wrapper matching the expected lib.common.DB interface.

    Used as a fallback when the Python rewrite has not yet landed.
    """

    def __init__(self, path):
        self.path = Path(path)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")

    def execute(self, query, params=()):
        cur = self._conn.execute(query, params)
        self._conn.commit()
        return cur

    def query(self, query, params=()):
        cur = self._conn.execute(query, params)
        return cur.fetchall()

    def scalar(self, query, params=()):
        cur = self._conn.execute(query, params)
        row = cur.fetchone()
        if row is None:
            return None
        return row[0]

    def insert_returning_id(self, query, params=()):
        cur = self._conn.execute(query, params)
        self._conn.commit()
        return cur.lastrowid

    def close(self):
        self._conn.close()


@pytest.fixture
def sessions_dir(tmp_project):
    """Return the sessions directory path."""
    return tmp_project / ".claudes" / "sessions"


@pytest.fixture
def files_dir(tmp_project):
    """Return the shared files directory path."""
    return tmp_project / ".claudes" / "files"


def ts():
    """Return a timestamp in the same format as the board."""
    return time.strftime("%Y-%m-%d %H:%M")
