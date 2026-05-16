---
number: 34
title: "Pending actions queue: batch user-required operations with verification"
state: OPEN
labels: ["phase:1", "infra", "priority:p1"]
assignees: []
created: 2026-05-07
updated: 2026-05-10
---

# #34 Pending actions queue: batch user-required operations with verification

**State:** OPEN
**Labels:** phase:1, infra, priority:p1

---

## Problem

Some operations require user action (OAuth login, manual approval, npm publish). Currently when we hit an auth wall, we just fail and stop. The user doesn't want to be interrupted for each one.

## Design

Collect pending user actions into a queue, batch-present them when the user is available, then verify and close the loop.

### Flow

```
Hit auth wall → log to pending queue → continue other work
                      ↓
User available → show all pending → user acts → verify each → retry original op
```

### DB schema

```sql
CREATE TABLE pending_actions (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,            -- 'auth', 'approve', 'confirm'
    command TEXT NOT NULL,          -- command for user to run, e.g. 'lark-cli auth login --domain mail'
    reason TEXT NOT NULL,           -- why, e.g. '发庆祝邮件需要飞书邮箱授权'
    verify_command TEXT,            -- verification command
    retry_command TEXT,             -- original command to retry after verification
    status TEXT DEFAULT 'pending', -- pending → reminded → done → retried | failed
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
```

### Board commands

```bash
board --as <name> pending add --type auth --command "..." --reason "..." --verify "..."
board --as <name> pending list          # show all pending
board --as <name> pending verify        # run all verify_commands, update status
board --as <name> pending retry         # retry original ops for verified items
```

### Slash command

`/cnb-pending` — show all pending user actions in a nice list with `!` prefix commands the user can copy-paste.

### Integration points

- Any 同学 hitting a permission error should add to queue instead of failing
- Lead agent checks pending queue when user returns
- Dispatcher can periodically remind about unresolved pending items

## First use case

Lark mail auth needed for sending celebration email (Issue #33 notification system will also need this).

## Ownership

Owner implements, tests, and maintains this module permanently.
