---
number: 26
title: "Architecture debt: fragile foundations under cross-machine coordination"
state: OPEN
labels: []
assignees: []
created: 2026-05-06
updated: 2026-05-07
---

# #26 Architecture debt: fragile foundations under cross-machine coordination

**State:** OPEN

---

## Summary

cnb grew from a local tmux helper into a cross-machine coordination framework, but several core mechanisms haven't evolved to match. This issue tracks the structural problems that compound under multi-machine use.

## Problems

### 1. SQLite as cross-machine message broker

SQLite WAL mode is explicitly [unsupported over network filesystems](https://www.sqlite.org/wal.html). If cross-machine sync relies on shared/synced SQLite files, this is a data corruption risk, not just a performance concern. The current "new connection per call" design is fine for local use but doesn't address the fundamental transport problem.

### 2. Dual state: SQLite + filesystem inbox

`sync_inbox_to_file` writes `.md` files as a parallel representation of inbox state already in SQLite. Two sources of truth for the same data will diverge — especially across machines with any sync latency. One should be the canonical source; the other should be derived or eliminated.

### 3. Service discovery via `pgrep` and tmux session names

- `pgrep("dispatcher")` matches any process with "dispatcher" in its name — false positives on any machine running unrelated software.
- tmux session name conventions (`{prefix}-{name}`) are fragile: a user manually creating a matching session name breaks status detection.
- Cross-machine: each machine has its own tmux — the current model can only see local sessions.

### 4. Module decomposition without concern separation

The board was split into ~12 `board_*.py` files, but they all follow the same pattern: fetch row → check exists → print error → `raise SystemExit(1)`. The decomposition is by command name, not by concern. The repetitive error-handling boilerplate could be a shared pattern, but instead it's copy-pasted across modules.

Similarly, `concerns/` has 18 modules for the dispatcher's monitor loop — the monitoring infrastructure is more complex than the coordination it supports.

### 5. No end-to-end test coverage

266 unit tests verify individual functions against real SQLite, which is good. But there is zero testing of the actual multi-agent flow: two agents sending messages, task handoff, inbox delivery + notification. The test suite verifies parts, not the machine.

### 6. 17 uncommitted files across bin/, lib/, tests/, .claude/commands/

This isn't a single in-progress change — it's accumulated drift. Mixed committed/uncommitted state makes it hard to reason about what's deployed vs. what's experimental.

## Suggested direction

The core question is: what is the cross-machine transport layer? Once that's answered (dedicated sync protocol? hosted relay? CRDTs?), most of the above either resolves or becomes clearly scoped. Until then, these problems will keep compounding.
