---
number: 114
title: "Secure remote Feishu TUI watch over tunnel"
state: CLOSED
labels: ["enhancement", "phase:2", "infra", "priority:p1"]
assignees: []
created: 2026-05-10
updated: 2026-05-15
closed: 2026-05-15
---

# #114 Secure remote Feishu TUI watch over tunnel

**State:** CLOSED
**Labels:** enhancement, phase:2, infra, priority:p1

---

## Problem

Feishu remote control is not credible if the user can only send messages but cannot inspect the live TUI from a phone. The current bridge can start a local read-only Web TUI, but the safe remote story needs explicit product support instead of an ad hoc localhost link.

## Current stopgap

- Reuse the existing ngrok webhook tunnel instead of starting a second public tunnel.
- Serve a read-only `/watch` route from the local Feishu webhook process.
- Require a random `watch_token` in the URL/query or bearer header before exposing TUI HTML or snapshot JSON.
- Keep the TUI read-only: no keyboard input, tmux attach, or command execution through the web view.

## Follow-up support plan

1. Add first-class config and CLI support for remote watch URLs:
   - `watch_public_url`
   - `watch_token`
   - token rotation command
   - redacted status output by default
2. Add tunnel provider abstraction:
   - ngrok
   - Cloudflare Tunnel
   - localhost-only fallback
   - clear handling when only one ngrok tunnel is available
3. Add mobile-oriented UX:
   - stable `/watch` route
   - auto-refresh snapshot
   - visible session/project label
   - stale snapshot indicator
4. Add safety controls:
   - read-only by default
   - random unguessable tokens
   - optional allowlisted Feishu chat/sender binding
   - no token in logs or ordinary status output
5. Add tests and docs:
   - unauthenticated `/watch` returns 403
   - authenticated `/watch` and `/watch/snapshot` return 200
   - `/cnb_watch` replies with the configured public URL when present
   - README/README_zh setup notes for phone access

## Acceptance criteria

- A user can ask from Feishu for an observation link and receive a phone-openable HTTPS URL.
- The URL shows the current device-supervisor TUI within a few seconds.
- The public route is inaccessible without the configured token.
- Restarting `cnb feishu start` preserves the configured public watch route.
- Documentation clearly distinguishes message control, TUI snapshot, read-only watch, and any future interactive remote-control mode.

