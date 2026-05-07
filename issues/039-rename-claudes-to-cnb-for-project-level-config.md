---
number: 39
title: "Rename .claudes/ to .cnb/ for project-level config"
state: OPEN
labels: []
assignees: []
created: 2026-05-07
updated: 2026-05-07
---

# #39 Rename .claudes/ to .cnb/ for project-level config

**State:** OPEN

---

## Problem

CNB uses `.claudes/` for project-level data (board.db, config.toml, sessions/, logs/), but:

1. The CLI is called `cnb` — convention says config dir should be `.cnb/` (like `.git/`, `.cargo/`, `.docker/`)
2. The global registry already uses `~/.cnb/` — inconsistent with project-level `.claudes/`
3. `.claudes/` is easily confused with Claude Code's own `.claude/` directory (one letter difference)

## Proposed structure

```
.claude/              # Claude Code's own config (managed by Claude Code)
  commands/
    cnb-*.md          # CNB writes slash commands here (only cross-boundary point)

.cnb/                 # CNB's project data (renamed from .claudes/)
  board.db
  config.toml
  sessions/
  logs/
  keys/
  cv/
  files/
  okr/
```

## Migration

- Rename `.claudes/` → `.cnb/` in all code
- Add fallback: if `.cnb/` doesn't exist but `.claudes/` does, auto-migrate (rename + warn)
- Update `.gitignore` templates
- Update CLAUDE.md injection to reference `.cnb/`
- Update docs (README, CONTRIBUTING)

## Why not `.claude/cnb/`?

Coupling risk. `.claude/` is owned by Claude Code — if they change its structure, CNB breaks. Separate directories = each tool owns its own space. The only intentional coupling is slash commands in `.claude/commands/`.
