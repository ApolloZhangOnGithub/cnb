---
number: 28
title: "Agent status visibility: push-based heartbeat instead of pull-based polling"
state: CLOSED
labels: []
assignees: []
created: 2026-05-07
updated: 2026-05-07
closed: 2026-05-07
---

# #28 Agent status visibility: push-based heartbeat instead of pull-based polling

**State:** CLOSED

---

## Problem

Checking on other agents' status is clunky. Currently requires:
- `tmux capture-pane` to peek at raw terminal output (hacky, unstructured)
- `board --as X inbox` / `view` to poll for messages (active pulling)
- `swarm status` only tells you if tmux session is alive, not if agent is actually working

In a real company, you glance at Slack and see who's online, what they're doing. In cnb, you have to actively interrogate each agent.

## Proposed solution

**Push model: agent tool calls auto-emit heartbeat as a side effect.**

The `PostToolBatch` hook already fires after every tool batch. Extend it to write a heartbeat row:
`(timestamp, agent_name, last_tool_type, brief_summary)` to the board DB.

Then `board view` can show real-time status without tmux scraping:

```
sutskever   ● active (12s ago)   editing lib/swarm.py
lisa-su     ● active (3s ago)    running pytest
musk        ○ thinking (2m ago)  last: read CLAUDE.md
bezos       — offline
```

## Key design points

- No extra tool calls needed from agents — status is a byproduct, not a task
- Heartbeat timeout distinguishes "thinking" from "dead"
- Replaces the fragile `tmux capture-pane` scraping pattern
- Single `board view` gives full team visibility

## Related

This also addresses part of the UX feedback from musk (issue #27 context): agents need fewer tool calls to understand team state, not more.
