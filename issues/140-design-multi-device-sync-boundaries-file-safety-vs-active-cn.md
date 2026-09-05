---
number: 140
title: "Design multi-device sync boundaries: file safety vs active cnb runtime consistency"
state: OPEN
labels: ["enhancement", "phase:2", "infra", "migration", "priority:p2"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #140 Design multi-device sync boundaries: file safety vs active cnb runtime consistency

**State:** OPEN
**Labels:** enhancement, phase:2, infra, migration, priority:p2

---

## Problem

Users like iCloud/Drive-style sync because it protects local files and makes projects visible on multiple Macs. But cnb stores active organizational runtime state in local files and SQLite databases. Once users run multiple devices, generic file sync can create partial sync, conflict copies, stale paths, and concurrent writes to `.cnb/board.db`.

This is a product and architecture issue, not just documentation.

## Principle

Treat file safety and runtime consistency as separate layers:

- File safety: iCloud/Drive/Dropbox, Time Machine, backups, archive copies.
- Source truth: GitHub/Git remotes for code, review, PRs, releases.
- Runtime truth: cnb-controlled local state with explicit export/import, active/standby, locks, and verification.

## Requirements

- Detect when a registered project or cnb home lives inside common synced folders such as iCloud Drive, Dropbox, OneDrive, or Google Drive.
- Warn when a synced path is being used as an active cnb runtime root.
- Offer safe modes:
  - read-only/standby device;
  - local runtime state outside sync folder;
  - GitHub-only source sync;
  - explicit cnb migration bundle;
  - checkpoint before cutover.
- Never sync secrets/tokens/private keys by default.
- Do not let two devices silently act as active writers for the same project board.
- Provide user-facing guidance that respects the backup value of iCloud without pretending it is a distributed database.

## Long-term design questions

- Should cnb use an append-only event log for cross-device replication?
- Should `board.db` be export/import only, or support a real sync protocol?
- How should active writer leases work when a Mac sleeps or goes offline?
- What state belongs in Git, what belongs in cnb bundle, and what must remain machine-local?

## Acceptance criteria

- Docs explain iCloud as backup/transport, not active runtime consistency.
- Doctor/provisioning can warn on risky synced active paths.
- Migration tooling can produce a clean handoff that excludes secrets and runtime cache.
- Multi-device cutover has explicit active/standby state.
