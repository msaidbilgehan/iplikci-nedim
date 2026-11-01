-- Browser sessions (ADR-0007). The session cookie carries a random token; the database keeps only its SHA-256, so
-- a copy of the database (a backup) opens no session. Not primary data: after a rebuild the user signs in again.
CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY CHECK (length(token_hash) = 64),
    created_at TEXT NOT NULL,
    renewed_at TEXT NOT NULL,                    -- when the expiry was last pushed back
    expires_at TEXT NOT NULL
);
CREATE INDEX sessions_expiry ON sessions (expires_at);
