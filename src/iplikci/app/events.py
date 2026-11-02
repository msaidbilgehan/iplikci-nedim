"""The event log as the feed and its live stream read it (ADR-0014, architecture §13)."""

from dataclasses import dataclass
from typing import Any

from ..storage import events
from .workspace import Workspace


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


def newest(ws: Workspace) -> int:
    """The id of the newest event; 0 while the log is empty."""
    with ws.db() as db:
        return events.newest(db)
