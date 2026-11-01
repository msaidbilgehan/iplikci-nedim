-- Bills and receipts read from non-bank senders' e-mails (F14): matched to the bank's rows, never counted. Amounts
-- in minor units; lines is JSON ([{"description", "amount", "quantity"}], quantity a decimal string or null); due is
-- '' when the document prints none; ref is the total's place in the document, as for a row.
CREATE TABLE invoices (
    id        INTEGER PRIMARY KEY,
    sha256    TEXT NOT NULL REFERENCES documents (sha256),
    position  INTEGER NOT NULL,
    kind      TEXT NOT NULL,
    seller    TEXT NOT NULL,
    seller_id TEXT NOT NULL DEFAULT '',
    number    TEXT NOT NULL DEFAULT '',
    issued    TEXT NOT NULL,
    due       TEXT NOT NULL DEFAULT '',
    total     INTEGER NOT NULL,
    currency  TEXT NOT NULL,
    lines     TEXT NOT NULL DEFAULT '[]',
    ref       TEXT NOT NULL DEFAULT '',
    UNIQUE (sha256, position)
);
