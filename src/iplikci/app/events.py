"""The event log as the feed and its live stream read it (ADR-0014, architecture §13)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from ..storage import events
from .workspace import Workspace

REPLAY = timedelta(minutes=1)  # what a stream opened afresh tells again: the page may have been loading through it


@dataclass(frozen=True, slots=True)
class LoggedEvent:
    id: int
    at: str
    kind: str
    target: str
    detail: dict[str, Any]


def since(ws: Workspace, after: int = 0, limit: int = 100) -> list[LoggedEvent]:
    """The events after the one with id after, oldest first."""
    with ws.db() as db:
        found = events.since(db, after, limit)
    return [LoggedEvent(id, e.at, e.kind, e.target, e.detail) for id, e in found]


def fresh_start(ws: Workspace, now: datetime) -> int:
    """Where a stream opened afresh starts: after the newest event older than REPLAY. What happened before is in what
    the page loads, but the events of the moment the page was loading may be in neither: those come again."""
    with ws.db() as db:
        return events.newest_before(db, (now - REPLAY).replace(microsecond=0).isoformat())
