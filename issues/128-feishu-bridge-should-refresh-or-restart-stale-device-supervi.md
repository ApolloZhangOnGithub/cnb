---
number: 128
title: "Feishu bridge should refresh or restart stale device-supervisor prompt after upgrades"
state: CLOSED
labels: ["bug", "phase:2", "infra", "module:feishu", "module:runtime", "priority:p1"]
assignees: []
created: 2026-05-10
updated: 2026-05-11
closed: 2026-05-11
---

# #128 Feishu bridge should refresh or restart stale device-supervisor prompt after upgrades

**State:** CLOSED
**Labels:** bug, phase:2, infra, module:feishu, module:runtime, priority:p1

---

## Problem

The Feishu bridge can be updated and restarted while the existing `cnb-device-supervisor` Codex tmux session keeps running. New inbound messages include the latest bridge affordance block, but the long-lived Codex process still has the old startup system prompt in its launch argv.

During the May 10 Feishu live debugging session, this left the supervisor process with an older system prompt even after the bridge gained `ask`, readback/resource handoff notes, and fake-emoji guidance. The per-message affordance block mitigates it, but it is easy to misdiagnose when inspecting process state.

## Desired behavior

The bridge/runtime should make prompt freshness explicit and safe. Options:

- detect supervisor prompt version/hash drift in `cnb feishu status`;
- offer `cnb feishu restart-supervisor` or an automatic safe restart when idle;
- record the active prompt version in activity/status state;
- avoid restarting while the supervisor is actively working unless explicitly requested.

## Acceptance criteria

- `cnb feishu status` can indicate whether the running device-supervisor prompt is current.
- There is a documented safe path to refresh the supervisor prompt without losing active Feishu work.
- Tests cover drift detection and the no-restart-while-working guard.

## Labels

Module: Feishu bridge + runtime supervisor lifecycle.
