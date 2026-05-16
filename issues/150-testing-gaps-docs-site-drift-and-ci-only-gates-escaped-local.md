---
number: 150
title: "Testing gaps: docs/site drift and CI-only gates escaped local validation"
state: CLOSED
labels: ["bug", "phase:1", "infra", "priority:p1"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
closed: 2026-05-10
---

# #150 Testing gaps: docs/site drift and CI-only gates escaped local validation

**State:** CLOSED
**Labels:** bug, phase:1, infra, priority:p1

---

## Problem

Current validation is not enough. PR #149 exposed two gaps that should have been caught earlier:

- `site/contributing.html` drifted into a stale hand-written copy of `CONTRIBUTING.md`; the page could be broken while README/docs checks still passed.
- Registry and consistency failures only appeared in GitHub Actions after push, because local validation did not run the exact synthetic-merge and immutable-registry workflow path.

This means the project can look green locally while public pages or PR-only gates are still broken.

## Acceptance Criteria

- Add a site/docs check that prevents hand-maintained duplicate docs from drifting, starting with `site/contributing.html` vs `CONTRIBUTING.md`.
- Add link/redirect smoke coverage for `site/*.html` so stale or broken public entrypoints fail locally and in CI.
- Add a local command that mirrors the Registry Chain Guard PR path, including the existing-block immutability check against `origin/master`.
- Document the required pre-push gate for PR branches so maintainers do not rely on remote CI to discover these failures.
- Fold these checks into CI or `make ci` without making routine iteration painfully slow.

## Related

- Related broader roadmap: #88
- Found while closing #149
