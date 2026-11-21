---
number: 155
title: "Fail closed when a low-tier model skips a required Feishu reply"
state: CLOSED
labels: ["phase:1", "infra"]
assignees: []
created: 2026-05-10
updated: 2026-05-15
closed: 2026-05-15
---

# #155 Fail closed when a low-tier model skips a required Feishu reply

**State:** CLOSED
**Labels:** phase:1, infra

---

## Problem

When operating with a lower-tier model (for example `gpt-5.4-mini`), the agent can complete work in the shell but still drop the required final Feishu reply. That is an operational failure, not just a quality regression: the user sees silence and assumes nothing happened.

## Why this matters

For this workflow, a task is not done until the Feishu reply is actually sent. If the model forgets that final step, the bridge loses its main contract with the user. That failure is more harmful on low-tier models because they are more likely to skip a required terminal action when the reasoning budget is tight.

## Desired behavior

- Required final replies must be treated as a hard gate.
- If the reply send path fails, the task must remain open / marked blocked.
- The bridge should surface a clear operator-visible error instead of silently continuing.
- Low-tier model runs should not be allowed to “complete” if the required reply was not confirmed sent.
- This should apply to Feishu replies and any other mandatory closeout notification paths.

## Reflection from this run

I did hit the user-visible version of this: work finished in the shell, but the important last message can be missed or delayed when the model is low-tier or the run is noisy. That should be fail-closed, not best-effort.

## Acceptance

- Add a guard that verifies final Feishu reply success before closeout.
- Add regression coverage for a simulated reply failure.
- Make the failure obvious in logs / board state.
- Keep normal final-only notification behavior for successful runs.

