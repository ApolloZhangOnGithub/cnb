"""Tests for notification concerns: TimeAnnouncer, BugSLAChecker."""

import subprocess
from datetime import datetime
from unittest.mock import MagicMock, patch

from lib.concerns.config import DispatcherConfig
from lib.concerns.notifications import (
    BugSLAChecker,
    InboxNudger,
    ManagerCloseoutEscalator,
    ProductionLineIntake,
    QueuedMessageFlusher,
    TimeAnnouncer,
)

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
# InboxNudger
# ===========================================================================


class TestInboxNudger:
    @patch("lib.concerns.notifications.tmux_send", return_value=True)
    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=True)
    @patch("lib.concerns.notifications.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.notifications.db")
    def test_nudges_when_unread(self, mock_db, mock_devs, mock_running, mock_ok, mock_send, tmp_path):
        cfg = make_cfg(tmp_path)
        mock_db.return_value.scalar.return_value = 3
        nudger = InboxNudger(cfg)

        nudger.nudge_if_unread("alice")
        assert mock_send.call_count == 1
        sent_text = mock_send.call_args[0][1]
        assert "inbox" in sent_text

    @patch("lib.concerns.notifications.tmux_send", return_value=True)
    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=True)
    @patch("lib.concerns.notifications.db")
    def test_no_nudge_when_zero_unread(self, mock_db, mock_running, mock_ok, mock_send, tmp_path):
        cfg = make_cfg(tmp_path)
        mock_db.return_value.scalar.return_value = 0
        nudger = InboxNudger(cfg)

        nudger.nudge_if_unread("alice")
        assert mock_send.call_count == 0

    @patch("lib.concerns.notifications.tmux_send", return_value=True)
    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=False)
    @patch("lib.concerns.notifications.db")
    def test_no_nudge_when_offline(self, mock_db, mock_running, mock_ok, mock_send, tmp_path):
        cfg = make_cfg(tmp_path)
        mock_db.return_value.scalar.return_value = 5
        nudger = InboxNudger(cfg)

        nudger.nudge_if_unread("alice")
        assert mock_send.call_count == 0

    @patch("lib.concerns.notifications.tmux_send", return_value=True)
    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=True)
    @patch("lib.concerns.notifications.db")
    def test_db_error_silently_skipped(self, mock_db, mock_running, mock_ok, mock_send, tmp_path):
        cfg = make_cfg(tmp_path)
        mock_db.return_value.scalar.side_effect = Exception("db locked")
        nudger = InboxNudger(cfg)

        nudger.nudge_if_unread("alice")
        assert mock_send.call_count == 0

    def test_no_nudge_when_board_db_missing(self, tmp_path):
        cfg = make_cfg(tmp_path)
        cfg.board_db = tmp_path / "nonexistent.db"
        nudger = InboxNudger(cfg)

        with patch("lib.concerns.notifications.tmux_send") as mock_send:
            nudger.nudge_if_unread("alice")
            assert mock_send.call_count == 0

    @patch("lib.concerns.notifications.tmux_send", return_value=True)
    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=True)
    @patch("lib.concerns.notifications.get_dev_sessions", return_value=["alice", "bob"])
    @patch("lib.concerns.notifications.db")
    def test_tick_iterates_all_sessions(self, mock_db, mock_devs, mock_running, mock_ok, mock_send, tmp_path):
        cfg = make_cfg(tmp_path, ["alice", "bob"])
        mock_db.return_value.scalar.return_value = 1
        nudger = InboxNudger(cfg)

        nudger.tick(1000)
        assert mock_send.call_count == 2


# ===========================================================================
# ManagerCloseoutEscalator
# ===========================================================================


