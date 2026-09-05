---
number: 147
title: "Decision: keep Mac companion native; defer Electron to a future cross-platform console"
state: OPEN
labels: ["enhancement", "phase:3", "decision", "module:mac-companion", "priority:p2"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #147 Decision: keep Mac companion native; defer Electron to a future cross-platform console

**State:** OPEN
**Labels:** enhancement, phase:3, decision, module:mac-companion, priority:p2

---

## Decision

Do not migrate the CNB Mac companion/device-supervisor app to Electron for the 1.0-alpha or early 1.0 path.

Keep the Mac companion native Swift/SwiftUI/AppKit-first while the product surface is primarily:

- menu bar status;
- device-supervisor health;
- local terminal/TUI/watch integration;
- macOS permissions and local filesystem/process integration;
- low idle resource usage;
- iCloud/local path awareness;
- future Apple Health / wellbeing signals.

Electron should remain a future option only for a separate cross-platform web console if Windows/Linux users become a first-class target and shared web UI velocity matters more than native Mac integration.

## Why not Electron now

Electron is good for shipping the same HTML/CSS/TypeScript UI across platforms, but it is heavy for a Mac-local supervisor:

- larger app bundle and memory footprint;
- weaker native macOS feel than SwiftUI/AppKit;
- more indirection for permissions, menu bar, local process, health, and file integrations;
- encourages web-console thinking before the owner workflow is stable;
- risks copying OpenClaw/Hermes-style broad platform scope too early.

## When to revisit

Reopen the decision only if at least two of these become true:

- Windows/Linux desktop users are an explicit 1.x target;
- the same console must run on web, desktop, and remote devices;
- the SwiftUI app becomes a drag on UI iteration speed;
- a React/TypeScript team or plugin ecosystem becomes central;
- the Mac app is only a thin shell around a web console;
- native-only features are no longer differentiating.

## Alternative path

A better staged architecture:

1. Keep Mac companion native for device-supervisor ownership.
2. Expose local/cloud state through `cnb-sync-gateway` and stable JSON APIs.
3. Build a web console later using TypeScript/React only if cross-platform demand is proven.
4. If desktop packaging is needed, evaluate Tauri before Electron for lighter footprint.
5. Keep native SwiftUI for Mac-specific health, menu bar, shortcut, file/process, and local automation surfaces.

## Competitive reference

Observed patterns:

- ChatGPT macOS app on this machine appears native: no Electron Framework and no `app.asar`; bundle includes App Intents resources and standard macOS app structure.
- Claude desktop app on this machine is Electron: it contains Electron Framework and `app.asar`.
- DeepSeek official product is primarily web/mobile; public third-party desktop wrappers commonly use Electron around `chat.deepseek.com`.
- OpenClaw is very broad and TypeScript-heavy because it prioritizes multi-channel integrations, plugin SDK, UI, and companion apps.

## Acceptance criteria

- The product roadmap explicitly treats Electron as deferred, not assumed.
- Mac companion work continues in SwiftUI/AppKit for 1.0-alpha.
- Cross-platform console requirements are collected separately before any migration.
- Any future Electron/Tauri decision must include memory footprint, startup time, native permission surface, and owner workflow tradeoffs.

