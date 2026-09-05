---
number: 238
title: "follow-up: consolidate bin/cnb update-check into Python (post #224 deferred)"
state: OPEN
labels: ["phase:2", "infra", "priority:p2"]
assignees: []
created: 2026-05-17
updated: 2026-05-17
---

# #238 follow-up: consolidate bin/cnb update-check into Python (post #224 deferred)

**State:** OPEN
**Labels:** phase:2, infra, priority:p2

---

## Background

PR #228 (merged into PR #224) attempted to replace the bash `_check_update` in `bin/cnb` with a call into `bin/board update-check` so both entry points share one implementation. That consolidation was reverted in commit 94b0c6d on PR #224 because:

- Sync hook (`bin/board update-check --quiet 2>/dev/null || true` before subcommand dispatch) broke `test_global_registry.py::TestCmdProjectsScan::test_bin_cnb_projects_scan_dispatches_json_contract` on Linux CI (empty stdout for `cnb projects scan --json`; could not reproduce locally on macOS).
- Detached variant (`( ... ) & disown`) fixed that test but broke `test_version_subcommand_notifies_lead_when_outdated` — the notification didn't fire before the test's inbox check.

So both paths exist today: `bin/board update-check` (Python, for tongxue invoking `board` directly) and the legacy `_check_update` bash (for `cnb <subcmd>` and interactive banner). Small amount of duplicated logic.

## Goal

Get back to one source of truth without the CI failures above.

## Approach to try

- Reproduce the original failure on a Linux box (the bug is OS-specific — local macOS passes both tests).
- Likely candidates: bash 5 vs 3.2 behavior under `set -euo pipefail`, fd-inheritance differences, Python subprocess startup time differences.
- Once reproduced, fix narrowly and re-land the consolidation.

## Acceptance

- Single implementation of update-check (no bash `_check_update` in `bin/cnb`).
- `test_global_registry.py::test_bin_cnb_projects_scan_dispatches_json_contract` passes on Linux CI.
- `test_entrypoint.py::test_version_subcommand_notifies_lead_when_outdated` passes on Linux CI.
- No regression in tests that were green before.

## Not urgent

Functional state is fine (KR2 #43 shipped via the Python `bin/board` hook). This is code-hygiene cleanup, not a blocker.
