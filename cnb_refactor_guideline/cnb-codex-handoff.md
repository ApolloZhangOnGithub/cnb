# Codex handoff — cnb org-runtime refactor

## Context

We are refactoring `ApolloZhangOnGithub/cnb` from a mixed CLI/tmux/SQLite script system into a local-first AI organization runtime.

Do **not** start with a big rewrite. The first goal is to establish architecture docs, stabilize legacy behavior with characterization tests, then implement a thin vertical slice:

```text
Command -> Policy -> Event -> Projection
Signal -> RouteDecision -> Obligation
```

## Hard rules

1. Keep `main` usable after every PR.
2. Do not remove legacy `board`/`cnb` behavior in early phases.
3. Do not introduce `cnbd` first; build library-mode kernel first.
4. All new organization state changes must go through command/event/projection.
5. Do not directly mutate SQLite outside store/projection/migration code.
6. Do not let adapters or runtime code mutate org state directly.
7. Treat runtime/tmux output as observation, not truth.
8. Keep PRs small and reviewable.
9. Every new state transition needs tests.
10. Update architecture docs if a file responsibility changes.

## Attach/apply first

Apply the architecture docs patch before coding:

```bash
git apply /path/to/cnb-architecture-docs.patch
```

After applying, read:

```text
docs/architecture/org-runtime/README.md
docs/architecture/org-runtime/00-principles.md
docs/architecture/org-runtime/01-domain-model.md
docs/architecture/org-runtime/02-file-contracts.md
docs/architecture/org-runtime/module-manifest.yaml
docs/adr/0001-org-runtime-kernel.md
docs/adr/0002-ownership-as-accountability-contract.md
docs/adr/0003-runtime-is-not-truth.md
```

## First PR: architecture docs only

Goal: merge the architecture package with no behavior change.

Allowed changes:

```text
docs/architecture/org-runtime/**
docs/adr/**
```

Acceptance:

- docs added;
- no runtime code changes;
- no test behavior changes;
- docs describe file responsibilities clearly enough for implementation PRs.

## Second PR: characterization tests for legacy behavior

Goal: lock important old behavior before changing internals.

Add or improve tests for:

```text
board own claim/list/map
find_owner path/prefix/longest-prefix behavior
scan issue route/dedup behavior
task add/list/done behavior
inbox send/ack behavior
```

Allowed changes:

```text
tests/**
```

Only change source code if a test helper is impossible without a tiny harmless seam.

Acceptance:

- legacy tests pass;
- tests document current behavior, even if behavior is imperfect;
- no architecture rewrite yet.

## Third PR: OrgKernel and event-store skeleton

Goal: add minimal infrastructure without taking over old commands.

Create these files:

```text
lib/cnb/org/commands.py
lib/cnb/org/events.py
lib/cnb/org/kernel.py
lib/cnb/org/policies.py
lib/cnb/store/event_store.py
lib/cnb/store/command_store.py
lib/cnb/store/projections.py
lib/cnb/store/unit_of_work.py
```

Implement only:

```text
Command dataclass / typed envelope
Event dataclass / typed envelope
OrgKernel.handle(command)
PolicyDecision allow/deny/requires_approval
EventStore.append/list_since
CommandStore idempotency record
Projection hook interface
one dummy command + one dummy event for tests only
```

Do not wire legacy commands yet, except optionally through tests.

Acceptance:

- a command can produce an event;
- idempotency prevents duplicate command effects;
- projections can be rebuilt in a minimal test;
- no legacy command behavior changes.

## Fourth PR: Ownership v2 path-routing vertical slice

Goal: implement the first real vertical slice:

```text
cnb owner route path <path>
cnb owner explain <route-decision-id>
```

Create or implement:

```text
lib/cnb/org/scopes.py
lib/cnb/org/ownership.py
lib/cnb/org/routing.py
lib/cnb/org/health.py        # only minimal placeholder if needed
lib/cnb/cli/owner.py
```

Add projections/tables as needed for:

```text
scopes_current
scope_patterns_current
ownership_current
route_decisions_current
```

Required behavior:

- scopes can have path patterns;
- ownership assignment binds durable actor to scope;
- route path returns a RouteDecision, not a bare owner string;
- route decision includes candidates, evidence, confidence, decision, reason;
- exact child scope beats broad parent scope when confidence is clear;
- close competing candidates return conflict/fallback;
- no match returns fallback;
- `explain` prints stored evidence.

Acceptance:

```bash
cnb owner route path lib/feishu_bridge.py
cnb owner explain <route-decision-id>
```

must work in tests.

Do not modify Feishu/GitHub/runtime/dispatcher in this PR.

## Fifth PR: obligations minimal slice

Goal: convert route decisions into accountable obligations.

Implement:

```text
obligations_current
ObligationOpened
ObligationAccepted
ObligationRejected
ObligationDelegated
ObligationEscalated
ObligationSatisfied
```

CLI:

```bash
cnb obligation list
cnb obligation accept <id>
cnb obligation reject <id> "reason"
cnb obligation delegate <id> <actor>
cnb obligation escalate <id> "reason"
cnb obligation satisfy <id>
```

Acceptance:

- owner can accept own obligation;
- non-owner cannot accept;
- reject records reason and creates fallback/project-manager follow-up if configured;
- delegation does not transfer accountability;
- tests cover state transitions.

## Review checklist for every PR

Ask before merging:

1. Which refactor scope does this PR belong to?
2. Which files are allowed by `module-manifest.yaml`?
3. Does it bypass command/event/projection?
4. Does it directly mutate SQLite outside store/projection/migration?
5. Does it put domain policy in CLI/adapters/runtime?
6. Does it keep legacy behavior working?
7. Does it add domain tests?
8. Can projections be rebuilt?
9. Can a reviewer explain every new state transition?
10. Is the PR small enough to revert safely?

## Non-goals until later

Do not implement yet:

```text
full cnbd daemon
capability tokens
runtime owner protection
Feishu adapter rewrite
GitHub adapter rewrite
Task v2 full migration
full scheduler migration
legacy cleanup
```

Those come after the first organization kernel, ownership route, and obligation slices are stable.
