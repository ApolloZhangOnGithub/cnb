---
number: 32
title: "Add persistent mail system with CC and threading"
state: CLOSED
labels: []
assignees: []
created: 2026-05-07
updated: 2026-05-07
closed: 2026-05-07
---

# #32 Add persistent mail system with CC and threading

**State:** CLOSED

---

## Problem

cnb currently has two messaging mechanisms:
- **inbox** — ephemeral, read-and-gone, no CC, no threading
- **encrypted mailbox** — async but designed for sealed private messages, not team communication

Neither supports basic team email patterns: sending to multiple recipients with CC, threading replies, persistent messages that survive session restarts.

When agents are offline (which is most of the time), there is no way to leave them structured communication that they'll see on next startup.

## Proposed design

### Mail table in board.db

```sql
CREATE TABLE mail (
    id INTEGER PRIMARY KEY,
    thread_id INTEGER,          -- NULL for new thread, references mail.id for replies
    sender TEXT NOT NULL,
    recipients TEXT NOT NULL,    -- JSON array: ["lisa-su", "musk"]
    cc TEXT DEFAULT '[]',       -- JSON array: ["sutskever"]
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    read_by TEXT DEFAULT '[]'   -- JSON array: tracks who has read it
);
```

### CLI interface

```bash
# Send
board --as alice mail send --to lisa-su,musk --cc sutskever \
  --subject "remote_exec ownership" --body "Requirements doc ready. Who takes it?"

# Read
board --as lisa-su mail list                  # all mail (unread marked)
board --as lisa-su mail list --unread         # unread only
board --as lisa-su mail read 42               # read specific mail
board --as lisa-su mail reply 42 "I'll take it"

# On startup (auto-injected)
board --as <name> mail list --unread          # agent sees mail on boot
```

### Key differences from inbox

| | inbox | mail |
|---|---|---|
| Persistence | read = gone | permanent, read_by tracks who read |
| CC | no | yes |
| Threading | no | reply chains via thread_id |
| Subject line | no | yes |
| Survives session | no | yes |
| Group send | broadcast only | explicit to + cc |

### Notification on startup

When an agent starts, auto-run `mail list --unread` and inject the summary into context. Like checking your email when you open your laptop.

### Future extension point

The mail system should expose a notifier interface so that external channels (GitHub webhook, real email via Gmail API, push notification) can be plugged in later without changing the mail table or CLI.

## Related

- #31 — agent identity and access control (mail sender verification depends on this)
- #31 comment re: agent recall (mail is useful only if agents can be brought back to read it)
