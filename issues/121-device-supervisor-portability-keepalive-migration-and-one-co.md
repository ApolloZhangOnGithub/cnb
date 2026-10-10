---
number: 121
title: "Device supervisor portability: keepalive, migration, and one-command bootstrap"
state: OPEN
labels: ["enhancement", "phase:2", "infra", "priority:p1"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #121 Device supervisor portability: keepalive, migration, and one-command bootstrap

**State:** OPEN
**Labels:** enhancement, phase:2, infra, priority:p1

---

## Problem

The Feishu remote-control path is now useful, but it still depends on the current Mac staying awake, online, authenticated, and correctly configured. If the user takes the Mac outside, closes the lid, changes network, or wants to move the device supervisor to a different machine, CNB needs a reliable portability story.

## Product direction

Do not treat a moving laptop as the durable control plane. The durable path should be:

1. Keep a stationary always-on host as the primary device supervisor, or make the current host explicitly kept awake while plugged in.
2. Treat live tmux/Codex/Claude sessions as non-migratable runtime state.
3. Migrate durable CNB state through checkpoint/export/import and restart/re-hydrate sessions on the target host.
4. Make first-time setup one command plus explicit user-owned credential authorization.

## Scope

### Keepalive

- launchd service for `cnb feishu start` / bridge watchdog.
- launchd or tmux-managed tunnel service for ngrok/watch.
- optional `caffeinate` helper for plugged-in temporary laptop operation.
- health check that reports Mac sleep risk, battery/power state, tunnel state, bridge state, and watch state.

### Migration

- `cnb device checkpoint` writes handoff state for the device supervisor:
  - registered projects;
  - per-project `.cnb/board.db` / ownership / tasks / status;
  - current Feishu bridge config with secrets redacted;
  - open issues and handoff notes;
  - current git remotes / branches / dirty status summary.
- `cnb device restore` consumes a checkpoint and recreates project registry and config skeletons.
- Explicitly do not live-migrate tmux/Codex/Claude processes.

### One-command bootstrap

- `cnb device bootstrap` checks/install prompts for:
  - Python / npm package;
  - tmux;
  - Codex or Claude Code CLI;
  - ngrok binary, with a clear user-owned `ngrok config add-authtoken ...` step;
  - Feishu app credentials and webhook URL verification;
  - GitHub auth where needed.
- It should end with runnable verification:
  - `cnb feishu status`;
  - unauthenticated watch route returns 403;
  - authenticated watch route returns 200;
  - test reply succeeds.

### Optional HA later

- device registry with active primary / standby hosts;
- heartbeat and stale primary detection;
- stable tunnel provider abstraction, preferably Cloudflare Tunnel or a fixed domain;
- manual failover first, automatic failover later.

## Acceptance criteria

- A user can bootstrap a fresh Mac or always-on host without reading internal docs.
- Secrets are never included in portable bundles by default.
- The tool clearly tells the user which credentials must be authorized per host.
- The migration story preserves durable project/team state and clearly explains that live terminal processes are restarted, not moved.

