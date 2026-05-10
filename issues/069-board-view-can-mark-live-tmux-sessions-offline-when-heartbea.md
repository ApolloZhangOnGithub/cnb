---
number: 69
title: "board view can mark live tmux sessions offline when heartbeat is stale"
state: CLOSED
labels: []
assignees: []
created: 2026-05-09
updated: 2026-05-09
closed: 2026-05-09
---

# #69 board view can mark live tmux sessions offline when heartbeat is stale

**State:** CLOSED

---

## Summary

`board view` derives liveness from `sessions.last_heartbeat` first. If that heartbeat is old, it returns `offline` immediately and never checks the actual tmux session. In the Codex swarm run on 2026-05-10, several sessions were still alive with `pane_current_command=node`, but `board view` showed them as offline with old heartbeat timestamps.

## Evidence

Live tmux/swarm state showed running Codex sessions:

```text
./bin/swarm status
musk: running (tmux, engine: codex)
tester: running (tmux, engine: codex)
forge: running (tmux, engine: codex)
lead: running (tmux, engine: codex)
sutskever: running (tmux, engine: codex)
lisa-su: running (tmux, engine: codex)
codex: running (tmux, engine: codex)
```

But `./bin/board --as bezos view` showed old-heartbeat sessions such as `Musk`, `Lisa-su`, and `Sutskever` as offline.

## Root cause

`lib/board_view.py::_heartbeat_status` returns `offline` when `last_heartbeat` is older than 600 seconds. The tmux fallback only runs when heartbeat is missing or unparsable, not when heartbeat is stale.

## Impact

The project lead gets a false picture of who is still active. That makes owner/lead follow-up unreliable during multi-agent runs, especially when Codex sessions do not refresh heartbeat but remain alive in tmux.

## Expected behavior

Fresh heartbeat should still win. For stale heartbeat, `board view` should fall back to tmux and report a live non-shell pane as running, preserving the stale heartbeat age as context.

