---
number: 24
title: "Rewrite bin/swarm from bash to Python"
state: CLOSED
labels: ["enhancement"]
assignees: []
created: 2026-05-06
updated: 2026-05-06
closed: 2026-05-06
---

# #24 Rewrite bin/swarm from bash to Python

**State:** CLOSED
**Labels:** enhancement

---

## Context

`bin/swarm` is 896 lines of bash — the largest remaining bash file in a project that's otherwise Python. Its complexity (tmux session management, health checks, start/stop/status) is well beyond what bash handles cleanly.

## Scope

Rewrite to Python module(s) under `lib/`, keeping the same CLI interface:
- `cnb swarm start <names...>`
- `cnb swarm stop <names...>`
- `cnb swarm status`
- `cnb swarm restart <name>`

## Notes

- tmux interaction can use `subprocess.run` (same as current bash `tmux` calls)
- Config parsing already has Python equivalents in `lib/common.py`
- Should be decomposable: `lib/swarm.py` for core logic, thin `bin/swarm` entry point
