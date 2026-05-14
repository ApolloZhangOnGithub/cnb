---
number: 78
title: "Documented /cnb activation path has no installed slash command"
state: CLOSED
labels: ["bug", "phase:1", "infra"]
assignees: []
created: 2026-05-09
updated: 2026-05-09
closed: 2026-05-09
---

# #78 Documented /cnb activation path has no installed slash command

**State:** CLOSED
**Labels:** bug, phase:1, infra

---

## Problem

The README recommends activating the machine-level terminal supervisor from any Claude Code session with `/cnb`, but the implementation does not generate a `/cnb` slash command.

Documented path:

```bash
claude          # start Claude Code normally, anywhere
/cnb            # activate terminal supervisor mode
```

Implementation evidence from the current checkout:

- `bin/cnb` creates `.claude/commands/cnb-watch.md`, `cnb-overview.md`, `cnb-progress.md`, `cnb-history.md`, `cnb-pending.md`, `cnb-update.md`, and `cnb-help.md`.
- There is no `.claude/commands/cnb.md` generation.
- `tests/test_entrypoint.py::TestSlashCommands::test_slash_commands_created` asserts only the `cnb-*` commands, not `/cnb` itself.

## Impact

The recommended quick-start path is likely a dead end for new users. This is especially serious now that the terminal supervisor role is supposed to be the machine-level entry point for managing all local cnb projects.

## Expected behavior

One of these should be true:

1. `/cnb` exists as an installed slash command and starts/attaches the terminal supervisor flow, or
2. README stops advertising `/cnb` and documents the actual available command.

## Suggested fix

- Add `.claude/commands/cnb.md` generation in `bin/cnb` or `bin/init`.
- The command should route to the terminal supervisor entrypoint, not a per-project background worker.
- Add a regression test that checks `cnb.md` exists and contains the correct activation instructions.
- Keep `/cnb-help` listing aligned with the actual command set.
