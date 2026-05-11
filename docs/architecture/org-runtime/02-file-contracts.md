# 02 — File Contracts

This document explains exactly what each proposed source file should contain.

The point is not only package organization. The point is preventing responsibility drift.

Every file below has:

- **Purpose** — why the file exists.
- **Contains** — allowed classes/functions.
- **Must not contain** — boundaries that prevent future mess.
- **Public surface** — expected interfaces.
- **Tests** — where behavior should be tested.

## Layer rules

```text
bin/                 process shims only
lib/cnb/cli/          parse args, print output, submit commands
lib/cnb/daemon/       local API, single-writer coordination, capability auth
lib/cnb/org/          domain concepts, policies, command handlers
lib/cnb/store/        persistence, events, commands, projections, migrations
lib/cnb/scheduler/    durable jobs and leases
lib/cnb/runtime/      process/tmux backend and observations
lib/cnb/adapters/     external systems as signal/notification adapters
lib/cnb/legacy/       compatibility wrappers only
```

Dependency direction:

```text
cli -> daemon client or org kernel
adapter -> command/signal API
scheduler -> org services + store
runtime -> backend primitives only
org -> store interfaces, not concrete CLI
store -> no org policy decisions
```

Forbidden dependency examples:

```text
org imports cli                      forbidden
store imports tmux backend           forbidden
adapter mutates projection directly  forbidden
runtime changes task state           forbidden
cli updates SQLite directly          forbidden
```

---

# bin/

## `bin/cnb`

**Purpose**

Executable shim for the main CLI.

**Contains**

Only shell or Python bootstrap that execs `python -m cnb.cli.main` or installed console entry.

**Must not contain**

- business logic,
- database access,
- tmux control,
- ownership logic,
- update checks mixed with command execution.

**Public surface**

```bash
cnb <subcommand> ...
```

**Tests**

Smoke test that `bin/cnb --help` dispatches to CLI.

## `bin/board`

**Purpose**

Legacy compatibility shim.

**Contains**

Argument translation from old `board --as actor ...` form into new command API where possible.

**Must not contain**

New features. It should shrink over time.

**Public surface**

Existing board commands only.

**Tests**

Legacy compatibility tests.

---

# `lib/cnb/cli/`

CLI files parse arguments, call a command client or local kernel, and render output. They do not decide policy.

## `lib/cnb/cli/main.py`

**Purpose**

Top-level CLI entrypoint and subcommand router.

**Contains**

- `main(argv=None) -> int`
- construction of subparsers,
- dispatch to subcommand modules,
- common output format flags,
- error rendering.

**Must not contain**

- direct SQLite writes,
- ownership resolver logic,
- policy checks,
- tmux calls.

**Public surface**

```python
def main(argv: list[str] | None = None) -> int
```

**Tests**

CLI parser smoke tests and command dispatch tests.

## `lib/cnb/cli/client.py`

**Purpose**

Client for sending command envelopes to `cnbd`, or to in-process `OrgKernel` during pre-daemon phase.

**Contains**

- `CommandClient`
- daemon socket request/response handling,
- fallback to local kernel when daemon disabled,
- timeout and retry behavior for command submission.

**Must not contain**

- domain policy,
- projection update logic,
- command construction for specific domains beyond generic envelope submission.

**Public surface**

```python
class CommandClient:
    def submit(self, command: CommandEnvelope) -> CommandResult: ...
    def query(self, query: QueryEnvelope) -> QueryResult: ...
```

**Tests**

Fake daemon client tests; local mode tests.

## `lib/cnb/cli/org.py`

**Purpose**

CLI commands for organization-wide status and health.

**Contains**

Commands:

```bash
cnb org health
cnb org brief
cnb org actors
cnb org scopes
```

**Must not contain**

Health calculation logic. It should call query APIs.

**Public surface**

```python
def register(subparsers) -> None
```

**Tests**

Output rendering tests with fixed query results.

