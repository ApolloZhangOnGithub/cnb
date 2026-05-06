"""board_db — DB connection, helpers, and .md file sync."""

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
    Adds .md file sync helpers on top of the BaseDB interface.
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
            applied = run_migrations(self.db_path, install_home)
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

    # --- .md file sync ---
    #
    # All writes use temp-file + atomic rename to avoid corruption on
    # crash mid-write.  Section detection is strict: ## heading must be
    # followed by space or end-of-line (not e.g. "## @收件箱-extra").

    INBOX_HEADINGS: tuple[str, ...] = ("## @inbox", "## @收件箱")
    TASK_HEADINGS: tuple[str, ...] = ("## Current task", "## 当前任务")

    @staticmethod
    def _replace_section(
        text: str,
        headings: tuple[str, ...],
        replacement: str | None,
    ) -> str | None:
        """Replace or remove the content of a named Markdown section.

        If *replacement* is None, the section is removed.  Returns the new
        text, or None if the section was not found and no append is needed.
        """
        lines = text.split("\n")
        out: list[str] = []
        in_section = False
        found = False

        for line in lines:
            stripped = line.strip()
            if any(stripped == h or stripped.startswith(h + " ") for h in headings):
                found = True
                in_section = True
                if replacement is not None:
                    out.append(line)
                    out.append(replacement)
                continue
            if in_section and (line.startswith("#") and not line.startswith("# ")):
                # sub-headings inside section are fine; only break on peer ##
                pass
            elif in_section and line.startswith("## "):
                in_section = False
                out.append("")
                out.append(line)
                continue
            if in_section:
                continue
            out.append(line)

        if not found:
            return None
        return "\n".join(out)

    def _atomic_write(self, path: Path, content: str) -> None:
        """Write *content* to *path* atomically (temp + rename)."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp.write_text(content)
            tmp.replace(path)
        except OSError:
            pass

    # ── inbox sync ──

    def sync_inbox_to_file(
        self, target: str, *, c: sqlite3.Connection | None = None
    ) -> None:
        """Sync unread inbox messages to {target}.md file.

        Accepts an optional *c* to use the caller's connection (so that
        uncommitted inbox rows are visible within a transaction).
        """
        if not self.env:
            return
        sf = self.env.sessions_dir / f"{target}.md"
        if not sf.exists():
            return
        rows = self.query(
            "SELECT '- [' || m.ts || '] **' || m.sender || '**: ' || substr(m.body, 1, 60) "
            "FROM inbox i JOIN messages m ON i.message_id=m.id "
            "WHERE i.session=? AND i.read=0 ORDER BY m.ts",
            (target,),
            c=c,
        )
        inbox_lines = "\n".join(r[0] for r in rows) if rows else ""

        try:
            text = sf.read_text()
        except OSError:
            return

        result = self._replace_section(text, self.INBOX_HEADINGS, inbox_lines or None)
        if result is not None:
            self._atomic_write(sf, result)
        elif inbox_lines:
            heading = self.INBOX_HEADINGS[1]  # canonical: Chinese heading
            self._atomic_write(sf, text.rstrip("\n") + f"\n\n{heading}\n{inbox_lines}\n")

    def clear_inbox_file(self, target: str) -> None:
        if not self.env:
            return
        sf = self.env.sessions_dir / f"{target}.md"
        if not sf.exists():
            return
        try:
            text = sf.read_text()
        except OSError:
            return
        result = self._replace_section(text, self.INBOX_HEADINGS, None)
        if result is not None:
            self._atomic_write(sf, result)

    # ── status sync ──

    def sync_status_to_file(self, target: str, status: str) -> None:
        if not self.env:
            return
        sf = self.env.sessions_dir / f"{target}.md"
        if not sf.exists():
            return
        try:
            text = sf.read_text()
        except OSError:
            return
        result = self._replace_section(text, self.TASK_HEADINGS, status)
        if result is not None:
            self._atomic_write(sf, result)

    def deliver_to_inbox(
        self, sender: str, recipient: str, msg_id: int, *, c: sqlite3.Connection | None = None
    ) -> None:
        if recipient == "all":
            sessions = self.query("SELECT name FROM sessions WHERE name != ?", (sender,), c=c)
            for (target,) in sessions:
                self.execute(
                    "INSERT INTO inbox(session, message_id) VALUES (?, ?)",
                    (target, msg_id),
                    c=c,
                )
            for (target,) in sessions:
                self.sync_inbox_to_file(target, c=c)
                inbox_delivered.emit(target)
        else:
            self.ensure_session(recipient, c=c)
            self.execute(
                "INSERT INTO inbox(session, message_id) VALUES (?, ?)",
                (recipient, msg_id),
                c=c,
            )
            self.sync_inbox_to_file(recipient, c=c)
            inbox_delivered.emit(recipient)
