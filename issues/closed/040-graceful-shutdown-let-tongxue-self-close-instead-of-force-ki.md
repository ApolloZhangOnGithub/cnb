---
number: 40
title: "Graceful shutdown: let tongxue self-close instead of force-kill"
state: CLOSED
labels: []
assignees: []
created: 2026-05-07
updated: 2026-05-07
closed: 2026-05-07
---

# #40 Graceful shutdown: let tongxue self-close instead of force-kill

**State:** CLOSED

---

## Problem

Current `cnb swarm stop` is a force-kill with auto-save bolted on:
1. Sends `git add -A && git commit -m '[WIP] auto-save'` to each tmux session
2. Immediately kills the session
3. Tongxue have no chance to finish in-progress work or do a proper handoff

This is not graceful — it's "save and die." The WIP commits are messy and the tongxue can't wrap up cleanly.

## Observed better behavior

When we broadcast `board --as lead send all "准备收工"`, tongxue naturally:
- Finished their current task
- Committed with proper messages (not WIP)
- Updated their session status with detailed next-steps
- Confirmed back to the lead ("已保存状态，随时可以收工")

This took ~3 minutes and produced much cleaner state than force-stop.

## Proposed: `cnb stop` (graceful, default)

1. Broadcast a shutdown notice via board: `send all "收工：请保存状态并确认"`
2. Wait for each tongxue to either:
   - Update status to contain "shutdown" / "saved" / "收工", OR
   - Timeout (configurable, default 3 min)
3. After all confirm (or timeout), kill tmux sessions
4. Only fall back to WIP auto-save for tongxue that didn't respond

`cnb stop --force` keeps the current immediate-kill behavior.

## Benefits

- Clean commits instead of WIP noise
- Tongxue save meaningful state (next-steps, blockers, handoff notes)
- Session files have proper status for next startup
- Respects the "peer, not worker" philosophy — tongxue clock out, not get killed
