-- Structured engine run history.
-- Attendance text logs are useful for humans, but session_runs is the
-- queryable record of which engine each session used for every clock-in.
CREATE TABLE IF NOT EXISTS session_runs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT NOT NULL REFERENCES sessions(name) ON DELETE CASCADE,
    engine TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_runs_session_started ON session_runs(session, started_at);
CREATE INDEX IF NOT EXISTS idx_session_runs_open ON session_runs(session, ended_at);