## `lib/cnb/cli/owner.py`

**Purpose**

CLI commands for scope, ownership, routing, handoff, and owner health.

**Contains**

Commands:

```bash
cnb owner scope list
cnb owner scope show <scope>
cnb owner route issue <id>
cnb owner explain <decision-id>
cnb owner claim <scope>
cnb owner assign <scope> <actor>
cnb owner transfer <scope> <from> <to>
cnb owner health
cnb owner brief <actor>
```

**Must not contain**

- resolver scoring,
- route decision storage,
- handoff policy.

**Public surface**

```python
def register(subparsers) -> None
```

**Tests**

Golden CLI output for route explanation and health.

## `lib/cnb/cli/obligation.py`

**Purpose**

CLI commands for obligation lifecycle.

**Contains**

Commands:

```bash
cnb obligation list
cnb obligation show <id>
cnb obligation accept <id>
cnb obligation reject <id> <reason>
cnb obligation delegate <id> <actor>
cnb obligation escalate <id> <reason>
cnb obligation satisfy <id>
```

**Must not contain**

State transition legality. It submits commands only.

**Public surface**

```python
def register(subparsers) -> None
```

**Tests**

Command envelope construction tests.

## `lib/cnb/cli/task.py`

**Purpose**

CLI commands for task lifecycle.

**Contains**

Commands:

```bash
cnb task add
cnb task list
cnb task show
cnb task accept
cnb task block
cnb task complete
```

**Must not contain**

- verification execution,
- direct task state changes,
- review policy.

**Public surface**

```python
def register(subparsers) -> None
```

**Tests**

Command envelope and output tests.

## `lib/cnb/cli/runtime.py`

**Purpose**

CLI commands for runtime sessions.

**Contains**

Commands:

```bash
cnb runtime list
cnb runtime start <actor>
cnb runtime stop <actor>
cnb runtime restart <actor>
cnb runtime capture <actor>
```

**Must not contain**

- direct tmux calls,
- stop protection logic,
- session state mutation.

**Public surface**

```python
def register(subparsers) -> None
```

**Tests**

Runtime command envelope tests.

---

# `lib/cnb/daemon/`

Daemon files manage local API, single-writer behavior, command authentication, and scheduling coordination.

## `lib/cnb/daemon/main.py`

**Purpose**

Entrypoint for `cnbd`.

**Contains**

- daemon argument parsing,
- startup/shutdown,
- initialization of store, kernel, scheduler, runtime backends,
- signal handling.

**Must not contain**

Domain command logic.

**Public surface**

```python
def main(argv: list[str] | None = None) -> int
```

**Tests**

Daemon startup smoke with temp project.

## `lib/cnb/daemon/ipc.py`

**Purpose**

Local IPC protocol over Unix socket or local HTTP.

**Contains**

- request/response schema,
- socket server/client helpers,
- serialization/deserialization,
- basic timeouts.

**Must not contain**

- command policy,
- domain-specific routing,
- database schema.

**Public surface**

```python
class IpcServer: ...
class IpcClient: ...
```

**Tests**

Round-trip serialization and error handling.

## `lib/cnb/daemon/auth.py`

**Purpose**

Validate actor capability tokens and daemon-local identities.

**Contains**

- token loading,
- token verification,
- actor resolution,
- expiration checks.

**Must not contain**

Authorization policy beyond token validity. Domain capability checks live in `org/policies.py`.

**Public surface**

```python
class Authenticator:
    def authenticate(self, request) -> AuthenticatedActor: ...
```

**Tests**

Token valid/expired/missing cases.

## `lib/cnb/daemon/server.py`

**Purpose**

Request handler connecting IPC to command/query handlers.

**Contains**

- receive command/query,
- authenticate,
- call `OrgKernel`,
- return result,
- structured error mapping.

**Must not contain**

Domain logic or SQL.

**Public surface**

```python
class DaemonServer:
    def handle_request(self, request) -> response: ...
```

