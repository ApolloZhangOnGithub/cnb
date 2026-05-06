"""board_db — DB connection and helpers."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from lib.common import (  # noqa: F401 — re-export ts for board_* modules
    BaseDB,
    ClaudesEnv,
    Signal,
    sanitize_session_name,
    ts,
)

# Emitted when deliver_to_inbox() delivers a message. Session name is the arg.
# Subscribers (e.g., FileWatcher) can react instantly without polling.
inbox_delivered = Signal[str]()


class BoardDB(BaseDB):
    """Unified SQLite wrapper — new connection per call, no pooling.

    Accepts either a ClaudesEnv (production) or a bare Path/str (tests, lightweight callers).
    SQLite is the single source of truth; no .md file sync.
    """

    def __init__(self, env_or_path: ClaudesEnv | Path | str):
        if isinstance(env_or_path, ClaudesEnv):
            self.env: ClaudesEnv | None = env_or_path
            self.db_path = env_or_path.board_db
            if not self.db_path.exists():
                print("ERROR: board.db not found. Run: cnb init <session-names>", flush=True)
                raise SystemExit(1)
            # Auto-apply pending schema migrations (idempotent, fast if up-to-date)
            self._auto_migrate()
        else:
            self.env = None
            self.db_path = Path(env_or_path)

    def _auto_migrate(self) -> None:
        """Apply pending schema migrations on first load (idempotent).

        Only prints output when migrations were actually applied.
        """
        try:
            from lib.migrate import run_migrations

            install_home = self.env.install_home if self.env else Path(__file__).resolve().parent.parent
            run_migrations(self.db_path, install_home)
        except SystemExit:
            raise
        except Exception as e:
            print(f"WARNING: migration check failed: {e}", flush=True)

    @contextmanager
    def conn(self) -> Generator[sqlite3.Connection, None, None]:
        """New connection per call. Commits on success, rolls back on exception."""
        c = sqlite3.connect(str(self.db_path))
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def query(
        self, sql: str, params: tuple[Any, ...] = (), *, c: sqlite3.Connection | None = None
    ) -> list[sqlite3.Row]:
        if c is not None:
            return c.execute(sql, params).fetchall()
        with self.conn() as conn:
            return conn.execute(sql, params).fetchall()

    def query_one(
        self, sql: str, params: tuple[Any, ...] = (), *, c: sqlite3.Connection | None = None
    ) -> sqlite3.Row | None:
        rows = self.query(sql, params, c=c)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: tuple[Any, ...] = (), *, c: sqlite3.Connection | None = None) -> Any:
        row = self.query_one(sql, params, c=c)
        return row[0] if row else None

    def execute(self, sql: str, params: tuple[Any, ...] = (), *, c: sqlite3.Connection | None = None) -> int:
        if c is not None:
            return c.execute(sql, params).lastrowid
        with self.conn() as conn:
            cur = conn.execute(sql, params)
            return cur.lastrowid

    def execute_changes(self, sql: str, params: tuple[Any, ...] = (), *, c: sqlite3.Connection | None = None) -> int:
        if c is not None:
            c.execute(sql, params)
            return c.execute("SELECT changes()").fetchone()[0]
        with self.conn() as conn:
            conn.execute(sql, params)
            return conn.execute("SELECT changes()").fetchone()[0]

    def ensure_session(self, name: str, *, c: sqlite3.Connection | None = None) -> None:
        n = name.lower()
        existing = self.scalar("SELECT COUNT(*) FROM sessions WHERE name=?", (n,), c=c)
        if existing == 0:
            self.execute("INSERT INTO sessions(name) VALUES (?)", (n,), c=c)

    def deliver_to_inbox(
        self, sender: str, recipient: str, msg_id: int, *, c: sqlite3.Connection | None = None
    ) -> None:
        if recipient == "all":

            def _do(conn: sqlite3.Connection) -> list[str]:
                conn.execute(
                    "INSERT INTO inbox(session, message_id) SELECT name, ? FROM sessions WHERE name != ?",
                    (msg_id, sender),
                )
                return [r[0] for r in conn.execute("SELECT name FROM sessions WHERE name != ?", (sender,)).fetchall()]

            if c is not None:
                targets = _do(c)
            else:
                with self.conn() as conn:
                    targets = _do(conn)
            for target in targets:
                inbox_delivered.emit(target)
        else:
            self.ensure_session(recipient, c=c)
            self.execute(
                "INSERT INTO inbox(session, message_id) VALUES (?, ?)",
                (recipient, msg_id),
                c=c,
            )
            inbox_delivered.emit(recipient)
