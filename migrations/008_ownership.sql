-- Ownership registry: who owns which paths/modules
CREATE TABLE IF NOT EXISTS ownership(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    path_pattern TEXT NOT NULL,
    claimed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime')),
    UNIQUE(session, path_pattern)
);
CREATE INDEX IF NOT EXISTS idx_ownership_session ON ownership(session);
CREATE INDEX IF NOT EXISTS idx_ownership_path ON ownership(path_pattern);
