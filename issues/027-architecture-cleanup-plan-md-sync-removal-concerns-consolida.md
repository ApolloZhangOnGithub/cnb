---
number: 27
title: "Architecture cleanup plan: .md sync removal, concerns/ consolidation, cmd_ standardization"
state: CLOSED
labels: []
assignees: []
created: 2026-05-06
updated: 2026-05-07
closed: 2026-05-07
---

# #27 Architecture cleanup plan: .md sync removal, concerns/ consolidation, cmd_ standardization

**State:** CLOSED

---

## Background

Issue #26 identified structural problems. musk, sutskever, bezos conducted an architecture discussion and reached consensus on three concrete changes.

## 1. Remove .md file sync — keep SQLite as sole source of truth

**What**: Delete `sync_inbox_to_file`, `clear_inbox_file`, `sync_status_to_file`, `_replace_section`, `_atomic_write` from `board_db.py`, and all call sites.

**Call sites to remove**:
- `board_db.py:258, 267` — inside `deliver_to_inbox`
- `board_task.py:103` — task assignment notification
- `board_lock.py:75` — git lock notification
- `board_msg.py:121` — status update

**Why**: The .md files are a parallel state representation that can diverge from SQLite, especially under sync latency. Agents already use `board --as <name> inbox` for reliable state. The 120 lines of section parsing, regex matching, and atomic writes are pure overhead.

**Caveat**: `file_watcher.py` (concerns/) monitors .md file changes to trigger nudges. After removing .md sync, file_watcher needs to be rewired to watch the SQLite DB (or replaced by the existing `inbox_delivered` Signal + tmux `send-keys` nudge path, which already works).

**Net result**: ~120 lines deleted from `board_db.py`, call sites simplified, one entire class of consistency bugs eliminated.

## 2. Consolidate concerns/ from 16 to 9 modules

Current state: 886 lines across 16 modules, most are 20-40 lines — too granular to justify separate files.

**Merge plan**:

| New module | Merges | Lines |
|---|---|---|
| `idle.py` | `idle_detector.py` + `idle_killer.py` + `idle_nudger.py` | ~135 |
| `health.py` | `health_checker.py` + `resource_monitor.py` + `session_keepalive.py` | ~142 |
| `coral.py` | `coral_manager.py` + `coral_poker.py` | ~119 |
| `notifications.py` | `inbox_nudger.py` + `time_announcer.py` + `bug_sla_checker.py` | ~100 |

**Keep as-is**: `base.py`, `config.py`, `helpers.py`, `file_watcher.py`, `adaptive_throttle.py` — these are either infrastructure or large enough to stand alone.

## 3. Standardize board cmd_ function signatures

**Problem**: `cmd_*` functions have inconsistent signatures — some take `(db, identity, args)`, some `(db, identity)`, some `(db, args)`, some just `(db)`. This makes the routing in `bin/board` messier than it needs to be.

**Proposal**: Standardize to `cmd_*(db: BoardDB, identity: str, args: list[str])` for all commands. Commands that don't need identity or args simply ignore them. This lets `bin/board` route uniformly without special-casing signatures.

## 4. Fix pgrep dispatcher detection (minor)

`board_view.py` uses `_pgrep("dispatcher")` which matches any process with "dispatcher" in its name. Replace with PID file or query the sessions table.

Note: `pgrep -P <pid>` in `concerns/helpers.py` is a different usage (child process tree inspection) and is correct — don't touch it.

## Non-goal

**Do not abstract the fetch-check-print-exit pattern** in `board_*.py`. This is CLI's natural shape, not a code smell. Extracting a `require_resource()` helper adds indirection without reducing real complexity.

## Execution

- musk: .md sync removal (item 1)
- sutskever: concerns/ consolidation (item 2)
- Item 3 and 4 can be done by anyone after 1 and 2 land

Discussed in: musk → all (11:29), sutskever → all (11:32), bezos → musk (11:30)