class TestManagerCloseoutEscalator:
    def _mock_counts(self, *, unread: int, own_open: int, other_open: int):
        fake_db = MagicMock()

        def scalar(sql, params):
            if "FROM inbox" in sql:
                return unread
            if "session=?" in sql:
                return own_open
            if "session!=?" in sql:
                return other_open
            raise AssertionError(f"unexpected query: {sql}")

        fake_db.scalar.side_effect = scalar
        return fake_db

    @patch("lib.concerns.notifications.board_send")
    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=True)
    @patch("lib.concerns.notifications.get_dev_sessions", return_value=["project-manager", "alice"])
    @patch("lib.concerns.notifications.db")
    def test_escalates_stuck_manager_closeout(self, mock_db, mock_devs, mock_running, mock_ok, mock_send, tmp_path):
        cfg = make_cfg(tmp_path, ["project-manager", "alice"])
        mock_db.return_value = self._mock_counts(unread=3, own_open=1, other_open=0)
        escalator = ManagerCloseoutEscalator(cfg)

        escalator.tick(1000)
        escalator.tick(1015)
        mock_send.assert_not_called()

        escalator.tick(1030)
        mock_send.assert_called_once()
        assert mock_send.call_args[0][1] == "project-manager"
        assert "closeout escalation" in mock_send.call_args[0][2]

    @patch("lib.concerns.notifications.board_send")
    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=True)
    @patch("lib.concerns.notifications.get_dev_sessions", return_value=["project-manager"])
    @patch("lib.concerns.notifications.db")
    def test_no_escalation_while_worker_tasks_remain(
        self, mock_db, mock_devs, mock_running, mock_ok, mock_send, tmp_path
    ):
        cfg = make_cfg(tmp_path, ["project-manager"])
        mock_db.return_value = self._mock_counts(unread=3, own_open=1, other_open=1)
        escalator = ManagerCloseoutEscalator(cfg)

        escalator.tick(1000)
        escalator.tick(1015)
        escalator.tick(1030)

        mock_send.assert_not_called()

    @patch("lib.concerns.notifications.board_send")
    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=True)
    @patch("lib.concerns.notifications.get_dev_sessions", return_value=["project-manager"])
    @patch("lib.concerns.notifications.db")
    def test_escalation_cooldown_prevents_spam(self, mock_db, mock_devs, mock_running, mock_ok, mock_send, tmp_path):
        cfg = make_cfg(tmp_path, ["project-manager"])
        mock_db.return_value = self._mock_counts(unread=3, own_open=1, other_open=0)
        escalator = ManagerCloseoutEscalator(cfg)

        escalator.tick(1000)
        escalator.tick(1015)
        escalator.tick(1030)
        escalator.tick(1045)
        escalator.tick(1060)

        assert mock_send.call_count == 1


# ===========================================================================
# ProductionLineIntake
# ===========================================================================


class TestProductionLineIntake:
    def test_selects_project_manager(self, tmp_path):
        cfg = make_cfg(tmp_path, ["alice", "project-manager"])
        intake = ProductionLineIntake(cfg)

        assert intake._manager() == "project-manager"

    def test_prioritizes_p0_bug_before_unlabeled(self, tmp_path):
        cfg = make_cfg(tmp_path, ["project-manager"])
        intake = ProductionLineIntake(cfg)

        issues = [
            {"number": 200, "title": "later", "labels": [], "url": "u"},
            {
                "number": 100,
                "title": "urgent",
                "labels": [{"name": "priority:p0"}, {"name": "bug"}],
                "url": "u",
            },
        ]

        with patch.object(intake, "_fetch_open_issues", return_value=issues):
            ranked = intake._ranked_candidates(set())

        assert [issue["number"] for issue in ranked] == [100, 200]

    @patch("lib.concerns.notifications.log")
    @patch("lib.concerns.notifications.db")
    def test_adds_tasks_until_stack_limit(self, mock_db, mock_log, tmp_path):
        cfg = make_cfg(tmp_path, ["project-manager"])
        fake_db = MagicMock()
        fake_conn = MagicMock()
        fake_db.conn.return_value.__enter__.return_value = fake_conn
        fake_db.conn.return_value.__exit__.return_value = False
        fake_db.scalar.side_effect = [0, 0, 0, 1, 2]
        fake_db.query.return_value = []
        fake_db.execute.side_effect = [11, 12, 13]
        mock_db.return_value = fake_db
        intake = ProductionLineIntake(cfg)
        issues = [
            {"number": 1, "title": "one", "labels": [{"name": "priority:p1"}], "url": "https://e/1"},
            {"number": 2, "title": "two", "labels": [{"name": "priority:p1"}], "url": "https://e/2"},
            {"number": 3, "title": "three", "labels": [{"name": "priority:p1"}], "url": "https://e/3"},
        ]

        with patch.object(intake, "_fetch_open_issues", return_value=issues):
            intake.tick(1000)

        assert fake_db.execute.call_count == 3
        assert fake_db.post_message.call_count == 3
        first_insert = fake_db.execute.call_args_list[0][0][1]
        assert first_insert[0] == "project-manager"
        assert "#1" in first_insert[1]
        assert first_insert[2] == "active"
        assert first_insert[3] == 80
        assert mock_log.call_count == 3

    @patch("lib.concerns.notifications.db")
    def test_skips_when_manager_stack_is_full(self, mock_db, tmp_path):
        cfg = make_cfg(tmp_path, ["project-manager"])
        fake_db = MagicMock()
        fake_db.scalar.return_value = ProductionLineIntake.STACK_LIMIT
        mock_db.return_value = fake_db
        intake = ProductionLineIntake(cfg)

        with patch.object(intake, "_fetch_open_issues") as fetch:
            intake.tick(1000)

        fetch.assert_not_called()


