# Changelog

## 0.5.46-dev (unreleased)

### Documentation

- **Deployment closeout notes** - Appended the custom-domain deployment status, HTTPS follow-up commands, and first `c-n-b` npm release reminders without replacing the existing runbooks.

## 0.5.45-dev (unreleased)

### Documentation

- **c-n-b package rename** — Renamed the public package surface from the retired name to `c-n-b`, updated install commands, release workflows, and site copy, and added a CI branding check to prevent wrong npm install guidance.

## 0.5.44 (2026-05-10)

### CI/CD

- **npm publish verification retry** — Retry npmjs readback after Trusted Publishing so registry propagation lag does not fail an otherwise successful release.
- **Prepare Release PR fallback** — Keep the release branch workflow successful when repository settings block GitHub Actions from creating pull requests, and write the manual compare link to the step summary.
- **npm package metadata normalization** — Normalize the `cnb` bin path to npm's package metadata format so publish no longer auto-corrects it.

## 0.5.43 (2026-05-10)

### CI/CD

- **Trusted npm publishing** — Added the release workflow for npmjs Trusted Publishing, with GitHub Packages mirroring for repository package visibility.
- **Release preparation automation** — Added a Prepare Release workflow that updates release metadata, inserts the changelog entry, opens the release PR, and dispatches CI / CodeQL for generated branches.
- **Package smoke checks** — Centralized npm tarball validation in `bin/check-npm-package`, including required-file checks, secret-looking path rejection, and global install smoke coverage.
- **Post-publish verification** — Release publishing now verifies npm dist-tags, installs the published package from npmjs, and checks the GitHub Packages mirror.
- **Docs and site maintenance** — Added the GitHub Pages contributing page, package publishing runbook, contribution wall docs, avatar generation guidance, custom domain docs, and README maturity updates.
- **Workflow maintenance** — Updated GitHub Actions usage to the current Node 24 action generation and kept CI, CodeQL, Pages, and issue sync workflows current.

## 0.5.42-dev (unreleased)

### Documentation

- **Tongxue avatar generation** — Documented safe provider choices for AI-generated tongxue avatars, including OpenAI `gpt-image-1-mini` as the default and Apple Image Playground / `ImageCreator` as a local native-app fallback.

## 0.5.38-dev (unreleased)

### Documentation

- **Broad contribution wall** — Added a compact README contribution wall and reference document for non-commit contribution signals such as issues, reviews, checks, board ownership, and GitHub App identity evidence.

## 0.5.37-dev (unreleased)

### Documentation

- **GitHub Pages site** — Added a public project site under `site/` with a lightweight static publishing workflow to keep the product entrypoint separate from the README.
- **README maturity pass** — Added badges, start-here routing, project status evidence, architecture layers, and a repository map for both English and Chinese README files.
- **Metadata refresh** — Pointed package homepage metadata at the Pages site and expanded npm keywords to cover Codex, Feishu/Lark, local-first coordination, and developer tools.

## 0.5.36-dev (unreleased)

### Bug Fixes

- **Protected issue sync branch** — Updated the issue mirror workflow to push generated issue snapshots to a bot branch and open or update a pull request instead of pushing directly to protected `master`.
- **Issue sync PR fallback** — Let the issue mirror workflow complete after pushing the sync branch when repository settings block GitHub Actions from creating pull requests.
- **Issue sync lease refresh** — Fetch the existing sync branch before using `--force-with-lease`, avoiding stale-lease failures on repeated workflow runs.
- **Issue mirror version gate** — Allow generated `issues/` mirror-only changes to skip the VERSION bump requirement while preserving the gate for code and documentation updates.
- **Issue mirror merge-base check** — Preserve full base history in the VERSION gate so `origin/master...HEAD` works for generated issue mirror branches.

## 0.5.31 (2026-05-10)

### Features

