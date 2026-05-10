---
number: 70
title: "board view conflates session liveness with active work"
state: CLOSED
labels: []
assignees: []
created: 2026-05-09
updated: 2026-05-09
closed: 2026-05-09
---

# #70 board view conflates session liveness with active work

**State:** CLOSED

---

## Problem

Managing Claude Code/Codex-style tmux sessions needs two separate signals:

- liveness: the tmux session and agent process still exist
- work state: the agent is actively doing work instead of sitting idle at a prompt

`lib/board_view.py` currently collapses those into labels such as `active`, `running`, and `offline`. After the tmux fallback, a stale heartbeat with a live non-shell pane is shown as `running`, even when the agent is alive but idle. That makes board-level management unreliable because an idle live session can look the same as a session actively executing work.

The project already has partial working/idle signals elsewhere (`lib/panel.py`, `lib/health.py`, and `lib/concerns/idle.py`), but the board view does not expose the distinction.

## Expected

Board status should distinguish the two dimensions. For example:

- `working`: alive and actively executing work
- `alive idle`: alive, but no current work signal
- `shell` / `offline`: not an active agent process

Heartbeat age should remain visible so stale telemetry is still diagnosable.

## Acceptance

- Update board view status derivation to avoid labeling every live tmux agent as actively running.
- Reuse project-local tmux/pane evidence where possible.
- Add focused tests for alive-idle versus working detection.
- Keep the change limited to board status reporting.
