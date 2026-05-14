# 04 — Data Model

This document defines the SQLite layout for the organization runtime.

The database has three categories:

1. append-only facts: `events`, `commands`,
2. current-state projections: `*_current`,
3. durable execution state: `jobs_current`.

## Design rules

- Events are the durable fact source.
- Projection tables are rebuildable.
- Jobs are durable and recoverable.
- Migrations must support legacy board data.
- External adapters must not own a separate truth database for organization facts.

## Event store

```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    causation_id TEXT,
    correlation_id TEXT,
    created_at TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL
);

CREATE INDEX idx_events_project_id ON events(project_id, id);
CREATE INDEX idx_events_type ON events(type);
CREATE INDEX idx_events_correlation ON events(correlation_id);
```

Notes:

- `causation_id` usually points to command id or job id.
- `correlation_id` groups a flow such as issue routing or handoff.
- `payload_sha256` helps detect corruption and debugging mistakes.

## Command log

```sql
CREATE TABLE commands (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    idempotency_key TEXT,
    state TEXT NOT NULL,
    result_json TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE UNIQUE INDEX idx_commands_idempotency
ON commands(project_id, idempotency_key)
WHERE idempotency_key IS NOT NULL;
```

Command states:

```text
received
running
succeeded
failed
```

## Actors

```sql
CREATE TABLE actors_current (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE actor_roles_current (
    actor_id TEXT NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY(actor_id, role)
);

CREATE TABLE actor_capabilities_current (
    actor_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    scope_id TEXT,
    expires_at TEXT,
    PRIMARY KEY(actor_id, capability, scope_id)
);
```

## Sessions

```sql
CREATE TABLE sessions_current (
    id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    engine TEXT NOT NULL,
    backend TEXT NOT NULL,
    runtime_ref TEXT NOT NULL,
    state TEXT NOT NULL,
    started_at TEXT NOT NULL,
    last_heartbeat TEXT,
    stopped_at TEXT
);

CREATE INDEX idx_sessions_actor_state
ON sessions_current(actor_id, state);
```

Session states:

```text
starting
ready
busy
idle
stopped
crashed
```

## Scopes

```sql
CREATE TABLE scopes_current (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    parent_scope_id TEXT,
    risk_level TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE scope_patterns_current (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_id TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    pattern TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    UNIQUE(scope_id, pattern_type, pattern)
);

CREATE INDEX idx_scope_patterns_type_pattern
ON scope_patterns_current(pattern_type, pattern);
```

Pattern types:

```text
path
label
keyword
test_file
ci_job
symbol
doc_section
external_system
```

## Contracts

```sql
CREATE TABLE contracts_current (
    scope_id TEXT PRIMARY KEY,
    contract_json TEXT NOT NULL,
    imported_from TEXT,
    version TEXT,
    updated_at TEXT NOT NULL
);
```

Contract details stay JSON because policies will evolve faster than basic projections.

## Ownership

```sql
CREATE TABLE ownership_current (
    id TEXT PRIMARY KEY,
    scope_id TEXT NOT NULL,
    owner_actor_id TEXT NOT NULL,
    backup_actor_id TEXT DEFAULT '',
    state TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    assigned_by TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    accepted_at TEXT,
    archived_at TEXT
);

CREATE UNIQUE INDEX idx_one_active_owner_per_scope
ON ownership_current(scope_id)
WHERE state IN ('active', 'probation', 'transferring');

CREATE INDEX idx_ownership_owner
ON ownership_current(owner_actor_id, state);
```

Ownership states:

```text
proposed
active
probation
transferring
orphaned
suspended
archived
```

## Route decisions

```sql
CREATE TABLE route_decisions_current (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    chosen_scope_id TEXT,
    chosen_owner_actor_id TEXT,
    fallback_actor_id TEXT DEFAULT '',
    confidence REAL NOT NULL,
    candidates_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    reason TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX idx_route_source
ON route_decisions_current(source_type, source_id);

CREATE INDEX idx_route_owner
ON route_decisions_current(chosen_owner_actor_id, created_at);
```

Decisions:

```text
routed
routed_cc
fallback
conflict
ignored
```

## Obligations

