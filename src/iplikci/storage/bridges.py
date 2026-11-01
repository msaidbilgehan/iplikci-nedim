"""The paired browser extensions (ADR-0016), each with the SHA-256 of its token, and the Gmail ids of the messages
they delivered: those the service holds, and those it refused with why."""

import sqlite3
from collections.abc import Sequence
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


def remember(db: Database, gmail_id: str, sha256: str, complete: bool) -> None:
    """A message the service holds, by Gmail's id: a scan of Gmail does not download it again, unless it came with
    its attachments left out. A refusal of it before is history: two extensions may deliver the same message, the
    whole one refused and an older version's copy without attachments kept after it, which a scan must complete."""
    with db.transaction():
        db.execute(
            "INSERT OR REPLACE INTO bridge_messages (gmail_id, sha256, delivered_at, complete) VALUES (?, ?, ?, ?)",
            (gmail_id, sha256, now(), int(complete)),
        )
        db.execute("DELETE FROM bridge_refused WHERE gmail_id = ?", (gmail_id,))


@dataclass(frozen=True, slots=True)
class Held:
    sha256: str
    complete: bool | None  # None: not looked at yet


def held(db: Database, gmail_id: str) -> Held | None:
    row = db.one("SELECT sha256, complete FROM bridge_messages WHERE gmail_id = ?", (gmail_id,))
    if row is None:
        return None
    return Held(str(row["sha256"]), None if row["complete"] is None else bool(row["complete"]))


def unchecked(db: Database) -> list[tuple[str, str]]:
    """(Gmail id, sha256) of the held messages not looked at yet for attachments left out."""
    return [
        (str(r["gmail_id"]), str(r["sha256"]))
        for r in db.rows("SELECT gmail_id, sha256 FROM bridge_messages WHERE complete IS NULL")
    ]


def set_complete(db: Database, gmail_id: str, complete: bool) -> None:
    with db.transaction():
        db.execute("UPDATE bridge_messages SET complete = ? WHERE gmail_id = ?", (int(complete), gmail_id))


def refuse(db: Database, gmail_id: str, taken: str, reason: str, domain: str, key: str) -> None:
    """A message the service did not keep, by Gmail's id, under the settings key: a scan does not download it again
    while the key stays."""
    with db.transaction():
        db.execute(
            "INSERT OR REPLACE INTO bridge_refused (gmail_id, taken, reason, domain, key, refused_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (gmail_id, taken, reason, domain, key, now()),
        )


def missing(db: Database, gmail_ids: Sequence[str], key: str) -> list[str]:
    """The ids of gmail_ids no whole delivered message carries and none refused under key, in the order given and
    without repeats: a message held with its attachments left out is missing too."""
    wanted = list(dict.fromkeys(gmail_ids))
    known: set[str] = set()
    for start in range(0, len(wanted), 500):  # SQLite allows a limited number of parameters
        chunk = wanted[start : start + 500]
        marks = ", ".join("?" * len(chunk))
        known |= {
            str(r["gmail_id"])
            for r in db.rows(
                f"SELECT gmail_id FROM bridge_messages WHERE gmail_id IN ({marks}) AND complete IS NOT 0 "
                f"UNION SELECT gmail_id FROM bridge_refused WHERE key = ? AND gmail_id IN ({marks})",
                [*chunk, key, *chunk],
            )
        }
    return [i for i in wanted if i not in known]


@dataclass(frozen=True, slots=True)
class Refusals:
    taken: str
    reason: str
    domain: str
    count: int


def refusals(db: Database, key: str) -> list[Refusals]:
    """The messages refused under key, counted by what became of them, why and from which domain; most first."""
    rows = db.rows(
        "SELECT taken, reason, domain, count(*) AS n FROM bridge_refused WHERE key = ? "
        "GROUP BY taken, reason, domain ORDER BY n DESC, taken, reason, domain",
        (key,),
    )
    return [Refusals(str(r["taken"]), str(r["reason"]), str(r["domain"]), int(r["n"])) for r in rows]
