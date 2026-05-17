"""Tests for lib/concerns/digest_scheduler — scheduled digest delivery."""

import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from lib.concerns.config import DispatcherConfig
from lib.concerns.digest_scheduler import DigestScheduler


def _make_cfg(tmp_path: Path) -> DispatcherConfig:
    db_path = tmp_path / "board.db"
    claudes = tmp_path / ".claudes"
    claudes.mkdir(exist_ok=True)
    return DispatcherConfig(
        prefix="cnb",
        project_root=tmp_path,
        claudes_dir=claudes,
        sessions_dir=claudes / "sessions",
        board_db=db_path,
        suspended_file=claudes / "suspended.json",
        board_sh="./board",
        coral_sess="cnb-lead",
        dispatcher_session="cnb-dispatcher",
        log_dir=tmp_path / "logs",
        okr_dir=claudes / "okr",
    )


def _init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions(name TEXT PRIMARY KEY, status TEXT DEFAULT '',
            persona TEXT DEFAULT '', updated_at TEXT DEFAULT '', last_heartbeat TEXT DEFAULT NULL);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL DEFAULT '', sender TEXT NOT NULL, recipient TEXT NOT NULL,
            body TEXT NOT NULL, attachment TEXT DEFAULT NULL);
        CREATE TABLE IF NOT EXISTS bugs(id TEXT PRIMARY KEY, severity TEXT NOT NULL, sla TEXT NOT NULL,
            reporter TEXT NOT NULL, assignee TEXT DEFAULT '', status TEXT DEFAULT 'OPEN',
            description TEXT NOT NULL,
            reported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
            fixed_at TEXT DEFAULT NULL, evidence TEXT DEFAULT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,
            session TEXT NOT NULL, description TEXT NOT NULL, status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 0, created_at TEXT NOT NULL DEFAULT '', done_at TEXT DEFAULT NULL);
        CREATE TABLE IF NOT EXISTS kudos(id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL, target TEXT NOT NULL, reason TEXT NOT NULL,
            evidence TEXT DEFAULT NULL, ts TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS notification_log(id INTEGER PRIMARY KEY AUTOINCREMENT,
            notif_type TEXT NOT NULL, recipient TEXT NOT NULL,
            ref_type TEXT NOT NULL, ref_id TEXT NOT NULL, channel TEXT NOT NULL,
            sent_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')));
        CREATE TABLE IF NOT EXISTS inbox(id INTEGER PRIMARY KEY, session TEXT, message_id INTEGER,
            delivered_at TEXT DEFAULT '', read INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO sessions(name) VALUES ('alice');
        INSERT INTO sessions(name) VALUES ('bob');
        """
    )
    conn.commit()
    return conn


class TestDigestSchedulerInit:
    def test_interval(self, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)
        assert sched.interval == 30

    def test_initial_state(self, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)
        assert sched._last_daily_date == ""
        assert sched._last_weekly_date == ""


class TestTickTiming:
    @patch("lib.concerns.digest_scheduler.datetime")
    def test_skips_outside_9am_window(self, mock_dt, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)
        mock_dt.now.return_value = datetime(2026, 5, 8, 10, 0)
        sched.tick(100)
        assert sched._last_daily_date == ""

    @patch("lib.concerns.digest_scheduler.datetime")
    def test_skips_after_minute_5(self, mock_dt, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)
        mock_dt.now.return_value = datetime(2026, 5, 8, 9, 10)
        sched.tick(100)
        assert sched._last_daily_date == ""

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    @patch("lib.concerns.digest_scheduler.datetime")
    def test_sends_at_9am(self, mock_dt, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)
        mock_dt.now.return_value = datetime(2026, 5, 8, 9, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        sched.tick(100)
        assert sched._last_daily_date == "2026-05-08"
        assert mock_send.call_count >= 1


class TestDailyDigest:
    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice", "bob"])
    @patch("lib.concerns.digest_scheduler.board_send")
    def test_sends_to_subscribed_members(self, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)
        sched._send_daily("2026-05-08")
        assert mock_send.call_count == 2

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice", "bob"])
    @patch("lib.concerns.digest_scheduler.board_send")
    def test_deduplicates(self, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)
        sched._send_daily("2026-05-08")
        first_count = mock_send.call_count
        sched._send_daily("2026-05-08")
        assert mock_send.call_count == first_count

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    def test_skips_if_daily_digest_already_logged_today(self, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        conn = _init_db(cfg.board_db)
        date_str = datetime.now().strftime("%Y-%m-%d")
        conn.execute(
            """
            INSERT INTO notification_log(notif_type, recipient, ref_type, ref_id, channel, sent_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("daily-digest", "alice", "digest", "manual-digest", "board-inbox", f"{date_str} 08:15:00"),
        )
        conn.commit()

        sched = DigestScheduler(cfg)
        sched._send_daily(date_str)

        mock_send.assert_not_called()
        conn.close()

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=[])
    @patch("lib.concerns.digest_scheduler.board_send")
    def test_no_subscribers_no_send(self, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)
        sched._send_daily("2026-05-08")
        mock_send.assert_not_called()

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    def test_records_in_notification_log(self, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        conn = _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)
        sched._send_daily("2026-05-08")
        count = conn.execute("SELECT COUNT(*) FROM notification_log WHERE notif_type='daily-digest'").fetchone()[0]
        assert count == 1
        conn.close()

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    def test_digest_content_sent(self, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)
        sched._send_daily("2026-05-08")
        msg = mock_send.call_args[0][2]
        assert "[Daily Digest]" in msg

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    @patch("lib.notification_delivery.subprocess.run")
    def test_records_human_lark_im_subscriber(self, mock_run, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        conn = _init_db(cfg.board_db)
        toml = cfg.claudes_dir / "notifications.toml"
        toml.write_text(
            '[human]\nname = "Test User"\nemail = "test@example.com"\nlark_chat_id = "oc_123"\ndaily-digest = true\n'
        )
        mock_run.return_value = Mock(returncode=0, stdout="{}", stderr="")
        sched = DigestScheduler(cfg)

        sched._send_daily("2026-05-08")

        mock_send.assert_called_once()
        recipients = conn.execute(
            "SELECT recipient, channel FROM notification_log WHERE notif_type='daily-digest' ORDER BY recipient"
        ).fetchall()
        assert [(r[0], r[1]) for r in recipients] == [("alice", "board-inbox"), ("human", "lark-im")]
        conn.close()

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    def test_skips_unconfigured_human_lark_im_record(self, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        conn = _init_db(cfg.board_db)
        toml = cfg.claudes_dir / "notifications.toml"
        toml.write_text('[human]\nname = "Test User"\nemail = "test@example.com"\ndaily-digest = true\n')
        sched = DigestScheduler(cfg)

        sched._send_daily("2026-05-08")

        recipients = conn.execute(
            "SELECT recipient, channel FROM notification_log WHERE notif_type='daily-digest' ORDER BY recipient"
        ).fetchall()
        assert [(r[0], r[1]) for r in recipients] == [("alice", "board-inbox")]
        conn.close()


class TestWeeklyReport:
    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    def test_sends_weekly_on_monday(self, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        toml = cfg.claudes_dir / "notifications.toml"
        toml.write_text("[defaults]\nweekly-report = true\n")
        sched = DigestScheduler(cfg)
        sched._send_weekly("2026-05-11")
        assert mock_send.call_count >= 1
        msg = mock_send.call_args[0][2]
        assert "Weekly Report" in msg

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    def test_weekly_deduplicates(self, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        toml = cfg.claudes_dir / "notifications.toml"
        toml.write_text("[defaults]\nweekly-report = true\n")
        sched = DigestScheduler(cfg)
        sched._send_weekly("2026-05-11")
        first_count = mock_send.call_count
        sched._send_weekly("2026-05-11")
        assert mock_send.call_count == first_count

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    def test_weekly_skips_unsubscribed(self, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)
        sched._send_weekly("2026-05-11")
        mock_send.assert_not_called()

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    @patch("lib.concerns.digest_scheduler.generate_weekly_report")
    def test_weekly_swallows_report_generation_exception(self, mock_generate, mock_send, mock_sessions, tmp_path):
        """If `generate_weekly_report` raises, the scheduler must not crash the dispatcher."""
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        toml = cfg.claudes_dir / "notifications.toml"
        toml.write_text("[defaults]\nweekly-report = true\n")
        mock_generate.side_effect = RuntimeError("DB locked")

        sched = DigestScheduler(cfg)
        # Must not raise.
        sched._send_weekly("2026-05-11")
        mock_send.assert_not_called()

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    @patch("lib.notification_delivery.subprocess.run")
    def test_weekly_records_human_lark_im_subscriber(self, mock_run, mock_send, mock_sessions, tmp_path):
        """Weekly external-channel delivery success path mirrors daily."""
        cfg = _make_cfg(tmp_path)
        conn = _init_db(cfg.board_db)
        toml = cfg.claudes_dir / "notifications.toml"
        toml.write_text(
            "[defaults]\nweekly-report = true\n"
            '[human]\nname = "Test User"\nemail = "test@example.com"\n'
            'lark_chat_id = "oc_123"\nweekly-report = true\n'
        )
        mock_run.return_value = Mock(returncode=0, stdout="{}", stderr="")
        sched = DigestScheduler(cfg)

        sched._send_weekly("2026-05-11")

        recipients = conn.execute(
            "SELECT recipient, channel FROM notification_log WHERE notif_type='weekly-report' ORDER BY recipient"
        ).fetchall()
        assert ("human", "lark-im") in [(r[0], r[1]) for r in recipients]
        conn.close()


class TestExceptionPaths:
    """Cover the broad except: branches that protect the dispatcher loop."""

    def test_already_sent_today_returns_false_on_db_error(self, tmp_path, monkeypatch):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)

        # Force the DB call to raise — the helper must catch and return False so the
        # caller proceeds to send rather than silently no-op-ing.
        def boom(*a, **kw):
            raise sqlite3.OperationalError("simulated DB failure")

        monkeypatch.setattr("lib.concerns.digest_scheduler.db", lambda _: Mock(scalar=boom))
        assert sched._already_sent_today("daily-digest", "2026-05-08") is False

    def test_record_digest_swallows_insert_exception(self, tmp_path, monkeypatch):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        sched = DigestScheduler(cfg)

        def broken_db(_):
            class _BrokenConn:
                def conn(self):
                    raise sqlite3.OperationalError("simulated")

            return _BrokenConn()

        monkeypatch.setattr("lib.concerns.digest_scheduler.db", broken_db)
        # Must not raise — exception should be logged via `warn(...)` and swallowed.
        sched._record_digest("daily-digest", "alice", "2026-05-08", "board-inbox")

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    @patch("lib.concerns.digest_scheduler.generate_daily_digest")
    def test_daily_swallows_digest_generation_exception(self, mock_generate, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        mock_generate.side_effect = RuntimeError("DB locked")

        sched = DigestScheduler(cfg)
        # Must not raise; no send because we bail before delivery.
        sched._send_daily("2026-05-08")
        mock_send.assert_not_called()


class TestTickWeekly:
    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    @patch("lib.concerns.digest_scheduler.datetime")
    def test_fires_weekly_on_monday(self, mock_dt, mock_send, mock_sessions, tmp_path):
        """tick at 9am on a Monday should trigger both daily and weekly send paths."""
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        toml = cfg.claudes_dir / "notifications.toml"
        toml.write_text("[defaults]\nweekly-report = true\ndaily-digest = true\n")
        # 2026-05-11 is a Monday.
        mock_dt.now.return_value = datetime(2026, 5, 11, 9, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        sched = DigestScheduler(cfg)
        sched.tick(100)

        assert sched._last_daily_date == "2026-05-11"
        assert sched._last_weekly_date == "2026-05-11"

    @patch("lib.concerns.digest_scheduler.get_dev_sessions", return_value=["alice"])
    @patch("lib.concerns.digest_scheduler.board_send")
    @patch("lib.concerns.digest_scheduler.datetime")
    def test_skips_weekly_on_non_monday(self, mock_dt, mock_send, mock_sessions, tmp_path):
        cfg = _make_cfg(tmp_path)
        _init_db(cfg.board_db)
        toml = cfg.claudes_dir / "notifications.toml"
        toml.write_text("[defaults]\nweekly-report = true\ndaily-digest = true\n")
        # 2026-05-12 is a Tuesday — daily yes, weekly no.
        mock_dt.now.return_value = datetime(2026, 5, 12, 9, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        sched = DigestScheduler(cfg)
        sched.tick(100)

        assert sched._last_daily_date == "2026-05-12"
        assert sched._last_weekly_date == ""
