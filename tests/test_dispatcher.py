"""Tests for dispatcher pid lock and TimeAnnouncer startup initialization.

Covers:
  - _acquire_pidlock() prevents duplicate dispatcher instances
  - _acquire_pidlock() reclaims stale pidfiles from dead processes
  - TimeAnnouncer initializes last_hour to current hour (prevents message storm)
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.concerns.config import DispatcherConfig
from lib.concerns.notifications import TimeAnnouncer


@pytest.fixture
def cfg(tmp_path):
    claudes_dir = tmp_path / ".claudes"
    claudes_dir.mkdir()
    (claudes_dir / "sessions").mkdir()
    (claudes_dir / "logs").mkdir()
    (claudes_dir / "okr").mkdir()
    return DispatcherConfig(
        prefix="cc-test",
        project_root=tmp_path,
        claudes_dir=claudes_dir,
        sessions_dir=claudes_dir / "sessions",
        board_db=claudes_dir / "board.db",
        suspended_file=claudes_dir / "suspended",
        board_sh="/usr/bin/true",
        coral_sess="cc-test-dispatcher",
        dispatcher_session="dispatcher",
        log_dir=claudes_dir / "logs",
        okr_dir=claudes_dir / "okr",
        dev_sessions=["alice", "bob"],
    )


def _acquire_pidlock(claudes_dir: Path) -> Path:
    """Local copy of dispatcher's _acquire_pidlock for isolated testing."""
    pidfile = claudes_dir / "dispatcher.pid"
    if pidfile.exists():
        try:
            old_pid = int(pidfile.read_text().strip())
            os.kill(old_pid, 0)
            print(f"FATAL: dispatcher already running (pid {old_pid})", file=sys.stderr)
            raise SystemExit(1)
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    pidfile.write_text(str(os.getpid()))
    return pidfile


class TestPidLock:
    def test_creates_pidfile(self, cfg):
        pidfile = _acquire_pidlock(cfg.claudes_dir)
        assert pidfile.exists()
        assert pidfile.read_text().strip() == str(os.getpid())

    def test_blocks_when_pid_alive(self, cfg):
        pidfile = cfg.claudes_dir / "dispatcher.pid"
        pidfile.write_text(str(os.getpid()))
        with pytest.raises(SystemExit):
            _acquire_pidlock(cfg.claudes_dir)

    def test_reclaims_stale_pidfile(self, cfg):
        pidfile = cfg.claudes_dir / "dispatcher.pid"
        pidfile.write_text("99999999")
        result = _acquire_pidlock(cfg.claudes_dir)
        assert result.read_text().strip() == str(os.getpid())

    def test_reclaims_corrupted_pidfile(self, cfg):
        pidfile = cfg.claudes_dir / "dispatcher.pid"
        pidfile.write_text("not-a-number")
        result = _acquire_pidlock(cfg.claudes_dir)
        assert result.read_text().strip() == str(os.getpid())


class TestTimeAnnouncerInit:
    def test_last_hour_initialized_to_current(self, cfg):
        announcer = TimeAnnouncer(cfg)
        assert announcer.last_hour == datetime.now().hour

    def test_no_announcement_on_first_tick_at_minute_zero(self, cfg):
        """last_hour == current hour means tick() returns early even at :00."""
        announcer = TimeAnnouncer(cfg)
        fake_now = datetime(2026, 5, 8, announcer.last_hour, 0, 0)
        with patch("lib.concerns.notifications.board_send") as mock_send:
            with patch("datetime.datetime") as mock_dt:
                mock_dt.now.return_value = fake_now
                announcer.tick(0)
            mock_send.assert_not_called()
