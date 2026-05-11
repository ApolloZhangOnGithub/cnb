# cnb Org Runtime Architecture

This directory is the authoritative architecture guide for the cnb rewrite.

The rewrite is not a cosmetic package split. The goal is to turn cnb from a collection of tmux/SQLite/CLI scripts into a local-first AI organization runtime.

Core promise:

> Any signal entering cnb must be explainably routed to a scope, become an accountable obligation, be acted on by an authorized actor, and leave durable organizational memory.

## Reading order

1. `00-principles.md` — goals, non-goals, invariants, and forbidden shortcuts.
2. `01-domain-model.md` — vocabulary and concept relationships.
3. `02-file-contracts.md` — exact responsibility of every proposed source file.
4. `03-command-event-policy.md` — command handling, policy checks, events, projections.
5. `04-data-model.md` — SQLite schema and projection strategy.
6. `05-ownership-design.md` — ownership, scope, contract, routing, obligation, handoff.
7. `06-runtime-scheduler-adapters.md` — daemon, runtime backend, scheduler, external adapters.
8. `07-migration-plan.md` — incremental migration from current board scripts.
9. `08-testing-and-quality.md` — test matrix, quality gates, and review checklist.
10. `module-manifest.yaml` — machine-readable file map for implementation planning.

## Architectural center

The architectural center is `lib/cnb/org/`, not `bin/`, not `tmux`, and not a database table.

The central flow is:

```text
Command -> Authentication -> Policy -> Event -> Projection -> Job/Notification
```

The central organization loop is:

```text
Signal -> RouteDecision -> Obligation -> Task/Review/Escalation -> Verification -> Memory
```

## What this document set should prevent

It should prevent these failure modes:

- A file becomes a grab bag of helpers.
- A command handler directly mutates SQLite.
- An adapter bypasses policy and updates organization state directly.
- Runtime observation is treated as truth.
- Ownership degenerates back to `session owns path_pattern`.
- A message is mistaken for responsibility acceptance.
- An AI agent restart loses responsibility context.
