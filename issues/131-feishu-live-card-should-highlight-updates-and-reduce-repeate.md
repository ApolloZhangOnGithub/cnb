---
number: 131
title: "Feishu live card should highlight updates and reduce repeated boilerplate hints"
state: OPEN
labels: ["enhancement", "phase:2", "infra", "module:feishu", "priority:p2"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #131 Feishu live card should highlight updates and reduce repeated boilerplate hints

**State:** OPEN
**Labels:** enhancement, phase:2, infra, module:feishu, priority:p2

---

## Context

User feedback from Feishu while using the live activity card: the card content should make important changes easier to notice, and the repeated guidance text is too noisy after the first or early updates.

## Requirements

- Highlight meaningful changes in the current live card, such as new user requests, active command/output changes, errors, blockers, or changed status lines.
- Keep the first-time onboarding hint available, but suppress repeated boilerplate such as “后续自动状态会更新这张卡片” after the first or early card updates.
- Preserve a compact fallback for users who have not seen the card before, but let normal recurring updates focus on signal.
- Avoid expanding notification volume; this is a rendering/content policy improvement, not a push-frequency increase.

## Acceptance criteria

- Repeated live card updates no longer include the same long auto-update explanation every time.
- Important changed/new lines are visually distinguishable in Feishu-supported rich text/card rendering.
- Snapshot text remains readable in plain fallback clients.
- Tests cover first/early card rendering versus later repeated updates.
