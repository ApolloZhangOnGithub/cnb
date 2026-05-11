# ADR 0001 — Introduce Organization Kernel

## Status

Proposed

## Context

The current system mixes CLI handlers, SQLite mutations, tmux process control, task state changes, ownership routing, and external adapters. This makes it hard to explain responsibility, recover after crashes, and enforce authorization.

## Decision

Introduce `OrgKernel` as the domain entrypoint. All organization state changes go through:

```text
Command -> Policy -> Event -> Projection
```

CLI, adapters, daemon, and scheduler call the kernel rather than directly mutating state.

## Consequences

Positive:

- state changes become auditable,
- projections can be rebuilt,
- adapters cannot bypass policy,
- ownership and obligation flows become explicit.

Negative:

- more upfront structure,
- migration must preserve legacy behavior,
- command/event schema needs careful versioning.
