-- What Claude keeps across conversations (F16, K30, ADR-0023): the notes any agent connected over MCP reads and writes,
-- from whichever folder or application it connects. Primary data: no document knows them, so the rebuild carries them
-- in its dump and the backups keep them. The user reads and removes them on the Claude bağlantısı screen.
CREATE TABLE memories (
    name        TEXT PRIMARY KEY,  -- a short kebab-case handle: how a note is read, written again and removed
    kind        TEXT NOT NULL,     -- MemoryKind: user, feedback, project, reference
    description TEXT NOT NULL,     -- one line: the index shows it, so a later conversation knows when to read the note
    body        TEXT NOT NULL,     -- the note itself
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    actor       TEXT NOT NULL      -- who wrote it last (Actor): Claude through the MCP server, or the user
);