```sql
CREATE TABLE obligations_current (
    id TEXT PRIMARY KEY,
    route_decision_id TEXT,
    scope_id TEXT NOT NULL,
    owner_actor_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    state TEXT NOT NULL,
    delegated_to TEXT DEFAULT '',
    due_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_obligations_owner_state
ON obligations_current(owner_actor_id, state);

CREATE INDEX idx_obligations_scope_state
ON obligations_current(scope_id, state);

CREATE INDEX idx_obligations_source
ON obligations_current(source_type, source_id);
```

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

## Tasks

```sql
CREATE TABLE tasks_current (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    source_type TEXT,
    source_id TEXT,
    obligation_id TEXT,
    scope_id TEXT,
    creator_actor_id TEXT NOT NULL,
    assignee_actor_id TEXT,
    state TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal',
    risk_level TEXT NOT NULL DEFAULT 'green',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_tasks_assignee_state
ON tasks_current(assignee_actor_id, state);

CREATE INDEX idx_tasks_scope_state
ON tasks_current(scope_id, state);

CREATE INDEX idx_tasks_obligation
ON tasks_current(obligation_id);
```

Task states:

```text
draft
assigned
accepted
in_progress
blocked
awaiting_user
verifying
review
done
failed
cancelled
```

## Verification

```sql
CREATE TABLE verification_runs_current (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    scope_id TEXT,
    state TEXT NOT NULL,
    command_json TEXT NOT NULL,
    result_json TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_verification_task
ON verification_runs_current(task_id);
```

States:

```text
queued
running
passed
failed
cancelled
```

## Handoffs

```sql
CREATE TABLE handoffs_current (
    id TEXT PRIMARY KEY,
    scope_id TEXT NOT NULL,
    from_actor_id TEXT NOT NULL,
    to_actor_id TEXT NOT NULL,
    state TEXT NOT NULL,
    checklist_json TEXT NOT NULL DEFAULT '{}',
    handoff_note TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE INDEX idx_handoffs_scope_state
ON handoffs_current(scope_id, state);
```

States:

```text
requested
checklist_generated
prepared
accepted
completed
cancelled
```

## Jobs

```sql
CREATE TABLE jobs_current (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    state TEXT NOT NULL,
    run_after TEXT NOT NULL,
    lease_owner TEXT,
    lease_until TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_jobs_due
ON jobs_current(state, run_after);

CREATE INDEX idx_jobs_lease
ON jobs_current(lease_until);
```

Job states:

```text
queued
running
succeeded
failed
cancelled
```

## Deliveries and notifications

```sql
CREATE TABLE deliveries_current (
    id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    recipient_actor_id TEXT,
    external_recipient TEXT,
    subject TEXT DEFAULT '',
    body TEXT NOT NULL,
    related_type TEXT,
    related_id TEXT,
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_deliveries_related
ON deliveries_current(related_type, related_id);
```

Important: deliveries reference obligations, route decisions, tasks, approvals, or handoffs. Message body is not the source of truth.

## Approvals

```sql
CREATE TABLE approvals_current (
    id TEXT PRIMARY KEY,
    requested_by TEXT NOT NULL,
    requested_from TEXT NOT NULL,
    related_type TEXT NOT NULL,
    related_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
```

States:

```text
requested
granted
denied
expired
cancelled
```

## Health projections

Health can be computed on demand or cached.

If cached:

```sql
CREATE TABLE org_health_current (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    computed_at TEXT NOT NULL
);
```

## Legacy migration mapping

Old table to new model:

| Old concept | New concept |
|---|---|
| `sessions.name` | `actors_current.id` plus `sessions_current` |
| `ownership.session` | `ownership_current.owner_actor_id` |
| `ownership.path_pattern` | legacy `scope` with `path` pattern |
| `tasks.session` | `tasks_current.assignee_actor_id` |
| `messages/inbox` | `deliveries_current` and possibly conversation projection |
| `pending_actions` | obligation/task/approval depending on semantics |

Migration should append migration events, not silently seed only projections.

Example migration event:

```text
LegacyOwnershipMigrated
payload:
  old_session: alice
  old_path_pattern: lib/
  new_scope_id: legacy-path-lib
  new_owner_actor_id: alice
```

## Projection rebuild procedure

1. Start transaction.
2. Clear all `*_current` tables.
3. Replay events in order.
4. Apply projection handlers.
5. Record projection version equal to last event id.
6. Commit.

Do not replay commands. Events are the fact source.
