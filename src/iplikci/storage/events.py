"""The event log (ADR-0014, architecture §13): what happened, appended and never rewritten. For what a reading
finds the same event twice is no news: `record` does not add an event the log already holds with the same kind,
target and detail. The feed's changes are news each time it sees them (`append`)."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .db import Database, now


@dataclass(frozen=True, slots=True)
class Event:
    at: str
    kind: str
    target: str
    detail: dict[str, Any]


def record(db: Database, kind: str, target: str = "", /, **detail: Any) -> bool:
    """Add an event unless the log holds it already; whether it was added."""
    text = json.dumps(detail, ensure_ascii=False, sort_keys=True)
    with db.transaction():
        if db.scalar("SELECT 1 FROM events WHERE kind = ? AND target = ? AND detail = ?", (kind, target, text)):
            return False
        db.execute("INSERT INTO events (at, kind, target, detail) VALUES (?, ?, ?, ?)", (now(), kind, target, text))
    return True


def append(db: Database, kind: str, target: str = "", /, **detail: Any) -> None:
    """Add an event as it is: the feed records a change once, when it sees it, so the same event again is news."""
    text = json.dumps(detail, ensure_ascii=False, sort_keys=True)
    with db.transaction():
        db.execute("INSERT INTO events (at, kind, target, detail) VALUES (?, ?, ?, ?)", (now(), kind, target, text))


def restore(db: Database, event: Event) -> None:
    """An event as a dump of the primary data recorded it, with its own time."""
    with db.transaction():
        db.execute(
            "INSERT INTO events (at, kind, target, detail) VALUES (?, ?, ?, ?)",
            (event.at, event.kind, event.target, json.dumps(event.detail, ensure_ascii=False, sort_keys=True)),
        )


def since(db: Database, after: int = 0, limit: int = 100) -> list[tuple[int, Event]]:
    """The events after the one with id after, oldest first, with their ids: what a feed has not seen yet."""
    rows = db.rows("SELECT * FROM events WHERE id > ? ORDER BY id LIMIT ?", (after, limit))
    return [(int(r["id"]), Event(r["at"], r["kind"], r["target"], json.loads(r["detail"]))) for r in rows]


def since_time(db: Database, at: str) -> list[tuple[int, Event]]:
    """The events recorded at or after a time (UTC, as stored), oldest first, with their ids."""
    rows = db.rows("SELECT * FROM events WHERE at >= ? ORDER BY id", (at,))
    return [(int(r["id"]), Event(r["at"], r["kind"], r["target"], json.loads(r["detail"]))) for r in rows]


def newest_first(
    db: Database, before: int = 0, limit: int = 100, codes: Sequence[str] = (), families: Sequence[str] = ()
) -> list[tuple[int, Event]]:
    """The events before the one with id before (0: from the newest), newest first, with their ids. codes and
    families narrow them: an event of one of the codes ("transaction.created"), or whose kind starts with one of the
    families ("document."); neither given, every kind."""
    where: list[str] = []
    params: list[object] = []
    if before:
        where.append("id < ?")
        params.append(before)
    kinds = [("kind = ?", [code]) for code in codes] + [("substr(kind, 1, ?) = ?", [len(f), f]) for f in families]
    if kinds:
        where.append("(" + " OR ".join(clause for clause, _ in kinds) + ")")
        params += [value for _, values in kinds for value in values]
    sql = "SELECT * FROM events" + (f" WHERE {' AND '.join(where)}" if where else "") + " ORDER BY id DESC LIMIT ?"
    rows = db.rows(sql, [*params, limit])
    return [(int(r["id"]), Event(r["at"], r["kind"], r["target"], json.loads(r["detail"]))) for r in rows]


def newest(db: Database) -> int:
    """The id of the last event; 0 when there is none."""
    return int(db.scalar("SELECT COALESCE(MAX(id), 0) FROM events") or 0)


def newest_before(db: Database, at: str) -> int:
    """The id of the last event recorded before a time (UTC, as stored); 0 when there is none."""
    return int(db.scalar("SELECT COALESCE(MAX(id), 0) FROM events WHERE at < ?", (at,)) or 0)


def entries(db: Database, kind: str | None = None) -> list[Event]:
    rows = (
        db.rows("SELECT * FROM events ORDER BY id")
        if kind is None
        else db.rows("SELECT * FROM events WHERE kind = ? ORDER BY id", (kind,))
    )
    return [Event(r["at"], r["kind"], r["target"], json.loads(r["detail"])) for r in rows]
