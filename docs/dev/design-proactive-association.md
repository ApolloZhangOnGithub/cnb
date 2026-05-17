# Design — Proactive Association (#158)

Status: draft  
Owner: lisa-su  
Last updated: 2026-05-17

## Problem

Today a tongxue only speaks when spoken to. In real long-running collaboration, humans do something more useful — they *remember a related thought later* and bring it back proactively: "this is similar to what we hit in #42 last week", "the file you just touched is the one we agreed bezos owns". cnb has no first-class way to do that. Helpful adjacent context stays unsaid; the user has to ask the exact next question, every time.

(See issue #158 for the user-facing problem statement and acceptance criteria — this doc is the implementation design.)

## Goal

Add a lightweight proactive-association mechanism that lets tongxue occasionally surface related thoughts, prior-thread connections, or adjacent suggestions **when confidence is high and the interruption cost is low** — without breaking the existing reactive chat behaviour and without becoming chat noise.

## Non-goals

- General notification framework. We are not building a generic pub/sub. Reuse the board.
- Replacing inbox. Hints are a *separate ignorable layer*; the inbox is still the source of truth for "things you must read".
- Cross-project recall. v1 stays scoped to one project's board + JSONL window. Cross-project recall is the next layer once we have telemetry to justify the broader scope.
- Replacing CLAUDE.md memory. Memory captures durable preferences; hints surface ephemeral associations. Different timescales, different storage.

## Architecture

### Data model

```
hints (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  sender       TEXT NOT NULL,        -- tongxue that emitted the hint
  recipient    TEXT NOT NULL,        -- tongxue the hint is for
  body         TEXT NOT NULL,        -- short prose ("this looks related to #42")
  signals      TEXT NOT NULL,        -- JSON: which detectors fired, their weights
  confidence   REAL NOT NULL,        -- 0..1, derived from signals
  refs         TEXT,                 -- JSON: {"issues":[42], "paths":["lib/x.py"]}
  ts           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
  expires_at   TEXT NOT NULL,        -- TTL — default 7d
  surfaced_at  TEXT,                 -- set when shown to recipient
  status       TEXT NOT NULL DEFAULT 'pending'  -- pending|surfaced|expired|muted|dropped_rate
)
```

```
hint_events (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  hint_id   INTEGER NOT NULL REFERENCES hints(id),
  event     TEXT NOT NULL,    -- emit | surface | ignore | click | mute
  ts        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')),
  meta      TEXT              -- JSON, event-specific
)
```

```
hint_mutes (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  recipient  TEXT NOT NULL,
  scope      TEXT NOT NULL,   -- sender | topic
  value      TEXT NOT NULL,   -- the muted sender name or topic key
  ts         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))
)
```

Storage rationale: same SQLite as the rest of the board, no second store. Migration goes into the existing `schema.sql` evolution path.

### Detection — v1 heuristic, data-ready for v2 model

A tongxue's reply emits 0+ hints. Detection runs *after* the tongxue commits a reply, not as part of message handling, so it cannot block conversation.

Signals (v1; each contributes a weight, normalized into `confidence`):

| Signal | Weight | Rationale |
|---|---|---|
| Shared issue/PR number in recent context | 0.5 | Strongest — explicit cross-reference |
| Shared file path / module name | 0.3 | Strong but noisier (`README.md` matches everywhere) |
| Keyword overlap above threshold | 0.2 | Backstop — pure text |
| Recency decay (24h half-life) | × | Multiplier on all signals |

`confidence ≥ 0.6` → hint enters `pending`. The threshold is a config knob in `notifications.toml` per recipient (see KR3 work).

Hand-crafted v1, **logged from day one for v2**. Every emit/surface/ignore/click event lands in `hint_events`. Once we have ≥ ~10k events we can train a small classifier on "which hints land vs get ignored" and replace the weighted-sum with a learned model. Bitter Lesson alignment — the hand-crafted heuristic is scaffolding, not destination.

### Guardrails

Four layers, non-negotiable in v1:

1. **Hard rate cap**: max N hints/hour/sender per recipient (default 3). Excess hints get `status='dropped_rate'` and are logged for telemetry. Drops are final — they do not requeue when the window expires.
2. **Per-topic cooldown**: same `refs.issues[0]` or `refs.paths[0]` cannot surface a hint to the same recipient twice in 24h.
3. **Confidence threshold**: default 0.6, recipient-tunable via `notifications.toml`. Below threshold → `status='pending'` but `surfaced_at` never set.
4. **Mute knob**: `board hint mute <sender>` per recipient; `board hint mute --topic <issue|path>` per topic. Mutes write to `hint_mutes` and are checked at surface time.

### Surface placement

Hints render at the top of `board view` (per-tongxue dashboard) as a single yellow block — same visual weight as the runtime-alert block landed in #153. The pattern already proves out as "helpful, ignorable".

```
💡 from bezos (2h ago, conf 0.78)
   你刚提到的 token_usage.py 跟 PR #221 的 alert hook 共用。值得对一下。
   [ignore] board hint mute bezos
```

`board hint list` for the full audit. `board hint clear` to mark all surfaced hints `ignored`. No new keystroke required at startup — hints surface inside the existing inbox-check flow.

**Critically: hints don't poison the inbox.** Clearing them doesn't mark associated messages read; they just expire silently. Inbox-unread count is unaffected.

## CLI surface

```
board hint emit <recipient> <body> [--refs issues:42,paths:lib/x.py] [--confidence 0.8]
board hint list [--for <recipient>] [--from <sender>] [--all]
board hint clear [--for <recipient>]
board hint mute <sender>
board hint mute --topic <issue:42|path:lib/x.py>
board hint unmute <sender>
```

`emit` is normally called by a tongxue's reply pipeline, not by hand. Manual `emit` exists for debugging.

## Implementation phases

### Phase 1 — plumbing (this design's MVP)
- Add three tables to `schema.sql`.
- `lib/board_hint.py`: emit / list / clear / mute / unmute CLI handlers.
- Wire into `bin/board` registry.
- Surface block in `cmd_view` (board_view.py) above the existing runtime-alert block.
- Telemetry: log all events to `hint_events`.
- Tests: schema migration, emit/list/mute roundtrip, rate cap, cooldown, confidence threshold, mute scope (sender vs topic), no-inbox-poison.

### Phase 2 — detection
- `lib/hint_detector.py`: compute signals, confidence, emit hints. Pure function — takes (sender's recent outbox + recipient's just-received message) → list of hints.
- Hook into the tongxue reply pipeline. Async (post-commit), never blocks.
- Tests: each signal in isolation; combined confidence math; threshold behaviour.

### Phase 3 — UX polish + v2 prep
- `board hint stats` for telemetry inspection (emit-vs-surface vs-ignore rates per sender/recipient).
- Sample export: `board hint export-events --since N` to dump training data.
- Once dataset is large enough, swap weighted-sum for learned model — purely behind the `confidence` function, no schema or CLI change.

## Test plan

Per issue #158 acceptance:

1. **Positive**: tongxue A sends message referencing `#42` and `lib/foo.py` at t=0. At t=6h, tongxue B sends an unrelated question that mentions `lib/foo.py`. Hint surfaces in B's `board view`. Confidence above threshold via path-overlap signal.
2. **No-spam (rate cap)**: A emits 5 hints in 10 minutes targeted at B. Only the first 3 surface; the 4th and 5th get `status='dropped_rate'`. The 4th does *not* requeue if the rate window expires later — drop is final.
3. **No-false-positive**: A and B exchange messages on a topic neither has touched before — no hint fires (no association in either side's history).
4. **Mute respected**: B mutes A → subsequent emits from A enter `pending` but never reach `surfaced_at`. B unmutes → next emit surfaces normally.
5. **Inbox not poisoned**: B clears hints → B's unread message count is unchanged.
6. **Telemetry complete**: every emit/surface/ignore writes to `hint_events`.

## Open questions

1. **Cross-tongxue vs same-pair only.** v1 limits hints to direct sender↔recipient pairs (B receives hints only from tongxue who have messaged B before). Lead confirmed this scope. Cross-tongxue sourcing (A surfaces a hint based on C's prior thread with B) is deferred — needs a clearer privacy/permission model and arguably needs the learned model first to avoid spam.
2. **TTL on hints.** Default 7 days. Tunable per recipient via `notifications.toml`. Open: do we want auto-purge of expired hints from the table, or keep for telemetry? Lean toward keep — `status='expired'` rows fuel the v2 model.
3. **Hints across cnb restarts.** Hints are SQLite-backed → survive restart automatically. No special handling needed.

## Versioning + rollout

v1 ships behind a flag in `notifications.toml`:

```toml
[hints]
enabled = false  # default off; opt-in per recipient
threshold = 0.6
rate_limit_per_hour = 3
ttl_days = 7
```

Default off so existing tongxue don't get surprised. Once a small set of recipients opt-in and the telemetry says "yes, this is useful", we flip the default to on.

## Sequencing

Stacks on KR3 holding queue (`lisa-su/kr3-digest-scheduler-coverage`) since both touch `notifications.toml` — but doesn't depend on it functionally. Can ship in parallel once the current PR wave (#221, #224, #229, #233 etc.) lands.

Implementation can be picked up by lisa-su (observability-themed) or bezos (testing-heavy). No strong preference.

## References

- Issue #158 (proactive association)
- PR #221 / commit shipping the runtime-alert pattern this design borrows (`board view` yellow block)
- KR3 holding queue: notification_config.py coverage prep (`b1370ac`)
- Bitter Lesson — design intentionally keeps room to swap heuristic for learned model
