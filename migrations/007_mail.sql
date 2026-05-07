-- Persistent mail system with CC and threading.
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
