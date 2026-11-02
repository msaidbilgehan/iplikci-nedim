"""The SQLite connection and the schema migrations (ADR-0004).

One file in the data folder, in WAL mode so readers never wait for the writer; foreign keys on; a busy timeout
so two processes (the service, the CLI, the MCP bridge) take turns instead of failing. Migrations are numbered
SQL files applied in order when a database opens; an existing database is backed up first.
"""

import functools
import os
import re
import sqlite3
import sys
from collections.abc import Generator, Iterator, Sequence
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any, Self

BUSY_TIMEOUT_MS = 10_000
_MIGRATION = re.compile(r"(\d{4})_([a-z0-9_]+)\.sql")

type Params = Sequence[Any] | dict[str, Any]


class Database:
    """A connection with explicit transactions: nothing is written outside `with db.transaction():`."""

    def __init__(self, connection: sqlite3.Connection, path: Path | None):
        self.connection = connection
        self.path = path
        self._depth = 0

    def execute(self, sql: str, params: Params = ()) -> sqlite3.Cursor:
        return self.connection.execute(sql, params)

    def executemany(self, sql: str, rows: Sequence[Params]) -> sqlite3.Cursor:
        return self.connection.executemany(sql, rows)

    def rows(self, sql: str, params: Params = ()) -> list[sqlite3.Row]:
        return self.connection.execute(sql, params).fetchall()

    def one(self, sql: str, params: Params = ()) -> sqlite3.Row | None:
        row: sqlite3.Row | None = self.connection.execute(sql, params).fetchone()
        return row

    def scalar(self, sql: str, params: Params = ()) -> Any:
        row = self.one(sql, params)
        return None if row is None else row[0]

    @contextmanager
    def transaction(self) -> Generator["Database"]:
        """One write transaction; nested uses join the outer one. BEGIN IMMEDIATE takes the write lock at once,
        so two writers queue on the busy timeout instead of failing halfway."""
        if self._depth:
            self._depth += 1
            try:
                yield self
            finally:
                self._depth -= 1
            return
        self.connection.execute("BEGIN IMMEDIATE")
        self._depth = 1
        try:
            yield self
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise
        else:
            self.connection.execute("COMMIT")
        finally:
            self._depth = 0

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def connect(path: Path | None, backups: Path | None = None) -> Database:
    """Open (or create) the database at path and bring its schema up to date; path None is an in-memory
    database for tests. backups is where an existing database is copied before a migration changes it."""
    fresh = path is None or not path.exists()
    target = ":memory:" if path is None else str(path)
    connection = sqlite3.connect(target, autocommit=True, timeout=BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    if path is not None and fresh and sys.platform != "win32":
        os.chmod(path, 0o600)  # SQLite gives its -wal and -shm files the database's permissions
    connection.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA foreign_keys = ON")
    if path is not None:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
    db = Database(connection, path)
    migrate(db, None if fresh else backups)
    return db


@functools.cache
def migrations() -> tuple[tuple[int, str, str], ...]:
    """(number, name, SQL) of every migration shipped with the package, in order. Read once a process: every
    connection asks, and an update replacing the package under a running service must not fail its connections (the
    service restarts after an update)."""
    found: list[tuple[int, str, str]] = []
    for entry in resources.files(__package__).joinpath("migrations").iterdir():
        match = _MIGRATION.fullmatch(entry.name)
        if match:
            found.append((int(match[1]), match[2], entry.read_text(encoding="utf-8")))
    found.sort()
    if [n for n, _, _ in found] != list(range(1, len(found) + 1)):
        raise RuntimeError(f"göç numaraları 1'den başlayıp aralıksız artmalı: {[n for n, _, _ in found]}")
    return tuple(found)


def applied(db: Database) -> set[int]:
    exists = db.scalar("SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'")
    if not exists:
        return set()
    return {int(row[0]) for row in db.rows("SELECT version FROM schema_migrations")}


class NewerDatabase(Exception):
    """A newer version of the program has changed the database: this one would read it wrong (Turkish message)."""


def migrate(db: Database, backups: Path | None) -> list[int]:
    """Apply the migrations the database lacks, each in its own transaction; returns their numbers. A
    database that already holds data is backed up into backups first. NewerDatabase when a newer version has
    migrated it further than this one knows: an older copy of the program opened again never runs on it."""
    done = applied(db)
    newest = schema_version()
    if done and max(done) > newest:
        raise NewerDatabase(
            "Bu veri klasörünü İplikçi Nedim'in daha yeni bir sürümü açmış (veritabanının son göçü "
            f"{max(done)}, bu sürümün bildiği son göç {newest}). İplikçi Nedim'in yeni sürümünü açın."
        )
    pending = [m for m in migrations() if m[0] not in done]
    if pending and done and backups is not None:
        backup(db, backups / f"iplikci göç öncesi {max(done):04d} {_stamp()}.db")
    for number, name, sql in pending:
        with db.transaction():
            for statement in _statements(sql):
                db.execute(statement)
            db.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (number, name, now()),
            )
    return [number for number, _, _ in pending]


