"""What Claude keeps across conversations (F16, ADR-0023): one note a row, named by a short handle. Primary data: no
document knows it, so the rebuild carries it in the dump and the backups keep it. The audit log records each change by
the note's name, never its text."""

import sqlite3
from dataclasses import dataclass

from ..domain.codes import Actor, MemoryKind
from . import audit
from .db import Database, now

WRITTEN, REMOVED = "memory.written", "memory.removed"  # the audit log's actions


@dataclass(frozen=True, slots=True)
class Memory:
    name: str
    kind: MemoryKind
    description: str
    body: str
    created_at: str
    updated_at: str
    actor: Actor  # who wrote it last


def _memory(row: sqlite3.Row) -> Memory:
    return Memory(
        row["name"],
        MemoryKind(row["kind"]),
        row["description"],
        row["body"],
        row["created_at"],
        row["updated_at"],
        Actor(row["actor"]),
    )


def every(db: Database) -> list[Memory]:
    """Every note, by name."""
    return [_memory(r) for r in db.rows("SELECT * FROM memories ORDER BY name")]


def count(db: Database) -> int:
    return int(db.scalar("SELECT count(*) FROM memories"))


def get(db: Database, name: str) -> Memory | None:
    row = db.one("SELECT * FROM memories WHERE name = ?", (name,))
    return None if row is None else _memory(row)


def write(db: Database, name: str, kind: MemoryKind, description: str, body: str, actor: Actor) -> Memory:
    """Keep the note name says; one already kept under it is replaced and keeps the time it was first written. Nothing
    is written or recorded when it stays as it was."""
    with db.transaction():
        old = get(db, name)
        if old is not None and (old.kind, old.description, old.body) == (kind, description, body):
            return old
        at = now()
        kept = Memory(name, kind, description, body, old.created_at if old else at, at, actor)
        db.execute(
            "INSERT INTO memories (name, kind, description, body, created_at, updated_at, actor) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (name) DO UPDATE SET kind = excluded.kind, "
            "description = excluded.description, body = excluded.body, updated_at = excluded.updated_at, "
            "actor = excluded.actor",
            (kept.name, kept.kind, kept.description, kept.body, kept.created_at, kept.updated_at, kept.actor),
        )
        audit.record(db, actor, WRITTEN, name, created=old is None)
    return kept


def remove(db: Database, name: str, actor: Actor) -> Memory | None:
    """Take the note away; the note as it was, or None when there was none."""
    with db.transaction():
        old = get(db, name)
        if old is not None:
            db.execute("DELETE FROM memories WHERE name = ?", (name,))
            audit.record(db, actor, REMOVED, name)
    return old


def restore(db: Database, memory: Memory) -> None:
    """A note as a dump of the primary data recorded it, with its own times."""
    with db.transaction():
        db.execute(
            "INSERT INTO memories (name, kind, description, body, created_at, updated_at, actor) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                memory.name,
                memory.kind,
                memory.description,
                memory.body,
                memory.created_at,
                memory.updated_at,
                memory.actor,
            ),
        )


def put(db: Database, memory: Memory) -> None:
    """A note as another computer has it (ADR-0025), with its own times and author; the one here replaced."""
    with db.transaction():
        db.execute(
            "INSERT INTO memories (name, kind, description, body, created_at, updated_at, actor) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (name) DO UPDATE SET kind = excluded.kind, "
            "description = excluded.description, body = excluded.body, created_at = excluded.created_at, "
            "updated_at = excluded.updated_at, actor = excluded.actor",
            (
                memory.name,
                memory.kind,
                memory.description,
                memory.body,
                memory.created_at,
                memory.updated_at,
                memory.actor,
            ),
        )


def drop(db: Database, name: str) -> None:
    """A note another computer took away (ADR-0025)."""
    with db.transaction():
        db.execute("DELETE FROM memories WHERE name = ?", (name,))