- **Ownership autonomy (Issue #45)** — Full ownership lifecycle: `board own claim/list/disown/map` for path-based ownership registry, `task done` auto-runs pytest before marking complete (skip with `--skip-verify`), auto-creates PR via `gh pr create` on feature branches after verified completion, `board scan` checks GitHub issues and CI status and routes notifications to path owners. Migration 008 adds `ownership` table.
- **`.claudes/` → `.cnb/` rename with backward compatibility** — New projects initialize to `.cnb/`. Existing `.claudes/` projects keep working via fallback in `find_claudes_dir()`, `bin/cnb`, `bin/init`, and `lib/migrate.py`. Prints migration hint when legacy directory detected.

- **Notification push system (Issue #33)** — Full notification infrastructure: TOML-based subscription config (`notifications.toml`), `NotificationPushConcern` for realtime @mention and bug activity delivery, `DigestScheduler` for daily/weekly digest scheduling, `generate_daily_digest` for activity summaries, and `bin/notify` CLI for subscription management, test delivery, and notification log viewing. Includes `notification_log` DB table for dedup.
- **Pending actions queue** — `board pending` subcommand for tracking actions requiring user intervention (auth, approve, confirm). Supports add/list/verify/retry/resolve lifecycle with subprocess-based verification.
- **Global project registry (Issue #36)** — `lib/global_registry.py` for cross-project discovery and shared credential status tracking. Registry at `~/.cnb/` stores project list and credential status (valid/expired/unknown). Integrated into `bin/init` (auto-register), `bin/cnb projects list|cleanup`, and `bin/doctor` (stale project and expired credential checks).
- **Token usage tracking (Issue #38)** — `cnb usage` command parses Claude Code JSONL session logs to show per-agent token usage and estimated API costs. Summary view aggregates by agent name; `--detail` shows per-session breakdown. Supports Opus, Sonnet, and Haiku pricing.
- **Automated shutdown flow (Issue #41)** — `cnb shutdown` orchestrates the full shift-end flow: broadcast shutdown notice, wait for acks (configurable timeout), auto-collect per-agent daily reports (`lib/shift_report.py`), generate `_meta.md` shift summary, save to `dailies/{shift}/`, and stop all sessions. Supports `--dry-run`, `--no-stop`, `--skip-broadcast`, `--timeout` flags. Includes `lib/shift_report.py` for per-agent report generation and shift metadata with git commit counts.

### Bug Fixes
- **GitHub Packages mirror workflow** — Added a manual workflow that mirrors an already-published npmjs `c-n-b` release into the scoped GitHub Packages package `@apollozhangongithub/cnb`, keeping the GitHub sidebar populated without changing the canonical npmjs install path.
- **npm dependency disclosure** — Added package metadata and install documentation so npm users do not mistake the JavaScript dependency count for the full runtime requirements. The package now declares Node support and optional peer CLIs for Claude Code / Codex while documenting Python, tmux, git, and `cryptography`.
- **Package visibility documentation** — Clarified that the installable `c-n-b` package lives on npmjs.com while GitHub's repository Packages sidebar only shows GitHub Packages. Added npm release tag guidance and package metadata links.
- **BBS LIKE wildcard injection** — Thread ID prefix matching (`LIKE ?`) did not escape `%` and `_` wildcards in user input. Added `_escape_like()` helper.
- **BBS reply atomicity** — `cmd_reply` insert and notification message were in separate transactions; wrapped in single `with db.conn()` block.
- **board_lock pgrep timeout** — `subprocess.run(["pgrep", ...])` in `cmd_git_unlock` had no timeout. Added `timeout=5`.
- **parse_flags silent truncation** — Value flag at end of args (missing value) silently returned partial results. Now prints error and raises `SystemExit(1)`.
- **resources _load_prev_state crash** — `read_text()` could raise `OSError` on unreadable state file, crashing monitor loop. Added try/except.
- **npmignore recursive pycache** — `__pycache__` pattern only matched top-level. Added `**/__pycache__/` for nested directories.
- **board_mail LIKE ESCAPE missing** — `_escape_like()` was applied to mail recipient/CC matching but the SQL lacked `ESCAPE '\\'`, making the escaping ineffective. Added ESCAPE clause.
- **board_view cmd_get LIKE injection** — File hash prefix matching used `LIKE` with `ESCAPE` clause but didn't escape user input. Applied `escape_like()`.
- **Duplicated `_escape_like` consolidated** — Three identical copies in board_bbs/board_mail/board_view merged into `common.escape_like()`.
- **board_tui osascript timeout** — `subprocess.run(["osascript", ...])` had no timeout, risking indefinite hang. Added `timeout=10`.
- **Flaky test root cause: Signal leak** — `conftest.py` autouse fixture only cleared `_db_cache` but not `inbox_delivered` Signal listeners, causing mock failures under `pytest-randomly`.
- **inject.py unhandled TimeoutExpired** — `send_tmux`/`send_screen` send-keys calls lacked try/except, crashing on slow tmux/screen responses.
- **board_tui unhandled TimeoutExpired** — `_tmux()` and `_tmux_out()` subprocess calls could crash with TimeoutExpired. Added exception handling.
- **board_view _git timeout** — `_git()` subprocess call lacked TimeoutExpired/OSError handling.
- **board_view history invalid limit** — `cmd_history` passed user input to `int()` without catching `ValueError`. Now prints error and exits.
- **panel invalid interval** — `panel.py main()` passed `sys.argv[1]` to `int()` without catching `ValueError`. Now prints error and exits.

### Security

- **Pre-commit hook auto-install** — `bin/init` now installs `bin/secret-scan` as a git pre-commit hook automatically. Appends to existing hooks, idempotent on re-run. Directly addresses BUG-005 root cause.
- **Shell injection in pending commands** — `board_pending.py` executed user-supplied verify/retry commands with `shell=True`, allowing shell metacharacter injection. Replaced with `shlex.split()`.
- **LIKE wildcard injection in history** — `cmd_history` used user input directly in a LIKE pattern without `escape_like()`. Fixed.
- **Bug assign / kudos target validation** — `_bug_assign` and `cmd_kudos` accepted arbitrary target names without checking session existence. Now reject non-existent sessions.

### Tests

- tmux_utils (30): tmux_run, tmux_ok, tmux_send, has_session, pane_command, capture_pane, is_agent_running
- Pre-commit hook (5): install in git repo, skip when no git/no script, append to existing, idempotent
- Secret-scan test fix: fixed import (ModuleNotFoundError from hyphenated filename), fixed 2 assertions (pattern ordering overlap)
- Notification config (29): load, is_subscribed, channel_for, subscribers_for, TOML parsing
- Notification push (27): mention regex, scan mentions/bugs, dedup, delivery, config reload
- Digest (16): daily digest generation, all sections, edge cases, truncation
- Digest scheduler (13): timing, daily/weekly send, dedup, subscriber filtering
- Notify CLI (28): status, subscriptions, test, digest, log, routing
- Board pending (28): add/list/verify/retry/resolve, validation, subprocess mock
- Board mail (33): send/list/read/reply, CC, threading, unread tracking, LIKE prefix regression
- Token usage (23): JSONL parsing, cost estimation, aggregation, slug generation, CLI output
- Global registry (28): register/list/remove projects, credential update/check, cleanup stale, corrupt file handling
- Shift report (23): agent report generation, shift meta, shift numbering, git commits
- Shutdown flow (20): active sessions, unread count, broadcast, wait acks, collect reports, save shift, full flow orchestration

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
