#!/usr/bin/env python3
"""Shared utilities for cnb Python modules."""

import sqlite3
from abc import ABC, abstractmethod
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, TypeVar


def find_claudes_dir() -> Path:
    """Find project config directory. Prefers .cnb/, falls back to .claudes/."""
    import os

    _DIRS = (".cnb", ".claudes")

    def _pick(root: Path) -> Path | None:
        for name in _DIRS:
            p = root / name
            if p.is_dir():
                if name == ".claudes":
                    print(f"提示: 检测到旧目录 {p}，建议重命名为 .cnb/（mv .claudes .cnb）", flush=True)
                return p
        return None

    env_root = os.environ.get("CNB_PROJECT")
    if env_root:
        found = _pick(Path(env_root))
        if found:
            return found

    d = Path.cwd()
    while d != d.parent:
        found = _pick(d)
        if found:
            return found
        d = d.parent
    raise FileNotFoundError(".cnb/ (or .claudes/) not found (set CNB_PROJECT or run from project dir)")


def _parse_toml(path: Path) -> dict:
    """Parse a simple TOML config file (handles our flat key=value format)."""
    import tomllib

    return tomllib.loads(path.read_text())


def _write_config_toml(path: Path, data: dict) -> None:
    """Serialize *data* back to our config.toml format."""
    lines: list[str] = []
    for key, val in data.items():
        if key == "session":
            continue
        if isinstance(val, list):
            items = ", ".join(f'"{v}"' for v in val)
            lines.append(f"{key} = [{items}]")
        else:
            lines.append(f'{key} = "{val}"')
    lines.append("")
    for name, section in data.get("session", {}).items():
        lines.append(f"[session.{name}]")
        for k, v in section.items():
            sv = str(v)
            if "\n" in sv:
                lines.append(f'{k} = """{sv}"""')
            else:
                lines.append(f'{k} = "{sv}"')
        lines.append("")
    path.write_text("\n".join(lines) + "\n")


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
            print("ERROR: config.toml not found. Run: cnb init <session-names>", flush=True)
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


def validate_identity(db: "BaseDB", identity: str) -> None:
    name = identity.lower()
    if name in PRIVILEGED_ROLES:
        return
    exists = db.scalar("SELECT COUNT(*) FROM sessions WHERE name=?", (name,))
    if not exists:
        print(f"ERROR: '{name}' is not a registered session")
        raise SystemExit(1)


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


def escape_like(s: str) -> str:
    """Escape SQL LIKE wildcards (%, _) for safe use with ESCAPE '\\'."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


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
    """Abstract base for SQLite wrappers for the cnb board database.

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

    Used by: bin/dispatcher and standalone scripts.
    For board_* modules, use BoardDB.
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
            return c.execute(sql, params).lastrowid or 0


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
        arg = args[i]
        # Support --key=value syntax
        if "=" in arg:
            key, val = arg.split("=", 1)
            if key in val_lookup:
                result[val_lookup[key]] = val
                i += 1
                continue
            if key in bool_lookup:
                print(f"ERROR: {arg} 不接受参数值（布尔型）")
                raise SystemExit(1)
            positional.append(arg)
            i += 1
        elif arg in val_lookup:
            canonical = val_lookup[arg]
            if i + 1 >= len(args):
                print(f"ERROR: {arg} 需要一个参数值")
                raise SystemExit(1)
            result[canonical] = args[i + 1]
            i += 2
        elif arg in bool_lookup:
            result[bool_lookup[arg]] = True
            i += 1
        else:
            positional.append(arg)
            i += 1
    return result, positional