**Tests**

Command request integration with fake kernel.

---

# `lib/cnb/org/`

The org package owns domain rules. It should be mostly pure Python and heavily tested.

## `lib/cnb/org/kernel.py`

**Purpose**

Single entrypoint for domain commands and queries.

**Contains**

- command dispatch,
- transaction boundaries through store unit of work,
- invocation of policy services,
- event appending,
- projection update request,
- job scheduling request.

**Must not contain**

- CLI parsing,
- tmux operations,
- adapter-specific API calls.

**Public surface**

```python
class OrgKernel:
    def handle_command(self, command: CommandEnvelope) -> CommandResult: ...
    def handle_query(self, query: QueryEnvelope) -> QueryResult: ...
```

**Tests**

End-to-end domain command tests with in-memory/temp SQLite store.

## `lib/cnb/org/commands.py`

**Purpose**

Typed command envelope and domain command payloads.

**Contains**

- dataclasses or pydantic-like typed structures,
- command type constants,
- validation of payload shape only.

**Must not contain**

- policy decisions,
- database writes,
- CLI output.

**Public surface**

```python
@dataclass(frozen=True)
class CommandEnvelope: ...
```

**Tests**

Payload validation tests.

## `lib/cnb/org/events.py`

**Purpose**

Typed event definitions.

**Contains**

- event names,
- event payload dataclasses,
- serialization helpers,
- schema versioning for event payloads.

**Must not contain**

Projection logic.

**Public surface**

```python
@dataclass(frozen=True)
class Event: ...
def make_event(...) -> Event: ...
```

**Tests**

Event serialization and version compatibility tests.

## `lib/cnb/org/actors.py`

**Purpose**

Actor domain model and actor lifecycle commands.

**Contains**

- actor creation/update logic,
- actor status updates,
- actor lookup helpers,
- actor-state events.

**Must not contain**

Session runtime backend logic. Session state lives in `sessions.py`.

**Public surface**

```python
class ActorService:
    def register_actor(...): ...
    def update_status(...): ...
```

**Tests**

Actor registration, status, duplicate actor tests.

## `lib/cnb/org/roles.py`

**Purpose**

Role definitions and role assignment semantics.

**Contains**

- role constants,
- default capabilities per role,
- role assignment validation.

**Must not contain**

Ownership assignment. Roles are not ownership.

**Public surface**

```python
ROLE_PROJECT_MANAGER = "project-manager"
def default_capabilities_for_role(role: str) -> set[str]: ...
```

**Tests**

Role default capability tests.

## `lib/cnb/org/capabilities.py`

**Purpose**

Capability data model and capability checks.

**Contains**

- capability constants,
- scope-aware capability matching,
- expiration-aware capability evaluation.

**Must not contain**

Token authentication. That is daemon auth.

**Public surface**

```python
class CapabilityService:
    def has_capability(actor_id, capability, scope_id=None) -> bool: ...
```

**Tests**

Scoped capability matching tests.

## `lib/cnb/org/sessions.py`

**Purpose**

SessionRun domain state and session events.

**Contains**

- session state transitions,
- handling runtime observations,
- mapping actor to current sessions.

**Must not contain**

Actual tmux/process calls. Runtime backend lives in `runtime/`.

**Public surface**

```python
class SessionService:
    def record_started(...): ...
    def record_observation(...): ...
    def mark_stopped(...): ...
```

**Tests**

Session state machine tests.

## `lib/cnb/org/scopes.py`

**Purpose**

Scope model, scope pattern import, and scope validation.

**Contains**

- scope definitions,
- pattern loading from org spec,
- conflict detection between scopes,
- scope hierarchy checks.

**Must not contain**

Routing decisions. Resolver lives in `routing.py`.

**Public surface**

```python
class ScopeService:
    def import_spec(...): ...
    def validate_scopes(...): ...
    def list_active_scopes(...): ...
```

**Tests**

Scope import, parent-child, overlap detection tests.

