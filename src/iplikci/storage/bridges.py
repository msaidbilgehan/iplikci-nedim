"""The paired browser extensions (ADR-0016): each with the SHA-256 of its token."""

import sqlite3
from dataclasses import dataclass

from .db import Database, now


@dataclass(frozen=True, slots=True)
class Bridge:
    id: str
    token_hash: str
    name: str
    created_at: str
    last_seen: str
    revoked_at: str

    @property
    def active(self) -> bool:
        return not self.revoked_at


def _bridge(row: sqlite3.Row) -> Bridge:
    return Bridge(
        str(row["id"]),
        str(row["token_hash"]),
        str(row["name"]),
        str(row["created_at"]),
        str(row["last_seen"]),
        str(row["revoked_at"]),
    )


def add(db: Database, bridge_id: str, token_hash: str, name: str) -> Bridge:
    at = now()
    with db.transaction():
        db.execute(
            "INSERT INTO bridges (id, token_hash, name, created_at, last_seen) VALUES (?, ?, ?, ?, ?)",
            (bridge_id, token_hash, name, at, at),
        )
    return Bridge(bridge_id, token_hash, name, at, at, "")


def by_token(db: Database, token_hash: str) -> Bridge | None:
    row = db.one("SELECT * FROM bridges WHERE token_hash = ?", (token_hash,))
    return None if row is None else _bridge(row)


def get(db: Database, bridge_id: str) -> Bridge | None:
    row = db.one("SELECT * FROM bridges WHERE id = ?", (bridge_id,))
    return None if row is None else _bridge(row)


def every(db: Database) -> list[Bridge]:
    return [_bridge(r) for r in db.rows("SELECT * FROM bridges ORDER BY created_at, id")]


def seen(db: Database, bridge_id: str, at: str) -> None:
    with db.transaction():
        db.execute("UPDATE bridges SET last_seen = ? WHERE id = ?", (at, bridge_id))


def revoke(db: Database, bridge_id: str) -> bool:
    with db.transaction():
        return bool(
            db.execute(
                "UPDATE bridges SET revoked_at = ? WHERE id = ? AND revoked_at = ''", (now(), bridge_id)
            ).rowcount
        )
