#!/usr/bin/env python3
"""Shared utilities for claudes-code Python modules."""

import os
import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


def find_claudes_dir() -> Path:
    """Walk up from cwd to find the .claudes/ directory."""
    d = Path.cwd()
    while d != d.parent:
        if (d / ".claudes").is_dir():
            return d / ".claudes"
        d = d.parent
    raise FileNotFoundError(".claudes/ not found")


@dataclass
class ClaudesEnv:
    claudes_dir: Path
    project_root: Path
    board_db: Path
    sessions_dir: Path
    cv_dir: Path
    prefix: str
    sessions: List[str]
    suspended_file: Path

    @classmethod
    def load(cls) -> "ClaudesEnv":
        cd = find_claudes_dir()
        pr = cd.parent
        config: dict = {}
        cf = cd / "config.sh"
        if cf.exists():
            for line in cf.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    v = v.strip('"').strip("'")
                    k = k.strip()
                    if k == "SESSIONS":
                        v = v.strip("()").split()
                    config[k] = v
        return cls(
            claudes_dir=cd,
            project_root=pr,
            board_db=cd / "board.db",
            sessions_dir=cd / "sessions",
            cv_dir=cd / "cv",
            prefix=config.get("PREFIX", "cc"),
            sessions=config.get("SESSIONS", []),
            suspended_file=cd / "suspended.list",
        )


class DB:
    """Thin wrapper around sqlite3 for the board database."""

    def __init__(self, path: Path) -> None:
        self.path = str(path)

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def execute(self, q: str, p: tuple = ()) -> sqlite3.Cursor:
        with self._conn() as c:
            cur = c.execute(q, p)
            c.commit()
            return cur

    def query(self, q: str, p: tuple = ()) -> list:
        with self._conn() as c:
            return c.execute(q, p).fetchall()

    def scalar(self, q: str, p: tuple = ()):
        r = self.query(q, p)
        return r[0][0] if r else None


def ts() -> str:
    """Current timestamp as 'YYYY-MM-DD HH:MM'."""
    return datetime.now().strftime("%Y-%m-%d %H:%M")


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