# ===========================================================================
# QueuedMessageFlusher
# ===========================================================================


class TestQueuedMessageFlusher:
    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=True)
    @patch("lib.concerns.notifications.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.notifications.tmux")
    @patch("subprocess.run")
    def test_flushes_queued_message(self, mock_subproc, mock_tmux, mock_devs, mock_running, mock_ok, tmp_path):
        cfg = make_cfg(tmp_path)
        flusher = QueuedMessageFlusher(cfg)

        mock_tmux.side_effect = lambda *args: {
            ("capture-pane", "-t", f"{PREFIX}-alice", "-p"): "output\nqueued message\n❯",
        }.get(args, "")

        flusher.tick(1000)
        mock_subproc.assert_called_once()
        assert mock_subproc.call_args[0][0] == ["tmux", "send-keys", "-t", f"{PREFIX}-alice", "Enter"]

    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=True)
    @patch("lib.concerns.notifications.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.notifications.tmux")
    @patch("subprocess.run")
    def test_no_flush_without_queued_message(self, mock_subproc, mock_tmux, mock_devs, mock_running, mock_ok, tmp_path):
        cfg = make_cfg(tmp_path)
        flusher = QueuedMessageFlusher(cfg)

        mock_tmux.side_effect = lambda *args: {
            ("capture-pane", "-t", f"{PREFIX}-alice", "-p"): "normal output\n❯",
        }.get(args, "")

        flusher.tick(1000)
        mock_subproc.assert_not_called()

    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=True)
    @patch("lib.concerns.notifications.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.notifications.tmux")
    @patch("subprocess.run")
    def test_no_flush_without_empty_prompt(self, mock_subproc, mock_tmux, mock_devs, mock_running, mock_ok, tmp_path):
        """queued message present but no empty prompt marker -> no flush."""
        cfg = make_cfg(tmp_path)
        flusher = QueuedMessageFlusher(cfg)

        mock_tmux.side_effect = lambda *args: {
            ("capture-pane", "-t", f"{PREFIX}-alice", "-p"): "queued message\n❯ typing something",
        }.get(args, "")

        flusher.tick(1000)
        mock_subproc.assert_not_called()

    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=True)
    @patch("lib.concerns.notifications.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.notifications.tmux")
    @patch("subprocess.run")
    def test_cooldown_prevents_repeat_flush(self, mock_subproc, mock_tmux, mock_devs, mock_running, mock_ok, tmp_path):
        cfg = make_cfg(tmp_path)
        flusher = QueuedMessageFlusher(cfg)

        mock_tmux.side_effect = lambda *args: {
            ("capture-pane", "-t", f"{PREFIX}-alice", "-p"): "queued message\n❯",
        }.get(args, "")

        flusher.tick(1000)
        assert mock_subproc.call_count == 1

        mock_subproc.reset_mock()
        flusher.tick(1000 + QueuedMessageFlusher.COOLDOWN - 1)
        assert mock_subproc.call_count == 0

    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=True)
    @patch("lib.concerns.notifications.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.notifications.tmux")
    @patch("subprocess.run")
    def test_flush_allowed_after_cooldown(self, mock_subproc, mock_tmux, mock_devs, mock_running, mock_ok, tmp_path):
        cfg = make_cfg(tmp_path)
        flusher = QueuedMessageFlusher(cfg)

        mock_tmux.side_effect = lambda *args: {
            ("capture-pane", "-t", f"{PREFIX}-alice", "-p"): "queued message\n❯",
        }.get(args, "")

        flusher.tick(1000)
        mock_subproc.reset_mock()

        flusher.tick(1000 + QueuedMessageFlusher.COOLDOWN)
        assert mock_subproc.call_count == 1

    @patch("lib.concerns.notifications.tmux_ok", return_value=True)
    @patch("lib.concerns.notifications.is_claude_running", return_value=False)
    @patch("lib.concerns.notifications.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.notifications.tmux")
    @patch("subprocess.run")
    def test_no_flush_when_offline(self, mock_subproc, mock_tmux, mock_devs, mock_running, mock_ok, tmp_path):
        cfg = make_cfg(tmp_path)
        flusher = QueuedMessageFlusher(cfg)
        flusher.tick(1000)
        mock_subproc.assert_not_called()


