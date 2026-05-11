# 03 — Command, Policy, Event, Projection Flow

This document defines how state changes happen.

## The rule

No organization state may change without this flow:

```text
Command -> Authentication -> Authorization -> Policy -> Event -> Projection -> Jobs/Notifications
```

If code changes a projection table directly without an event, it is wrong.

## Command envelope

Every write operation is represented as a command envelope.

```json
{
  "id": "cmd_01J...",
  "project_id": "proj_cnb",
  "actor_id": "lisa-su",
  "type": "AcceptObligation",
  "payload": {
    "obligation_id": "obl_123"
  },
  "idempotency_key": "accept-obl_123-lisa-su",
  "created_at": "2026-05-11T10:00:00Z"
}
```

Fields:

- `id`: unique command id.
- `project_id`: project/org namespace.
- `actor_id`: durable actor identity.
- `type`: command name.
- `payload`: command-specific data.
- `idempotency_key`: optional key to prevent duplicate effects.
- `created_at`: client creation time.

## Command result

Command handlers return structured results.

```json
{
  "ok": true,
  "events": [123, 124],
  "projection_version": 123,
  "message": "Obligation accepted",
  "data": {
    "obligation_id": "obl_123"
  }
}
```

Failure result:

```json
{
  "ok": false,
  "error_code": "not_authorized",
  "message": "actor bob cannot accept obligation owned by lisa-su",
  "policy": "ObligationPolicy.accept"
}
```

## Authentication

Authentication answers:

```text
Who submitted this command?
```

In daemon mode, actor identity comes from capability token, not `--as`.

CLI legacy mode may pass actor explicitly only when `CNB_LEGACY_IMPERSONATION=1`.

## Authorization

Authorization answers:

```text
Does this actor have the capability needed by this command?
```

Examples:

| Command | Required capability |
|---|---|
| `AcceptObligation` | `accept_own_obligation` or manager override |
| `RejectObligation` | `reject_own_obligation` or manager override |
| `AssignTask` | `assign_task` |
| `CompleteTask` | `complete_assigned_task` or owner review capability |
| `TransferOwnership` | `transfer_ownership` |
| `RuntimeStopActor` | `manage_runtime` plus protection policy |
| `SubmitExternalSignal` | `submit_external_signal` |

## Policy

Policy answers:

```text
Even if this actor has a general capability, is this command valid in this exact state?
```

Examples:

- Can this actor accept this obligation?
- Is this obligation still open?
- Does task completion require verification?
- Does this scope require owner review?
- Does stopping this actor require handoff?
- Does this command require user approval?

Policy result:

```text
allow
deny
requires_approval
requires_review
requires_handoff
requires_fallback
```

Policy decisions must include reasons.

## Events

If command passes policy, it appends events.

Example:

```json
{
  "id": 12345,
  "project_id": "proj_cnb",
  "actor_id": "lisa-su",
  "type": "ObligationAccepted",
  "payload_json": {
    "obligation_id": "obl_123"
  },
  "causation_id": "cmd_01J...",
  "correlation_id": "issue_123_flow",
  "created_at": "2026-05-11T10:00:01Z",
  "payload_sha256": "..."
}
```

Event naming convention:

```text
NounPastTense
```

Examples:

```text
ActorRegistered
ScopeImported
OwnershipAssigned
OwnershipTransferRequested
RouteDecisionRecorded
ObligationOpened
ObligationAccepted
ObligationRejected
TaskCreated
TaskCompletionRequested
VerificationJobQueued
VerificationPassed
TaskMovedToReview
TaskDone
SessionStarted
SessionIdleObserved
RuntimeStopDenied
HandoffPrepared
HandoffCompleted
```

## Projection

Projection tables are current-state views.

Event handlers update projections synchronously after appending events.

Projection rules:

- Projection code must be deterministic.
- Projection code must not call external systems.
- Projection code must not run policy checks.
- Projection rebuild from event store must produce the same state as incremental updates.

## Jobs

Some events schedule jobs.

Examples:

| Event | Job |
|---|---|
| `TaskCompletionRequested` | `RunVerification` |
| `ObligationOpened` | `SendNotification` |
| `OwnershipTransferRequested` | `PrepareHandoffChecklist` |
| `SessionStarted` | `CheckSessionHealth` |
| `ScopeImported` | `ValidateScopePatterns` |
| `RouteDecisionRecorded` | `OpenObligation` if route requires action |

Jobs themselves must also append events for durable effects.

## Query flow

Reads do not append events.

```text
CLI query -> daemon/query client -> projection query -> result
```

Queries may enforce visibility rules, but must not change state.

## Idempotency

Commands that may be retried should include idempotency keys.

Examples:

```text
submit external issue signal: github-issue-87-updated-at-...
accept obligation: accept-obl_123-lisa-su
send notification: delivery-del_123-attempt-1
```

Command store checks whether a command with the same project and idempotency key already completed. If so, it returns previous result.

## Error classes

Use stable error codes:

```text
invalid_command
authentication_required
not_authorized
policy_denied
requires_approval
requires_review
requires_handoff
not_found
invalid_state
conflict
idempotency_conflict
storage_error
runtime_error
external_adapter_error
```

## Command examples

### Accept obligation

```text
Command: AcceptObligation
Policy:
  - obligation exists
  - state is open or delegated to this actor
  - actor is owner or delegated actor or manager
Events:
  - ObligationAccepted
Jobs:
  - maybe SendNotification to source thread
```

### Reject obligation

```text
Command: RejectObligation
Policy:
  - obligation exists
  - actor can reject own obligation
  - reason is non-empty
Events:
  - ObligationRejected
  - RouteDecisionRejected
  - FallbackObligationOpened if fallback configured
Jobs:
  - SendNotification to project-manager
  - maybe RoutingPatternSuggestion
```

### Complete task

```text
Command: CompleteTask
Policy:
  - task exists
  - actor is assignee or has manager/owner authority
  - task state is in_progress or reviewable
  - if scoped, load scope contract
Events:
  - TaskCompletionRequested
  - VerificationJobQueued
Jobs:
  - RunVerification
```

Task is not marked done until verification/review/approval events pass.

### Stop runtime actor

```text
Command: RuntimeStopActor
Policy:
  - actor has manage_runtime
  - runtime protection policy checks ownership/open obligations
  - if protected, deny or require handoff/force
Events:
  - RuntimeStopRequested
  - RuntimeStopAllowed or RuntimeStopDenied
Jobs:
  - StopRuntimeSession if allowed
```

## Implementation requirement

Each command handler should be small and structured:

```python
def handle_accept_obligation(ctx, command):
    payload = parse_payload(command)
    obligation = ctx.queries.get_obligation(payload.obligation_id)

    decision = ctx.policies.can_accept_obligation(command.actor_id, obligation)
    if not decision.allowed:
        return CommandResult.denied(decision)

    event = events.ObligationAccepted(...)
    ctx.events.append([event])
    ctx.projections.apply([event])
    ctx.jobs.enqueue_from_events([event])
    return CommandResult.ok(events=[event])
```

No handler should directly edit projection tables except through `ProjectionUpdater`.
