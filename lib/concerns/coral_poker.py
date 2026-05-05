"""CoralPoker — periodic heartbeat to dispatcher session."""

import re
import time

from .base import Concern
from .config import DispatcherConfig
from .helpers import db, is_claude_running, log, pane_md5, tmux, tmux_ok, tmux_send


class CoralPoker(Concern):
    interval = 120

    def __init__(self, cfg: DispatcherConfig) -> None:
        super().__init__()
        self.cfg = cfg
        self.last_poke: int = int(time.time())

    def poke(self, msg: str) -> bool:
        if not tmux_ok("has-session", "-t", self.cfg.coral_sess) or not is_claude_running(self.cfg.coral_sess):
            return False

        content = tmux("capture-pane", "-t", self.cfg.coral_sess, "-p") or ""
        prompts = [l for l in content.splitlines() if l.startswith("❯")]
        if prompts and re.match(r"^❯ .{3,}", prompts[-1]):
            log("Coral: skip (typing)")
            return False

        h1 = pane_md5(self.cfg.coral_sess)
        time.sleep(1)
        if h1 != pane_md5(self.cfg.coral_sess):
            log("Coral: skip (busy)")
            return False

        log("Coral: poking")
        tmux_send(self.cfg.coral_sess, msg)
        self.last_poke = int(time.time())
        return True

    def tick(self, now: int) -> None:
        unread = 0
        if self.cfg.board_db.exists():
            try:
                unread = (
                    db(self.cfg).scalar(
                        "SELECT COUNT(*) FROM inbox WHERE session=? AND read=0",
                        (self.cfg.dispatcher_session,),
                    )
                    or 0
                )
            except Exception:
                pass

        if unread > 0:
            self.poke(f"[Dispatcher] 你有 {unread} 条未读消息")
        elif (now - self.last_poke) >= self.interval:
            self.poke(f"[Dispatcher] heartbeat {time.strftime('%H:%M:%S')}")