## `lib/cnb/org/contracts.py`

**Purpose**

Scope contract model and contract evaluation helpers.

**Contains**

- verification command selection,
- review policy evaluation,
- red-flag detection inputs,
- contract freshness metadata.

**Must not contain**

Running shell commands. Verification execution is scheduler/runtime job.

**Public surface**

```python
class ContractService:
    def verification_plan_for(scope_id, task_id=None) -> VerificationPlan: ...
    def review_required_for(change) -> ReviewDecision: ...
```

**Tests**

Contract plan and review decision tests.

## `lib/cnb/org/ownership.py`

**Purpose**

Ownership assignment lifecycle.

**Contains**

- claim,
- assign,
- transfer request,
- archive,
- orphan marking,
- backup activation,
- active-owner uniqueness enforcement at domain level.

**Must not contain**

Routing score calculation. That is `routing.py`.

**Public surface**

```python
class OwnershipService:
    def claim_scope(...): ...
    def assign_owner(...): ...
    def request_transfer(...): ...
    def mark_orphaned(...): ...
```

**Tests**

Ownership lifecycle tests.

## `lib/cnb/org/routing.py`

**Purpose**

Resolve signals to explainable route decisions.

**Contains**

- `Signal` model,
- fact extraction,
- candidate collection,
- evidence scoring,
- decision policy for fallback/conflict/routed,
- route explanation construction.

**Must not contain**

Notification delivery, task creation, database SQL.

**Public surface**

```python
class OwnershipResolver:
    def resolve(self, signal: Signal) -> RouteDecision: ...
```

**Tests**

Golden route cases for issue/PR/CI/path/user request.

## `lib/cnb/org/obligations.py`

**Purpose**

Obligation lifecycle and state transitions.

**Contains**

- open obligation from route decision,
- accept,
- reject,
- delegate,
- escalate,
- satisfy,
- expiration rules.

**Must not contain**

Task execution or verification execution.

**Public surface**

```python
class ObligationService:
    def open_from_route(...): ...
    def accept(...): ...
    def reject(...): ...
    def delegate(...): ...
    def escalate(...): ...
    def satisfy(...): ...
```

**Tests**

Obligation state machine and authorization tests.

## `lib/cnb/org/tasks.py`

**Purpose**

Task lifecycle and relationship to obligations/scopes.

**Contains**

- create task,
- assign,
- accept,
- block,
- request completion,
- move to verification/review/done based on events.

**Must not contain**

Running verification commands. It schedules jobs.

**Public surface**

```python
class TaskService:
    def create_task(...): ...
    def request_completion(...): ...
    def apply_verification_result(...): ...
```

**Tests**

Task state transition tests.

## `lib/cnb/org/handoff.py`

**Purpose**

Ownership transfer continuity.

**Contains**

- handoff checklist generation,
- handoff preparation,
- acceptance,
- completion,
- handoff note validation.

**Must not contain**

Direct git operations. It can request data from adapter/services via interfaces.

**Public surface**

```python
class HandoffService:
    def prepare_checklist(...): ...
    def accept(...): ...
    def complete(...): ...
```

**Tests**

Transfer requires handoff tests.

## `lib/cnb/org/policies.py`

**Purpose**

Domain policy decisions.

**Contains**

- command authorization,
- ownership policy,
- routing policy,
- task policy,
- runtime protection policy,
- handoff policy,
- approval policy.

**Must not contain**

Persistence code or CLI rendering.

**Public surface**

```python
class PolicyEngine:
    def authorize_command(...): ...
    def evaluate_task_completion(...): ...
    def evaluate_runtime_stop(...): ...
```

**Tests**

Policy matrix tests.

## `lib/cnb/org/health.py`

**Purpose**

Compute organization health and ownership health from projections.

**Contains**

- unowned critical scope detection,
- orphaned owner detection,
- overloaded owner detection,
- route quality summary,
- stale contract detection,
- handoff debt detection.

