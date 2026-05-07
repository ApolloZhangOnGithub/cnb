---
number: 35
title: "Add per-session token usage tracking"
state: CLOSED
labels: [enhancement]
assignees: []
created: 2026-05-07
updated: 2026-05-07
closed: 2026-05-07
---

# #35 Add per-session token usage tracking

**State:** CLOSED
**Labels:** enhancement

---

## Problem

`cnb ps` / `cnb board overview` shows session status, messages, and tasks, but has no visibility into token consumption per session. When running a 6-person team, there's no way to know how much each instance is costing.

## Proposed Solution

Track token usage per session. Two approaches (not mutually exclusive):

### 1. Parse Claude Code session stats
Claude Code tracks its own token usage internally. cnb could:
- Periodically scrape the tmux pane for token counters (shown in the status bar)
- Or read Claude Code's session log files if they exist

### 2. Add `cnb usage` command
```
cnb usage              # all sessions
cnb usage yiming       # single session
```

Output:
```
=== Token Usage ===
  yiming     ↓ 45.2k  ↑ 12.8k  $0.23
  rubo       ↓ 38.1k  ↑ 15.2k  $0.21
  lidong     ↓ 52.0k  ↑ 18.4k  $0.28
  ...
  Total      ↓ 210k   ↑ 82k    $1.15
```

### 3. Schema addition
```sql
CREATE TABLE IF NOT EXISTS token_usage(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name),
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime'))
);
```

## Context

Found this gap while running a 6-person team on TokenDance_BBS project. User asked about token usage and there was no way to answer.

Also: the README doesn't mention this limitation or any cost monitoring guidance — worth adding a note.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