def written_by_newer(path: Path) -> int | None:
    """The newest migration of the database at path when a newer program made it, read without changing anything
    (the launcher asks before it registers an older copy); None for a database this program knows, or none at all."""
    if not path.is_file():
        return None
    try:
        with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as connection:
            newest = connection.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
    except sqlite3.Error:
        return None  # not a database of ours yet, or no migration made: connect makes it
    return int(newest) if newest is not None and int(newest) > schema_version() else None


def _statements(sql: str) -> Iterator[str]:
    """The statements of a migration file, split where SQLite says a statement is complete (a trigger body's
    semicolons do not end it)."""
    current = ""
    for line in sql.splitlines(keepends=True):
        current += line
        if sqlite3.complete_statement(current):
            if current.strip():
                yield current
            current = ""
    if any(line.strip() and not line.strip().startswith("--") for line in current.splitlines()):
        raise ValueError(f"göç dosyası yarım bir ifadeyle bitiyor: {current.strip()[:60]!r}")


def backup(db: Database, target: Path) -> Path:
    """A consistent copy of the database through SQLite's online backup API, safe while others write. The copy is
    one self-contained file: it leaves WAL mode, so it opens without -wal and -shm files beside it."""
    target.parent.mkdir(parents=True, exist_ok=True)
    copy = sqlite3.connect(target)
    try:
        db.connection.backup(copy)
        copy.execute("PRAGMA journal_mode = DELETE")
    finally:
        copy.close()
    if sys.platform != "win32":
        os.chmod(target, 0o600)
    return target


class SchemaMismatch(Exception):
    """A database opened only to read is at another schema than this program's: it cannot be migrated then."""


def open_read_only(path: Path) -> Database:
    """The database at path opened only to read, while no service writes it: never migrated, nothing written. Its
    schema must be this program's own (SchemaMismatch otherwise: the service migrates it when it starts)."""
    if not path.is_file():
        raise SchemaMismatch(f"veritabanı yok: {path.name}")
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=BUSY_TIMEOUT_MS / 1000)
    connection.row_factory = sqlite3.Row
    database = Database(connection, path)
    try:
        newest = connection.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
    except sqlite3.Error as exc:
        connection.close()
        raise SchemaMismatch("veritabanı okunamadı") from exc
    if newest != schema_version():
        connection.close()
        raise SchemaMismatch(f"veritabanı {newest} sürümünde, program {schema_version()} sürümünü bekliyor")
    return database


def open_copy(path: Path) -> Database:
    """A copy of the database (a backup's) opened read-only, as it is: no migration, nothing written."""
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return Database(connection, path)


def schema_version() -> int:
    """The newest migration this program knows: a database at a higher one was made by a newer version."""
    return migrations()[-1][0]


def now() -> str:
    """The current time as stored: ISO 8601 in UTC, to the second."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H.%M.%S")
