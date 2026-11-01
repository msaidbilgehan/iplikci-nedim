-- Phase 1's data core (architecture §8). Amounts are integers in the currency's smallest unit (ADR-0006);
-- dates are ISO 8601 text; codes are the domain's English codes. Every text column defaults to '' rather
-- than NULL so that UNIQUE constraints hold.

CREATE TABLE schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

-- One row per original in the vault (ADR-0003). The bytes are in vault/objects; what a reader made of them
-- is in the tables below and can be made again. A company document never gets a row: it is not kept.
CREATE TABLE documents (
    sha256         TEXT PRIMARY KEY CHECK (length(sha256) = 64),
    name           TEXT NOT NULL,                -- the file name it first came with (NFC)
    size           INTEGER NOT NULL,
    status         TEXT NOT NULL,                -- DocumentStatus
    reason         TEXT NOT NULL DEFAULT '',     -- why it is unprocessed, unreadable or removed (Turkish)
    kind           TEXT NOT NULL DEFAULT '',     -- DocumentKind of a processed document
    parser         TEXT NOT NULL DEFAULT '',     -- the reader that read it
    parser_version TEXT NOT NULL DEFAULT '',
    business_sig   TEXT NOT NULL DEFAULT '',     -- the company names it was read with; others mean read again
    holder         TEXT NOT NULL DEFAULT '',     -- the account holder the document prints
    receipt_key    TEXT NOT NULL DEFAULT '',     -- the same receipt as PDF and HTML is one receipt
    title          TEXT NOT NULL DEFAULT '',     -- a receipt's short title ("Kredi Taksiti 5678")
    verified       INTEGER,                      -- statements: 1 when they verify, 0 when not
    period_start   TEXT NOT NULL DEFAULT '',
    period_end     TEXT NOT NULL DEFAULT '',
    display_name   TEXT NOT NULL DEFAULT '',     -- the organizer's naming scheme; the name of a download
    parent         TEXT NOT NULL DEFAULT '',     -- the e-mail an attachment came in (its sha256)
    added_at       TEXT NOT NULL,
    read_at        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX documents_status ON documents (status);

-- Where a document came from, once per arrival (primary data: the vault cannot tell). The same bytes arriving
-- again add a source, not a document.
CREATE TABLE document_sources (
    id          INTEGER PRIMARY KEY,
    sha256      TEXT NOT NULL REFERENCES documents (sha256),
    kind        TEXT NOT NULL,                   -- SourceKind
    original    TEXT NOT NULL DEFAULT '',        -- the file name it arrived with
    origin      TEXT NOT NULL DEFAULT '',        -- where: a path, "archive.zip › member", an e-mail
    message_id  TEXT NOT NULL DEFAULT '',
    sender      TEXT NOT NULL DEFAULT '',
    subject     TEXT NOT NULL DEFAULT '',
    sent_at     TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL,
    UNIQUE (sha256, kind, original, origin, message_id)
);

-- What the reader made of a document, as it read it: the accounts it names, its statements with their rows,
-- and the rows of a receipt. The ledger combines them in memory on every analysis (architecture §11).
CREATE TABLE document_accounts (
    sha256   TEXT NOT NULL REFERENCES documents (sha256),
    position INTEGER NOT NULL,
    id       TEXT NOT NULL,
    label    TEXT NOT NULL,
    bank     TEXT NOT NULL,
    type     TEXT NOT NULL,
    currency TEXT NOT NULL,
    number   TEXT NOT NULL DEFAULT '',
    note     TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (sha256, position)
);

CREATE TABLE statements (
    id           INTEGER PRIMARY KEY,
    sha256       TEXT NOT NULL REFERENCES documents (sha256),
    position     INTEGER NOT NULL,
    account      TEXT NOT NULL,
    cut_date     TEXT NOT NULL,
    currency     TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT '',
    previous     INTEGER,                        -- NULL when the statement prints none
    total        INTEGER,
    total_is_sum INTEGER NOT NULL DEFAULT 0,
    start        TEXT NOT NULL DEFAULT '',       -- account lists: the first day they cover
    checks_ok    INTEGER NOT NULL DEFAULT 0,
    checks_total INTEGER NOT NULL DEFAULT 0,
    balances     TEXT NOT NULL DEFAULT '{}',     -- JSON: "YYYY-MM" -> month-end balance in the smallest unit
    UNIQUE (sha256, position)
);
CREATE INDEX statements_account ON statements (account, cut_date);

CREATE TABLE securities (
    statement_id INTEGER NOT NULL REFERENCES statements (id),
    position     INTEGER NOT NULL,
    code         TEXT NOT NULL,
    name         TEXT NOT NULL,
    quantity     TEXT NOT NULL,                  -- Decimal text (ADR-0006)
    value        INTEGER NOT NULL,               -- market value in TRY on as_of
    as_of        TEXT NOT NULL,
    PRIMARY KEY (statement_id, position)
);

-- A statement's rows. A row's identity is its document, its statement and its place there; two rows of one
-- statement with the same day and amount are both real and are never merged.
CREATE TABLE transactions (
    id            INTEGER PRIMARY KEY,
    sha256        TEXT NOT NULL REFERENCES documents (sha256),
    statement_id  INTEGER NOT NULL REFERENCES statements (id),
    position      INTEGER NOT NULL,
    date          TEXT NOT NULL,
    description   TEXT NOT NULL,
    amount        INTEGER NOT NULL,
    currency      TEXT NOT NULL,
    kind          TEXT NOT NULL,
    account       TEXT NOT NULL,
    original      TEXT NOT NULL DEFAULT '',
    installment   TEXT NOT NULL DEFAULT '',
    bank_category TEXT NOT NULL DEFAULT '',
    counterparty  TEXT NOT NULL DEFAULT '',
    source        TEXT NOT NULL DEFAULT '',
    UNIQUE (statement_id, position)
);
CREATE INDEX transactions_document ON transactions (sha256);
CREATE INDEX transactions_account_date ON transactions (account, date);

-- The rows of receipts (and, later, bank notices): evidence the ledger settles against the statements.
CREATE TABLE evidence (
    id            INTEGER PRIMARY KEY,
    sha256        TEXT NOT NULL REFERENCES documents (sha256),
    position      INTEGER NOT NULL,
    date          TEXT NOT NULL,
    description   TEXT NOT NULL,
    amount        INTEGER NOT NULL,
    currency      TEXT NOT NULL,
    kind          TEXT NOT NULL,
    account       TEXT NOT NULL,
    original      TEXT NOT NULL DEFAULT '',
    installment   TEXT NOT NULL DEFAULT '',
    bank_category TEXT NOT NULL DEFAULT '',
    counterparty  TEXT NOT NULL DEFAULT '',
    source        TEXT NOT NULL DEFAULT '',
    UNIQUE (sha256, position)
);

-- The user's notes and corrections, bound to a transaction's fingerprint so a new reading keeps them
-- (architecture §8). Primary data. subject records what the fingerprint pointed at, for an orphan.
CREATE TABLE annotations (
    fingerprint TEXT PRIMARY KEY,
    note        TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '[]',      -- JSON list of strings
    category    TEXT NOT NULL DEFAULT '',        -- a category that replaces the rules' one
    necessity   TEXT NOT NULL DEFAULT '',        -- a Necessity that replaces the rules' one
    subject     TEXT NOT NULL DEFAULT '{}',      -- JSON: account, date, amount, currency, description
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    actor       TEXT NOT NULL                    -- Actor of the last change
);

-- Who changed what and when (architecture §21). Primary data; never rewritten.
CREATE TABLE audit_log (
    id     INTEGER PRIMARY KEY,
    at     TEXT NOT NULL,
    actor  TEXT NOT NULL,                        -- Actor
    action TEXT NOT NULL,                        -- e.g. document.stored, document.business, annotation.set
    target TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '{}'            -- JSON: identifiers and counts, never amounts or names
);
CREATE INDEX audit_log_action ON audit_log (action, target);

-- Full-text search over what the readers read: descriptions, parties and document names, folded the way the
-- program compares Turkish text (domain.text.fold) so "şube", "SUBE" and "Şube" find each other.
CREATE VIRTUAL TABLE search USING fts5 (
    text,
    sha256 UNINDEXED,
    kind UNINDEXED,                              -- transaction, evidence or document
    ref UNINDEXED,                               -- the row's id; the sha256 for a document
    tokenize = 'unicode61 remove_diacritics 2'
);
