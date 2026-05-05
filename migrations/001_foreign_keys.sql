-- 001_foreign_keys.sql
-- Add foreign key constraints to prevent orphaned data.
-- All cascading rules use CASCADE so that deleting a session/proposal/thread
-- automatically cleans up related rows.

PRAGMA foreign_keys = ON;

-- Create a pseudo-session 'all' so FK on messages.recipient works.
-- 'all' is the broadcast pseudo-recipient used by send-to-all.
INSERT OR IGNORE INTO sessions(name, status, updated_at)
VALUES ('all', 'system', strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'));

-- inbox: must reference valid session + valid message
-- Rebuild with FK (SQLite requires recreating the table)
CREATE TABLE IF NOT EXISTS inbox_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    delivered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M', 'now', 'localtime')),
    read INTEGER DEFAULT 0
);
INSERT INTO inbox_new SELECT * FROM inbox;
DROP TABLE inbox;
ALTER TABLE inbox_new RENAME TO inbox;
CREATE INDEX IF NOT EXISTS idx_inbox ON inbox(session, read);

-- votes: must reference valid proposal
CREATE TABLE IF NOT EXISTS votes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    voter TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT DEFAULT '',
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M', 'now', 'localtime')),
    UNIQUE(proposal_id, voter)
);
INSERT INTO votes_new SELECT * FROM votes;
DROP TABLE votes;
ALTER TABLE votes_new RENAME TO votes;

-- thread_replies: must reference valid thread
CREATE TABLE IF NOT EXISTS thread_replies_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    author TEXT NOT NULL,
    body TEXT NOT NULL,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M', 'now', 'localtime'))
);
INSERT INTO thread_replies_new SELECT * FROM thread_replies;
DROP TABLE thread_replies;
ALTER TABLE thread_replies_new RENAME TO thread_replies;
CREATE INDEX IF NOT EXISTS idx_replies ON thread_replies(thread_id);

-- suspended: must reference valid session
CREATE TABLE IF NOT EXISTS suspended_new (
    name TEXT PRIMARY KEY REFERENCES sessions(name) ON DELETE CASCADE,
    suspended_by TEXT NOT NULL,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M', 'now', 'localtime'))
);
INSERT INTO suspended_new SELECT * FROM suspended;
DROP TABLE suspended;
ALTER TABLE suspended_new RENAME TO suspended;

-- tasks: must reference valid session
CREATE TABLE IF NOT EXISTS tasks_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M', 'now', 'localtime')),
    done_at TEXT DEFAULT NULL
);
INSERT INTO tasks_new SELECT * FROM tasks;
DROP TABLE tasks;
ALTER TABLE tasks_new RENAME TO tasks;
CREATE INDEX IF NOT EXISTS idx_tasks ON tasks(session, status);
