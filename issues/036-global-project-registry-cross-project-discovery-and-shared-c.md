---
number: 36
title: "Global project registry: cross-project discovery and shared credentials"
state: CLOSED
labels: []
assignees: []
created: 2026-05-07
updated: 2026-05-07
closed: 2026-05-07
---

# #36 Global project registry: cross-project discovery and shared credentials

**State:** CLOSED

---

## Problem

On the same machine, multiple cnb projects each have their own `.claudes/` and don't know about each other. But some state is machine-level — npm tokens, lark auth, etc. When one project discovers a token expired, others have no way to know until they hit the same wall independently.

## Design

### Global config directory: `~/.cnb/`

```
~/.cnb/
  projects.json            # registry of all projects on this machine
  shared/
    credentials.json       # shared credential status (not secrets — just valid/expired)
    pending_actions.json   # machine-level pending user actions
```

### projects.json

```json
{
  "projects": [
    {"path": "/path/to/project-a", "name": "cnb", "last_active": "2026-05-08T04:00:00Z"},
    {"path": "/path/to/project-b", "name": "other", "last_active": "2026-05-07T10:00:00Z"}
  ]
}
```

### Workflow

1. `cnb init` auto-registers into `~/.cnb/projects.json`
2. Any project discovers token expired → writes `~/.cnb/shared/credentials.json` marking `npm: expired`
3. Other projects see the flag on startup → skip the wall, add to pending actions
4. User fixes it once (`npm login`) → flag updated to `valid` → all projects benefit
5. `cnb doctor` checks global shared state

### CLI commands

```bash
cnb projects list                      # list all projects on this machine
cnb projects broadcast "message"       # notify all projects
cnb projects cleanup                   # remove stale entries
```

### Integration points

- `cnb init` → register
- `cnb doctor` → check global state
- credential checks → read/write shared status
- pending_actions (#34) → can be global or per-project

## Implementation

1. `lib/global_registry.py` — read/write `~/.cnb/` files
2. `bin/cnb` subcommand `projects` 
3. Hook into `cnb init` for auto-registration
4. Hook into `cnb doctor` for global health check
5. Tests
