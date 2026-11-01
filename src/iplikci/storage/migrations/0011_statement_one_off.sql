-- A passbook (e-cüzdan) is the account as the bank sent it once, when it opened: banks mail no monthly list after it,
-- so the month-end does not wait for the account's later days. 1 for such a statement.
ALTER TABLE statements ADD COLUMN one_off INTEGER NOT NULL DEFAULT 0;
