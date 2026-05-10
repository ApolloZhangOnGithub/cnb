# CNB Mac Companion

Native macOS companion for the device supervisor viewpoint.

This is the first-phase local Mac surface. It does not use ActivityKit, does not
boot Simulator, and does not create a floating island. It reads local cnb board
state and presents it through a normal SwiftUI app window plus a system menu-bar
extra.

## Run

```bash
./script/build_and_run.sh
```

The script builds a SwiftPM app, stages `dist/CNBMacCompanion.app`, kills any old
`CNBMacCompanion` process, and opens the fresh app bundle.

Use `./script/build_and_run.sh --verify` to build, launch, and assert that the
app process is running. Use `./script/build_and_run.sh --no-launch` for a build
only.

## Behavior

- Adds an embedded Feishu Web TUI view in the sidebar, menu-bar extra, and
  `CNB > Feishu TUI` command. The app starts the existing built-in
  `cnb feishu watch-serve` page locally and renders it with WebKit, so the
  Feishu `/watch` web link and the Mac app share the same HTML and snapshot
  refresh behavior.
- Keeps the native Feishu chat view available from the sidebar, the menu-bar
  extra, and the `CNB > Feishu Chat` command. The chat surface stays compact
  and iMessage-like; Feishu connection fields live behind the bottom-left
  Settings entry instead of the transcript.
- Reads Feishu chat settings from `~/.cnb/feishu_chat.json` first, then
  `~/.cnb/config.toml` sections `[feishu]` or `[notification.feishu]`. The
  settings panel can also store local overrides in app preferences.
- Sends text messages through Feishu OpenAPI, renders text/post/card/media-style
  message payloads into readable transcript text, and can optionally notify the
  local CNB Feishu bridge webhook after a message is sent.
- Automatically syncs the latest Feishu chat messages while the app is open.
  The transcript keeps messages in chronological order and uses Feishu
  `has_more` / `page_token` pagination to load earlier history when the user
  scrolls to the top.
- Reads `~/.cnb/projects.json`.
- Uses `<project>/.cnb/board.db` first, then legacy
  `<project>/.claudes/board.db`.
- Counts pending actions, tasks, unread inbox items, sessions, and blocked
  sessions through read-only `sqlite3` calls.
- Shows non-running registered projects as idle, and registered projects without
  a board as no-board instead of hiding them.
- Refreshes local state every five seconds while the app is running.
- Localizes UI strings with an Apple string catalog plus runtime
  `Localizable.strings` resources. The default language is Simplified Chinese;
  English is available by launching with `CNB_COMPANION_LANGUAGE=en`.
- Offers safe actions only: refresh, open project folder, open Terminal at the
  project, reveal the board database, and open `~/.cnb`.
