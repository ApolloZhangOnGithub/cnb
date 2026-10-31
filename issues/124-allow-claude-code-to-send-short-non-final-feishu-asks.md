---
number: 124
title: "Allow Claude Code to send short non-final Feishu asks"
state: CLOSED
labels: ["enhancement", "phase:2", "infra"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
closed: 2026-05-10
---

# #124 Allow Claude Code to send short non-final Feishu asks

**State:** CLOSED
**Labels:** enhancement, phase:2, infra

---

## Problem

Today `cnb feishu reply <message_id> ...` is the only user-visible Feishu response channel for the device supervisor. That command intentionally marks the Feishu activity as done, which is correct for final results or hard blockers, but awkward when Claude Code only needs one short clarification, confirmation, or user requirement during an ongoing task.

## Desired behavior

Add an explicit short non-final reply command so the supervisor can ask the user for small bits of input without closing the current activity.

## Acceptance criteria

- Provide a CLI command such as `cnb feishu ask <message_id> "short question"`.
- The command sends a Feishu reply to the original message but does not mark the activity done.
- The command enforces a short/mobile-friendly payload and rejects long summaries or code blocks.
- The supervisor prompt and bridge affordance text explain when to use `ask` versus final `reply`.
- Tests cover success, non-final activity state, and validation failures.

## Notes

This is separate from live activity cards and readback/resource handoff. It is a low-noise human-in-the-loop channel for cases where continuing safely requires a concise user answer.
