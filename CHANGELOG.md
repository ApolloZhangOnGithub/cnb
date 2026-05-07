# Changelog

## 0.5.0 (2026-05-08)

### Bug Fixes

- **Swarm: stale session detection** — `swarm start` now checks if the agent process is actually running, not just whether the tmux session exists. Stale sessions (agent exited, shell lingering) are automatically cleaned up and restarted. `swarm status` shows "stale" for these sessions instead of falsely reporting "running".
- **Dispatcher: zombie process prevention** — Added PID lock (`dispatcher.pid`) to prevent multiple dispatcher instances. Root cause of the clock message storm (70+ zombies each sending hourly announcements). Pidfile is cleaned up on graceful shutdown.
- **Dispatcher: clock message storm** — `TimeAnnouncer` now initializes `last_hour` to current hour on startup, preventing duplicate hourly announcements when dispatcher restarts mid-hour.
- **Nudge: hyphenated session names** — `_nudge_session` used `isalnum()` which rejected names like "lisa-su". Fixed to use regex `^[a-z0-9][a-z0-9_-]*$`.
- **Nudge: idle detection accuracy** — `_is_idle()` now scans last 10 lines of pane (not just last line) to find the prompt marker, accounting for Claude Code's status bar layout.
- **Dispatcher: premature exit** — Main loop no longer exits when the coral/dispatcher tmux session is missing. Now exits only when ALL dev sessions are gone.

### Features

- **Heartbeat/pulse system** — New `board pulse` command: lightweight heartbeat that updates `last_heartbeat` timestamp and returns unread count. Replaces heavy `inbox` call in PostToolBatch hooks.
- **Heartbeat status tiers** — Board views now show agent liveness: `● active` (<2m), `◐ thinking` (2-3m), `○ stale` (3-10m), `· offline` (>10m), with tmux fallback for sessions without heartbeat.
- **QueuedMessageFlusher** — New dispatcher concern that auto-sends Enter when nudged commands queue up in idle agent panes (30s cooldown).
- **Portable hook paths** — PostToolBatch hook now uses `CNB_PROJECT` env var instead of hardcoded absolute paths, works across machines.

### Tests

- 314 tests total (up from ~280)
- Added pulse/heartbeat tests (5 core + 12 status tier boundary tests)
- Heartbeat status tests cover all tier boundaries, tmux fallback, malformed timestamps

## 0.4.0 (2026-05-06)

- Renamed `cs-*` to `cnb-*` across all commands and config
- Added `CNB_PROJECT` environment variable for portable project paths
- Auto-start dispatcher from `cnb` entry point
- TUI (`cnb ui`) improvements: per-window status, direct attach
