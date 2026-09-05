---
number: 115
title: "Track GitHub Actions Node 24 migration"
state: CLOSED
labels: []
assignees: []
created: 2026-05-10
updated: 2026-05-10
closed: 2026-05-10
---

# #115 Track GitHub Actions Node 24 migration

**State:** CLOSED

---

## Context

GitHub Actions currently warns on CI, CodeQL, Pages, and package mirror runs that Node.js 20 actions are deprecated.

Observed warnings mention:
- Node.js 24 becomes the default on 2026-06-02.
- Node.js 20 is removed from runners on 2026-09-16.
- Affected actions include `actions/checkout@v4`, `actions/setup-python@v5`, and `actions/setup-node@v4`.

## Why this matters

The workflows are green today, but the warning is time-bound. If the action ecosystem or our workflows are not ready for Node 24, CI/CD may start failing without a code change.

## Acceptance Criteria

- Audit `.github/workflows/*.yml` for Node 20-backed actions.
- Upgrade actions to Node 24-ready major versions where available.
- If upgrades are not available, decide whether to set `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` in a controlled PR and verify all workflows.
- Keep a fallback note for `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION` only as a temporary emergency option, not normal configuration.
- Verify CI, CodeQL, Pages, Sync Issues, and GitHub Package Mirror after the change.

