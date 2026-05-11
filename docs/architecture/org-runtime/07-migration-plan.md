# 07 — Migration Plan

This plan migrates cnb gradually without breaking all existing commands at once.

## Migration strategy

Do not rewrite the whole system in one pass.

Use this sequence:

```text
1. Add architecture docs and invariants.
2. Add org kernel library behind old commands.
3. Add event store and projections.
4. Migrate ownership first.
5. Migrate scan to route decision + obligation.
6. Migrate task completion to contract verification.
7. Add handoff and runtime protection.
8. Add daemon and capabilities.
9. Move adapters to signal/command model.
10. Remove legacy mutation paths.
```

## Phase 0 — Docs, invariants, characterization tests

Deliverables:

```text
docs/architecture/org-runtime/*
legacy behavior tests
architecture review checklist
```

Actions:

- Document current-to-new concept mapping.
- Add tests for existing `board own`, `board task`, `scan`, `inbox`, `status` behaviors.
- Add rule: new code should not add direct DB mutations outside existing legacy code.

Exit criteria:

```text
team can explain Actor vs Session, Ownership vs Task, Message vs Obligation
legacy tests capture current behavior
```

## Phase 1 — OrgKernel library

Deliverables:

```text
lib/cnb/org/kernel.py
lib/cnb/org/commands.py
lib/cnb/org/events.py
lib/cnb/store/event_store.py
lib/cnb/store/projections.py
lib/cnb/store/unit_of_work.py
```

Actions:

- Implement command envelope.
- Implement event append.
- Implement projection updater for a small subset.
- Allow CLI/legacy command to call kernel in-process.

Exit criteria:

```text
command -> event -> projection works
projection rebuild works
idempotency works
```

## Phase 2 — Ownership v2 base

Deliverables:

```text
lib/cnb/org/scopes.py
lib/cnb/org/contracts.py
lib/cnb/org/ownership.py
scope/ownership projections
cnb.org.toml or cnb.ownership.toml import
```

Actions:

- Add scope, patterns, contracts, assignments.
- Migrate legacy ownership table into legacy path scopes.
- Keep old `own claim/list/map` behavior through facade.

Legacy mapping:

```text
old ownership.session -> owner_actor_id
old ownership.path_pattern -> scope pattern path
legacy scope id -> legacy-path-<normalized>
```

Exit criteria:

```text
old ownership map still works
new scope list works
one active owner per scope enforced
```

## Phase 3 — Routing and route decisions

Deliverables:

```text
lib/cnb/org/routing.py
route_decisions_current
cnb owner route
cnb owner explain
```

Actions:

- Implement resolver with evidence and confidence.
- Make old `find_owner(path)` call resolver internally.
- Add golden tests for routes.

Exit criteria:

```text
path route explains candidates/evidence
low confidence fallback works
conflict fallback works
```

## Phase 4 — Obligations

Deliverables:

```text
lib/cnb/org/obligations.py
obligations_current
cnb obligation accept/reject/delegate/escalate/satisfy
```

Actions:

- Route decisions open obligations.
- Notifications reference obligations.
- Owner rejection creates fallback obligation.

Exit criteria:

```text
scan issue creates route decision and obligation
owner can accept/reject
a rejected obligation no longer looks unhandled
fallback obligation is created when appropriate
```

## Phase 5 — Task v2 and contract verification

Deliverables:

```text
lib/cnb/org/tasks.py
verification_runs_current
RunVerification job
scoped task CLI
```

Actions:

- Add task source, scope, obligation references.
- Change task completion into `TaskCompletionRequested`.
- Run scope contract verification before done.
- Add review/approval transitions.

Exit criteria:

```text
task complete does not directly mark done
verification failure blocks done
scoped task uses scope contract
non-owner assignee requires owner review when configured
```

## Phase 6 — Handoff and runtime protection

Deliverables:

```text
lib/cnb/org/handoff.py
lib/cnb/runtime/protection.py
handoffs_current
owner protection policy
```

Actions:

- Implement transfer/handoff lifecycle.
- Generate handoff checklist.
- Stop/restart checks owner protection.
- Orphan detection schedules backup/fallback.

Exit criteria:

```text
transfer requires handoff accept
protected owner cannot be normal-stopped while open obligations exist
force stop emits audit event
orphan owner produces health warning and backup action
```

## Phase 7 — cnbd and capabilities

Deliverables:

```text
lib/cnb/daemon/*
capability token creation/verification
CLI CommandClient
legacy impersonation gate
```

Actions:

- Start daemon as single writer.
- CLI submits commands over IPC.
- Actor identity comes from token.
- `--as` allowed only in legacy/dev mode.

Exit criteria:

```text
actor cannot accept another actor's obligation
adapter cannot complete task
legacy --as disabled by default
```

## Phase 8 — Adapter convergence

Deliverables:

```text
GitHub signal ingestion
Feishu signal ingestion
sync gateway reads main event store
```

Actions:

- GitHub issue/PR/CI -> Signal -> route -> obligation.
- Feishu message -> Signal, not tmux injection.
- Web/Mac clients read projections and submit commands.

Exit criteria:

```text
adapters do not write organization tables directly
all adapter writes go through command API
sync gateway exposes main event stream
```

## Phase 9 — Legacy cleanup

Actions:

- Convert old board handlers to thin wrappers.
- Remove direct mutation paths.
- Remove message-body dedup logic.
- Deprecate old path-only ownership commands or translate them.
- Update docs and README.

Exit criteria:

```text
all write paths emit events
all current projections rebuild from events
legacy behavior either mapped or explicitly deprecated
```

## Rollback approach

Each phase must be reversible or at least non-destructive.

Rules:

- Do not delete old tables until migration has passed for at least one release.
- Keep migration audit events.
- Keep old command wrappers until replacement CLI is stable.
- Add feature flags for new routing/obligation behavior.

Suggested flags:

```text
CNB_ORG_KERNEL=1
CNB_OWNERSHIP_V2=1
CNB_OBLIGATIONS=1
CNB_DAEMON=1
CNB_LEGACY_IMPERSONATION=1
```

## Suggested first PRs

PR 1:

```text
architecture docs
module manifest
no behavior change
```

PR 2:

```text
event store + command envelope + projection skeleton
```

PR 3:

```text
scope/contract/ownership projections + legacy migration
```

PR 4:

```text
OwnershipResolver + cnb owner route/explain
```

PR 5:

```text
obligations lifecycle + scan route decision integration
```

PR 6:

```text
scoped task completion + verification job
```
