---
number: 95
title: "Terminal supervisor Live Activity / CNB Island"
state: CLOSED
labels: ["enhancement", "phase:3", "infra"]
assignees: []
created: 2026-05-09
updated: 2026-05-10
closed: 2026-05-10
---

# #95 Terminal supervisor Live Activity / CNB Island

**State:** CLOSED
**Labels:** enhancement, phase:3, infra

---

## Problem

cnb currently has useful status surfaces (`cnb ps`, `board view`, `/cnb-overview`, `/cnb-pending`), but they require the user or terminal supervisor to actively ask for state. The terminal supervisor already represents the user-facing operational viewpoint, so it should have a glanceable Mac surface for local project attention state.

## Product Direction

Build a local Mac companion surface from the terminal supervisor perspective:

1. State export: cnb writes compact terminal-supervisor state to `~/.cnb/live_state.json`.
2. ActivityKit integration: an iOS/Mac Catalyst host app starts and updates the Live Activity.
3. WidgetKit extension: system-rendered Live Activity presentations define Dynamic Island, Lock Screen, and Mac menu-bar behavior.
4. Operations: start with safe read-only actions, then add confirmable cnb command operations later.

Do not implement this as an NSPanel, custom floating window, or fake menu-bar item.

## Scope

The island should show:

- active project count;
- active/pending tasks;
- unread board messages;
- pending user actions;
- top blocked project or highest-priority pending action;
- shutdown/update/CI activity when those flows are active.

Initial safe operations:

- refresh;
- start/update/end the system Live Activity;
- inspect pending action command and reason.

Out of scope for the first prototype:

- running retries;
- marking pending actions done;
- starting/stopping swarms;
- global shutdown;
- auto-update execution.

## Acceptance Criteria

1. `tools/cnb-island/script/export_live_state.py` writes `~/.cnb/live_state.json`.
2. ActivityKit host and WidgetKit Live Activity source can be type-checked against the iOS Simulator SDK.
3. The local Xcode project builds with signing disabled for validation.
4. The Live Activity content state can display project/task/pending/unread totals.
5. Stale registry paths do not crash the state exporter.
6. No board mutation happens without an explicit future confirmation design.
