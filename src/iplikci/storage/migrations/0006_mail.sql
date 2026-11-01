-- Where each mail connector stands (ADR-0015, ADR-0016): an IMAP folder's UIDVALIDITY and last UID, the browser
-- bridge's last message, and how the last run went. The mailbox's address lives in settings.toml, not here.
CREATE TABLE mail_state (
    connector   TEXT NOT NULL,                -- imap or browser_bridge
    folder      TEXT NOT NULL DEFAULT '',     -- the IMAP folder as the server names it; '' for the bridge
    uidvalidity INTEGER NOT NULL DEFAULT 0,
    last_uid    INTEGER NOT NULL DEFAULT 0,
    last_id     TEXT NOT NULL DEFAULT '',     -- the bridge: Gmail's id of the newest message it delivered
    last_date   TEXT NOT NULL DEFAULT '',     -- and that message's date
    scan_key    TEXT NOT NULL DEFAULT '',     -- what was searched; another one means reading again from the start
    last_run    TEXT NOT NULL DEFAULT '',     -- the last run that worked
    last_error  TEXT NOT NULL DEFAULT '',     -- the last failure, in Turkish; '' after a run that worked
    stopped     INTEGER NOT NULL DEFAULT 0,   -- 1 after a refused login: no attempt until the user sets it up again
    totals      TEXT NOT NULL DEFAULT '{}',   -- JSON: messages by outcome since the setup
    PRIMARY KEY (connector, folder)
);
