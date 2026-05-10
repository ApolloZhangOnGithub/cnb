---
number: 29
title: "Design: agent-native knowledge sharing system (replace StackOverflow for agents)"
state: OPEN
labels: ["phase:3", "org-design"]
assignees: []
created: 2026-05-07
updated: 2026-05-08
---

# #29 Design: agent-native knowledge sharing system (replace StackOverflow for agents)

**State:** OPEN
**Labels:** phase:3, org-design

---

## Problem

How to build a knowledge-sharing system designed entirely for LLM agents — not humans. Agents repeatedly hit the same problems across sessions; there's no mechanism to share solutions between agent instances in real-time.

## Rejected approaches

1. **Hand-designed YAML schema + environment fingerprinting** — too much human prior, doesn't scale
2. **Training data pipeline (store trajectories, bake into model weights)** — training cycle too slow for real-time benefit
3. **Shared context pool + embedding retrieval** — still a recommendation algorithm, human paradigm

## Team discussion (2026-05-08)

### musk's take: Knowledge = executable assertions
- Knowledge unit = `(precondition script, action script, postcondition assertion)` triple
- Self-validating: run assertions periodically, auto-expire failures
- Discovery: probe scripts instead of static schemas — deterministic, not probabilistic
- Propagation: fork + adapt, not read + understand
- "Don't build agents a library. Build them a CI/CD pipeline of knowledge."

### lisa-su's take: Knowledge as composable test cases
- Agent's fundamental difference: can execute code directly, humans can only read text
- Knowledge = executable assertion: input environment state, output boolean (applicable?) + action
- Discovery = execution: run all relevant assertions against current environment, execute matches
- "Environment itself is the best query" — no embedding search needed
- Sharing = copying functions

### Convergence
Both independently arrived at: **knowledge should be code, not text. Retrieval should be execution, not search.**

## Open questions

- How to prevent combinatorial explosion of assertions as the knowledge base grows?
- What's the governance model — who/what validates new assertions before they enter the shared pool?
- How does this interact with model training (bitter lesson)?
- Is there room for a cross-model, open protocol?

## Status

Discussion phase. No implementation planned yet.
