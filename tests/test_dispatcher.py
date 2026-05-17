"""Tests for dispatcher pid lock, TimeAnnouncer init, and code-change detection.

Covers:
  - _acquire_pidlock() prevents duplicate dispatcher instances
  - _acquire_pidlock() reclaims stale pidfiles from dead processes
  - TimeAnnouncer initializes last_hour to current hour (prevents message storm)
  - _max_mtime / _code_changed detect lib/concerns/* edits and debounce mid-save
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


# ---------------------------------------------------------------------------
# Auto-reload detection (#235): mirror dispatcher's _max_mtime / _code_changed
# locally — bin/dispatcher is a script without a .py extension, so the test
# uses copies just like the _acquire_pidlock pattern above.
# ---------------------------------------------------------------------------


def _max_mtime(paths: tuple[Path, ...]) -> float:
    latest = 0.0
    for root in paths:
        if root.is_file():
            try:
                latest = max(latest, root.stat().st_mtime)
            except OSError:
                continue
            continue
        if not root.is_dir():
            continue
        for py in root.rglob("*.py"):
            try:
                latest = max(latest, py.stat().st_mtime)
            except OSError:
                continue
    return latest


def _code_changed(paths: tuple[Path, ...], baseline_mtime: float, sleep) -> bool:
    if _max_mtime(paths) <= baseline_mtime:
        return False
    sleep(0)  # debounce delay (injected — tests do not block)
    return _max_mtime(paths) > baseline_mtime


class TestMaxMtime:
    def test_returns_zero_for_empty_dir(self, tmp_path):
        (tmp_path / "empty").mkdir()
        assert _max_mtime((tmp_path / "empty",)) == 0.0

    def test_returns_zero_for_missing_path(self, tmp_path):
        assert _max_mtime((tmp_path / "does-not-exist",)) == 0.0

    def test_picks_latest_across_files(self, tmp_path):
        a = tmp_path / "a.py"
        b = tmp_path / "b.py"
        a.write_text("# a")
        b.write_text("# b")
        os.utime(a, (1000, 1000))
        os.utime(b, (2000, 2000))
        assert _max_mtime((tmp_path,)) == 2000.0

    def test_picks_latest_across_paths(self, tmp_path):
        dir_a = tmp_path / "a"
        dir_a.mkdir()
        file_b = tmp_path / "b.py"
        (dir_a / "x.py").write_text("")
        file_b.write_text("")
        os.utime(dir_a / "x.py", (1000, 1000))
        os.utime(file_b, (3000, 3000))
        assert _max_mtime((dir_a, file_b)) == 3000.0

    def test_ignores_non_py_files(self, tmp_path):
        (tmp_path / "ignored.txt").write_text("")
        os.utime(tmp_path / "ignored.txt", (9999, 9999))
        (tmp_path / "watched.py").write_text("")
        os.utime(tmp_path / "watched.py", (1000, 1000))
        assert _max_mtime((tmp_path,)) == 1000.0

    def test_explicit_file_path_does_not_require_py_extension(self, tmp_path):
        # Explicit file paths (e.g. bin/dispatcher) bypass the .py glob.
        script = tmp_path / "dispatcher"
        script.write_text("#!/usr/bin/env python3")
        os.utime(script, (5000, 5000))
        assert _max_mtime((script,)) == 5000.0


class TestCodeChanged:
    def test_returns_false_when_nothing_changed(self, tmp_path):
        (tmp_path / "x.py").write_text("")
        baseline = _max_mtime((tmp_path,))
        sleep_calls: list[float] = []
        result = _code_changed((tmp_path,), baseline, sleep=sleep_calls.append)
        assert result is False
        assert sleep_calls == [], "no sleep when no change — short-circuit"

    def test_returns_true_when_change_persists_through_debounce(self, tmp_path):
        f = tmp_path / "x.py"
        f.write_text("")
        os.utime(f, (1000, 1000))
        baseline = _max_mtime((tmp_path,))
        os.utime(f, (2000, 2000))
        sleep_calls: list[float] = []
        result = _code_changed((tmp_path,), baseline, sleep=sleep_calls.append)
        assert result is True
        assert sleep_calls == [0], "debounce sleep fires before second check"

    def test_returns_false_when_change_reverts_during_debounce(self, tmp_path):
        """Mid-save flicker: file mtime briefly newer, then reverted."""
        f = tmp_path / "x.py"
        f.write_text("")
        os.utime(f, (1000, 1000))
        baseline = _max_mtime((tmp_path,))
        os.utime(f, (2000, 2000))

        def revert_during_sleep(_):
            os.utime(f, (1000, 1000))

        result = _code_changed((tmp_path,), baseline, sleep=revert_during_sleep)
        assert result is False
