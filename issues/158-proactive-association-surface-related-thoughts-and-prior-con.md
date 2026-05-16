---
number: 158
title: "Proactive association: surface related thoughts and prior context as occasional conversational prompts"
state: OPEN
labels: ["enhancement", "phase:1", "infra"]
assignees: []
created: 2026-05-11
updated: 2026-05-11
---

# #158 Proactive association: surface related thoughts and prior context as occasional conversational prompts

**State:** OPEN
**Labels:** enhancement, phase:1, infra

---

# Proactive association: surface related thoughts and prior context as occasional conversational prompts

## Problem

Today tongxue mostly responds reactively. In real conversations, humans often remember a related thought later, connect it to something said earlier, and bring it up proactively. That behavior is valuable: it can reopen useful topics, remind the user of prior context, and create more natural collaboration.

Right now cnb has little structure for that kind of association-driven initiative. A session can answer well, but it does not have a first-class way to occasionally say, "this seems related to what we discussed earlier" or "I remembered a useful adjacent idea" without waiting for a direct prompt.

## Impact

- Conversations feel less natural and less useful over long-running work.
- The system underuses prior context and related observations.
- Helpful follow-up ideas are left unsaid unless the user asks the exact next question.

## Expected

Add a lightweight proactive-association mechanism that lets tongxue occasionally surface related thoughts, prior-thread connections, or adjacent suggestions when confidence is high and the interruption cost is low.

Possible behaviors:

- remember a prior topic and re-surface it when a new message is related;
- notice a nearby idea or inconsistency and raise it as a brief prompt;
- opportunistically start a topic when the session has a strong contextual link, not random chatter;
- keep it rare, contextual, and easy to ignore.

## Acceptance

- Add a concrete design for proactive associative prompting.
- Define guardrails so the feature does not spam or derail active work.
- Preserve current reactive chat behavior when no good association exists.
- Add tests or scenario coverage for at least one positive case and one no-spam/no-false-positive case.

