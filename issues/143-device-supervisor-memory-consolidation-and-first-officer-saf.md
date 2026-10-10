---
number: 143
title: "Device supervisor memory consolidation and first-officer safety loop"
state: OPEN
labels: ["enhancement", "phase:2", "ownership", "infra", "module:runtime", "priority:p1"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #143 Device supervisor memory consolidation and first-officer safety loop

**State:** OPEN
**Labels:** enhancement, phase:2, ownership, infra, module:runtime, priority:p1

---

## Background

Long-running device supervisors accumulate a lot of state: Feishu messages, terminal transcripts, issue decisions, git diffs, test failures, user preferences, and project-local conventions. More memory is useful only if it is layered, reviewable, and periodically consolidated. If it grows as one undifferentiated prompt, it will become expensive, stale, contradictory, and overconfident.

Anthropic's Dreams feature is a useful reference point, but CNB should not copy it as an opaque self-rewrite loop. Officially, Dreams are a Managed Agents research-preview pipeline that reads an existing memory store plus optional past sessions, then writes a separate output memory store for human review; it does not mutate the input store directly.

Reference: https://platform.claude.com/docs/en/managed-agents/dreams

## Problem

CNB currently has a device-supervisor loop, Feishu routing, tmux/session state, issue/board state, and local memory artifacts, but it lacks a disciplined lifecycle for memory and operational safety.

Risks already visible in dogfood:

- stale activity state can keep a Feishu card running after the task is actually done;
- old conclusions can leak into later decisions without source or expiry;
- repeated context summaries can grow without deduplication;
- dirty worktrees and missed checkpoints rely too much on the human owner noticing;
- a single device supervisor can become a single point of failure during migration, crash, or long sessions.

## Proposal

Add a conservative memory consolidation and "first officer" safety loop for device supervisors.

### Memory layers

CNB should treat memory as a pyramid, not one growing prompt:

- raw transcript: Feishu, terminal, tool outputs, git/test logs; archive only;
- flight recorder: compact event stream of who did what and when;
- shift/daily summary: active operational state and handoff;
- project memory: stable conventions, known pitfalls, architecture facts;
- decision/playbook: reviewed rules and reusable procedures;
- active prompt: minimal current-task context only.

### Dream-like consolidation

Implement an auditable local equivalent before relying on provider-specific Dreams:

1. Trigger on schedule, shift end, task completion, or explicit command.
2. Read bounded inputs: recent transcripts, Feishu activity state, issue changes, git diff/status, tests, and cost ledger.
3. Produce a candidate memory delta, not an in-place rewrite.
4. Include sources, timestamps, confidence, and expiry conditions.
5. Let the device supervisor or first officer review/promote the delta.
6. Keep raw evidence available for rollback and dispute resolution.

Possible commands, subject to design:

```bash
cnb memory dream --project <name> --since 24h --dry-run
cnb memory review <delta-id>
cnb memory promote <delta-id> --scope project
cnb memory archive-stale --older-than 30d
```

### First officer role

The "first officer" should not be a second chatty supervisor or a competing CEO. It should be a low-noise safety role:

- detect stuck activity cards, stale open requests, and missed final replies;
- monitor dirty worktree, missing commits/checkpoints, cost burn, and long-running tasks;
- review supervisor conclusions from a separate context when risk is high;
- prepare handoff state for migration to another machine;
- take over only when the primary supervisor is dead, stale, or explicitly transferred;
- run memory consolidation proposals without directly overwriting memory.

## Non-goals

- Do not build a complex HR/management hierarchy here; that belongs to #79.
- Do not claim CNB has provider-grade Dreams before it has an auditable local flow.
- Do not let an agent silently rewrite long-term memory.
- Do not put raw transcripts directly into future prompts by default.
- Do not make the first officer another source of notification noise.

## Acceptance criteria

- There is a documented memory layer model for device supervisors.
- A prototype can generate a candidate memory delta from recent local evidence without modifying existing memory.
- Candidate deltas include sources, confidence, timestamps, and expiry/review guidance.
- A first-officer health check can detect at least stale activity, dirty worktree, long-running sessions, and missing checkpoint risk.
- The primary supervisor remains in control unless failover is explicit or health rules say it is stale.
- The feature is dogfooded on Feishu/device-supervisor workflows before it is generalized.

## Related work

- #121 device supervisor portability and bootstrap
- #129 stale open Feishu activity visibility
- #135 worktree checkpoint and dirty-state guard
- #142 Feishu activity coalescing and done-state reliability
- #79 organization layer, for later team/role modeling beyond a single device supervisor

