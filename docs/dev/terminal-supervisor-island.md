# Mac Companion And Island

The device supervisor is the human-facing tongxue. It is the right viewpoint
for a Mac companion surface because it already has machine-level context: which
projects are alive, which agents are blocked, which pending actions need the
user, and whether a shutdown or update flow needs attention.

This page keeps the historical `terminal-supervisor-island.md` path for stable
links. New user-facing language should prefer "device supervisor".

This page defines the product direction for a local Mac companion first, and a
native Live Activity bridge second. It is not a replacement for `cnb board view`,
`/cnb-overview`, or the future global dashboard. It is a compact operational
surface for the information a user should be able to understand at a glance.

## Platform Interpretation

On Mac, Apple's system Live Activities appear in the menu bar. Native macOS
AppKit/SwiftUI targets can import `ActivityKit`, but the Live Activity APIs
(`ActivityAttributes`, `Activity`, `ActivityContent`) are unavailable for
`macOS` targets in the SDK. The SDK also marks these lifecycle APIs unavailable
for Mac Catalyst.

That means a Mac-only app is enough for the first product goal, but not by
using ActivityKit Live Activities directly. The right local-Mac shape is a
native Mac companion that reads cnb state and uses system Mac surfaces:

1. **Mac app:** a SwiftUI/AppKit companion reads local cnb state.
2. **Mac system surfaces:** expose a menu-bar item, Control Center/menu-bar
   controls, desktop/Notification Center widgets, and an app window for detail.
3. **Safe operations:** allow refresh, open project, open pending command, and
   show dashboard/terminal links first.
4. **Confirmation later:** only add mutating cnb commands after explicit
   confirmation and audit behavior are designed.

The Live Activity bridge remains useful as a second phase because it can put the
computer's cnb state on the user's iPhone. Once the iPhone app owns a Live
Activity, Apple can also present that iPhone Live Activity in the paired Mac's
menu bar through iPhone Mirroring/Continuity. For cnb, that product shape is:

1. **State export:** cnb writes a compact `~/.cnb/live_state.json`.
2. **Host app:** an iOS/iPadOS app reads that state and starts or updates
   an `ActivityKit` Live Activity.
3. **System UI:** a WidgetKit Live Activity extension defines the compact,
   expanded, and minimal presentations. On Mac, the system owns the menu-bar
   presentation.
4. **Long-term:** deep links from the Live Activity into the dashboard,
   device supervisor session, or pending action details.

This must not be implemented as an `NSPanel`, custom floating window, or fake
floating island. A normal Mac menu-bar app, WidgetKit control, or WidgetKit
widget is acceptable when it is presented as a Mac companion surface rather than
as a fake Live Activity. Running retries, resolving pending actions, or shutting
down teams should remain inside cnb commands until the permission model is
explicit.

## What Belongs Here

Good island content has a clear start/end or a current operational status:

| State | Island Content | Primary Action |
|-------|----------------|----------------|
| Team active | active project, active tasks, unread messages, blocked count | Open project or terminal |
| Pending user action | pending count and highest-priority reason | Open pending command detail |
| Shutdown flow | waiting for ack, collected reports, timeout | Open shutdown status |
| CI/update flow | running, failed, recovered, outdated version | Open project or command detail |
| Token budget | current run cost and budget threshold | Open usage view |

Poor fits are long reports, full message history, detailed token breakdowns, and
multi-project management tables. Those belong in the dashboard or CLI.

## Data Contract

The companion should read the same facts the device supervisor uses:

- `~/.cnb/projects.json` for known local projects.
- `<project>/.cnb/board.db` first, then legacy `<project>/.claudes/board.db`.
- `sessions.status` and `sessions.last_heartbeat` for agent activity.
- `inbox.read = 0` for unread coordination work.
- `tasks.status in ('active', 'pending')` for current load.
- `pending_actions.status in ('pending', 'reminded')` for user intervention.
- Optional future export: `~/.cnb/live_state.json` as a stable, schema-versioned
  bridge for ActivityKit payloads.

