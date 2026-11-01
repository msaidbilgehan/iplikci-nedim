"""SQLite storage (ADR-0004): the connection, the numbered migrations and thin repository modules with
hand-written SQL. The documents themselves are in the vault; what is here is either read from them again
on demand (parsed rows) or primary data that must never be lost (sources, annotations, the audit log)."""
