"""board_pulse — lightweight heartbeat + unread count for PostToolBatch hook."""

from lib.board_db import BoardDB, ts


def cmd_pulse(db: BoardDB, identity: str) -> None:
    name = identity.lower()
    db.ensure_session(name)
    now = ts()
    db.execute("UPDATE sessions SET last_heartbeat=? WHERE name=?", (now, name))
    count = db.scalar("SELECT COUNT(*) FROM inbox WHERE session=? AND read=0", (name,))
    if count:
        print(f"{count} 条未读")
