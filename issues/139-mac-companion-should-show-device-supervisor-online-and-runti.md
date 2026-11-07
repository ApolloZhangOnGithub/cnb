---
number: 139
title: "Mac companion should show device-supervisor online and runtime health"
state: OPEN
labels: ["bug", "enhancement", "phase:2", "infra", "module:feishu", "module:runtime", "module:mac-companion", "priority:p1"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #139 Mac companion should show device-supervisor online and runtime health

**State:** OPEN
**Labels:** bug, enhancement, phase:2, infra, module:feishu, module:runtime, module:mac-companion, priority:p1

---

## Problem

The current cnb app / Mac companion status model focuses on registered projects and project board state. It does not treat the device/terminal supervisor and its runtime services as first-class status. During Feishu dogfooding and upcoming iMac migration, this makes the app misleading: a project can appear quiet or active while the actual user-facing supervisor, Feishu bridge, or watch service is down/stale.

## Current evidence

- `tools/cnb-mac-companion/Sources/CNBMacCompanion/Services/CNBStateReader.swift` reads `~/.cnb/projects.json` and project `.cnb/board.db` / `.claudes/board.db`.
- It summarizes project tasks, unread messages, pending actions, and board sessions.
- It sets `supervisorName` from `CNB_SUPERVISOR` or a default string, but does not verify the supervisor tmux session/process.
- It does not surface whether `cnb-device-supervisor`, `cnb-feishu-bridge`, `cnb-feishu-watch`, ngrok/webhook, or Feishu notification policy are healthy.

## Requirements

The app should include a device-runtime section/status source with at least:

- device supervisor identity and active/standby role;
- supervisor tmux session existence and current command/liveness;
- Feishu bridge running/stale/down;
- watch service running/stale/down and whether the public URL is configured;
- active project directory and current device-supervisor cwd when available;
- warning when the app can read projects but the user-facing supervisor is offline;
- explicit migration/cutover state for old Mac standby vs iMac active.

## Acceptance criteria

- The Mac companion can distinguish `projects are quiet` from `device supervisor is offline`.
- The menu bar summary shows a degraded state when the supervisor or bridge/watch service is down.
- The project list remains useful, but device-runtime health is visible without opening a terminal.
- The implementation uses a reusable cnb runtime-status/doctor source instead of duplicating fragile process parsing inside Swift where possible.

## Related

- #121 device supervisor portability / iMac migration
- #128 stale device-supervisor prompt after upgrades
- #129 live activity should surface stale open requests
- #137 Feishu device-supervisor provisioning wizard
- #127 existing Mac companion chat defects