**Must not contain**

State mutation.

**Public surface**

```python
class HealthService:
    def org_health(...): ...
    def ownership_health(...): ...
```

**Tests**

Health scenario tests.

## `lib/cnb/org/memory.py`

**Purpose**

Generate briefs from durable memory.

**Contains**

- owner brief,
- task brief,
- project brief,
- handoff brief,
- memory query helpers.

**Must not contain**

Prompt templates that invent policy. Briefs summarize existing facts and contracts.

**Public surface**

```python
class BriefService:
    def owner_brief(actor_id) -> Brief: ...
    def task_brief(task_id) -> Brief: ...
    def project_brief() -> Brief: ...
```

**Tests**

Golden brief tests.

## `lib/cnb/org/approvals.py`

**Purpose**

High-risk action approval lifecycle.

**Contains**

- approval request creation,
- approval grant/deny,
- approval expiration,
- policy integration for red flags.

**Must not contain**

External messaging delivery. Notification service sends approval requests.

**Public surface**

```python
class ApprovalService:
    def request_approval(...): ...
    def grant(...): ...
    def deny(...): ...
```

**Tests**

Approval-required and approval-expired tests.

---

# `lib/cnb/store/`

Store files persist commands, events, projections, and migrations. They do not decide domain policy.

## `lib/cnb/store/unit_of_work.py`

**Purpose**

Transaction boundary for command handling.

**Contains**

- SQLite connection management,
- begin/commit/rollback,
- accessors for event store, command store, projection writer, job store.

**Must not contain**

Domain rules.

**Public surface**

```python
class UnitOfWork:
    def __enter__(self): ...
    def commit(self): ...
    def rollback(self): ...
```

**Tests**

Rollback and commit behavior tests.

## `lib/cnb/store/event_store.py`

**Purpose**

Append and read durable events.

**Contains**

- append events,
- read by id range,
- read by correlation,
- idempotent append under command transaction,
- payload hashing.

**Must not contain**

Projection logic or domain rules.

**Public surface**

```python
class EventStore:
    def append(self, events: list[Event]) -> list[int]: ...
    def read_after(self, event_id: int, limit: int = 1000) -> list[Event]: ...
```

**Tests**

Append/read/hash tests.

## `lib/cnb/store/command_store.py`

**Purpose**

Persist command envelopes and idempotency results.

**Contains**

- record command received,
- check idempotency key,
- record command completion/failure,
- command result caching.

**Must not contain**

Policy decisions.

**Public surface**

```python
class CommandStore:
    def begin_command(...): ...
    def complete_command(...): ...
```

**Tests**

Idempotency tests.

## `lib/cnb/store/projections.py`

**Purpose**

Apply events to current-state projection tables.

**Contains**

- projection handlers by event type,
- rebuild projections from event store,
- projection version metadata.

**Must not contain**

Command validation. Projection applies already-authorized events.

**Public surface**

```python
class ProjectionUpdater:
    def apply(self, events: list[Event]) -> None: ...
    def rebuild(self) -> None: ...
```

**Tests**

Projection rebuild equals incremental update.

## `lib/cnb/store/queries.py`

**Purpose**

Read-only projection queries for CLI, daemon, and services.

**Contains**

- typed query methods,
- projection reads,
- no mutation.

**Must not contain**

Policy logic. Query may filter by actor if caller already authorized.

**Public surface**

```python
class QueryStore:
    def get_task(...): ...
    def list_obligations(...): ...
```

**Tests**

Projection query tests.

## `lib/cnb/store/migrations.py`

**Purpose**

Schema migration runner.

**Contains**

- migration discovery,
- applied migration tracking,
- upgrade path,
- legacy schema migration helpers.

**Must not contain**

Business logic beyond data migration.

**Public surface**

```python
class MigrationRunner:
    def upgrade(self) -> None: ...
```

**Tests**

Fresh DB and legacy DB migration tests.

---

