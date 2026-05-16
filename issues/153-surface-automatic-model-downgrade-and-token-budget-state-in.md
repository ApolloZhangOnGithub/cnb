---
number: 153
title: "Surface automatic model downgrade and token budget state in production-line mode"
state: OPEN
labels: ["phase:1", "infra", "org-design"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #153 Surface automatic model downgrade and token budget state in production-line mode

**State:** OPEN
**Labels:** phase:1, infra, org-design

---

## Problem

When the runtime silently falls back to a smaller model tier (for example, `gpt-5.4-mini`), operators lose visibility into the actual coordination capacity of the current run. That makes it easy to assume the team is still running at full strength when it is not.

At the same time, token consumption is spread across multiple local sessions and coordination loops, so there is no obvious operator-facing control plane for:

- current model / reasoning tier
- total token burn across the run
- projected budget exhaustion
- when to warn the user that the session has auto-degraded

This matters more in production-line mode, where the dispatcher keeps feeding a manager task stack from upstream issues. If the team is going to continue autonomously, it needs a visible model/budget state and a clear shutdown policy. Otherwise we get the worst case: the pipeline keeps nudging while the run is already effectively degraded or should be wrapped up.

## Desired behavior

1. Detect automatic model downgrade or reasoning-tier reduction and surface it immediately to the operator/user.
2. Track aggregate token usage across the active run, not just per session.
3. Expose a clear budget view: current burn, threshold, and remaining runway.
4. In production-line mode, make shutdown / handoff explicit when the queue is drained or the run is effectively done.
5. Preserve the existing final-only notification model for normal messaging; this should be a targeted runtime signal, not noisy chat spam.

## Questions / design points

- Where should the downgrade signal live: session status, board overview, dispatcher log, or a dedicated usage command?
- What threshold should trigger a user reminder for token burn or model fallback?
- How should production-line mode decide between "keep feeding work" and "let everyone go home"?
- Should the shutdown criterion be driven by task queue state, unread inboxes, or an explicit operator flag?

## Related work

- #38 token usage tracking
- #102 manager closeout escalation
- production-line intake / task stack flow

