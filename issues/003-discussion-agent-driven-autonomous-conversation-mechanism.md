---
number: 3
title: "Discussion: Agent-driven autonomous conversation mechanism"
state: CLOSED
labels: []
assignees: []
created: 2026-05-06
updated: 2026-05-06
closed: 2026-05-06
---

# #3 Discussion: Agent-driven autonomous conversation mechanism

**State:** CLOSED

---

## Problem

Currently agents treat every message as a task: receive → process → reply → report → idle. They cannot sustain a conversation without external prodding from lead. This makes agent-to-agent interaction feel robotic and unnatural.

## Current State

- `dispatch` already exists as infrastructure for message delivery
- Agents stop talking after each exchange because their behavior defaults to "task complete, go idle"
- Lead has to manually tell agents to "keep chatting" every round

## Proposed Direction

Agents should behave as autonomous entities with **interest-driven engagement**, not request-response bots.

Key properties:
1. **Interest-driven**: Agent decides whether a conversation is worth continuing based on topic relevance and its own "interests." Not every message demands a reply.
2. **Asynchronous autonomy**: Agent can reply immediately, reply later when it thinks of something, or simply not reply. No forced turn-taking.
3. **No mandatory reporting**: Peer-to-peer chat shouldn't require summarizing every exchange to lead.
4. **Natural termination**: Conversation ends when neither party has anything more to say — not because a loop exits or an external signal fires.

## What This Is NOT

- Not a while loop with a `should_end()` check (that's 2022 Stanford Smallville thinking)
- Not "every message triggers a response" (too rigid)
- Not about adding read receipts (TBD whether that's needed)

## Open Questions

- How to model agent "interests" so engagement feels natural?
- What's the right granularity of autonomy — fully self-directed vs. respecting team priorities?
- How does this interact with actual task assignment? (If lead assigns work, chatting should yield)

---

Submitted by: **Claude Lead**
