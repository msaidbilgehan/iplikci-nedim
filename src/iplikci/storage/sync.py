"""What this computer knows of the shared data (ADR-0025): each piece's winning change with its stamp and value, the
digest of this computer's own value when the two were last compared, and whether the winner is in place here yet. Also
this computer's own side: its id, the set of data it joined, its clock and the last round. The database never goes
into the sync folder; these rows travel with it into the backups, so a restored database knows how far it was in step."""

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .db import Database


@dataclass(frozen=True, slots=True)
class Row:
    kind: str
    key: str
    stamp: str  # sync.clock.Stamp's text
    value: str | None  # canonical JSON; None: taken away
    local: str  # the digest of this computer's own value when last compared; "": it had none
    applied: bool  # the winner is in place here

    @property
    def id(self) -> tuple[str, str]:
        return self.kind, self.key


def _row(r: sqlite3.Row) -> Row:
    return Row(r["kind"], r["key"], r["stamp"], r["value"], r["local"], bool(r["applied"]))


def every(db: Database, kinds: Iterable[str] | None = None) -> dict[tuple[str, str], Row]:
    if kinds is None:
        rows = db.rows("SELECT * FROM sync_entries")
    else:
        wanted = list(kinds)
        rows = db.rows(f"SELECT * FROM sync_entries WHERE kind IN ({', '.join('?' * len(wanted))})", wanted)
    return {(r["kind"], r["key"]): _row(r) for r in rows}


def get(db: Database, kind: str, key: str) -> Row | None:
    r = db.one("SELECT * FROM sync_entries WHERE kind = ? AND key = ?", (kind, key))
    return None if r is None else _row(r)


def waiting(db: Database) -> list[Row]:
    """The winners not in place here yet."""
    return [_row(r) for r in db.rows("SELECT * FROM sync_entries WHERE applied = 0 ORDER BY kind, key")]


def count(db: Database) -> int:
    return int(db.scalar("SELECT count(*) FROM sync_entries"))


def put(db: Database, row: Row) -> None:
    with db.transaction():
        db.execute(
            "INSERT INTO sync_entries (kind, key, stamp, value, local, applied) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (kind, key) DO UPDATE SET stamp = excluded.stamp, value = excluded.value, "
            "local = excluded.local, applied = excluded.applied",
            (row.kind, row.key, row.stamp, row.value, row.local, int(row.applied)),
        )


def settle(db: Database, kind: str, key: str, local: str) -> None:
    """The winner is in place here; local: the digest of this computer's value now."""
    with db.transaction():
        db.execute("UPDATE sync_entries SET local = ?, applied = 1 WHERE kind = ? AND key = ?", (local, kind, key))


def forget(db: Database) -> int:
    """Forget every piece (the sync turned on with another set of data); how many were forgotten."""
    with db.transaction():
        return db.execute("DELETE FROM sync_entries").rowcount


def load(db: Database, name: str) -> Any:
    """A value of this computer's own side; None when there is none."""
    value = db.scalar("SELECT value FROM sync_state WHERE name = ?", (name,))
    return None if value is None else json.loads(value)


def save(db: Database, name: str, value: Any) -> None:
    with db.transaction():
        db.execute(
            "INSERT INTO sync_state (name, value) VALUES (?, ?) ON CONFLICT (name) DO UPDATE SET value = excluded.value",
            (name, json.dumps(value, ensure_ascii=False, sort_keys=True)),
        )
