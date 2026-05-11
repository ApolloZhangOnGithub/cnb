# 01 — Domain Model

This document defines the vocabulary for the rewrite. These words must be used consistently across code, schema, tests, CLI, and docs.

## Organization

An organization is the project-local system of actors, roles, scopes, ownership, work, authority, communication, and memory.

It is not merely a list of running agents.

An organization answers:

- Who exists?
- Who has which role?
- Who owns which scope?
- Who can decide what?
- What signals are active?
- What obligations are open?
- What tasks are being executed?
- What counts as done?
- What memory must be restored after restart?

## Actor

An actor is a durable identity.

Examples:

- `device-supervisor`
- `project-manager`
- `lisa-su`
- `dario`
- `github-adapter`
- `feishu-adapter`

Actor fields:

```text
id
kind: human | ai | system | adapter
display_name
status
roles
capabilities
created_at
updated_at
```

Actor is not a process. Actor is not a tmux pane.

## SessionRun

A session run is one runtime instance of an actor.

Fields:

```text
id
actor_id
engine: claude | codex | qwen | shell
backend: tmux | process | screen
runtime_ref
state: starting | ready | busy | idle | stopped | crashed
started_at
last_heartbeat
stopped_at
```

A single actor can have many session runs over time.

A session crash must not erase ownership.

## Role

A role is a behavior template, not responsibility ownership.

Examples:

- `device-supervisor`
- `project-manager`
- `scope-owner`
- `executor`
- `reviewer`
- `release-manager`
- `adapter`

Role answers: "How may this actor act?"

Ownership answers: "What scope is this actor accountable for?"

## Capability

A capability is a permission to submit a command or perform a class of actions.

Examples:

```text
read_own_inbox
ack_own_delivery
accept_own_obligation
reject_own_obligation
delegate_own_obligation
update_own_status
create_task
complete_assigned_task
review_owned_scope
assign_task
transfer_ownership
approve_high_risk_action
manage_runtime
submit_external_signal
```

Capabilities may be scoped:

```text
actor lisa-su has review_owned_scope for scope feishu-bridge
```

## Scope

A scope is a responsibility boundary.

A scope may correspond to a module, service, integration, release process, security concern, runtime concern, or documentation area.

Scope is not equal to path.

Fields:

```text
id
kind: module | service | integration | runtime | docs | release | security | infra
title
description
parent_scope_id
risk_level: green | yellow | red | critical
active
```

Scope patterns may include:

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

## Contract

A contract defines what responsible operation of a scope means.

It includes:

- verification commands,
- review rules,
- approval rules,
- handoff requirements,
- runtime protection,
- escalation policy,
- red flags.

Without a contract, ownership is only a label.

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
requires_user_approval_if = [
  "auth token handling",
  "public webhook behavior",
  "allowed chat id policy"
]
```

## OwnershipAssignment

Ownership is an accountability relationship between actor and scope.

Fields:

```text
id
scope_id
owner_actor_id
backup_actor_id
state: proposed | active | probation | transferring | orphaned | suspended | archived
source: manual | migration | handoff | inferred
confidence
assigned_by
assigned_at
accepted_at
archived_at
```

Ownership does not mean the owner must execute every task. It means the owner is accountable for scope health, triage, review, verification, escalation, and handoff.

## Signal

A signal is input that may require organization response.

Examples:

- GitHub issue
- GitHub PR
- CI failure
- user request
- Feishu message
- runtime alert
- file change
- scheduled check

A signal does not directly become a task. It first goes through routing.

## RouteDecision

A route decision explains how a signal was interpreted.

Fields:

```text
id
source_type
source_id
decision: routed | routed_cc | fallback | conflict | ignored
chosen_scope_id
chosen_owner_actor_id
fallback_actor_id
confidence
candidates_json
evidence_json
reason
created_at
```

A route decision must be explainable.

## Obligation

An obligation is ownership activated by a signal.

Fields:

```text
id
route_decision_id
scope_id
owner_actor_id
kind: triage | fix | review | verify | maintain | handoff
source_type
source_id
state: open | accepted | rejected | delegated | escalated | satisfied | expired | cancelled
delegated_to
due_at
created_at
updated_at
```

Owner actions:

```text
accept
reject
delegate
escalate
satisfy
```

The organization cannot assume responsibility was accepted until the obligation state says so.

## Task

A task is an execution unit.

Fields:

```text
id
title
description
source_type
source_id
obligation_id
scope_id
creator_actor_id
assignee_actor_id
state: draft | assigned | accepted | in_progress | blocked | awaiting_user | verifying | review | done | failed | cancelled
priority
risk_level
verification_policy_id
created_at
updated_at
```

A task may satisfy an obligation, but it is not itself the accountability relationship.

## Job

A job is a durable system action.

Examples:

- `RunVerification`
- `SendNotification`
- `RouteGitHubIssue`
- `RouteCIFailure`
- `GenerateOwnerBrief`
- `DetectOrphanOwner`
- `PrepareHandoffChecklist`
- `CaptureSessionSnapshot`
- `CheckSessionHealth`

Jobs are scheduled, leased, retried, and recoverable.

## Artifact

An artifact is something produced or modified by work.

Examples:

- file diff,
- PR,
- issue comment,
- verification result,
- release package,
- migration file,
- documentation change.

Artifacts should connect tasks and obligations to concrete outputs.

## Policy

A policy decides whether a command or state transition is allowed, denied, requires approval, requires review, requires fallback, or requires handoff.

Examples:

- ownership policy,
- routing policy,
- task policy,
- runtime protection policy,
- handoff policy,
- approval policy,
- notification policy.

## Memory

Memory is durable organizational history.

It includes:

- events,
- route decisions,
- accepted/rejected obligations,
- verification results,
- handoff notes,
- reviews,
- generated briefs.

Prompt is not memory. Prompt consumes memory.

## Main relationships

```text
Organization contains Actors, Scopes, Policies, Memory.
Actor occupies Roles and holds Capabilities.
Actor runs SessionRuns.
Scope has Contract and Patterns.
Actor owns Scope through OwnershipAssignment.
Signal produces RouteDecision.
RouteDecision opens Obligation.
Obligation may create Task, Review, Escalation, or Handoff.
Task creates Jobs and Artifacts.
Contract defines Verification and Review.
Events record all durable facts.
Projections expose current views.
Briefs summarize memory for AI actors.
```
