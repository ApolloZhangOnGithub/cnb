"""DigestScheduler — sends daily/weekly digests at scheduled times."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from lib.digest import generate_daily_digest, generate_weekly_report
from lib.notification_config import load as load_config
from lib.notification_delivery import deliver_external

from .base import Concern
from .config import DispatcherConfig
from .helpers import board_send, db, get_dev_sessions, log, warn


class DigestScheduler(Concern):
    interval = 30

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self._last_daily_date: str = ""
        self._last_weekly_date: str = ""
        self._reserved_digests: set[tuple[str, str, str]] = set()

    def _config_path(self) -> Path:
        return self.cfg.claudes_dir / "notifications.toml"

    @staticmethod
    def _ref_id(date_str: str) -> str:
        return f"digest-{date_str}"

    @classmethod
    def _reservation_key(cls, notif_type: str, recipient: str, date_str: str) -> str:
        return f"notification:{notif_type}:{recipient}:{cls._ref_id(date_str)}"

    def _already_sent(self, notif_type: str, recipient: str, date_str: str) -> bool:
        try:
            count = db(self.cfg).scalar(
                "SELECT COUNT(*) FROM notification_log WHERE notif_type=? AND recipient=? AND ref_id=?",
                (notif_type, recipient, self._ref_id(date_str)),
            )
            return bool(count)
        except Exception:
            return (notif_type, recipient, date_str) in self._reserved_digests

    def _reserve_digest(self, notif_type: str, recipient: str, date_str: str) -> bool:
        """Atomically reserve one recipient/day before delivery.

        notification_log remains the human-visible audit trail, but it is not
        unique in older databases. meta.key is primary-keyed, so INSERT OR
        IGNORE gives the dispatcher a durable per-recipient cooldown even if
        the daemon restarts or two dispatcher loops overlap.
        """
        token = (notif_type, recipient, date_str)
        if token in self._reserved_digests:
            return False
        if self._already_sent(notif_type, recipient, date_str):
            self._reserved_digests.add(token)
            return False
        try:
            with db(self.cfg).conn() as c:
                c.execute(
                    "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
                    (
                        self._reservation_key(notif_type, recipient, date_str),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )
                reserved = int(c.execute("SELECT changes()").fetchone()[0]) == 1
        except Exception as e:
            warn(f"digest reserve: {e}")
            reserved = True
        if reserved:
            self._reserved_digests.add(token)
        return reserved

    def _record_digest(self, notif_type: str, recipient: str, date_str: str, channel: str) -> None:
        try:
            with db(self.cfg).conn() as c:
                c.execute(
                    "INSERT INTO notification_log(notif_type, recipient, ref_type, ref_id, channel) VALUES(?,?,?,?,?)",
                    (notif_type, recipient, "digest", self._ref_id(date_str), channel),
                )
        except Exception as e:
            warn(f"digest record: {e}")

    def tick(self, now: int) -> None:
        d = datetime.now()
        if d.hour != 9 or d.minute > 5:
            return

        date_str = d.strftime("%Y-%m-%d")

        if date_str != self._last_daily_date:
            self._send_daily(date_str)
            self._last_daily_date = date_str

        if d.weekday() == 0 and date_str != self._last_weekly_date:
            self._send_weekly(date_str)
            self._last_weekly_date = date_str

    def _send_daily(self, date_str: str) -> None:
        config = load_config(self._config_path())
        members = get_dev_sessions(self.cfg)
        subscribers = config.subscribers_for("daily-digest", members)

        if not subscribers:
            return

        try:
            board = db(self.cfg)
            digest_text = generate_daily_digest(board)
        except Exception as e:
            warn(f"digest generation failed: {e}")
            return

        sent = 0
        for member in subscribers:
            if not self._reserve_digest("daily-digest", member, date_str):
                log(f"Daily digest already sent to {member} for {date_str}, skipping")
                continue
            channel = config.channel_for(member)
            if channel == "board-inbox":
                board_send(self.cfg, member, digest_text)
                self._record_digest("daily-digest", member, date_str, channel)
                sent += 1
                continue

            result = deliver_external(config, member, channel, "daily-digest", digest_text, f"digest-{date_str}")
            if result.delivered:
                self._record_digest("daily-digest", member, date_str, channel)
                sent += 1
            log(f"[digest] {member}: {result.detail}")

        log(f"Daily digest sent to {sent}/{len(subscribers)} subscribers")

    def _send_weekly(self, date_str: str) -> None:
        config = load_config(self._config_path())
        members = get_dev_sessions(self.cfg)
        subscribers = config.subscribers_for("weekly-report", members)

        if not subscribers:
            return

        try:
            board = db(self.cfg)
            report_text = generate_weekly_report(board)
        except Exception as e:
            warn(f"weekly report generation failed: {e}")
            return

        sent = 0
        for member in subscribers:
            if not self._reserve_digest("weekly-report", member, date_str):
                log(f"Weekly report already sent to {member} for {date_str}, skipping")
                continue
            channel = config.channel_for(member)
            if channel == "board-inbox":
                board_send(self.cfg, member, report_text)
                self._record_digest("weekly-report", member, date_str, channel)
                sent += 1
                continue

            result = deliver_external(config, member, channel, "weekly-report", report_text, f"digest-{date_str}")
            if result.delivered:
                self._record_digest("weekly-report", member, date_str, channel)
                sent += 1
            log(f"[digest] {member}: {result.detail}")

        log(f"Weekly report sent to {sent}/{len(subscribers)} subscribers")
