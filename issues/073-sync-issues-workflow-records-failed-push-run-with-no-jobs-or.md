---
number: 73
title: "sync-issues workflow records failed push run with no jobs or logs"
state: OPEN
labels: ["bug", "phase:1", "infra"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
---

# #73 sync-issues workflow records failed push run with no jobs or logs

**State:** OPEN
**Labels:** bug, phase:1, infra

---

## Problem

After PR #71 was squash-merged to `master`, GitHub Actions created a failed run for `.github/workflows/sync-issues.yml` on the push event:

- run: https://github.com/ApolloZhangOnGithub/cnb/actions/runs/25608547876
- event: `push`
- head: `3038baeb1f7eb27af4b681c75a5e7cbc8a13d82c`
- conclusion: `failure`
- jobs: `[]`

`gh run view --log-failed` returns `failed to get run log: log not found`, so there is no job-level evidence to inspect. The workflow file currently declares `issues`, `schedule`, and `workflow_dispatch` triggers, not `push`, which makes this failure ambiguous.

## Impact

The main CI workflow for the same merge commit is green, but the repository still shows an extra failed workflow run after merge. That makes remote health look worse than the actual code/test state.

## Acceptance

- Determine why `sync-issues.yml` records a failed push run with no jobs/logs.
- Either fix the workflow trigger/config or document the GitHub Actions behavior if it is external.
- Confirm future issue sync events and master pushes do not leave unexplained failed runs.
