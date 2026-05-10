PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions(
    name TEXT PRIMARY KEY,
    status TEXT DEFAULT '',
    persona TEXT DEFAULT '',
    updated_at TEXT DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime')),
    last_heartbeat TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS messages(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime')),
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    body TEXT NOT NULL,
    attachment TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_ts ON messages(ts);
CREATE INDEX IF NOT EXISTS idx_msg_to ON messages(recipient);
CREATE INDEX IF NOT EXISTS idx_msg_from ON messages(sender);

CREATE TABLE IF NOT EXISTS inbox(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    delivered_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime')),
    read INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_inbox ON inbox(session, read);

CREATE TABLE IF NOT EXISTS proposals(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL,
    type TEXT DEFAULT 'A',
    content TEXT NOT NULL,
    status TEXT DEFAULT 'OPEN',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime')),
    decided_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS votes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    voter TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT DEFAULT '',
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime')),
    UNIQUE(proposal_id, voter)
);

CREATE TABLE IF NOT EXISTS files(
    hash TEXT PRIMARY KEY,
    original_name TEXT NOT NULL,
    extension TEXT DEFAULT '',
    sender TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime'))
);

CREATE TABLE IF NOT EXISTS bugs(
    id TEXT PRIMARY KEY,
    severity TEXT NOT NULL,
    sla TEXT NOT NULL,
    reporter TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    status TEXT DEFAULT 'OPEN',
    description TEXT NOT NULL,
    reported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime')),
    fixed_at TEXT DEFAULT NULL,
    evidence TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_bugs ON bugs(status);

CREATE TABLE IF NOT EXISTS threads(
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime'))
);

CREATE TABLE IF NOT EXISTS thread_replies(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    author TEXT NOT NULL,
    body TEXT NOT NULL,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_replies ON thread_replies(thread_id);

CREATE TABLE IF NOT EXISTS kudos(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender TEXT NOT NULL,
    target TEXT NOT NULL,
    reason TEXT NOT NULL,
    evidence TEXT DEFAULT NULL,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime'))
);

CREATE TABLE IF NOT EXISTS suspended(
    name TEXT PRIMARY KEY REFERENCES sessions(name) ON DELETE CASCADE,
    suspended_by TEXT NOT NULL,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime'))
);

CREATE TABLE IF NOT EXISTS tasks(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime')),
    done_at TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks ON tasks(session, status);

CREATE TABLE IF NOT EXISTS meta(
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mailbox(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime')),
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    encrypted_body TEXT NOT NULL,
    read INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_mailbox ON mailbox(recipient, read);

CREATE TABLE IF NOT EXISTS git_locks(
    id INTEGER PRIMARY KEY CHECK (id = 1),
    session TEXT NOT NULL,
    reason TEXT DEFAULT '',
    acquired_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
    expires_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS notification_log(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notif_type TEXT NOT NULL,
    recipient TEXT NOT NULL,
    ref_type TEXT NOT NULL,
    ref_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    sent_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_notif_dedup ON notification_log(notif_type, recipient, ref_id);
CREATE INDEX IF NOT EXISTS idx_notif_ts ON notification_log(sent_at);

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

CREATE TABLE IF NOT EXISTS ownership(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    path_pattern TEXT NOT NULL,
    claimed_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime')),
    UNIQUE(session, path_pattern)
);
CREATE INDEX IF NOT EXISTS idx_ownership_session ON ownership(session);
CREATE INDEX IF NOT EXISTS idx_ownership_path ON ownership(path_pattern);

CREATE TABLE IF NOT EXISTS session_runs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    engine TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_runs_session_started ON session_runs(session, started_at);
CREATE INDEX IF NOT EXISTS idx_session_runs_open ON session_runs(session, ended_at);

CREATE TABLE IF NOT EXISTS mail(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER REFERENCES mail(id) ON DELETE CASCADE,
    sender TEXT NOT NULL,
    recipients TEXT NOT NULL,
    cc TEXT DEFAULT '[]',
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
    read_by TEXT DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_mail_thread ON mail(thread_id);
CREATE INDEX IF NOT EXISTS idx_mail_sender ON mail(sender);
CREATE INDEX IF NOT EXISTS idx_mail_ts ON mail(ts);
