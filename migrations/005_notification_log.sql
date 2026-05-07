-- Track delivered notifications to prevent duplicates.
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
