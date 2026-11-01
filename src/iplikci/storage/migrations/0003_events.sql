-- What happened (ADR-0014, architecture §13). Primary data, appended and never rewritten. The reading job records
-- parser.format_alarm here when a reader recognises a document and then cannot read it, or reads a statement that
-- does not verify (ADR-0005); the feed and the notifications start from this table.
CREATE TABLE events (
    id     INTEGER PRIMARY KEY,
    at     TEXT NOT NULL,
    kind   TEXT NOT NULL,                        -- e.g. parser.format_alarm (architecture §13)
    target TEXT NOT NULL DEFAULT '',             -- what it concerns: a document's sha256
    detail TEXT NOT NULL DEFAULT '{}'            -- JSON: identifiers and reasons
);
CREATE INDEX events_kind ON events (kind, target);
