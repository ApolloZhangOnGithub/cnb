#!/usr/bin/env python3
"""Shared utilities for claudes-code Python modules."""

import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, TypeVar

# ---------------------------------------------------------------------------
# Error types — inspired by Claude Code's errors.ts hierarchy
# ---------------------------------------------------------------------------


class ClaudesError(Exception):
    """Base error for claudes-code. All domain errors inherit from this."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.name = type(self).__name__


class AbortError(ClaudesError):
    """Raised when an operation is cancelled (timeout, signal, user interrupt)."""


def to_error(e: object) -> Exception:
    """Normalize any thrown value into an Exception. Use at catch-site boundaries."""
    return e if isinstance(e, Exception) else Exception(str(e))


def error_message(e: object) -> str:
    """Extract a human-readable message from any error-like value."""
    return str(e) if isinstance(e, Exception) else str(e)


def find_claudes_dir() -> Path:
    """Walk up from cwd to find the .claudes/ directory."""
    d = Path.cwd()
    while d != d.parent:
        if (d / ".claudes").is_dir():
            return d / ".claudes"
        d = d.parent
    raise FileNotFoundError(".claudes/ not found")


def _parse_toml(path: Path) -> dict:
    """Parse a simple TOML config file (handles our flat key=value format)."""
    import tomllib

    return tomllib.loads(path.read_text())


@dataclass
class ClaudesEnv:
    claudes_dir: Path
    project_root: Path
    install_home: Path
    board_db: Path
    sessions_dir: Path
    cv_dir: Path
    log_dir: Path
    prefix: str
    sessions: list[str]
    suspended_file: Path
    attendance_log: Path

    @classmethod
    def load(cls) -> "ClaudesEnv":
        cd = find_claudes_dir()
        pr = cd.parent
        config: dict = {}

        toml_file = cd / "config.toml"
        if toml_file.exists():
            config = _parse_toml(toml_file)
        else:
            print("ERROR: config.toml not found in .claudes/. Run: claudes-code init <session-names>", flush=True)
            raise SystemExit(1)

        log_dir = cd / "logs"
        install_home_raw = config.get("claudes_home", str(cd.parent))
        install_home = Path(install_home_raw) if install_home_raw else cd.parent
        return cls(
            claudes_dir=cd,
            project_root=pr,
            install_home=install_home,
            board_db=cd / "board.db",
            sessions_dir=cd / "sessions",
            cv_dir=cd / "cv",
            log_dir=log_dir,
            prefix=config.get("prefix", "cc"),
            sessions=config.get("sessions", []),
            suspended_file=cd / "suspended.list",
            attendance_log=log_dir / "attendance.log",
        )


PRIVILEGED_ROLES: frozenset[str] = frozenset({"lead", "dispatcher"})

TERMINAL_TASK_STATUSES: frozenset[str] = frozenset({"done"})
TERMINAL_BUG_STATUSES: frozenset[str] = frozenset({"FIXED"})


def is_privileged(name: str) -> bool:
    """Return True if *name* is a privileged role (lead/dispatcher)."""
    return name in PRIVILEGED_ROLES


def is_terminal_task_status(status: str) -> bool:
    """Return True if *status* is a terminal state (task will not transition further).

    Guards against operating on dead tasks: inject, assign, nudge, etc.
    """
    return status in TERMINAL_TASK_STATUSES


def is_terminal_bug_status(status: str) -> bool:
    """Return True if *status* is a terminal state (bug is resolved).

    Guards against reassigning or updating resolved bugs.
    """
    return status in TERMINAL_BUG_STATUSES


def sanitize_session_name(name: str) -> str:
    """Strip path traversal and other filesystem-dangerous characters.

    Session names become .md filenames in sessions/. This prevents names like
    '../evil' from escaping the sessions directory.
    """
    return name.replace("/", "_").replace("\\", "_").replace("\0", "")


def ts() -> str:
    """Current timestamp as 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_suspended(name: str, sf: Path) -> bool:
    """Check if a session name appears in the suspended.list file."""
    return sf.exists() and name in sf.read_text().splitlines()


