# 06 — Runtime, Scheduler, and Adapters

This document defines how execution, timers, external systems, and process control relate to the organization kernel.

## Rule

Runtime, scheduler, and adapters are servants of the organization kernel. They are not sources of organization truth.

```text
runtime observes and executes process operations
scheduler runs durable jobs
adapters translate external systems to signals/notifications
org kernel decides organization state
```

## cnbd

`cnbd` is the local daemon and single-writer coordinator.

Responsibilities:

- accept local commands and queries,
- authenticate capability tokens,
- call `OrgKernel`,
- serialize writes,
- own scheduler worker lifecycle,
- expose event/projection stream to clients,
- coordinate runtime backend calls.

Non-responsibilities:

- implementing domain policies,
- owning GitHub/Feishu semantics,
- embedding CLI output formatting.

## Runtime backend

The runtime backend controls processes.

Interface:

```python
class RuntimeBackend:
    def start(self, spec) -> RuntimeRef: ...
    def stop(self, runtime_ref) -> StopResult: ...
    def send_input(self, runtime_ref, text: str) -> SendResult: ...
    def capture(self, runtime_ref) -> Snapshot: ...
```

`tmux` is one backend. The design must allow future backends.

## Runtime observations

Runtime monitor converts backend state into observation events.

Examples:

```text
SessionSnapshotCaptured
SessionHeartbeatObserved
SessionIdleObserved
SessionBusyObserved
SessionCrashedObserved
```

Observation events are facts about what was observed, not final organization conclusions.

Example:

```text
Observed: pane has prompt-like marker
Not allowed: mark task done
```

## Session state

Session state is projection built from events.

States:

```text
starting
ready
busy
idle
stopped
crashed
```

Runtime events:

```text
SessionStartRequested
SessionStarted
SessionReadyObserved
SessionHeartbeatObserved
SessionIdleObserved
SessionBusyObserved
SessionStopRequested
SessionStopped
SessionCrashedObserved
```

## Runtime protection

Before stopping or restarting a session, runtime must ask policy.

Policy inputs:

```text
actor_id
reason
active ownership assignments
open obligations
scope risk levels
handoff state
backup availability
force flag
```

Outcomes:

```text
allow
deny
requires_handoff
requires_force_audit
requires_backup_activation
```

Example:

```text
actor lisa-su owns feishu-bridge
open obligation issue#123 exists
runtime stop requested by idle killer
=> deny, reason protected_owner_has_open_obligation
```

## Scheduler

The scheduler replaces ad-hoc dispatcher concern loops.

It runs durable jobs.

Job table fields:

```text
id
type
state
run_after
lease_owner
lease_until
attempts
payload_json
created_at
updated_at
```

Job flow:

```text
claim due job
  -> acquire lease
  -> execute
  -> append events
  -> update projections
  -> enqueue follow-up jobs
  -> mark succeeded/failed
```

Lease expiry allows crash recovery.

## Job types

### `RunVerification`

Input:

```text
task_id
scope_id
verification_plan
```

Output events:

```text
VerificationStarted
VerificationPassed or VerificationFailed
TaskMovedToReview or TaskDone or TaskReturnedToInProgress
```

### `SendNotification`

Input:

```text
recipient
channel
related_type
related_id
body
```

Output events:

```text
NotificationAttempted
NotificationDelivered or NotificationFailed
```

### `RouteGitHubIssue`

Input:

```text
issue payload or issue id
```

Output events:

```text
ExternalSignalReceived
RouteDecisionRecorded
ObligationOpened
```

### `RouteCIFailure`

Input:

```text
run id
job name
failed files
logs summary
```

Output events:

```text
RouteDecisionRecorded
ObligationOpened or FallbackObligationOpened
```

### `GenerateOwnerBrief`

Input:

```text
actor_id
```

Output:

```text
OwnerBriefGenerated
```

### `DetectOrphanOwner`

Input:

```text
actor_id or project_id
```

Output:

```text
OwnershipMarkedOrphaned
BackupActivationRequested
OrphanObligationOpened
```

### `PrepareHandoffChecklist`

Input:

```text
handoff_id
```

Output:

```text
HandoffChecklistGenerated
```

### `CaptureSessionSnapshot`

Input:

```text
session_id
```

Output:

```text
SessionSnapshotCaptured
```

### `CheckSessionHealth`

Input:

```text
session_id
```

Output:

```text
SessionHeartbeatObserved
SessionCrashedObserved
SessionIdleObserved
```

## Adapter rule

Adapters translate. They do not decide organization state.

Allowed:

```text
external event -> Signal -> SubmitExternalSignal command
notification request -> external reply/send
```

Forbidden:

```text
adapter -> update task table
adapter -> assign owner directly
adapter -> mark obligation accepted
adapter -> tmux send organization command to bypass policy
```

## GitHub adapter

Inputs:

```text
issue
PR
CI failure
comment
review
```

Outputs to org kernel:

```text
ExternalSignalReceived
```

For PRs, adapter should normalize:

```text
changed files
labels
assignees
review requests
CI job names
```

For CI failures, adapter should normalize:

```text
run id
job name
failed tests
failed files if known
summary
```

GitHub adapter may send comments only when scheduler/job requests a notification or reply.

## Feishu adapter

Inputs:

```text
user message
button action
approval response
```

Outputs to org kernel:

```text
ExternalUserMessageReceived
ApprovalResponseReceived
```

Forbidden:

```text
start supervisor tmux session directly
inject raw command into tmux pane
mutate task/ownership tables
```

Flow:

```text
Feishu message
  -> Signal
  -> device-supervisor/project-manager route
  -> command/obligation/task as needed
  -> FeishuReplyRequested
  -> adapter sends reply
```

## Sync gateway

The sync gateway must publish the main event store and projections.

It must not maintain a separate client-visible event truth.

Endpoints:

```text
GET /events?after=<event_id>
GET /projections/ownership
GET /projections/tasks
GET /projections/org-health
POST /commands
```

Write endpoint submits command envelopes and uses the same policy path.

## Web or Mac companion

These clients read projections and submit commands.

They are not privileged by being local UI.

All writes must pass capability and policy.

## Failure recovery

### Runtime backend failure

- record `RuntimeOperationFailed`,
- do not mutate organization state beyond failure event,
- schedule retry or escalation if policy says so.

### Scheduler crash

- job lease expires,
- another worker reclaims,
- idempotency prevents duplicate side effects.

### Adapter failure

- record notification/sync failure,
- retry with backoff,
- do not mark obligation/task completed.

### Projection corruption

- rebuild projections from events,
- compare projection version to latest event id.

## Metrics

Runtime/scheduler/adapter health should expose:

```text
running sessions by actor
stale sessions
protected stop denials
job backlog by type
failed jobs by type
notification failure rate
adapter sync lag
projection lag
```
