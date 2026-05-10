---
number: 76
title: "Organization reform: clarify authority, ownership, and shutdown governance"
state: OPEN
labels: ["phase:1", "org-design"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
---

# #76 Organization reform: clarify authority, ownership, and shutdown governance

**State:** OPEN
**Labels:** phase:1, org-design

---

## Problem

Development is currently outpacing the organization system. The team can produce code, but coordination boundaries are still ambiguous and create avoidable risk.

Observed issues:
- Lead authority is not encoded strongly enough: lead-as-user-facing-terminal and lead-as-team-owner are easy to confuse.
- Operators can accidentally coordinate by impersonating sessions with --as <name>.
- Dirty worktree work from multiple issues becomes mixed, making verification and delivery hard to trust.
- Many open issues have no explicit owner/reviewer/next checkpoint.
- Historical/offline sessions keep unread inbox state and pollute dashboards/digests.
- PR review and merge ownership is unclear; checks can be green while PRs remain blocked.
- Board task queue is not the single source of truth for all assignments.
- Proposal lifecycle has no cleanup/decision discipline.

## Required reforms

1. Authority model
   - User authorizes lead.
   - Lead owns team coordination and priority decisions.
   - Dispatcher only keeps sessions alive, runs health checks, and escalates blockers to lead.
   - Operators may restore infrastructure or execute explicit user commands, but should not bypass lead for team management.

2. Observation without impersonation
   - Land a read-only inspect path for inbox/tasks that does not require acting as another session.
   - Record when privileged cross-session inspection is allowed.

3. Work ownership discipline
   - One active issue = one owner, one clean worktree/branch, one review path.
   - Every active issue must have owner, reviewer, expected artifact, verification command, and next checkpoint.
   - Shared dirty worktree is only for triage, not final delivery.

4. Shutdown and handoff discipline
   - End-of-shift flow must be explicit: broadcast, ack, collect daily/shift reports, stop sessions, preserve unresolved blockers.
   - Historical/offline sessions need archive/offboard/hibernate rules so dashboards reflect real active teams.

5. Governance hygiene
   - Close stale/test proposals.
   - Define PR merge captain/reviewer rotation.
   - Require task queue entries for all non-trivial assignments.

## Acceptance criteria

- Documented lead/dispatcher/operator responsibility boundaries.
- A board-visible checklist for issue ownership and handoff.
- Read-only inspect workflow merged or explicitly linked as dependency.
- Shutdown flow produces a shift report and leaves no live team session running after stop.
- Dashboard excludes or clearly separates archived/offline historical sessions.
- Open PRs and active issues each have a named owner and next action.

## Priority

P0 organization reform. Treat this as higher priority than new feature development.
