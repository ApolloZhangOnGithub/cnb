# CNB Island Live Activity Bridge

This tool is intentionally **not** a floating window or custom menu-bar status
item. It is the source scaffold for the optional iPhone/iPadOS Live Activity
bridge. The first local Mac companion lives in `../cnb-mac-companion/`.

The implementation path is:

1. `export_live_state.py` writes a compact device-supervisor state file at
   `~/.cnb/live_state.json`.
2. An iOS/iPadOS host app reads that file and starts or updates an
   `ActivityKit` Live Activity.
3. A WidgetKit Live Activity extension defines the system-rendered compact,
   expanded, and minimal presentations. On Mac, the system owns the menu-bar
   presentation.

Native AppKit/SwiftUI macOS targets cannot create Live Activities directly:
`ActivityAttributes`, `Activity`, and `ActivityContent` are unavailable for
`macOS` targets in the SDK. The same SDK interfaces mark the ActivityKit
lifecycle APIs unavailable for Mac Catalyst, so this scaffold intentionally
targets iOS/iPadOS plus a WidgetKit extension. The Mac menu-bar surface is still
system-owned when Apple presents the Live Activity on Mac.

## Verification

```bash
./script/export_live_state.py
./script/typecheck_live_activity.sh
./script/build_xcode.sh
```

`typecheck_live_activity.sh` type-checks the ActivityKit app source and WidgetKit
extension source against the iOS Simulator SDK. `build_xcode.sh` builds the
minimal host app plus WidgetKit extension against the iOS Simulator SDK with
`CODE_SIGNING_ALLOWED=NO` for local validation.

## Feishu Chat

The host app now includes a compact Feishu chat panel using a Claude/ChatGPT
style transcript and bottom composer. It uses bot identity and Feishu OpenAPI:

- `POST /open-apis/auth/v3/tenant_access_token/internal` for a tenant token;
- `POST /open-apis/im/v1/messages?receive_id_type=chat_id` to send text into a
  configured chat;
- optional `POST /open-apis/im/v1/messages/{message_id}/reply` when a reply
  message ID is set;
- `GET /open-apis/im/v1/messages` to refresh recent chat messages;
- optional POST to the configured CNB Feishu bridge webhook after a successful
  Feishu send, reusing the real Feishu `message_id` so the Mac supervisor can
  route work and reply back into the same Feishu thread.

For simulator checks, export the same `[feishu]` config used by the Mac bridge:

```bash
./script/export_feishu_chat_config.py
```

That writes `~/.cnb/feishu_chat.json` with `appID`, `appSecret`, `chatID`,
`chatIDs`, `replyMessageID`, `webhookURL`, and `verificationToken`. `chatID`
keeps the existing single-chat path compatible; `chatIDs` preserves every
configured `chat_id`, `allowed_chat_ids`, or `chat_ids` entry for read-only
multi-control-room surfaces. The simulator and physical-device scripts copy this
file into the app container when it exists. Do not commit generated files that
contain app secrets.

## Vision Feishu Viewer

`CNBVision` is the first Apple Vision Pro surface. It is a native SwiftUI
visionOS target, not a web wrapper and not a bundled `lark-cli` path. visionOS
apps do not have a Mac-like shell/subprocess model for running a local CLI, so
the first implementation reads the same `feishu_chat.json` handoff and calls
Feishu OpenAPI directly. It aggregates recent messages from all configured
control chats in `chatIDs`, which means one shared control group can show all
device supervisor bots, and multiple allowlisted groups can be viewed together.
It is read-only today; device-chief leases and cross-device routing are separate
cnb coordination features, not enforced by this viewer.

Build it locally with:

```bash
./script/build_vision.sh
```

Run it on the visionOS simulator with:

```bash
./script/run_vision_simulator.sh
```

The runner exports `~/.cnb/feishu_chat.json`, boots an Apple Vision Pro
simulator, builds `CNBVision`, installs it, copies the Feishu config into the
app data container, and launches the app. Override the simulator with
`CNB_VISION_SIMULATOR_DEVICE="Apple Vision Pro"`.

## Admin To Do

The status tab reads `ADMIN_TO_DO.md` from the app data container and presents it
as actionable maintainer work instead of requiring the user to inspect the root
Markdown file manually. `run_iphone_simulator.sh` and `run_physical_iphone.sh`
copy the repository-level `ADMIN_TO_DO.md` into app `Documents` alongside
`live_state.json` and `feishu_chat.json`.

## Viewing

The runtime path is iPhone-simulator only and refuses to continue if a visionOS
simulator is already booted:

```bash
./script/run_iphone_simulator.sh
```

The script exports the current cnb state, boots an iPhone simulator, builds and
installs the host app plus WidgetKit extension, copies `~/.cnb/live_state.json`,
`~/.cnb/feishu_chat.json`, and `ADMIN_TO_DO.md` into the app container, starts
the system Live Activity, then terminates the app so the native Dynamic Island
remains visible on the Home Screen. Override the device with
`CNB_IOS_SIMULATOR_DEVICE="iPhone 17 Pro"`.

For physical iPhone development, use the dedicated device path. It builds signed
iphoneos products in `/private/tmp` to avoid Desktop/File Provider xattrs, then
installs, copies the current CNB state into the app data container, and launches
with Live Activity autostart:

```bash
CNB_IOS_DEVICE="Kezhen 的 iPhone 深蓝色" ./script/run_physical_iphone.sh
```

The script defaults to `CNB_DEVELOPMENT_TEAM=N2PMDDULMW` and fails early with
device-connection instructions if CoreDevice reports the iPhone as unavailable.

The non-runtime visual path is Xcode's WidgetKit preview canvas:

1. Open `CNBIsland.xcodeproj` manually.
2. Select `Sources/CNBIslandWidget/CNBIslandLiveActivity.swift`.
3. Use the previews named `CNB Lock Screen`, `CNB Island Compact`,
   `CNB Island Expanded`, and `CNB Island Minimal`.

The implementation uses `Resources/Localizable.xcstrings` for Simplified
Chinese and English strings. `zh-Hans` is the development language and default
export locale. Set `CNB_LIVE_STATE_LOCALE=en` when exporting state to write
English dynamic title/detail text.

For the first local-Mac product, build and run `../cnb-mac-companion/`. For a
paired-Mac menu-bar Live Activity product, the remaining production step is a
real transport from Mac cnb state to the iPhone host app plus signing.
