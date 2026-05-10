---
number: 95
title: "Terminal supervisor Live Activity / CNB Island"
state: OPEN
labels: [enhancement, phase:3, infra]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #95 Terminal supervisor Live Activity / CNB Island

**State:** OPEN
**Labels:** enhancement, phase:3, infra

---

## Problem

cnb currently has useful status surfaces (`cnb ps`, `board view`,
`/cnb-overview`, `/cnb-pending`), but they all require the user or terminal
supervisor to actively ask for state. The terminal supervisor already represents
the user's operational viewpoint, so it should have a glanceable Mac surface for
what needs attention right now.

## Product Direction

Build the optional iPhone Live Activity bridge from the terminal supervisor
perspective. The first local-Mac surface is tracked separately in #96.

1. **State export:** cnb writes compact terminal-supervisor state to
   `~/.cnb/live_state.json`.
2. **ActivityKit integration:** an iOS/iPadOS host app starts and updates
   the Live Activity.
3. **WidgetKit extension:** system-rendered Live Activity presentations define
   Dynamic Island, Lock Screen, and paired-Mac menu-bar behavior.
4. **Operations:** start with safe actions only, then add confirmable cnb command
   operations.

Do not implement this as an `NSPanel`, custom floating window, or fake floating
island.

## Scope

The iPhone Live Activity should show:

- active project count;
- active/pending tasks;
- unread board messages;
- pending user actions;
- top blocked project or highest-priority pending action;
- shutdown/update/CI activity when those flows are active.

Initial safe operations:

- refresh;
- start/update/end the system Live Activity;
- inspect pending action command and reason.

Out of scope for the first prototype:

- running retries;
- marking pending actions done;
- starting/stopping swarms;
- global shutdown;
- auto-update execution.

## Data Contract

Read from existing local state:

- `~/.cnb/projects.json`;
- `<project>/.cnb/board.db`;
- fallback legacy `<project>/.claudes/board.db`;
- `sessions`, `inbox`, `tasks`, `pending_actions`, and latest `messages`.

Future ActivityKit work should use a compact exported content state instead of
making the widget extension perform broad filesystem discovery.

## Implementation Notes

Prototype path: `tools/cnb-island/`.

The first implementation intentionally avoids adding a new Python daemon. The cnb
side exports compact state, and the ActivityKit host app consumes that state.

Platform note: Apple documents that Live Activities can appear on a paired Mac,
and Apple Support describes those Mac menu-bar Live Activities as coming from
the user's iPhone through iPhone Mirroring/Continuity. Local SDK checks confirm
that native macOS and Mac Catalyst targets cannot directly create ActivityKit
Live Activities. Therefore this issue remains useful as an iPhone bridge, while
the local Mac companion is #96 and uses native Mac app/widget/control surfaces.

## Acceptance Criteria

1. `tools/cnb-island/script/export_live_state.py` writes
   `~/.cnb/live_state.json`.
2. `tools/cnb-island/script/typecheck_live_activity.sh` type-checks the
   ActivityKit host source and WidgetKit Live Activity source.
3. `tools/cnb-island/script/build_xcode.sh` builds the host app and widget
   extension for local validation.
4. The Live Activity content state can display project/task/pending/unread
   totals.
5. Stale registry paths do not crash the state exporter.
6. No board mutation happens without an explicit future confirmation design.

## Prototype Checkpoint - 2026-05-10

Added initial ActivityKit source scaffold in `tools/cnb-island/`.

Implemented:

- read-only state exporter for `~/.cnb/projects.json` and project `board.db`;
- `.cnb/board.db` first, legacy `.claudes/board.db` fallback;
- stale/nonexistent registry path filtering;
- compact `~/.cnb/live_state.json` payload;
- default Simplified Chinese dynamic title/detail export, with
  `CNB_LIVE_STATE_LOCALE=en` for English payload text;
- shared `ActivityAttributes` and `ContentState`;
- ActivityKit host app source for start/update/end;
- auto-start mode via `CNB_AUTOSTART_ACTIVITY=1` for simulator/runtime checks;
- host-app Feishu chat panel with ChatGPT/Claude-style transcript, settings
  disclosure, bottom composer, OpenAPI send/refresh, optional reply
  `message_id`, and optional CNB bridge webhook notification after successful
  Feishu send;
- `script/export_feishu_chat_config.py` for staging bot/chat/webhook settings
  from `~/.cnb/config.toml` into `~/.cnb/feishu_chat.json`;
- WidgetKit Live Activity source using `ActivityConfiguration`;
- visible compact Dynamic Island content with explicit foreground styling;
- `Resources/Localizable.xcstrings` attached to both the app and widget
  extension targets, with `zh-Hans` as the development language and English
  translations;
- WidgetKit preview definitions for Lock Screen, compact, expanded, and minimal
  Live Activity presentations;
- minimal Xcode project with host app target and widget extension target.
- iPhone-simulator-only runtime script `script/run_iphone_simulator.sh`, which
  refuses to continue if a visionOS simulator is already booted.

Verification:

- `pkill -x CNBIsland` closed the previous non-system prototype.
- Native macOS SDK check confirmed `ActivityAttributes`, `Activity`, and
  `ActivityContent` are unavailable for `macOS` targets.
- Local SDK interface check also confirmed those ActivityKit lifecycle APIs are
  unavailable for Mac Catalyst, so the scaffold targets iOS/iPadOS plus a
  WidgetKit extension.
- iOS Simulator SDK check confirmed the ActivityKit and WidgetKit source path is
  type-checkable.
- `cd tools/cnb-island && ./script/export_live_state.py` wrote
  `~/.cnb/live_state.json`.
- `cd tools/cnb-island && ./script/export_feishu_chat_config.py --output /tmp/cnb-feishu-chat-check.json`
  wrote valid JSON with app/chat/webhook keys; the temporary check file was
  removed after validation.
- `cd tools/cnb-island && ./script/typecheck_live_activity.sh` passed.
- `cd tools/cnb-island && ./script/build_xcode.sh` built the host app and
  WidgetKit extension successfully for `iphonesimulator` with
  `CODE_SIGNING_ALLOWED=NO`.
- `cd tools/cnb-island && ./script/run_iphone_simulator.sh` built, installed,
  copied state, launched the host app, auto-started the Live Activity, and left
  the native Dynamic Island visible on the iPhone 17 Pro simulator.
- Booted simulator check after runtime QA showed only iOS booted:
  `iPhone 17 Pro (6039A585-C215-4A84-B232-7F4E955E5977) (Booted)`;
  no visionOS simulator was booted.
- Runtime screenshot captured at
  `tools/cnb-island/build/screenshots/cnb-island-home-final.png`.
- `git diff --check` => clean.

Remaining before calling this product-ready:

- visual QA pass across light/dark mode and crowded menu-bar setups;
- transport from Mac cnb state to the iPhone host app;
- explicit confirmation design for any mutating cnb operation.
