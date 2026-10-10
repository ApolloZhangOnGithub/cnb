---
number: 135
title: "Add worktree checkpoint and dirty-state guard for long-running cnb sessions"
state: OPEN
labels: ["phase:1", "infra", "priority:p1"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #135 Add worktree checkpoint and dirty-state guard for long-running cnb sessions

**State:** OPEN
**Labels:** phase:1, infra, priority:p1

---

## Problem

Long-running cnb/Codex work often leaves valuable state only in a dirty local worktree. Operators can forget to commit or summarize, which risks losing work during migration, restart, prompt refresh, or handoff. A permanently dirty worktree also makes it hard to tell which changes are intentional, user-owned, generated, or abandoned.

## Requirements

- Add a lightweight checkpoint workflow for long-running sessions.
- Surface dirty worktree state before shutdown, migration, prompt refresh, or handoff.
- Distinguish uncommitted code changes, generated artifacts, local secrets/config, and external GitHub-only planning work.
- Provide a safe default: summarize + stash/branch/commit recommendation, without auto-committing secrets or user changes.
- Integrate with device supervisor / project lead flow so the user does not have to remember git hygiene manually.

## Acceptance criteria

- A command or guard can report current dirty state with clear buckets and suggested action.
- Before supervisor migration or shutdown, cnb warns if important repo changes are uncommitted.
- The guard refuses or warns loudly when secret-looking files would be committed.
- The workflow references #74 for repository sweep and #41 for shift-report style handoff.

## Related

- #74 repository maintenance sweep
- #41 automated shift report
- #121 device supervisor portability
- #60 secret safety
