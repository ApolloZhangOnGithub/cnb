---
number: 127
title: "Mac companion chat defects: send shortcut, attachments, card rendering, routing, and UI polish"
state: OPEN
labels: ["bug", "enhancement", "phase:2", "infra", "module:mac-companion", "priority:p2"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #127 Mac companion chat defects: send shortcut, attachments, card rendering, routing, and UI polish

**State:** OPEN
**Labels:** bug, enhancement, phase:2, infra, module:mac-companion, priority:p2

---

## Reported from Feishu / Mac companion dogfood

The Mac companion chat prototype is usable enough to send a text message into the CNB bridge, but dogfooding exposed several product defects. Do not treat this as an implementation request yet; this issue records the defects for triage.

## Problems

1. **Enter key does not send**
   - Pressing Return in the Mac chat app does not submit the current message.
   - Expected: Return sends, Shift+Return inserts a newline, or the UI clearly documents the chosen behavior.

2. **No image / attachment support**
   - The app currently handles plain text only.
   - It should support at least image and file handoff, matching the Feishu bridge resource model where inbound resources can be downloaded into `~/.cnb/feishu_resources/<message_id>/` and passed to the device supervisor.

3. **Interactive card rendering is incomplete**
   - A card appears as text like:
     `"[Card: Codex 实时一屏 · 8s\n只显示当前一屏]"`
   - The content below the card is empty/missing.
   - Expected: render card header/subtitle plus useful body content, or present a clear compact fallback with the current screen text.

4. **Message attribution / routing classification is wrong**
   - Content sent from the app to the CLI/device-supervisor can be misclassified as coming from the CLI side.
   - Expected: messages from `cnb-mac-companion`, Feishu bot, user, and device-supervisor remain visually and semantically distinct.

5. **UI quality is rough**
   - Several UI surfaces are visually unpolished.
   - Needs focused pass on spacing, typography, message bubbles/list layout, empty states, error states, attachment affordances, and card fallback styling.

## Acceptance criteria

- Return/Shift+Return behavior is explicit and tested.
- Images/files can be attached or at least represented with a useful placeholder and local handoff path.
- Feishu interactive cards show non-empty meaningful content in the companion.
- Sender attribution is correct for app-originated, bridge-originated, and supervisor-originated messages.
- Basic chat UI is polished enough for daily dogfooding.

## Context

- Prototype path: `tools/cnb-mac-companion/`.
- Relevant renderer: `FeishuMessageContentRenderer`.
- Existing product direction: local issue mirror `issues/096-terminal-supervisor-mac-companion.md` and `docs/terminal-supervisor-island.md`.

