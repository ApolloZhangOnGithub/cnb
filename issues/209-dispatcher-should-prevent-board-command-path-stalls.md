---
number: 209
title: "Dispatcher should prevent board command-path stalls"
state: CLOSED
labels: ["bug", "phase:1", "infra"]
assignees: []
created: 2026-05-16
updated: 2026-05-16
closed: 2026-05-16
---

# #209 Dispatcher should prevent board command-path stalls

**State:** CLOSED
**Labels:** bug, phase:1, infra

---

## Problem

Several delegated sessions stalled while repeatedly trying `./board --as <name> inbox` from the repo root, where `./board` does not exist. The supervisor had to manually inspect tmux panes and resend the absolute board path.

This creates two operational failures:
- classmates appear alive but do no useful work;
- dispatcher/lead status can claim coordination is running while task execution is actually stuck on a command-path mistake.

## Expected behavior

- New session prompts and dispatcher-assigned tasks should always include the absolute board command path from AGENTS.md.
- If a session repeatedly runs a missing board command, the dispatcher should detect it as a stalled/no-progress state and reassign or nudge with the exact command.
- The board/CLI should ideally expose a stable shim (`cnb board ...` or an installed `board`) so task prompts do not depend on cwd.

## Evidence from dogfooding

- docs-scout repeatedly ran `./board --as docs-scout inbox` and got `zsh: no such file or directory: ./board`.
- api-scout and test-scout also looped on inbox/status instead of advancing assigned tasks until manually re-prompted.

## Acceptance criteria

- Dispatch prompts contain the absolute board path or a cwd-independent command.
- A regression test covers task/inbox nudge text and confirms it does not emit bare `./board`.
- Stalled repeated command failures are visible in board progress/stalls output or trigger a dispatcher nudge.

