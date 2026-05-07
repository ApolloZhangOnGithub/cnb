-- Pending actions queue: batch user-required operations.
CREATE TABLE IF NOT EXISTS pending_actions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    command TEXT NOT NULL,
    reason TEXT NOT NULL,
    verify_command TEXT,
    retry_command TEXT,
    status TEXT DEFAULT 'pending',
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_actions(status);
CREATE INDEX IF NOT EXISTS idx_pending_creator ON pending_actions(created_by);