def date_to_epoch(s: str) -> int:
    """Parse a date string into a Unix epoch, trying multiple formats."""
    for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return int(datetime.strptime(s, f).timestamp())
        except ValueError:
            pass
    return 0


# ---------------------------------------------------------------------------
# Database wrappers (shared abstract base)
# ---------------------------------------------------------------------------


class BaseDB(ABC):
    """Abstract base for SQLite wrappers for the claudes-code board database.

    Guarantees: new connection per call, WAL mode, parameterized queries.
    Both DB (lightweight) and BoardDB (full-featured) implement this interface.
    """

    @abstractmethod
    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        """Execute a SELECT and return all rows."""

    @abstractmethod
    def scalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        """Execute a SELECT and return the first column of the first row, or None."""

    @abstractmethod
    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        """Execute a non-SELECT statement and return lastrowid."""


class DB(BaseDB):
    """Lightweight SQLite wrapper — new connection per call, no pooling.

    Used by: bin/dispatcher, lib/monitor.py, standalone scripts.
    For board_* modules, use BoardDB (which adds .md file sync helpers).
    """

    def __init__(self, path: Path) -> None:
        self.db_path = path

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

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.conn() as c:
            return c.execute(sql, params).fetchall()

    def scalar(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        rows = self.query(sql, params)
        return rows[0][0] if rows else None

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self.conn() as c:
            return c.execute(sql, params).lastrowid


# ---------------------------------------------------------------------------
# Signal — inspired by Claude Code's createSignal() (utils/signal.ts)
# ---------------------------------------------------------------------------

T = TypeVar("T")


class Signal(Generic[T]):
    """Lightweight pub/sub for pure event notification (no stored state).

    Distinct from a state store — there is no snapshot, no get_state().
    Subscribers are notified that "something happened", optionally with args.

    Usage:
        changed = Signal[str]()
        unsub = changed.subscribe(lambda src: print(f"changed: {src}"))
        changed.emit("file_watcher")   # prints "changed: file_watcher"
        unsub()                          # unsubscribed
    """

    def __init__(self) -> None:
        self._listeners: set[Callable[[T], None]] = set()

    def subscribe(self, listener: Callable[[T], None]) -> Callable[[], None]:
        """Register a listener. Returns an unsubscribe function."""
        self._listeners.add(listener)

        def unsubscribe() -> None:
            self._listeners.discard(listener)

        return unsubscribe

    def emit(self, arg: T) -> None:
        """Notify all listeners with *arg*."""
        for listener in list(self._listeners):
            try:
                listener(arg)
            except Exception:
                pass  # keep firing remaining listeners

    def clear(self) -> None:
        """Remove all listeners. Use in dispose/reset paths."""
        self._listeners.clear()


# ---------------------------------------------------------------------------
# CLI flag parser
# ---------------------------------------------------------------------------


def parse_flags(
    args: list[str],
    value_flags: dict[str, list[str]] | None = None,
    bool_flags: dict[str, list[str]] | None = None,
) -> tuple[dict[str, str | bool], list[str]]:
    """Parse CLI flags from an argument list, returning (flags_dict, positional_args).

    value_flags: canonical_name -> [aliases...] — flags that consume the next arg as value.
    bool_flags:  canonical_name -> [aliases...] — flags that set True when present.
    """
    value_flags = value_flags or {}
    bool_flags = bool_flags or {}

    val_lookup: dict[str, str] = {}
    for canonical, aliases in value_flags.items():
        for a in aliases:
            val_lookup[a] = canonical

    bool_lookup: dict[str, str] = {}
    for canonical, aliases in bool_flags.items():
        for a in aliases:
            bool_lookup[a] = canonical

    result: dict[str, str | bool] = {}
    positional: list[str] = []
    i = 0
    while i < len(args):
        if args[i] in val_lookup:
            canonical = val_lookup[args[i]]
            if i + 1 >= len(args):
                return result, positional
            result[canonical] = args[i + 1]
            i += 2
        elif args[i] in bool_lookup:
            result[bool_lookup[args[i]]] = True
            i += 1
        else:
            positional.append(args[i])
            i += 1
    return result, positional
