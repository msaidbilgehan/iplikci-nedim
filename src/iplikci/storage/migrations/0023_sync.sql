-- The sync folder (ADR-0025): the computers that share one set of data through a folder a sync service mirrors (Google
-- Drive's, iCloud Drive's, Dropbox's). What this computer knows of each piece of the shared data: the last change that
-- won (its stamp and value) and whether this computer's own copy took it. The database itself never goes into the
-- folder; each computer keeps its own and these rows say how far it is in step with the others.
CREATE TABLE sync_entries (
    kind    TEXT NOT NULL,                -- annotation, alias, memory, document, source, setting, file, messenger
    key     TEXT NOT NULL,                -- the piece within its kind: a fingerprint, an account, a document's sha256
    stamp   TEXT NOT NULL,                -- when it last changed, as a hybrid logical clock stamp (sync.clock)
    value   TEXT,                         -- the value that change gave, as canonical JSON; NULL: it was taken away
    local   TEXT NOT NULL DEFAULT '',     -- the digest of this computer's own value when the two were last compared
    applied INTEGER NOT NULL DEFAULT 1,   -- 0: the value waits to be put in place here (a document's bytes to come)
    PRIMARY KEY (kind, key)
);
CREATE INDEX sync_entries_waiting ON sync_entries (applied, kind);

-- This computer's own side of it: its id, the machine it belongs to, the set of data it joined, its clock and how
-- the last round went. Named JSON values.
CREATE TABLE sync_state (
    name  TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