# `lib/cnb/scheduler/`

## `lib/cnb/scheduler/jobs.py`

**Purpose**

Job model, job types, and job payload validation.

**Contains**

- job dataclasses,
- job type constants,
- payload schema validation.

**Must not contain**

Job execution logic.

**Public surface**

```python
@dataclass(frozen=True)
class Job: ...
```

**Tests**

Payload validation tests.

## `lib/cnb/scheduler/worker.py`

**Purpose**

Claim, execute, and finalize durable jobs.

**Contains**

- claim due jobs,
- execute by job type,
- append resulting events,
- retry/failure behavior.

**Must not contain**

Domain state mutation outside command/event path.

**Public surface**

```python
class SchedulerWorker:
    def run_once(self) -> int: ...
```

**Tests**

Job execution and failure recovery tests.

## `lib/cnb/scheduler/leases.py`

**Purpose**

Lease acquisition and expiration logic.

**Contains**

- atomic job lease claim,
- lease expiry,
- worker identity.

**Must not contain**

Job-specific behavior.

**Public surface**

```python
class LeaseManager:
    def claim_due_jobs(...): ...
```

**Tests**

Lease expiry/reclaim tests.

---

# `lib/cnb/runtime/`

Runtime files manage processes and observations only. They do not decide organization facts.

## `lib/cnb/runtime/backend.py`

**Purpose**

Abstract runtime backend interface.

**Contains**

```python
class RuntimeBackend:
    def start(self, spec) -> RuntimeRef: ...
    def stop(self, runtime_ref) -> StopResult: ...
    def send_input(self, runtime_ref, text: str) -> SendResult: ...
    def capture(self, runtime_ref) -> Snapshot: ...
```

**Must not contain**

Concrete tmux commands or domain policy.

**Tests**

Interface contract tests with fake backend.

## `lib/cnb/runtime/tmux_backend.py`

**Purpose**

Concrete tmux runtime backend.

**Contains**

- tmux session creation,
- stop,
- send input,
- capture pane,
- runtime ref parsing.

**Must not contain**

- owner protection decisions,
- task mutation,
- routing.

**Public surface**

```python
class TmuxBackend(RuntimeBackend): ...
```

**Tests**

Unit tests with mocked subprocess; optional integration tests behind flag.

## `lib/cnb/runtime/monitor.py`

**Purpose**

Convert runtime backend observations into observation events.

**Contains**

- heartbeat capture,
- snapshot capture,
- idle/busy observation heuristics,
- crash observation.

**Must not contain**

Final state decisions. It emits observations.

**Public surface**

```python
class RuntimeMonitor:
    def observe_session(session_id) -> list[Event]: ...
```

**Tests**

Observation generation tests.

## `lib/cnb/runtime/protection.py`

**Purpose**

Runtime stop/restart protection integration.

**Contains**

- calls to policy engine,
- conversion of runtime stop requests into commands/events,
- force-stop audit support.

**Must not contain**

tmux stop implementation.

**Public surface**

```python
class RuntimeProtectionService:
    def evaluate_stop(actor_id, reason) -> StopDecision: ...
```

**Tests**

Protected owner stop denial tests.

---

# `lib/cnb/adapters/`

Adapters translate external systems into signals and notifications. They do not mutate organization state directly.

## `lib/cnb/adapters/github.py`

**Purpose**

GitHub issue/PR/CI adapter.

**Contains**

- fetch/receive GitHub events,
- normalize into `Signal`,
- submit signal command,
- post comments/replies when requested by notification job.

**Must not contain**

Ownership resolver logic or direct SQLite updates.

**Public surface**

```python
class GitHubAdapter:
    def ingest_issue(...): ...
    def ingest_pr(...): ...
    def ingest_ci_failure(...): ...
```

**Tests**

GitHub payload normalization tests.

## `lib/cnb/adapters/feishu.py`

**Purpose**

Feishu/Lark message adapter.

**Contains**

