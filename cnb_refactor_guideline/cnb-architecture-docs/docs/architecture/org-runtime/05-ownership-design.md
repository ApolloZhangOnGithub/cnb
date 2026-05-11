# 05 — Ownership Design

Ownership is the central organization concept in cnb.

It must not degrade into `session owns path_pattern`.

## Definition

Ownership is an accountability contract:

```text
Actor owns Scope under Contract.
```

It means the actor is accountable for scope health, triage, review, verification, escalation, and handoff.

It does not mean the owner personally executes every task.

## Why ownership exists

AI actors are not stable human teammates. They restart, lose context, get killed, change models, forget previous work, and may misinterpret signals.

Ownership exists to maintain responsibility continuity despite those discontinuities.

It answers:

1. Which scope does this signal belong to?
2. Who is accountable for that scope?
3. Why did we decide that?
4. Is the owner available and capable?
5. What standard defines completion?
6. What happens if the owner goes away?

## Main concepts

```text
Scope             responsibility boundary
Contract          rules and completion standards for the scope
Assignment        current owner/backup for the scope
RouteDecision     explainable decision from signal to scope/owner/fallback
Obligation        activated responsibility item
Task              execution work that may satisfy obligation
Handoff           continuity process for ownership transfer
Protection        runtime safety rule for active owners
Brief             memory summary for owner restart
```

## Scope

A scope is a responsibility boundary.

Examples:

```text
feishu-bridge
ownership-routing
dispatcher-runtime
package-publishing
security-secret-scan
docs-readme-sync
```

A scope can be described by:

```text
paths
labels
keywords
tests
CI jobs
external systems
doc sections
symbols
```

Example TOML:

```toml
[[scope]]
id = "feishu-bridge"
kind = "integration"
title = "Feishu bridge"
risk_level = "yellow"
paths = [
  "lib/feishu_bridge.py",
  "tests/test_feishu_bridge.py",
  "docs/feishu-bridge.md"
]
labels = ["feishu", "lark", "bridge", "integration"]
keywords = ["webhook", "Feishu", "device supervisor", "resource handoff"]
```

## Contract

A contract defines what responsible operation means for a scope.

Example:

```toml
[scope.feishu-bridge.contract]
verify = [
  "python -m pytest tests/test_feishu_bridge.py -q",
  "ruff check lib/feishu_bridge.py tests/test_feishu_bridge.py"
]
review_required = true
handoff_required = true
stop_protection = "protected"
low_confidence_fallback = "project-manager"
conflict_fallback = "project-manager"
requires_user_approval_if = [
  "auth token handling",
  "public webhook behavior",
  "allowed chat id policy"
]
```

Contract responsibilities:

- choose verification plan,
- decide if owner review is required,
- identify red-flag changes,
- define handoff requirements,
- define runtime protection,
- define fallback actor for routing ambiguity.

## Assignment

Assignment binds owner to scope.

States:

```text
proposed
active
probation
transferring
orphaned
suspended
archived
```

Lifecycle:

```text
unowned -> proposed -> active -> transferring -> archived
active -> orphaned -> backup_active or transfer_requested
```

Rules:

- Critical scopes must have owner and backup.
- A scope can have only one accountable active owner.
- Backup does not automatically become accountable until backup activation or transfer.
- Assignment state changes must be events.

## Routing

Routing converts a signal into a route decision.

Input examples:

```text
issue
PR
CI failure
user request
runtime alert
file path
```

Output:

```text
RouteDecision
```

Never output only a string owner.

### Evidence sources

Strong evidence:

```text
explicit task/issue link
GitHub assignee
changed file exact scope path
```

Medium evidence:

```text
changed file parent path
issue/PR label
path mentioned in text
CI job/test file
```

Weak evidence:

```text
keyword
historical accepted route
owner health
```

### Routing decisions

```text
routed       confident route to owner
routed_cc    medium confidence; owner + project-manager copied
fallback     route to project-manager/fallback
conflict     multiple close candidates; fallback
ignored      no action needed
```

### Decision thresholds

```text
score >= 0.80:
  routed

0.55 <= score < 0.80:
  routed_cc, requires ack

score < 0.55:
  fallback

top1 - top2 < 0.15:
  conflict

owner orphaned:
  backup or fallback

owner overloaded:
  owner + backup cc or fallback depending policy
```

### Route explanation

Every route decision must record candidates and evidence.

Example:

