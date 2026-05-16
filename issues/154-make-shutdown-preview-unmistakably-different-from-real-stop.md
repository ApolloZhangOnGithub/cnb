---
number: 154
title: "Make shutdown preview unmistakably different from real stop"
state: OPEN
labels: ["phase:1", "infra"]
assignees: []
created: 2026-05-10
updated: 2026-05-10
---

# #154 Make shutdown preview unmistakably different from real stop

**State:** OPEN
**Labels:** phase:1, infra

---

## Problem

`cnb shutdown --dry-run` is technically safe, but in operator conversations its output is too easy to misread as a successful shutdown summary. In this session I treated a dry-run result as if it reflected actual stop state, which created avoidable confusion.

## Why this matters

Shutdown / offboarding is a high-trust operational action. A preview mode must be unmistakably non-destructive in both CLI output and downstream summaries, otherwise people can walk away believing the machine was stopped when it was only simulated.

## Desired behavior

- Dry-run output should scream `PREVIEW ONLY / NO ACTION TAKEN`.
- Any summary or status view derived from a dry-run should be clearly labeled as simulated.
- Shutdown-related helpers should separate `would happen` from `did happen` in a way that is hard to mistake in chat transcripts and logs.

## Reflection from this run

I used `cnb shutdown --dry-run` while answering a question about actual stop state, then spoke about the preview as if it were the real shutdown path. The command behaved correctly; the operational presentation was too easy to confuse.

## Related

- #41 Automated shift report: cnb shutdown flow
- #76 Organization reform: clarify authority, ownership, and shutdown governance

