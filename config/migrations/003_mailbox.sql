CREATE TABLE IF NOT EXISTS mailbox(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M','now','localtime')),
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    encrypted_body TEXT NOT NULL,
    read INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_mailbox ON mailbox(recipient, read);
