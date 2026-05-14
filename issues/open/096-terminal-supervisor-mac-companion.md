---
number: 96
title: "Terminal supervisor Mac companion"
state: OPEN
labels: [enhancement, phase:3, macos, ux]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #96 Terminal supervisor Mac companion

**State:** OPEN
**Labels:** enhancement, phase:3, macos, ux

---

## Problem

The first useful surface for cnb does not need iPhone distribution or cross-device
sync. The user primarily needs to understand local Mac cnb state without running
a command, then jump into the relevant dashboard, project, terminal, or pending
action.

## Decision

Build a native Mac companion first.

This should not pretend to be a Live Activity. Apple exposes ActivityKit Live
Activity lifecycle APIs for iOS/iPadOS apps, while local SDK checks show
`ActivityAttributes`, `Activity`, and `ActivityContent` are unavailable to
native macOS and Mac Catalyst targets. On Mac, Live Activities in the menu bar
are paired-iPhone Live Activities delivered through iPhone Mirroring/Continuity.

For local Mac use, use native Mac app surfaces:

- menu-bar companion status;
- WidgetKit controls that the user can place in Control Center or the menu bar;
- desktop or Notification Center widgets for glanceable state;
- a small app window for details and configuration.

The existing ActivityKit scaffold in `tools/cnb-island/` stays valuable as a
later iPhone bridge, so the iPhone can show the Mac's cnb status and the paired
Mac can show that iPhone Live Activity in the system menu bar.

## Prototype

Prototype path: `tools/cnb-mac-companion/`.

Implemented:

- SwiftPM native macOS SwiftUI app;
- normal foreground app window plus system `MenuBarExtra`;
- read-only local state reader for `~/.cnb/projects.json`;
- `.cnb/board.db` first, legacy `.claudes/board.db` fallback;
- read-only `sqlite3` counts for pending actions, tasks, unread inbox items,
  sessions, and blocked sessions;
- explicit status reasons for blocked, pending, unread, running, idle, and
  no-board projects;
- non-running registered projects are included instead of being hidden;
- five-second auto-refresh while the app is running;
- Apple-style localization resources with `Localizable.xcstrings` as the source
  catalog, runtime `Localizable.strings` files for `zh-Hans` and `en`, and
  Simplified Chinese as the default language;
- safe actions: refresh, open project folder, open Terminal at project, reveal
  board database, and open `~/.cnb`;
- `script/build_and_run.sh` that stages `dist/CNBMacCompanion.app` and launches
  it as a real macOS app bundle.

## Scope

The Mac companion should show:

- active local cnb projects;
- active/pending tasks;
- unread board messages;
- pending user actions;
- blocked or attention-needed sessions;
- shutdown/update/CI state when those flows are active.

Safe first operations:

- refresh state;
- open the local global dashboard or cnb home;
- open a project in Terminal;
- show the pending verification command;
- open the relevant board/pending view.

Out of scope for the first Mac companion:

- fake floating islands;
- unconfirmed board mutations;
- automatic retry execution;
- global shutdown execution;
- cross-device transport to iPhone.

## Data Contract

Reuse the same summary model as the Live Activity bridge:

- `~/.cnb/projects.json`;
- `<project>/.cnb/board.db`;
- fallback legacy `<project>/.claudes/board.db`;
- compact exported state at `~/.cnb/live_state.json`.

The Mac app can read local files directly. Widget/control extensions should
consume a compact shared state payload instead of doing broad project discovery.

## Acceptance Criteria

1. A native Mac target builds without ActivityKit lifecycle APIs.
2. The companion reads current local cnb state and tolerates stale registry
   paths.
3. The menu-bar/window surface shows pending, task, unread, and active project
   totals.
4. Clicking the surface opens the app or a project-specific view.
5. No board mutation happens without an explicit confirmation design.
6. The same summary model can later feed the iPhone Live Activity bridge.

## Prototype Checkpoint - 2026-05-10

Verification:

- `cd tools/cnb-mac-companion && ./script/build_and_run.sh --no-launch` builds
  cleanly.
- `cd tools/cnb-mac-companion && ./script/build_and_run.sh --verify` stages and
  opens `dist/CNBMacCompanion.app`.
- Runtime localization lookup returns Chinese and English strings from the
  staged resource bundle.
- `pgrep -fl CNBMacCompanion` confirms the app process is running.
- `xcrun simctl list devices booted` confirms no simulator was booted.
- `git diff --check` is clean.
