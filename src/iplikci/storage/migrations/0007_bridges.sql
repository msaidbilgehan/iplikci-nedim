-- The browser extensions paired with this service (ADR-0016). Only the SHA-256 of a bridge's token is kept; the
-- extension holds the token. A revoked bridge's requests are refused; its row stays to show when it was revoked.
CREATE TABLE bridges (
    id          TEXT PRIMARY KEY,
    token_hash  TEXT NOT NULL UNIQUE CHECK (length(token_hash) = 64),
    name        TEXT NOT NULL DEFAULT '',     -- the browser as the extension names itself ("Chrome 140, macOS")
    created_at  TEXT NOT NULL,
    last_seen   TEXT NOT NULL DEFAULT '',
    revoked_at  TEXT NOT NULL DEFAULT ''
);
