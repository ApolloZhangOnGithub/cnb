---
number: 102
title: "Dispatcher should escalate stuck manager closeout loops"
state: OPEN
labels: ["bug", "phase:1", "infra"]
assignees: []
created: 2026-05-11
updated: 2026-05-11
---

# #102 Dispatcher should escalate stuck manager closeout loops

## Problem

During a one-hour project-manager sprint, execution sessions completed and
reported their work, but `project-manager` did not synthesize the reports or
mark its manager task done. The dispatcher kept nudging inbox:

```text
NUDGE [inbox] project-manager
```

The manager session repeatedly ran `board --as project-manager inbox`, saw the
same unread reports and active manager task, and never closed the task.

## Impact

The system can keep sessions alive and nudge them, but sustained work still
stalls at the project-management closeout step. This makes "continuous
autonomous progress" unreliable even when all worker tasks are done.

## Expected

Dispatcher should recognize a likely closeout stall:

- a manager-like session has an active task;
- that session has unread inbox messages;
- all other active/pending tasks are complete, or only manager tasks remain;
- the unread/active condition persists across several dispatcher ticks.

When detected, dispatcher should send a stronger, specific closeout message
instead of repeating generic inbox nudges. The message should instruct the
manager to summarize reports, ack inbox, and mark the manager task done or
escalate blockers.

## Acceptance

- Add dispatcher logic that detects stuck manager closeout loops.
- Do not affect ordinary inbox nudges for normal worker sessions.
- Add unit coverage for: detection, no false positive while worker tasks remain,
  and cooldown/no spam behavior.
- Document or log the escalation clearly enough for device supervisors to audit.
