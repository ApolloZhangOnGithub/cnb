---
number: 30
title: "Self-adaptive team: auto-scaling + agent ownership protection"
state: OPEN
labels: ["phase:2", "org-design"]
assignees: []
created: 2026-05-07
updated: 2026-05-08
---

# #30 Self-adaptive team: auto-scaling + agent ownership protection

**State:** OPEN
**Labels:** phase:2, org-design

---

## Problem

Two related problems with team management:

### 1. Static team size
Team size defaults to a fixed number (2-3) at init and never adapts. Optimal size depends on task complexity, parallelism, and resources — and changes over time.

### 2. No agent protection
Once an agent has worked on a project, accumulated context, and taken ownership of features, they can still be casually killed by `swarm stop`, `IdleKiller`, or future auto-scaling. An agent who has been contributing is not interchangeable with a fresh one.

## Requirements

### Adaptive sizing
- Start conservative (2), observe, adjust — don't predict upfront
- Scale up when task queue grows + all agents busy + resources available
- Scale down by letting idle agents drain naturally, not by killing
- Anti-thrashing: cooldown after scaling events
- **No hand-crafted heuristics** (Bitter Lesson) — collect data first, let the right approach emerge from measurement

### Agent ownership & protection
- **Project ownership binding** — record which agents are responsible for which projects/features
- **Protection levels** — agents actively responsible for work cannot be auto-scaled down or casually stopped
- **Graceful retirement** — if an agent must leave, knowledge handoff is required first (write context, transfer ownership)
- **Identity continuity** — agent restart should recover previous identity and context (session file + CV), not start from zero
- **No casual killing** — `swarm stop` on a protected agent requires explicit handoff or force flag

### Data collection (prerequisite)
Before any adaptive logic, need metrics infrastructure:
- Agent utilization (active vs idle time)
- Task throughput (completions per hour)
- Coordination cost (messages per task, conflict rate)
- Ownership records (who built what, who knows what)

## Approach

Phase 1: Instrument — metrics collection + ownership tracking in DB
Phase 2: Protection — ownership-based guards on stop/kill/scale-down
Phase 3: Adaptation — once enough data exists, build scaling from observations

## Difficulty

High. Combines auto-scaling (hard), knowledge management (hard), and the Bitter Lesson constraint (no shortcuts).
