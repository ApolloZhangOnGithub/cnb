# Changelog

## 0.5.4-dev (unreleased)

### Features

- **Notification push system (Issue #33)** — Full notification infrastructure: TOML-based subscription config (`notifications.toml`), `NotificationPushConcern` for realtime @mention and bug activity delivery, `DigestScheduler` for daily/weekly digest scheduling, `generate_daily_digest` for activity summaries, and `bin/notify` CLI for subscription management, test delivery, and notification log viewing. Includes `notification_log` DB table for dedup.
- **Pending actions queue** — `board pending` subcommand for tracking actions requiring user intervention (auth, approve, confirm). Supports add/list/verify/retry/resolve lifecycle with subprocess-based verification.

### Bug Fixes

- **BBS LIKE wildcard injection** — Thread ID prefix matching (`LIKE ?`) did not escape `%` and `_` wildcards in user input. Added `_escape_like()` helper.
- **BBS reply atomicity** — `cmd_reply` insert and notification message were in separate transactions; wrapped in single `with db.conn()` block.
- **board_lock pgrep timeout** — `subprocess.run(["pgrep", ...])` in `cmd_git_unlock` had no timeout. Added `timeout=5`.
- **parse_flags silent truncation** — Value flag at end of args (missing value) silently returned partial results. Now prints error and raises `SystemExit(1)`.
- **resources _load_prev_state crash** — `read_text()` could raise `OSError` on unreadable state file, crashing monitor loop. Added try/except.
- **npmignore recursive pycache** — `__pycache__` pattern only matched top-level. Added `**/__pycache__/` for nested directories.

### Tests

- Notification config (29): load, is_subscribed, channel_for, subscribers_for, TOML parsing
- Notification push (27): mention regex, scan mentions/bugs, dedup, delivery, config reload
- Digest (16): daily digest generation, all sections, edge cases, truncation
- Digest scheduler (13): timing, daily/weekly send, dedup, subscriber filtering
- Notify CLI (28): status, subscriptions, test, digest, log, routing
- Board pending (28): add/list/verify/retry/resolve, validation, subprocess mock

## 0.5.1 (2026-05-08)

### Features

- **NudgeCoordinator** — Unified nudge concern replacing separate InboxNudger/QueuedMessageFlusher/IdleNudger. Enforces per-session cooldown across all nudge types, priority ordering (inbox > queued flush > idle), effectiveness tracking with exponential backoff, and cached session status checks.
- **Stale session detection** — `swarm start` now detects sessions where agent exited but tmux lingers, auto-cleans and restarts them. `swarm status` shows "stale" state.
- **Themes: threebody & titan** — Two new themes: `threebody` (三体 characters) and `titan` (科技先锋 — Chinese + international tech leaders). Removed `pokemon` theme.
- **Theme profiles** — New `lib/theme_profiles.py` provides full-name + info profiles for all person-name themes (ai, threebody, titan). Profiles are injected into agent system prompts at startup so agents know who they're named after.

### Bug Fixes

- **Dispatcher pid lock cleanup** — Pidfile removed on graceful shutdown, preventing stale locks.
- **TimeAnnouncer restart safety** — Initializes `last_hour` to current hour on startup, preventing duplicate announcements.
- **TimeAnnouncer dedup** — DB-level dedup check prevents duplicate clock messages under concurrent dispatchers.
- **AI theme duplicate names** — `sutskever` and `amodei` were duplicates of `ilya` and `dario` (same people, different name forms). Replaced with `vaswani` (Ashish Vaswani, Transformer inventor) and `radford` (Alec Radford, GPT author).
- **SessionBackend missing abstract method** — `inject_initial_prompt` was implemented in TmuxBackend/ScreenBackend but not declared in the ABC, so custom backends would silently lack it. Added to `SessionBackend`.
- **board_bbs thread view crash** — `query_one` could return `None` and be unpacked directly, crashing with `TypeError`. Added guard.
- **board_mailbox binascii import** — `base64.binascii.Error` works at runtime but is not recognized by type checkers. Changed to explicit `import binascii`.
- **board_task type safety** — `task_id` variable was reused across `str | None` and `int` assignments, masking potential `TypeError`. Refactored to separate `raw_id`/`task_id`.
- **FileWatcher fd leak** — `_loop()` now wraps kqueue setup and event loop in try/finally, ensuring all file descriptors and kqueue are closed on any exception. `_refresh()` closes fd if `kq.control()` fails after `os.open()`.
- **KqueueWatcher fd leak** — Same `_refresh()` fix applied to `lib/monitor.py` KqueueWatcher.
- **board_msg/board_admin missing timeouts** — `_nudge_session` and `cmd_suspend` subprocess calls now have `timeout=5` and catch `TimeoutExpired`/`OSError`.
- **board_vote eligible count** — `eligible` voter count query fixed to exclude dispatcher session correctly.
- **npm package.json drift** — Version was 0.4.2-dev (should be 0.5.1-dev), license was MIT (should be OpenAll-1.0). Fixed and added `bin/sync-version` script + CI check to prevent recurrence.

### Tests

- **908 tests total** (up from 314 — nearly tripled)
- NudgeCoordinator (16): cooldown, backoff, priority, offline sessions, structure
- Dispatcher (6): pid lock, TimeAnnouncer init
- Concern helpers (35): tmux ops, session detection, board_send, process inspection
- FileWatcher (15): tick/queue, suspension filtering, thread lifecycle
- BoardDB (27): connection lifecycle, query methods, deliver_to_inbox, signals
- Board admin (21): suspend, resume, kudos, kudos leaderboard
- Board mailbox (16): keygen, seal/unseal encryption, mailbox log
- Board lock (23): git lock acquire/extend/block, force-unlock, index.lock cleanup
- Board view (24): heartbeat status, P0 detection, file retrieval, history, freshness
- Board messaging (17): send/inbox/ack validation
- Migrate (15): schema migration discovery, version tracking, apply/skip
- Maintenance (17): prune, backup, restore, dry-run
- Doctor (23): DB integrity, orphan detection, config, Python version, disk space
- Resources (14): notify_if_changed state transitions/dedup, JSON serialization
- Notifications (21): InboxNudger, QueuedMessageFlusher, TimeAnnouncer, BugSLAChecker
- Board messaging ops (22): send/inbox/ack/status/log with attachments
- Health concerns (15), coral (12), idle concerns (22), adaptive throttle (9)
- Entrypoint (25): worker clamping, theme selection, banner, system prompt, slash commands
- Concern base (18): should_tick, maybe_tick, interval, subclassing
- Monitor (17): PollWatcher, create_watcher, handle_change
- Inject (18): detect_mode, send_tmux/screen, inject
- Health (15): get_sessions, is_claude_running, session_status
- Swarm backend (38): TmuxBackend, ScreenBackend, detect_backend
- Panel (7): status_icon pattern matching
- Board bug (32): report, assign, fix, list, overdue
- Board vote (14): vote, propose, tally, auto-decision
- Sync-version (13): conversions, check, sync, main modes
- Board TUI (17), CLI (4), theme profiles (12)

## 0.4.1 (2026-05-08 03:25)

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
