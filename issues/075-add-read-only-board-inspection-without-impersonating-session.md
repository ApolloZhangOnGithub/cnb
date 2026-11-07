---
number: 75
title: "Add read-only board inspection without impersonating sessions"
state: CLOSED
labels: ["phase:1", "infra", "priority:p1"]
assignees: []
created: 2026-05-09
updated: 2026-05-10
closed: 2026-05-10
---

# #75 Add read-only board inspection without impersonating sessions

**State:** CLOSED
**Labels:** phase:1, infra, priority:p1

---

## Problem

Project maintainers currently need to inspect another session's inbox or task queue by running commands such as:

```bash
bin/board --as <session> inbox
```

That conflates read-only observation with acting as that session. It can also write side effects such as ack marker files, and it makes operator logs look like the maintainer impersonated the session.

## Expected

Add a read-only inspection mechanism that lets privileged operators inspect session state without using `--as <target>`.

Desired properties:

- Read another session's unread inbox without marking anything seen/read.
- Read another session's task queue without mutating task state.
- Make observer identity explicit, for example `bin/board --as dispatcher inspect inbox <session>` or a no-identity read-only command.
- Do not create ack marker files for the inspected session.
- Keep existing `inbox` / `ack` behavior unchanged for the owner session.
- Tests should prove inspection has no side effects.

## Acceptance

- Add a CLI command for read-only inspection of inbox and tasks.
- Require a privileged identity for cross-session inspection if using `--as`; normal sessions should not inspect others.
- Add tests for unread inbox display, task queue display, no ack marker creation, and no read flag changes.
- Document the new command in the board command reference.

## Related

Raised during #74 maintenance sweep after an operator accidentally used `--as lead` / `--as <session>` for coordination and inspection. This issue is specifically about separating observation from impersonation.

