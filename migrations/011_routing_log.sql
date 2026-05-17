-- Audit trail for board scan routing decisions (#87 L1).
-- Each row records one issue/CI notification dispatched by _scan_issues
-- or _scan_ci, including the evidence that justified the recipient choice.
-- Used by `board own audit` for misroute debrief.
CREATE TABLE IF NOT EXISTS routing_log(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now','localtime')),
    kind TEXT NOT NULL,         -- 'issue' | 'ci'
    ref TEXT NOT NULL,          -- '#42' | 'branch:job'
    recipient TEXT NOT NULL,    -- session name or 'lead' or 'all'
    evidence TEXT NOT NULL,     -- 'assigned:bezos' | 'label:proj:foo' | 'path:lib/x.py' | 'fallback:no_match'
    confidence TEXT NOT NULL    -- 'high' | 'medium' | 'low' | 'fallback'
);
CREATE INDEX IF NOT EXISTS idx_routing_log_ref ON routing_log(ref);
CREATE INDEX IF NOT EXISTS idx_routing_log_recipient ON routing_log(recipient);
