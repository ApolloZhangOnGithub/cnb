---
number: 74
title: "Lead repository maintenance sweep: dirty worktree, stale PRs, and CI follow-ups"
state: OPEN
labels: ["phase:1", "infra", "priority:p0"]
assignees: []
created: 2026-05-09
updated: 2026-05-10
---

# #74 Lead repository maintenance sweep: dirty worktree, stale PRs, and CI follow-ups

**State:** OPEN
**Labels:** phase:1, infra, priority:p0

---

## Problem

The repository now has enough accumulated maintenance work that it needs explicit owner triage instead of opportunistic fixes.

Current visible backlog:

- shared worktree has many unstaged edits/deletions across docs, entrypoints, dispatcher/swarm, board modules, registry, and tests
- open PRs need owner review/merge/close decisions: #68 and #57
- open maintenance/infra issues include #73, #67, #63, #60, #59, #56, #54, #48, #43, #41, #38, #34
- master CI is currently green after #71, but check-consistency warns npm is outdated (`npm=0.5.1`, local `0.5.24`)
- `sync-issues.yml` produced a failed no-job run after merge; tracked in #73

## Expected

The project lead should run a maintenance sweep and report repository health with evidence. This is ownership work, not a new mechanism design task.

## Acceptance

- classify the dirty worktree by owner/issue and decide which changes become commits/PRs versus discard candidates
- review open PRs #68 and #57 and record concrete next actions
- triage the listed maintenance issues into immediate / later / duplicate / obsolete
- resolve or clearly scope #73
- decide whether npm publish/version follow-up is required after `0.5.24-dev` landed
- leave a concise status update on this issue with commands run, decisions made, and remaining blockers
