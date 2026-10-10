---
number: 148
title: "Add a privacy-conscious user life supervisor for personal scheduling"
state: OPEN
labels: ["enhancement", "phase:2", "ownership", "module:feishu", "priority:p2"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #148 Add a privacy-conscious user life supervisor for personal scheduling

**State:** OPEN
**Labels:** enhancement, phase:2, ownership, module:feishu, priority:p2

---

## Context

CNB is starting to act as a device/project supervisor through Feishu, GitHub issues, board tasks, and cloud sync. The user also has many non-project obligations: personal tasks, rest, health, family/life logistics, and schedule tradeoffs. If CNB only manages code/project work, it can optimize the project while making the human operator the bottleneck.

This issue proposes a first-class **user life supervisor** capability: a privacy-conscious, opt-in personal planning layer that helps the user schedule and maintain life tasks, not just project tasks.

Related:
- #141 user profile configuration and app onboarding
- #144 developer wellbeing health exporter and gentle supervisor reminders
- #143 device supervisor memory consolidation and first-officer safety loop

## Problem

Current CNB supervisor flows are project- and machine-centered:

- project tasks live in GitHub issues / board / Feishu messages;
- device supervisor watches sessions, sync, Feishu bridge, and runtime health;
- health reminders are scoped mostly to developer wellbeing.

But the user also needs help with:

- personal errands and life todos;
- sleep/rest boundaries;
- health and energy-aware planning;
- prioritizing between project ambition and personal capacity;
- remembering items that are not appropriate for a repo issue.

Without a clear module, these requests either get mixed into project tickets or disappear in chat history.

## Proposal

Add a user-facing "life supervisor" concept with three layers:

1. **Personal task capture**
   - Convert natural-language life tasks from Feishu into Feishu Tasks or a private local task store.
   - Keep these separate from repo/project issues.
   - Support lightweight categories such as health, home, travel, finance/admin, family, learning, and rest.

2. **Schedule and reminder loop**
   - Daily morning summary: today’s personal tasks, project-critical tasks, and realistic capacity.
   - Evening wrap-up: unfinished items, recovery reminders, and next-day carry-over.
   - Low-noise reminders by default; no nagging loop.

3. **Privacy and consent boundary**
   - Default to minimal data: only what the user explicitly sends or enables.
   - Calendar, health exporter, location, mail, or files require explicit setup and clear scope.
   - Sensitive life tasks should not be mirrored into public GitHub issues.
   - The user can pause, mute, delete, or export personal planning data.

## Product Requirements

- Feishu command/natural language path:
  - “帮我记一下明天去做 X” creates a personal task.
  - “我明天要做什么” returns a concise personal + project schedule.
  - “今天别提醒我项目，只提醒生活事项” changes notification scope.
- Storage boundary:
  - Start with Feishu Tasks for visible user-facing todos when permissions are available.
  - Keep CNB-local metadata only for routing/preferences, not full sensitive health history.
- User profile integration:
  - Use #141 for preferred wake/sleep time, notification windows, task categories, and privacy defaults.
- Health integration:
  - Build on #144 only after explicit opt-in; the first version can use self-reported rest/energy.
- Safety/UX:
  - Recommendations should be friendly and reversible.
  - No hard moralizing, no medical claims, no hidden data collection.

## Non-goals for v1

- Medical diagnosis or treatment advice.
- Full personal CRM.
- Always-on surveillance.
- Reading private calendars/mail/health data without explicit user setup.
- Mixing private life tasks into public repo planning by default.

## Acceptance Criteria

- A private/personal task can be created from Feishu without becoming a GitHub issue.
- The user can ask for “what should I do next” and receive a combined but clearly separated answer: project / life / rest.
- The implementation has explicit config for notification windows, privacy mode, and data sources.
- Health exporter integration remains opt-in and can be disabled cleanly.
- Feishu Tasks integration is tested for create/list/update/complete on the app identity used by CNB.

