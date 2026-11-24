-- The accounts the user says they closed (F07), with the day: from then on the account is listed with the closed ones,
-- out of every total, and no document is awaited for it. Primary data like the names the user gives accounts: no
-- reading of the documents knows it, the rebuild carries it in the dump and the sync folder shares it (ADR-0025).
CREATE TABLE account_closures (
    account    TEXT PRIMARY KEY,   -- the account's id (parsers.accounts)
    closed_on  TEXT NOT NULL,      -- YYYY-MM-DD: the day the account was closed
    updated_at TEXT NOT NULL,
    actor      TEXT NOT NULL       -- who marked it (Actor): the user on the account's page
);
