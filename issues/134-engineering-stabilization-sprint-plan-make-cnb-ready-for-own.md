---
number: 134
title: "Engineering stabilization sprint plan: make cnb ready for owner-led development"
state: OPEN
labels: ["phase:1", "infra", "org-design", "priority:p0"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #134 Engineering stabilization sprint plan: make cnb ready for owner-led development

**State:** OPEN
**Labels:** phase:1, infra, org-design, priority:p0

---

## Goal

Make `cnb` ready for owner-led development after the user migrates to another iMac, without spawning additional classmates before that migration. This sprint is about stabilization and operating discipline, not new large features.

## Sprint window

2026-05-10 through 2026-05-24.

## Operating rules

- Do not start additional cnb classmates until the user finishes iMac migration.
- Prefer GitHub issue/milestone/label work over editing the already-dirty local worktree.
- Keep PRs small and independently verifiable.
- Every implementation issue needs an explicit acceptance command or external verification step.
- Phase 3 and experiment issues stay out of the sprint unless they unblock stabilization.

## P0: unblock reliable install, ownership, CI, and release

- [ ] #132 Restore package/release correctness after `c-n-b` rename landed before npm package exists.
- [ ] #64 Decide and document device supervisor vs project lead responsibilities.
- [ ] #48 Establish code health owner scope and handoff expectations.
- [ ] #74 Sweep dirty worktree, stale PRs, and CI follow-ups.
- [ ] #60 Fix private-key/secret storage and gitignore safety.
- [ ] #77 Stop tests from polluting real `~/.cnb` state.
- [ ] #67 Make default pytest robust against ambient `pytest-randomly`.
- [ ] #73 Fix noisy/failed `sync-issues` workflow behavior.
- [ ] #100 Resolve npm `stable` tag after package/auth state is safe.

## P1: make owner-led work executable

- [ ] #34 Pending actions queue for user-required approvals and verification.
- [ ] #75 Read-only board inspection without impersonating sessions.
- [ ] #87 Routing evidence beyond prefix/substring ownership matching.
- [ ] #90 Harden Feishu local_openapi and webhook tests.
- [ ] #91 Add project discovery and Codex engine CLI regression tests.
- [ ] #88 Convert testing roadmap into practical regression matrix.
- [ ] #128 Refresh/restart stale device-supervisor prompt after upgrades.
- [ ] #129 Surface stale open requests before users ask why stuck.
- [ ] #114 Keep secure remote Feishu TUI watch production-ready.
- [ ] #121 Portability/bootstrap path for moving to another Mac.

## P2: useful but not allowed to block stabilization

Tracked with `priority:p2`, generally after this sprint: #127, #131, #99, #56, #43, #63, #41, #42, #47, #65.

## Acceptance for this planning issue

- P0/P1 issues are labeled and placed in the sprint milestone.
- P2 issues are labeled but not treated as blockers.
- The next project lead/code health owner can start from this issue without rereading all open issues.
- The user can migrate first; no new classmates are required to preserve this plan.
