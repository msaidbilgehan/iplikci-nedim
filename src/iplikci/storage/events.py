"""The event log (ADR-0014, architecture §13): what happened, appended and never rewritten. The same event twice
is no news: an event the log already holds, with the same kind, target and detail, is not added again."""

import json
from dataclasses import dataclass
from typing import Any

from .db import Database, now


@dataclass(frozen=True, slots=True)
class Event:
    at: str
    kind: str
    target: str
    detail: dict[str, Any]


def record(db: Database, kind: str, target: str = "", **detail: Any) -> bool:
    """Add an event unless the log holds it already; whether it was added."""
    text = json.dumps(detail, ensure_ascii=False, sort_keys=True)
    with db.transaction():
        if db.scalar("SELECT 1 FROM events WHERE kind = ? AND target = ? AND detail = ?", (kind, target, text)):
            return False
        db.execute("INSERT INTO events (at, kind, target, detail) VALUES (?, ?, ?, ?)", (now(), kind, target, text))
    return True


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


def entries(db: Database, kind: str | None = None) -> list[Event]:
    rows = (
        db.rows("SELECT * FROM events ORDER BY id")
        if kind is None
        else db.rows("SELECT * FROM events WHERE kind = ? ORDER BY id", (kind,))
    )
    return [Event(r["at"], r["kind"], r["target"], json.loads(r["detail"])) for r in rows]