```json
{
  "decision": "routed",
  "scope": "feishu-bridge",
  "owner": "lisa-su",
  "confidence": 0.88,
  "evidence": [
    {"kind": "label", "value": "feishu", "weight": 0.25},
    {"kind": "path", "value": "lib/feishu_bridge.py", "weight": 0.45},
    {"kind": "keyword", "value": "webhook", "weight": 0.10},
    {"kind": "owner_health", "value": "heartbeat 8m ago", "weight": 0.08}
  ]
}
```

## Obligation

A route decision that requires action opens an obligation.

Obligation states:

```text
open
accepted
rejected
delegated
escalated
satisfied
expired
cancelled
```

Owner actions:

```bash
cnb obligation accept obl_123
cnb obligation reject obl_123 "wrong scope"
cnb obligation delegate obl_123 bob
cnb obligation escalate obl_123 "needs user approval"
cnb obligation satisfy obl_123
```

Important distinction:

```text
notification sent != obligation accepted
```

## Rejection as first-class signal

If owner rejects an obligation, record it and fallback.

Flow:

```text
ObligationRejected
RouteDecisionRejected
FallbackObligationOpened
RoutingPatternSuggestionCreated
```

Rejections are not errors. They are routing feedback.

Metrics:

```text
accepted route count
rejected route count
fallback count
conflict count
owner average ack time
```

## Delegation vs transfer

Delegation:

```text
owner gives execution task to another actor
owner remains accountable
```

Transfer:

```text
ownership accountability moves to another actor after handoff
```

Never use one `assign` operation for both.

## Handoff

Handoff keeps ownership continuity.

States:

```text
requested
checklist_generated
prepared
accepted
completed
cancelled
```

Checklist includes:

```text
scope contract
open obligations
active tasks
dirty files
unmerged PRs
pending approvals
known risks
recent route decisions
recent rejected routes
verification history
handoff note
```

Transfer flow:

```text
TransferRequested
HandoffChecklistGenerated
HandoffPrepared
HandoffAccepted
OldAssignmentArchived
NewAssignmentActivated
```

Until completed, old owner remains protected.

## Owner protection

Active ownership affects runtime.

Stop rules:

```text
no ownership:
  allow stop

ownership but no open obligation:
  drain first

open obligation:
  deny normal stop

critical scope:
  require backup active or handoff complete

manual force:
  allow only with audit event and reason
```

Owner protection must be checked by:

```text
runtime stop
idle killer
scale down
restart
session cleanup
```

## Owner brief

Owner brief is the memory interface for AI actors.

It should include:

```text
actor identity
roles and capabilities
owned scopes
scope contracts
open obligations
delegated tasks
pending reviews
known risks
recent accepted/rejected routes
recent verification results
handoff notes
runtime protection status
```

Generated by:

```bash
cnb owner brief lisa-su
```

Used when starting or waking owner sessions.

## Ownership health

Health is more important than owner map.

`cnb owner health` should report:

```text
coverage:
  critical/yellow scopes with active owners

orphans:
  active owners with stale/no sessions and open obligations

conflicts:
  overlapping scopes causing ambiguous routing

overload:
  owners with too many active obligations/scopes

routing quality:
  accepted/rejected/fallback/conflict counts

stale contracts:
  scopes whose verification has not run recently

handoff debt:
  handoffs stuck in requested/prepared states
```

## Implementation stages

### Stage 1 — Scope and assignment

- Add scopes, patterns, contracts, ownership assignments.
- Migrate legacy `path_pattern` ownership into legacy scopes.

### Stage 2 — Resolver and route decisions

- Implement `OwnershipResolver`.
- Make `find_owner(path)` use resolver internally for compatibility.
- Add `cnb owner route` and `cnb owner explain`.

### Stage 3 — Obligations

- Route decisions open obligations.
- Owner can accept/reject/delegate/escalate/satisfy.

### Stage 4 — Task integration

- Tasks reference scope and obligation.
- Completion uses scope contract verification.

### Stage 5 — Handoff and protection

- Implement handoff lifecycle.
- Runtime stop checks owner protection.

### Stage 6 — Brief and health

- Generate owner brief.
- Compute ownership health.

## Acceptance tests

Minimum tests:

```text
exact path routes to child scope over parent
label + keyword route works
low confidence fallback
close candidates conflict fallback
orphan owner routes to backup
owner reject creates fallback obligation
delegation does not transfer accountability
transfer requires handoff accepted
protected owner cannot be idle-killed
scoped task completion runs contract verification
owner brief includes open obligations and known risks
```
