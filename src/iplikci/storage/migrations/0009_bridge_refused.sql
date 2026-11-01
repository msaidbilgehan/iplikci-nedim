-- The messages a browser extension delivered that the service did not keep (ADR-0016): from a sender on no list,
-- not verified by the receiving server, or a company's. Nothing of the message is kept but its Gmail id, what became
-- of it and why. A scan of Gmail does not download them again until the settings they were refused under change.
CREATE TABLE bridge_refused (
    gmail_id   TEXT PRIMARY KEY,            -- Gmail's message id, in decimal
    taken      TEXT NOT NULL,               -- unlisted, unverified, business
    reason     TEXT NOT NULL DEFAULT '',    -- what the trust rule saw: no-dmarc, dmarc:fail, header-from:…
    domain     TEXT NOT NULL DEFAULT '',    -- the sender's domain
    key        TEXT NOT NULL,               -- the settings it was refused under (app.bridge.refusal_key)
    refused_at TEXT NOT NULL
);
