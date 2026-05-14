"""Configuration object passed to all concerns as dependency injection."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DispatcherConfig:
    """Holds all paths and settings that concerns need."""

    prefix: str
    project_root: Path
    claudes_dir: Path
    sessions_dir: Path
    board_db: Path
    suspended_file: Path
    board_sh: str
    coral_sess: str
    dispatcher_session: str
    log_dir: Path
    okr_dir: Path
    dev_sessions: list[str] = field(default_factory=list)
