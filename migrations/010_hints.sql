-- Proactive association hints (#158, design doc: docs/dev/design-proactive-association.md).
-- Phase 1: plumbing only — detection (phase 2) + UX surface (phase 3) are separate.

CREATE TABLE IF NOT EXISTS hints(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    recipient TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    body TEXT NOT NULL,
    signals TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL DEFAULT 0.0,
    refs TEXT NOT NULL DEFAULT '{}',
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
    -- Default TTL keeps the schema self-contained for ad-hoc INSERTs / sqlite shell use.
    -- Production callers (emit_hint) override this with the per-config ttl_days.
    expires_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','+7 days','localtime')),
    surfaced_at TEXT DEFAULT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS idx_hints_recipient ON hints(recipient, status);
CREATE INDEX IF NOT EXISTS idx_hints_sender ON hints(sender);
CREATE INDEX IF NOT EXISTS idx_hints_expires ON hints(expires_at);

CREATE TABLE IF NOT EXISTS hint_events(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hint_id INTEGER NOT NULL REFERENCES hints(id) ON DELETE CASCADE,
    event TEXT NOT NULL,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
    meta TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_hint_events_hint ON hint_events(hint_id);
CREATE INDEX IF NOT EXISTS idx_hint_events_ts ON hint_events(ts);

CREATE TABLE IF NOT EXISTS hint_mutes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    scope TEXT NOT NULL,
    value TEXT NOT NULL,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
    UNIQUE(recipient, scope, value)
);
CREATE INDEX IF NOT EXISTS idx_hint_mutes_recipient ON hint_mutes(recipient);