# ===========================================================================
# TimeAnnouncer
# ===========================================================================


class TestTimeAnnouncer:
    def _make_fake_dt(self, hour, minute=0):
        """Build a mock datetime class whose .now() returns a fixed time."""
        fake_now = datetime(2026, 5, 8, hour, minute, 0)

        class FakeDT(datetime):
            @classmethod
            def now(cls, tz=None):
                return fake_now

        return FakeDT

    @patch("lib.concerns.notifications.board_send")
    def test_daily_announcement_at_9am(self, mock_board, tmp_path):
        cfg = make_dispatcher_config(tmp_path)
        announcer = TimeAnnouncer(cfg)
        announcer.last_hour = 8

        with patch("datetime.datetime", self._make_fake_dt(9, 0)):
            announcer.tick(1000)

        mock_board.assert_called_once()
        msg = mock_board.call_args[0][2]
        assert "Clock" in msg

    @patch("lib.concerns.notifications.board_send")
    def test_hourly_announcement(self, mock_board, tmp_path):
        cfg = make_dispatcher_config(tmp_path)
        announcer = TimeAnnouncer(cfg)
        announcer.last_hour = 13

        with patch("datetime.datetime", self._make_fake_dt(14, 0)):
            announcer.tick(1000)

        mock_board.assert_called_once()
        msg = mock_board.call_args[0][2]
        assert "14:00" in msg

    @patch("lib.concerns.notifications.board_send")
    def test_no_announcement_mid_hour(self, mock_board, tmp_path):
        cfg = make_dispatcher_config(tmp_path)
        announcer = TimeAnnouncer(cfg)
        announcer.last_hour = 14

        with patch("datetime.datetime", self._make_fake_dt(14, 30)):
            announcer.tick(1000)

        mock_board.assert_not_called()

    @patch("lib.concerns.notifications.board_send")
    def test_no_repeat_same_hour(self, mock_board, tmp_path):
        cfg = make_dispatcher_config(tmp_path)
        announcer = TimeAnnouncer(cfg)
        announcer.last_hour = 10

        with patch("datetime.datetime", self._make_fake_dt(10, 0)):
            announcer.tick(1000)

        mock_board.assert_not_called()

    @patch("lib.concerns.notifications.board_send")
    @patch("lib.concerns.notifications.db")
    def test_dedup_skips_when_already_sent(self, mock_db, mock_board, tmp_path):
        """If a clock message for this hour already exists in DB, skip sending."""
        cfg = make_dispatcher_config(tmp_path)
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
        cfg = make_dispatcher_config(tmp_path)
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
        cfg = make_dispatcher_config(tmp_path)
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
        cfg = make_dispatcher_config(tmp_path)
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
        cfg = make_dispatcher_config(tmp_path)
        poker = MagicMock()
        checker = BugSLAChecker(cfg, poker)

        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="No overdue bugs", stderr="")

        checker.tick(1000)
        poker.poke.assert_not_called()

    @patch("subprocess.run")
    def test_no_poke_on_empty_output(self, mock_run, tmp_path):
        cfg = make_dispatcher_config(tmp_path)
        poker = MagicMock()
        checker = BugSLAChecker(cfg, poker)

        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        checker.tick(1000)
        poker.poke.assert_not_called()

    @patch("subprocess.run")
    def test_silent_on_subprocess_error(self, mock_run, tmp_path):
        cfg = make_dispatcher_config(tmp_path)
        poker = MagicMock()
        checker = BugSLAChecker(cfg, poker)

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="board", timeout=10)

        checker.tick(1000)
        poker.poke.assert_not_called()

    @patch("subprocess.run")
    def test_uses_correct_board_command(self, mock_run, tmp_path):
        cfg = make_dispatcher_config(tmp_path)
        poker = MagicMock()
        checker = BugSLAChecker(cfg, poker)

        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="No overdue", stderr="")

        checker.tick(1000)
        called_args = mock_run.call_args[0][0]
        assert called_args == [cfg.board_sh, "bug", "overdue"]
