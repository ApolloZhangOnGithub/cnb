---
number: 204
title: "Dispatcher must auto-start and keep all classmates assigned by default"
state: CLOSED
labels: ["enhancement", "infra"]
assignees: []
created: 2026-05-16
updated: 2026-05-16
closed: 2026-05-16
---

# #204 Dispatcher must auto-start and keep all classmates assigned by default

**State:** CLOSED
**Labels:** enhancement, infra

---

## Problem

During Feishu dogfooding on 2026-05-16, the user made this a standing requirement: CNB should not depend on the device supervisor remembering to start dispatcher manually. Dispatcher must be on by default and keep classmates moving; when a classmate stops or finishes, it should continue finding/assigning work instead of waiting for user prompting.

## Desired behavior

- Default CNB launch starts dispatcher automatically.
- Lower-level swarm start paths also start dispatcher unless explicitly disabled.
- Dispatcher/watchdog ownership is visible in board/runtime status.
- Idle/done classmates are assigned follow-up work or at least surfaced as needing assignment.
- This should work for Codex-started classmates as well as Claude-started classmates.

## Acceptance criteria

- Fresh cnb launch and existing-project cnb launch keep dispatcher running.
- Direct cnb swarm start starts dispatcher by default.
- There is an opt-out for tests/manual debugging.
- Tests cover the default-on behavior.

Created from Feishu operations feedback; user explicitly said this is now the default requirement.
