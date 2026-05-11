# Tool Entrypoints

This directory contains executable entrypoints for cnb. Keep the root README focused on product positioning and the shortest user path; put tool usage notes here or in a dedicated runbook under [`../tools/`](../tools/).

## Entry Points

| Tool | Purpose | Usage Notes |
| --- | --- | --- |
| `cnb` | Main CLI for project init, team launch, management, registry, Feishu bridge, and project discovery. | Detailed project discovery usage lives in [`../tools/project-discovery/README.md`](../tools/project-discovery/README.md). |
| `cnb capture` | Receives user-authorized browser/app captures and stores `.cnb/captures/<id>/` artifacts. | Protocol notes live in [`../docs/capture-protocol.md`](../docs/capture-protocol.md) and [`../tools/web-capture/README.md`](../tools/web-capture/README.md). |
| `board` | Lower-level board operations: inbox, messages, status, tasks, ownership, pending actions, and views. | Prefer `cnb board ...` unless a test or script needs the direct entrypoint. |
| `swarm` | Starts and manages background tongxue sessions. | Usually invoked through `cnb` during normal operation. |
| `dispatcher` / `dispatcher-watchdog` | Monitors board activity and keeps coordination moving. | Background infrastructure; document operational changes before changing defaults. |
| `doctor` | Health checks for local cnb prerequisites and project state. | Use before diagnosing environment issues. |
| `hygiene` | Reports generated files, local runtime state, and suspicious untracked work. | Use before cleanup in a dirty shared worktree; it does not delete files. |
| `cnb resources` | Read-only resource and process-pressure diagnostics. | `--processes` groups high CPU/RSS processes and recommends safe next actions without stopping anything. |
| `registry` | Contributor registry helper. | Used by contributors to register identities and roles. |
| `notify` | Notification delivery helper. | Check configuration and side effects before using in automation. |
| `secret-scan` | Local secret scanning helper. | Run before committing changes that may contain credentials. |
| `check-readme-sync` | Verifies root README section parity between English and Chinese files. | Run when changing README sections. |
| `check-changelog` | Validates changelog entries. | Run when release notes or changelog fragments are touched. |
| `sync-version` | Synchronizes version metadata. | Use during release/version work. |

## Documentation Rule

If a tool has flags, persistent side effects, background processes, or a non-obvious workflow, add or update a README near the tool in the same change:

- Use this file for the executable map.
- Use `../tools/<tool-name>/README.md` for command-specific runbooks.
- Link to the implementation file and tests.
- Include invocation, required config or environment variables, state touched, verification commands, and safety notes.
