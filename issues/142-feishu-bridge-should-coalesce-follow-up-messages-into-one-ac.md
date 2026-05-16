---
number: 142
title: "Feishu bridge should coalesce follow-up messages into one active activity"
state: OPEN
labels: []
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #142 Feishu bridge should coalesce follow-up messages into one active activity

**State:** OPEN

---

## Problem

When a Feishu user sends a follow-up message while the device supervisor is still processing a previous message, the bridge/activity layer currently treats each inbound message as a separate tracked activity window/card. In practice, one natural conversation can quickly become two or three concurrent activity windows even though the user intent is one continuous thread.

Observed during live dogfooding: the user sent a follow-up while the previous Vue early-commit analysis was still in progress, then noted that Feishu started tracking multiple windows. This is confusing and creates noisy mobile state.

## Desired behavior

For messages from the same allowed chat/user that arrive while a device-supervisor task is active, CNB should support a coalescing model:

- Attach the new inbound message to the existing active activity/thread when it is likely a continuation.
- Mark it as a user supplement/interruption rather than opening a separate activity card by default.
- Preserve every `message_id` in the transcript so the supervisor can reply to the most recent or relevant one.
- Update the existing activity card summary to show that new user input arrived.
- Avoid spawning a new live activity unless the previous one is done, expired, or explicitly independent.

## Product rules to design

- Same chat + same sender + active supervisor session + short time window => default merge.
- If the new message explicitly changes topic, it can interrupt/replace the active task but should still use one visible activity unless configured otherwise.
- If a previous long-running task needs a final answer to an older `message_id`, the bridge should allow finalizing the merged thread once, not force one reply per message.
- The supervisor prompt should include a compact ordered list of pending/unanswered message ids in the merged thread.
- Mobile notification policy should avoid one push/card per supplement.

## Acceptance criteria

- Sending three consecutive Feishu messages during one active task produces one visible activity window/card, not three.
- The activity card indicates the latest user supplement and current handling state.
- `cnb feishu reply` can close/complete the merged activity using the latest message id or an explicit thread id.
- No message content is lost; all message ids remain auditable for debugging.
- Existing one-message request flow continues to work unchanged.

## Related areas

- Feishu activity card lifecycle
- inbound bridge prompt assembly
- `cnb feishu reply/ask/activity` state model
- mobile notification policy

