---
number: 152
title: "Keep Mac awake while Feishu device supervisor is on duty"
state: CLOSED
labels: ["bug", "infra"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
closed: 2026-05-10
---

# #152 Keep Mac awake while Feishu device supervisor is on duty

**State:** CLOSED
**Labels:** bug, infra

---

## Context

The Mac can auto-lock, sleep, or enter screensaver while the Feishu-routed device supervisor is expected to remain reachable. When that happens, the webhook/tmux path may still look partially alive, but the user-facing control loop becomes unreliable from mobile.

Observed during device-supervisor dogfooding on 2026-05-10: the user noticed the Mac automatically locks or starts screensaver during a remote supervision session.

## Expected behavior

When `cnb feishu start` brings the machine-level device supervisor bridge online on macOS, CNB should keep the machine awake for that duty window without permanently changing system settings.

## Proposed fix

Use macOS `caffeinate` as a lifecycle-scoped companion for the Feishu bridge / device supervisor runtime. The inhibitor should:

- start only on macOS and only when `caffeinate` is available;
- prevent idle sleep and display sleep while the Feishu device-supervisor bridge is running;
- stop when `cnb feishu stop` stops the bridge;
- be visible in `cnb feishu status`;
- not require sudo or mutate Energy Saver / Lock Screen settings.

## Acceptance criteria

- `cnb feishu start` starts a lifecycle-scoped caffeine process on macOS.
- `cnb feishu stop` stops that caffeine process.
- `cnb feishu status` reports whether caffeine is active, unavailable, or disabled.
- Non-macOS platforms degrade cleanly without failing bridge startup.
- Tests cover start/stop/status behavior without invoking the real `caffeinate`.

## Related area

- `lib/feishu_bridge.py`
- `docs/feishu-bridge.md`
- device supervisor runtime reliability

