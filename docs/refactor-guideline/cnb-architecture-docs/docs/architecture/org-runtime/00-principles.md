# 00 — Principles, Goals, Non-Goals, and Invariants

## Goal

cnb should become a local-first AI organization runtime.

It must help multiple AI actors collaborate around a project while preserving:

- responsibility continuity,
- explicit authority,
- explainable routing,
- durable memory,
- verifiable work completion,
- safe handoff,
- recoverability after crashes and restarts.

## Non-goals for the first rewrite

Do not start with:

- cloud multi-tenancy,
- complex workflow DSLs,
- black-box routing models,
- full UI rewrite,
- replacing tmux immediately,
- mandatory ownership for every file,
- full daemonization before the domain model is stable.

The first implementation may run in library mode, but it must already be structured as if it will later run behind `cnbd`.

## Core invariants

### I1. Organization facts only change through commands and events

Allowed:

```text
submit command -> authenticate -> authorize -> validate -> append event -> update projection
```

Forbidden:

```text
CLI handler -> direct SQLite UPDATE
adapter -> direct ownership/task mutation
dispatcher -> direct status mutation from tmux observation
Feishu bridge -> tmux send that changes organization facts
```

### I2. Actor is not session

`Actor` is a durable identity.

`SessionRun` is one runtime instance of that actor.

Ownership must bind to actor identity, not tmux pane, terminal session, or process ID.

### I3. Scope is not path

A path may be evidence for a scope. A scope is a responsibility boundary.

A scope can be defined by paths, labels, keywords, CI jobs, tests, external systems, docs, or symbols.

### I4. Ownership is not task assignment

Ownership is accountability for a scope.

A task is an execution unit that may be delegated.

The owner may delegate work but remains accountable until obligation satisfaction, transfer, or archive.

### I5. Message is not obligation

A notification tells someone something.

An obligation requires an accountable actor to accept, reject, delegate, escalate, or satisfy.

Every routed external signal that requires responsibility must create an obligation, not only a message.

### I6. Runtime observation is not organization truth

tmux output, prompt shape, pane command, and capture text are observations.

They can create events such as `SessionIdleObserved`, but policy and projections decide state.

### I7. Low confidence must fallback

The routing system must prefer fallback over silent misrouting.

If confidence is low, candidates conflict, owner is orphaned, or scope is ambiguous, route to project-manager or configured fallback.

### I8. Responsibility requires authority

An owner must have enough authority to close its obligations: review changes, reject wrong routing, request verification, delegate execution, and escalate risk.

High-risk actions may still require supervisor or user approval.

### I9. Every state transition must be explainable

A human or AI reviewer must be able to answer:

- What command caused this?
- Which actor submitted it?
- Which policy allowed or denied it?
- Which events were produced?
- Which projection changed?
- Which obligations or tasks are affected?

### I10. Rebuild must be possible

Projection tables are views. Events are the durable fact source.

`cnb store rebuild-projections` must reconstruct current views from events.

## Architectural review checklist

For any new code path that changes state, ask:

1. Is this a command?
2. Who is the actor?
3. What capability is required?
4. Which policy authorizes it?
5. Which event is appended?
6. Which projection changes?
7. Can it be rebuilt from events?
8. Does it create, close, or affect an obligation?
9. Does it require a job, notification, review, or approval?
10. Can it recover after process crash?
