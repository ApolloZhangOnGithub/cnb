---
number: 72
title: "CI fails on clean PRs due baseline format, typecheck, and version checks"
state: CLOSED
labels: []
assignees: []
created: 2026-05-09
updated: 2026-05-09
closed: 2026-05-09
---

# #72 CI fails on clean PRs due baseline format, typecheck, and version checks

**State:** CLOSED

---

## Problem

PR #71 is based on `origin/master` with only the board-view session-state fixes, but CI fails before the PR-specific tests are relevant. These are baseline CI blockers that make remote alignment unreliable.

Observed failures from GitHub Actions run `25608283890`:

- `lint`: `ruff format --check ...` reports `Would reformat: bin/init`
- `typecheck`: Linux `mypy lib/` reports existing `Any` returns in `lib/token_usage.py` and `lib/board_own.py`, and Linux-only `select.kqueue` / `select.kevent` attribute errors in `lib/monitor.py` and `lib/concerns/file_watcher.py`
- `check-consistency`: PR merge ref reports `VERSION unchanged (0.5.23-dev)`

Local reproduction on the clean PR worktree also confirms:

- `ruff format --check ...` fails on `bin/init`
- `mypy lib/` fails on `lib/token_usage.py` and `lib/board_own.py`
- version policy fails because the PR does not bump `VERSION`

## Expected

A clean PR from `origin/master` should be able to pass CI after its own focused fixes, without unrelated baseline failures blocking merge.

## Acceptance

- Format `bin/init` to satisfy full `ruff format --check`.
- Make `mypy lib/` pass on Linux for the existing type issues.
- Apply the project version bump consistently.
- Re-run PR checks until #71 is mergeable.
