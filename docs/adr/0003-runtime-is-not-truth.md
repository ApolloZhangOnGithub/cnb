# ADR 0003 — Runtime Observation Is Not Organization Truth

## Status

Proposed

## Context

tmux pane content and process status are unreliable as organization truth. A prompt marker does not mean an agent is ready; a changed pane does not mean progress; a stopped pane does not mean ownership is gone.

## Decision

Runtime backends only start, stop, send input, and capture snapshots. Runtime monitor emits observation events. Organization state is decided by policy and projections.

## Consequences

Positive:

- process control is isolated,
- owner protection can be enforced,
- future backends can replace tmux.

Negative:

- idle/health logic must move into explicit observation and policy services,
- some old heuristics need migration.
