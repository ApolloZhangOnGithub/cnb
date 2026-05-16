---
number: 129
title: "Feishu live activity should surface stale open requests before users ask why it is stuck"
state: OPEN
labels: ["enhancement", "phase:2", "infra", "module:feishu", "priority:p1"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #129 Feishu live activity should surface stale open requests before users ask why it is stuck

**State:** OPEN
**Labels:** enhancement, phase:2, infra, module:feishu, priority:p1

---

## Problem

Live Feishu mode currently sends ack and activity cards, but if the device supervisor receives a message and never sends a final `cnb feishu reply`, the user only sees a live card continuing or going quiet. In the May 10 debugging session, two Feishu messages were delivered and acked, but a tmux multiline injection issue left them without final replies until manual readback inspection.

The underlying injection bug has been fixed separately, but the product still needs a watchdog for this class of failure.

## Desired behavior

When a Feishu activity remains open beyond a threshold, CNB should surface it proactively without spamming. Examples:

- status should list stale open activity count and message IDs;
- live cards should show a clear "still open / possible stuck" state after the threshold;
- optional watchdog can send one diagnostic note or short ask when the supervisor appears idle but the activity is still open;
- readback troubleshooting should have a direct path from stale activity state.

## Acceptance criteria

- Configurable stale threshold for open Feishu activities.
- `cnb feishu status` reports stale open activities.
- Live card rendering distinguishes active work from stale open requests.
- Tests cover stale detection, no-spam behavior, and done-state cleanup.

## Labels

Module: Feishu bridge live activity and delivery diagnostics.
