-- The job queue (ADR-0014): what the service does in the background, kept so that a restart or a sleep loses
-- nothing. A job with a key is done once: the same key again adds nothing (one day's backup, one period's poll).
CREATE TABLE jobs (
    id          INTEGER PRIMARY KEY,
    kind        TEXT NOT NULL,                -- e.g. analysis.refresh, maintenance.purge
    payload     TEXT NOT NULL DEFAULT '{}',   -- JSON
    key         TEXT NOT NULL DEFAULT '',     -- the dedupe key; '' for none
    status      TEXT NOT NULL,                -- queued, running, done, failed
    attempts    INTEGER NOT NULL DEFAULT 0,
    run_after   TEXT NOT NULL,                -- the earliest start, UTC
    created_at  TEXT NOT NULL,
    started_at  TEXT NOT NULL DEFAULT '',
    finished_at TEXT NOT NULL DEFAULT '',
    last_error  TEXT NOT NULL DEFAULT ''      -- the exception's type and message of the last failed attempt
);
CREATE UNIQUE INDEX jobs_key ON jobs (key) WHERE key != '';
CREATE INDEX jobs_due ON jobs (status, run_after);

-- What the feed saw last (ADR-0014): the snapshot of the analysis the next one is compared with.
CREATE TABLE feed_state (
    name       TEXT PRIMARY KEY,
    value      TEXT NOT NULL,                 -- JSON
    updated_at TEXT NOT NULL
);
