---
number: 120
title: "Opt-in Feishu context readback for delivery troubleshooting"
state: CLOSED
labels: ["enhancement", "phase:2", "infra"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
closed: 2026-05-10
---

# #120 Opt-in Feishu context readback for delivery troubleshooting

**State:** CLOSED
**Labels:** enhancement, phase:2, infra

---

## Context check

- [x] I checked ROADMAP.md. This relates to the device supervisor / Feishu control path and #96/#95 adjacent companion work, but it is narrower: the CLI bridge should let the supervisor inspect Feishu context only when explicitly enabled and requested.
- [x] I searched open issues for Feishu history, readback, message history, and read status. #114 covers secure watch links; #95 covers the iPhone/Live Activity surface; neither gives the supervisor an on-demand Feishu-side audit command.
- [x] I searched relevant docs and current Feishu bridge behavior. Existing code can reply, update cards, fetch a referenced parent message, and expose Web TUI/status, but it cannot inspect recent chat history or bot-sent message read status on demand.
- [x] Remaining uncertainty: exact production permissions depend on the customer Feishu app configuration and chat type.

## Relationship to existing context

Related to #96 and #95 because both are user-facing device-supervisor surfaces. It does not overlap with #114, which is about securing the Web TUI watch tunnel. This issue is about a diagnostic capability for cases where the user asks why Feishu did not receive or display expected messages.

Phase label: phase:2
Type label: infra

## Problem and goal

Sometimes Feishu itself, app permissions, message delivery, or chat history visibility can be the failure point. When the user asks the device supervisor what happened, Claude Code currently only sees local tmux/CNB state and may not know whether the Feishu-side message, reply thread, or recent chat history actually exists.

Add an opt-in readback capability so the device supervisor can explicitly inspect recent Feishu chat history and message read-status clues for troubleshooting. This must not become default chat surveillance or automatic prompt stuffing.

## Design notes

- Default disabled in config.
- Only works for the allowlisted/bound chat unless an explicit chat ID is supplied and the local config permits it.
- Use Feishu OpenAPI message history and message content/read-status APIs with tenant access token.
- Summarize/sanitize output for CLI use; do not persist private message content.
- Expose the capability in the supervisor affordance text so Claude Code knows it exists when the user asks a delivery/debug question.

## Acceptance criteria

- `cnb feishu history` refuses unless readback is explicitly enabled.
- With readback enabled, `cnb feishu history --limit N` fetches recent messages from the configured chat and prints a concise diagnostic summary.
- `cnb feishu inspect-message <message_id>` can fetch one message and, when applicable, query read users for bot-sent messages, while tolerating permission errors with actionable output.
- Inbound prompts mention the readback command as an opt-in diagnostic tool, not normal operation.
- Tests cover disabled default, OpenAPI request shape, output formatting, and permission/error handling.
- README/README_zh/changelog document the privacy boundary and required Feishu permissions.
