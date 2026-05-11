# 08 — Testing and Quality Gates

This document defines how to test the organization runtime rewrite.

The rewrite is high-risk because it changes the meaning of state, responsibility, and execution. Tests must focus on invariants and recoverability, not only CLI output.

## Test layers

```text
unit tests          pure domain logic
projection tests    event -> current state
integration tests   command -> event -> projection -> jobs
legacy tests        old commands still mapped correctly
security tests      capability and authorization boundaries
runtime tests       backend observations and protection policy
adapter tests       external payload normalization
crash tests         recovery after interrupted jobs/projections
```

## Domain unit tests

### Actor/session tests

Cases:

```text
actor can have many session runs
session crash does not remove actor
actor status can update without changing ownership
session observation does not directly mutate task state
```

### Role/capability tests

Cases:

```text
role grants default capabilities
scoped capability only applies to matching scope
expired capability denied
adapter capability cannot complete task
```

### Scope/contract tests

Cases:

```text
scope import from cnb.org.toml
parent-child scope accepted
invalid duplicate scope rejected
pattern conflicts detected
contract verification plan selected
red flag requires approval
```

### Ownership lifecycle tests

Cases:

```text
green scope claim can activate immediately
yellow scope claim requires approval
critical scope requires owner and backup
only one active owner per scope
transfer requires handoff acceptance
archive keeps route history
orphan owner can activate backup
```

### Routing tests

Use golden fixtures.

Cases:

```text
exact file path routes to child scope over parent
changed file plus label routes confidently
keyword-only route falls below threshold and fallback
close top candidates become conflict
orphan owner chooses backup
owner overloaded routes with cc or fallback
red scope route allowed but completion approval required
```

Route tests must assert:

```text
decision
chosen scope
chosen owner/fallback
confidence range
evidence list
candidate list
reason text
```

### Obligation tests

Cases:

```text
route decision opens obligation
owner can accept own obligation
non-owner cannot accept
owner can reject with reason
reject creates fallback obligation
owner can delegate execution without transferring accountability
satisfy requires required verification/review when linked to task
expired obligation appears in health
```

### Task tests

Cases:

```text
task can reference scope and obligation
task complete emits completion requested, not done
contract verification pass moves to review or done
verification fail returns to in_progress or failed state
non-owner assignee requires owner review
approval-required task waits for approval
```

### Handoff tests

Cases:

```text
transfer request creates handoff
handoff checklist includes open obligations and tasks
new owner must accept
old owner remains protected until handoff completed
completed handoff activates new assignment
cancelled handoff leaves old owner active
```

### Policy tests

Cases:

```text
actor without capability denied
owner can reject own obligation
project-manager can resolve fallback obligation
adapter cannot mutate ownership
protected owner stop denied
force stop requires reason and audit
high-risk change requires approval
```

## Projection tests

Projection tests must compare incremental and rebuilt states.

Pattern:

```text
append events one by one -> apply projections
clear projections -> rebuild from event store
compare all current tables
```

Required projection scenarios:

```text
actor lifecycle
scope import
ownership assign/transfer/archive
route decision and obligation
obligation accept/reject/delegate
scoped task complete + verification
handoff lifecycle
runtime session observations
```

## Command integration tests

Test the full path:

```text
CommandEnvelope -> OrgKernel -> events -> projections -> jobs
```

Scenarios:

```text
issue route flow:
  SubmitExternalSignal -> RouteDecisionRecorded -> ObligationOpened -> SendNotification job

owner accept flow:
  AcceptObligation -> ObligationAccepted -> projection updated

owner reject flow:
  RejectObligation -> ObligationRejected -> fallback obligation

task completion flow:
  CompleteTask -> TaskCompletionRequested -> VerificationJobQueued

handoff flow:
  TransferOwnership -> HandoffChecklistGenerated -> HandoffAccepted -> assignment switch
```

## Runtime tests

### Backend tests

Use mocked subprocess for tmux backend.

Cases:

```text
start constructs expected tmux commands
stop constructs expected tmux commands
send input escapes safely
capture returns snapshot
backend failure returns structured error
```

### Monitor tests

Cases:

```text
snapshot creates observation event
idle-like output creates SessionIdleObserved
crash-like backend result creates SessionCrashedObserved
observation does not directly mark actor offline
```

### Protection tests

Cases:

```text
actor with no ownership can stop
owner with no open obligations requires drain
owner with open obligation denied normal stop
critical owner requires backup or handoff
force stop emits audit event
```

## Scheduler tests

Cases:

```text
due job claimed with lease
leased job not double-claimed
expired lease can be reclaimed
failed job retries with attempts incremented
verification job appends result event
notification job records delivery result
worker crash before projection can recover
```

## Adapter tests

Adapters should be tested for normalization, not domain decisions.

### GitHub

Cases:

```text
issue payload -> Signal with title/body/labels/assignees
PR payload -> Signal with changed files/labels/assignees
CI payload -> Signal with run id/job name/failure summary
adapter does not directly update task/ownership tables
```

### Feishu

Cases:

```text
message payload -> ExternalUserMessage signal
approval button -> ApprovalResponse signal
outbound notification formats reply
adapter does not tmux send
```

### Sync gateway

Cases:

```text
GET /events returns main event store events
projection endpoint reads projection table
POST /commands uses command path
no separate gateway event truth
```

## Security tests

Required cases:

```text
missing token denied
expired token denied
wrong actor cannot accept obligation
adapter token cannot complete task
legacy --as disabled unless flag enabled
actor cannot use capability outside scope
high-risk approval cannot be self-granted unless policy allows
```

## Crash and recovery tests

Cases:

```text
event appended but projection interrupted -> rebuild fixes projection
job running and daemon dies -> lease expires -> job reclaimed
notification sent but completion event missing -> idempotency prevents duplicate or records retry safely
verification process fails -> task not marked done
projection rebuild after migration matches expected state
```

## Legacy compatibility tests

While migration is active, old commands must either work or emit explicit deprecation errors.

Cases:

```text
board --as alice own claim lib/
board --as alice own list
board --as alice task add "..."
board --as alice task done <id>
board --as alice inbox
board --as alice status "..."
```

Expected behavior:

- old command maps to new command when possible,
- output remains acceptable,
- state changes emit events,
- legacy impersonation requires explicit mode once daemon/capability phase begins.

## Golden files

Keep golden output fixtures for:

```text
cnb owner route issue
cnb owner explain
cnb owner health
cnb org health
cnb owner brief
cnb task show
```

Golden tests make explanations stable and readable.

## Quality gates

A PR that changes stateful behavior must pass:

```text
unit tests
projection rebuild tests
command integration tests
security tests if command/auth touched
legacy tests if board compatibility touched
migration tests if schema touched
```

Code review questions:

```text
Does this write path submit a command?
Does it authenticate actor identity?
Does it check capability?
Does policy explain allow/deny?
Does it append event?
Can projection rebuild reproduce state?
Can crash/retry duplicate side effects?
Does this create or close an obligation?
Does this affect ownership, authority, or runtime protection?
```

## Forbidden patterns in tests

Do not write tests that assume:

```text
message body is dedup key
pane text means agent ready
--as is trustworthy identity
path prefix alone is enough ownership
verification pass means task can skip owner review
notification sent means obligation accepted
```

Those assumptions are exactly what the rewrite is trying to remove.
