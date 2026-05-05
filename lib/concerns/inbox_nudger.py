"""InboxNudger — detect unread inboxes, nudge sessions."""

from .base import Concern
from .config import DispatcherConfig
from .helpers import db, get_dev_sessions, is_claude_running, log, tmux_ok, tmux_send


class InboxNudger(Concern):
    interval = 5

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg

    def nudge_if_unread(self, name: str) -> None:
        if not self.cfg.board_db.exists():
            return
        try:
            unread = db(self.cfg).scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,)) or 0
        except Exception:
            return
        if unread <= 0:
            return

        sess = f"{self.cfg.prefix}-{name}"
        if not tmux_ok("has-session", "-t", sess) or not is_claude_running(sess):
            return

        log(f"INBOX: {name} has {unread} unread -> nudging")
        tmux_send(sess, f"./board --as {name} inbox")

    def tick(self, now: int) -> None:
        for name in get_dev_sessions(self.cfg):
            self.nudge_if_unread(name)