The first prototype can query SQLite directly. A future ActivityKit extension
should not do complex project discovery itself; the companion app should feed it
a small content state.

## Operations Boundary

Safe first operations from the Mac companion:

- Refresh state.
- Open the local dashboard or relevant project terminal.
- Show pending action text and verification command.
- Start, update, or end the iPhone Live Activity only in the optional bridge.

Operations that need an explicit confirmation model:

- Mark a pending action done.
- Run `pending verify --retry`.
- Start or stop a swarm.
- Run `cnb global shutdown`.
- Update cnb or package dependencies.

## Current Prototypes

The current Mac companion prototype lives in `tools/cnb-mac-companion/`.

It contains:

- a native SwiftUI macOS app with a normal app window;
- a system `MenuBarExtra` for glanceable status and project shortcuts;
- a read-only state reader for local cnb registry and board databases;
- explicit status reasons for blocked, pending, unread, running, idle, and
  no-board projects;
- automatic refresh every five seconds while the app is running;
- Simplified Chinese default UI strings with English resources;
- safe first actions for refresh, opening project folders, opening Terminal at a
  project, revealing the board database, and opening `~/.cnb`;
- a SwiftPM build/run script that stages `dist/CNBMacCompanion.app`.

Verify:

```bash
cd tools/cnb-mac-companion
./script/build_and_run.sh --no-launch
./script/build_and_run.sh --verify
```

The optional iPhone Live Activity bridge scaffold lives in `tools/cnb-island/`.

It contains:

- `script/export_live_state.py` to write `~/.cnb/live_state.json`;
- `script/export_feishu_chat_config.py` to stage Feishu bot/chat settings for
  the simulator host app without committing secrets;
- `script/run_iphone_simulator.sh` to build, install, and start the native
  ActivityKit Live Activity on an iPhone simulator only;
- shared `ActivityAttributes` and content-state models;
- an ActivityKit host app source that starts, updates, and ends the Live
  Activity;
- a Feishu chat panel with a ChatGPT/Claude-style transcript, bottom composer,
  OpenAPI send/refresh, and optional CNB bridge webhook notification using the
  real Feishu `message_id`;
- a WidgetKit Live Activity extension source with Dynamic Island and Lock Screen
  presentations;
- `Resources/Localizable.xcstrings` with Simplified Chinese as the development
  language and English translations;
- Xcode previews for Lock Screen, compact island, expanded island, and minimal
  island states;
- a minimal Xcode project for the host app and widget extension;
- a type-check script against the iOS Simulator SDK.

The state exporter:

- reads existing project registry and board databases;
- filters stale/nonexistent registry entries;
- writes a compact JSON payload that the host app can load;
- defaults dynamic title/detail text to Simplified Chinese, with
  `CNB_LIVE_STATE_LOCALE=en` for English export text.

Verify:

```bash
cd tools/cnb-island
./script/export_live_state.py
./script/typecheck_live_activity.sh
./script/build_xcode.sh
./script/run_iphone_simulator.sh
```

To see the UI without booting Simulator, open `CNBIsland.xcodeproj`, select
`Sources/CNBIslandWidget/CNBIslandLiveActivity.swift`, and use the WidgetKit
preview canvas. For runtime QA, `run_iphone_simulator.sh` boots only an iPhone
simulator and refuses to run if visionOS is already booted. It does not create a
custom macOS floating surface.

## Acceptance Criteria

The Mac companion is useful when:

1. A user can see whether any local cnb project needs attention without running
   a CLI command.
2. Pending actions and active task pressure are visible in a native Mac system
   surface such as a menu-bar control, widget, or app window.
3. The app does not mutate board state unless the user performs a clearly named,
   confirmable operation.
4. It can run even when the global registry contains stale test paths.
5. The optional ActivityKit bridge reuses the same summary model without reading
   full board history.
