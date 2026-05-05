"""Shared utilities for claudes-code Python scripts."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


def find_claudes_dir() -> Path:
    """Walk up from cwd to find .claudes/ directory."""
    d = Path.cwd()
    while d != d.parent:
        if (d / ".claudes").is_dir():
            return d / ".claudes"
        d = d.parent
    raise FileNotFoundError(
        "ERROR: .claudes/ not found. Run: claudes-code init <session-names>"
    )


@dataclass
class ClaudesEnv:
    """Resolved environment for a claudes-code project."""

    claudes_dir: Path
    project_root: Path
    board_db: Path
    sessions_dir: Path
    cv_dir: Path
    prefix: str
    sessions: List[str]
    suspended_file: Path
    log_dir: Path
    attendance_log: Path
    claudes_home: str = ""

    @classmethod
    def load(cls) -> "ClaudesEnv":
        cd = find_claudes_dir()
        pr = cd.parent
        config: dict = {}
        cf = cd / "config.sh"
        if cf.exists():
            for line in cf.read_text().splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k == "SESSIONS":
                        # Parse bash array: (a b c)
                        v = v.strip("()")
                        config[k] = v.split()
                    else:
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
            log_dir=cd / "logs",
            attendance_log=cd / "attendance.log",
            claudes_home=config.get("CLAUDES_HOME", ""),
        )


def is_suspended(name: str, suspended_file: Path) -> bool:
    """Check if a session name is in the suspended list."""
    if not suspended_file.exists():
        return False
    return name in suspended_file.read_text().splitlines()
