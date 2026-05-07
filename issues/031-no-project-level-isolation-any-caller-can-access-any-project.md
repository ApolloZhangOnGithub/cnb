---
number: 31
title: "No project-level isolation: any caller can access any project's agents"
state: CLOSED
labels: [bug]
assignees: []
created: 2026-05-07
updated: 2026-05-07
closed: 2026-05-07
---

# #31 No project-level isolation: any caller can access any project's agents

**State:** CLOSED
**Labels:** bug

---

## Problem

cnb has no project-level isolation. Setting `CNB_PROJECT` to any `.claudes/` directory grants full read/write access to that project's board, agents, tasks, and messages — with no authentication, scoping, or even a warning.

## Reproduction

```bash
# From a completely unrelated project:
CNB_PROJECT=/path/to/other-project/.claudes board --as anyone inbox
CNB_PROJECT=/path/to/other-project/.claudes board --as anyone send agent-name "hijacked"
```

No error. No warning. Full access.

## Impact

1. **No ownership boundary** — agents from project A are visible and writable from project B
2. **No namespace isolation** — agent names are global within a board.db; if two projects happen to share agent names, they collide
3. **No caller verification** — there's no check that the caller belongs to the project. An external process (or a confused human/AI) can read messages, send commands, or modify task state of agents they don't own

## Expected behavior

- `board` commands should verify the caller is a registered agent in the current project
- Cross-project access should require explicit opt-in (e.g., a shared token or inter-project protocol)
- At minimum: a warning when `CNB_PROJECT` doesn't match the current working directory's project

## Suggested directions

1. **Session token per project** — each `cnb init` generates a project-scoped token; board commands require it
2. **Agent identity binding** — board commands verify `--as <name>` against the registry chain; reject unregistered callers
3. **Working directory check** — if CWD is outside the project root, warn or refuse by default
