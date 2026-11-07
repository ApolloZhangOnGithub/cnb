---
number: 180
title: "Board delivery should nudge running sessions for messages and tasks"
state: CLOSED
labels: []
assignees: []
created: 2026-05-15
updated: 2026-05-15
closed: 2026-05-15
---

# #180 Board delivery should nudge running sessions for messages and tasks

**State:** CLOSED

---

## Problem\nDuring dogfooding, board messages and assigned tasks can be written to the database but fail to visibly reach a running session when that session is busy. The old nudge path only injected the inbox command when the recipient looked idle, so active Codex sessions could miss assignments until they manually polled.\n\n## Acceptance\n- board send still opens inbox directly when the recipient is idle.\n- busy recipients get a safe-point prompt to check inbox instead of being silently skipped.\n- task add --to triggers the same nudge path.\n- tests cover idle, busy, and task-assignment nudges.
