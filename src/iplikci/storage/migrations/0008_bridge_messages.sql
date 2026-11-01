-- The Gmail ids of the messages a browser extension delivered and the service holds (ADR-0016). The extension's scan
-- of Gmail ("Gmail'de eksikleri tara") asks which of the ids it found are missing, so each message is downloaded
-- once. A cache: losing it costs downloads, not documents, as the service knows every message by its bytes.
CREATE TABLE bridge_messages (
    gmail_id     TEXT PRIMARY KEY,            -- Gmail's message id, in decimal
    sha256       TEXT NOT NULL CHECK (length(sha256) = 64),
    delivered_at TEXT NOT NULL
);