- inbound message normalization,
- submit external signal,
- outbound reply sending when notification job requests it.

**Must not contain**

Direct tmux send, direct supervisor launch, task mutation.

**Public surface**

```python
class FeishuAdapter:
    def ingest_message(...): ...
    def send_reply(...): ...
```

**Tests**

Feishu payload normalization and outbound formatting tests.

## `lib/cnb/adapters/sync_gateway.py`

**Purpose**

Expose events/projections to clients.

**Contains**

- `GET /events?after=` behavior,
- read-only projection endpoints,
- command submission endpoint if gateway supports writes.

**Must not contain**

Separate event truth. It must publish the main event store, not its own parallel event log.

**Public surface**

```python
class SyncGateway: ...
```

**Tests**

Event stream and projection endpoint tests.

## `lib/cnb/adapters/web.py`

**Purpose**

Web UI adapter if needed.

**Contains**

- read projections,
- submit commands,
- render minimal server endpoints.

**Must not contain**

Domain policy logic.

**Tests**

Endpoint authorization and command submission tests.

---

# `lib/cnb/legacy/`

Legacy files preserve old behavior while migration proceeds.

## `lib/cnb/legacy/board_compat.py`

**Purpose**

Translate old board commands to new commands.

**Contains**

- old argument parsing,
- legacy output formatting,
- compatibility warnings,
- mapping to `OrgKernel` commands.

**Must not contain**

New domain behavior.

**Public surface**

```python
def board_main(argv: list[str] | None = None) -> int
```

**Tests**

Old command compatibility tests.

## `lib/cnb/legacy/migrations.py`

**Purpose**

Migrate old board data into new events/projections.

**Contains**

- old `ownership(session, path_pattern)` migration,
- old `tasks` migration,
- old `messages/inbox` migration,
- old session migration,
- migration audit events.

**Must not contain**

Runtime logic.

**Public surface**

```python
class LegacyMigrator:
    def migrate(self) -> MigrationReport: ...
```

**Tests**

Legacy DB fixture migration tests.

---

# File ownership of concepts

Use this table when deciding where code belongs.

| Concept | Owner file | Notes |
|---|---|---|
| Actor identity | `org/actors.py` | durable identity only |
| Session runtime state | `org/sessions.py` | domain state, not tmux calls |
| Role defaults | `org/roles.py` | no ownership assignment |
| Capability checks | `org/capabilities.py` + `org/policies.py` | token auth stays in daemon |
| Scope definitions | `org/scopes.py` | patterns and hierarchy |
| Contract rules | `org/contracts.py` | plan verification/review; do not run commands |
| Ownership lifecycle | `org/ownership.py` | assign/claim/transfer/archive |
| Routing decision | `org/routing.py` | explainable candidates/evidence |
| Obligation lifecycle | `org/obligations.py` | accept/reject/delegate/escalate/satisfy |
| Task lifecycle | `org/tasks.py` | execution unit state machine |
| Handoff | `org/handoff.py` | transfer continuity |
| Policy | `org/policies.py` | allow/deny/requires review/approval/fallback |
| Health | `org/health.py` | read-only analysis |
| Briefs | `org/memory.py` | summarize facts for AI actors |
| Events | `org/events.py` + `store/event_store.py` | event definition vs persistence |
| Projections | `store/projections.py` | current state views |
| Runtime backend | `runtime/*` | process control only |
| Job scheduling | `scheduler/*` | durable execution |
| External systems | `adapters/*` | signal/notification boundary only |

## File-level red flags

If a file begins to do any of the following, split or move code immediately:

- CLI file imports sqlite directly.
- Adapter writes projection tables.
- Runtime backend checks ownership state.
- Store layer decides policy.
- Routing sends notifications directly.
- Task service runs shell verification directly.
- Ownership service calculates issue keyword scores.
- Handoff service mutates tmux sessions.
- Health service appends events.
- Brief service invents facts not present in memory.
