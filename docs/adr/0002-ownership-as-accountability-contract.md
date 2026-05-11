# ADR 0002 — Model Ownership as Accountability Contract

## Status

Proposed

## Context

Path-prefix ownership is insufficient. It cannot express scope risk, verification standards, owner availability, backup, review rules, handoff, or routing evidence.

## Decision

Model ownership as:

```text
Actor owns Scope under Contract
```

A signal creates a `RouteDecision`, which opens an `Obligation`. The owner must accept, reject, delegate, escalate, or satisfy the obligation.

## Consequences

Positive:

- routing becomes explainable,
- owner rejection becomes useful feedback,
- task execution can be delegated without losing accountability,
- handoff and runtime protection can be enforced.

Negative:

- more concepts than old `session/path_pattern`,
- requires new health and migration logic.
