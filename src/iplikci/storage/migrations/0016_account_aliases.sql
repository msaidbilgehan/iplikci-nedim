-- The names the user gives accounts (F07): the interface shows one instead of the bank's label wherever it names the
-- account. Primary data: no reading of the documents knows them. The bank's label stays the account's own name: the
-- verification baseline, the report, the exports and the MCP tools keep using it.
CREATE TABLE account_aliases (
    account    TEXT PRIMARY KEY,   -- the account's id (parsers.accounts)
    alias      TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    actor      TEXT NOT NULL       -- who gave it (Actor): the user, or Claude through the MCP server
);
