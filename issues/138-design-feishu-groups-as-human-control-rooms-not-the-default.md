---
number: 138
title: "Design: Feishu groups as human control rooms, not the default tongxue message bus"
state: OPEN
labels: ["enhancement", "org-design", "module:feishu", "priority:p2"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #138 Design: Feishu groups as human control rooms, not the default tongxue message bus

**State:** OPEN
**Labels:** enhancement, org-design, module:feishu, priority:p2

---

## Question

Feishu has proven useful as a remote/mobile interface for the device supervisor. Should all tongxue talk to each other in Feishu groups?

## Recommendation

Use Feishu groups as human-facing control rooms and escalation surfaces, not as the default internal tongxue message bus. Keep the cnb board/SQLite task and inbox model as the system of record for tongxue-to-tongxue coordination.

## Why

Benefits of Feishu:

- excellent mobile UX for the human owner;
- easy migration/cutover group for old Mac supervisor, new iMac supervisor, and user;
- good place for summaries, approvals, blockers, final reports, and watch links;
- useful cross-device visibility when the local terminal is unavailable.

Risks if every internal message goes through Feishu:

- notification spam and high cognitive load;
- weak structure compared with board tasks, statuses, ownership, and verification records;
- harder replay/audit semantics for agent recovery;
- permission and privacy expansion across all background classmates;
- ambiguous responsibility when many bots speak in one group;
- possible loss of the low-token local coordination advantage.

## Proposed product shape

- Per-device migration/control group: user + old device supervisor + new device supervisor.
- Per-project control group: user + project lead + selected status bots, only after device supervisor is stable.
- Board remains the internal bus for routine task/inbox traffic.
- Feishu gets mirrored high-signal events: P0 blockers, pending user actions, PR/release status, shift reports, stuck/stale supervisor alerts, and explicit user requests.
- Optional `/cnb_board`, `/cnb_watch`, `/cnb_status` commands expose board/runtime state on demand.

## Acceptance criteria for future implementation

- A Feishu mirror policy exists with levels such as `off`, `final_only`, `control_room`, and `verbose_debug`.
- Internal board messages are not blindly forwarded to Feishu by default.
- Every Feishu-posted item maps back to a board task/issue/runtime event when possible.
- Users can keep mobile notifications quiet while still seeing high-signal control-room updates.
