-- The notifications (ADR-0010, architecture §14): what an alert rule said of an event on a channel, with the text as
-- it was sent. Primary data: the history the user reads, and what keeps a notification from going out twice. One per
-- rule, event key and channel: a second event of the same kind and target finds it and adds none. A failed attempt
-- is tried again later; a sent one never again. One kept back by the quiet hours or the channel's rate goes out in
-- the next digest.
CREATE TABLE notifications (
    id         INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    rule       TEXT NOT NULL,                -- the rule's name, as rules/alerts.yaml writes it
    event_id   INTEGER NOT NULL,             -- the event that matched it (events.id)
    kind       TEXT NOT NULL,                -- the event's kind
    key        TEXT NOT NULL,                -- the event's target, or "olay-<id>" for an event that names none
    channel    TEXT NOT NULL,                -- in_app, desktop, email, telegram
    detail     TEXT NOT NULL,                -- full, summary, minimal
    title      TEXT NOT NULL,                -- the text as sent
    body       TEXT NOT NULL,
    status     TEXT NOT NULL,                -- pending, sent, held, digested, failed
    attempts   INTEGER NOT NULL DEFAULT 0,
    next_at    TEXT NOT NULL DEFAULT '',     -- UTC; a pending one is not tried before
    sent_at    TEXT NOT NULL DEFAULT '',
    error      TEXT NOT NULL DEFAULT '',     -- why the last attempt failed, never a secret
    read_at    TEXT NOT NULL DEFAULT ''      -- in the interface's box: when the user saw it
);
CREATE UNIQUE INDEX notifications_once ON notifications (rule, kind, key, channel);
CREATE INDEX notifications_due ON notifications (status, channel, next_at);
