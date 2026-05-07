---
number: 38
title: "Token usage tracking: hard to discover / undocumented"
state: OPEN
labels: []
assignees: []
created: 2026-05-07
updated: 2026-05-07
---

# #38 Token usage tracking: hard to discover / undocumented

**State:** OPEN

---

## Problem

When running a 6-session CNB team (TokenDance BBS project), I needed to check token usage across all sessions. I searched exhaustively through:

- All `bin/` scripts (cnb, board, swarm, dispatcher, doctor, registry)
- All `lib/*.py` and `lib/concerns/*.py` modules
- `schema.sql` and board.db tables
- `.claudes/` directory (sessions, logs, config, attendance)
- CHANGELOG, README, CLAUDE.md

Could not find any built-in command to query token usage.

## What I found

The raw data exists in Claude Code's JSONL files at `~/.claude/projects/<project>/`, where each message entry has `message.usage` with `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`. But there's no CNB command to aggregate this.

I wrote a manual aggregation script and got useful results (per-session breakdown + cost estimate), but this should be a first-class feature.

## Suggestion

A command like `cnb usage` or `cnb board usage` that:
1. Finds all session JSONLs for the current project
2. Aggregates token counts per session
3. Estimates cost based on model pricing
4. Shows a summary table

Example output:
```
Session       Input     Output    Cache W      Cache R    Est. Cost
──────────── ────────── ────────── ────────── ──────────── ─────────
rubo                215    109,119    322,025   12,821,241    $8.50
chenlin             174    102,837    262,522   10,114,674    $7.20
...
TOTAL            53,584    537,613  1,646,614   52,243,100   $30.07
```

## Environment
- cnb v0.5.1-dev
- 6 sessions, ~30 min runtime
- macOS Darwin 25.4.0
