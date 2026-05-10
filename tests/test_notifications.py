"""Tests for notification concerns: TimeAnnouncer, BugSLAChecker."""

import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from lib.concerns.config import DispatcherConfig
from lib.concerns.notifications import BugSLAChecker, TimeAnnouncer

PREFIX = "cc-test"


def make_cfg(tmp_path: Path, sessions: list[str] | None = None) -> DispatcherConfig:
    sessions = sessions or ["alice"]
    cd = tmp_path / ".claudes"
    cd.mkdir(exist_ok=True)
    db_path = cd / "board.db"
    db_path.touch()
    return DispatcherConfig(
        prefix=PREFIX,
        project_root=tmp_path,
        claudes_dir=cd,
        sessions_dir=cd / "sessions",
        board_db=db_path,
        suspended_file=cd / "suspended",
        board_sh="./board",
        coral_sess=f"{PREFIX}-lead",
        dispatcher_session=f"{PREFIX}-dispatcher",
        log_dir=cd / "logs",
        okr_dir=cd / "okr",
        dev_sessions=sessions,
    )

# ===========================================================================
# TimeAnnouncer
# ===========================================================================


class TestTimeAnnouncer:
    def _make_fake_dt(self, hour, minute=0):
        """Build a mock datetime class whose .now() returns a fixed time."""
        fake_now = datetime(2026, 5, 8, hour, minute, 0)

        class FakeDT(datetime):
            @classmethod
            def now(cls):
                return fake_now

        return FakeDT

    @patch("lib.concerns.notifications.board_send")
    def test_daily_announcement_at_9am(self, mock_board, tmp_path):
        cfg = make_cfg(tmp_path)
        announcer = TimeAnnouncer(cfg)
        announcer.last_hour = 8

        with patch("datetime.datetime", self._make_fake_dt(9, 0)):
            announcer.tick(1000)

        mock_board.assert_called_once()
        msg = mock_board.call_args[0][2]
        assert "Clock" in msg

    @patch("lib.concerns.notifications.board_send")
    def test_hourly_announcement(self, mock_board, tmp_path):
        cfg = make_cfg(tmp_path)
        announcer = TimeAnnouncer(cfg)
        announcer.last_hour = 13

        with patch("datetime.datetime", self._make_fake_dt(14, 0)):
            announcer.tick(1000)

        mock_board.assert_called_once()
        msg = mock_board.call_args[0][2]
        assert "14:00" in msg

    @patch("lib.concerns.notifications.board_send")
    def test_no_announcement_mid_hour(self, mock_board, tmp_path):
        cfg = make_cfg(tmp_path)
        announcer = TimeAnnouncer(cfg)
        announcer.last_hour = 14

        with patch("datetime.datetime", self._make_fake_dt(14, 30)):
            announcer.tick(1000)

        mock_board.assert_not_called()

    @patch("lib.concerns.notifications.board_send")
    def test_no_repeat_same_hour(self, mock_board, tmp_path):
        cfg = make_cfg(tmp_path)
        announcer = TimeAnnouncer(cfg)
        announcer.last_hour = 10

        with patch("datetime.datetime", self._make_fake_dt(10, 0)):
            announcer.tick(1000)

        mock_board.assert_not_called()

    @patch("lib.concerns.notifications.board_send")
    @patch("lib.concerns.notifications.db")
    def test_dedup_skips_when_already_sent(self, mock_db, mock_board, tmp_path):
        """If a clock message for this hour already exists in DB, skip sending."""
        cfg = make_cfg(tmp_path)
        announcer = TimeAnnouncer(cfg)
        announcer.last_hour = 13
        mock_db.return_value.scalar.return_value = 1

        with patch("datetime.datetime", self._make_fake_dt(14, 0)):
            announcer.tick(1000)

        mock_board.assert_not_called()
        assert announcer.last_hour == 14

    @patch("lib.concerns.notifications.board_send")
    @patch("lib.concerns.notifications.db")
    def test_dedup_allows_when_not_sent(self, mock_db, mock_board, tmp_path):
        """If no clock message exists for this hour, send normally."""
        cfg = make_cfg(tmp_path)
        announcer = TimeAnnouncer(cfg)
        announcer.last_hour = 13
        mock_db.return_value.scalar.return_value = 0

        with patch("datetime.datetime", self._make_fake_dt(14, 0)):
            announcer.tick(1000)

        mock_board.assert_called_once()

    @patch("lib.concerns.notifications.board_send")
    @patch("lib.concerns.notifications.db")
    def test_dedup_db_error_allows_send(self, mock_db, mock_board, tmp_path):
        """If DB check fails, allow the send (fail-open for availability)."""
        cfg = make_cfg(tmp_path)
        announcer = TimeAnnouncer(cfg)
        announcer.last_hour = 13
        mock_db.return_value.scalar.side_effect = Exception("db locked")

        with patch("datetime.datetime", self._make_fake_dt(14, 0)):
            announcer.tick(1000)

        mock_board.assert_called_once()


# ===========================================================================
# BugSLAChecker
# ===========================================================================


class TestBugSLAChecker:
    @patch("subprocess.run")
    def test_pokes_coral_on_overdue(self, mock_run, tmp_path):
        cfg = make_cfg(tmp_path)
        poker = MagicMock()
        checker = BugSLAChecker(cfg, poker)

        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="P1 #42: fix crash (overdue 2h)", stderr=""
        )

        checker.tick(1000)
        poker.poke.assert_called_once()
        assert "SLA" in poker.poke.call_args[0][0]

    @patch("subprocess.run")
    def test_no_poke_when_no_overdue(self, mock_run, tmp_path):
        cfg = make_cfg(tmp_path)
        poker = MagicMock()
        checker = BugSLAChecker(cfg, poker)

        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="No overdue bugs", stderr="")

        checker.tick(1000)
        poker.poke.assert_not_called()

    @patch("subprocess.run")
    def test_no_poke_on_empty_output(self, mock_run, tmp_path):
        cfg = make_cfg(tmp_path)
        poker = MagicMock()
        checker = BugSLAChecker(cfg, poker)

        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        checker.tick(1000)
        poker.poke.assert_not_called()

    @patch("subprocess.run")
    def test_silent_on_subprocess_error(self, mock_run, tmp_path):
        cfg = make_cfg(tmp_path)
        poker = MagicMock()
        checker = BugSLAChecker(cfg, poker)

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="board", timeout=10)

        checker.tick(1000)
        poker.poke.assert_not_called()

    @patch("subprocess.run")
    def test_uses_correct_board_command(self, mock_run, tmp_path):
        cfg = make_cfg(tmp_path)
        poker = MagicMock()
        checker = BugSLAChecker(cfg, poker)

        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="No overdue", stderr="")

        checker.tick(1000)
        called_args = mock_run.call_args[0][0]
        assert called_args == [cfg.board_sh, "bug", "overdue"]
