"""The archive as the Documents screen lists it (F03): every kept document with what reading it decided, how it
arrived and when, newest first, a page at a time."""

import base64
import binascii
from collections.abc import Iterable
from dataclasses import dataclass

from ..domain.codes import DocumentStatus
from ..parsers import registry
from ..storage import documents
from .workspace import Workspace

KEPT = (DocumentStatus.PROCESSED, DocumentStatus.UNPROCESSED, DocumentStatus.UNREADABLE)  # removed: in the Trash
MAX_PAGE = 200


@dataclass(frozen=True, slots=True)
class Listed:
    sha256: str
    name: str  # the readable name reading gave it, else the file's own
    file: str  # the file's own name
    kind: str  # a DocumentKind code; "" when no reader took it
    parser: str
    reader: str  # what the reader reads, for people
    status: str  # a DocumentStatus code
    reason: str  # why it was not processed
    verified: bool | None  # a statement's totals or balances checked; None for other documents
    period_start: str
    period_end: str
    sources: list[str]  # SourceKind codes: how it arrived, first arrival first
    added_at: str
    size: int


@dataclass(frozen=True, slots=True)
class Page:
    items: list[Listed]
    next: str  # the cursor of the next page; "" on the last one


class BadCursor(ValueError):
    """The cursor is not one this service gave out."""


def page(ws: Workspace, statuses: Iterable[str] = (), cursor: str = "", limit: int = 50) -> Page:
    """A page of the kept documents (only those with one of statuses, when given), newest first."""
    wanted = [DocumentStatus(s) for s in statuses] or list(KEPT)
    if not set(wanted) <= set(KEPT):
        raise ValueError("a removed document is in the Trash, not listed")
    size = max(1, min(limit, MAX_PAGE))
    with ws.db() as db:
        rows = documents.newest_first(db, wanted, _decode(cursor) if cursor else None, size + 1)
        shown = rows[:size]
        kinds = documents.source_kinds(db, [d.sha256 for d in shown])
    items = [
        Listed(
            sha256=d.sha256,
            name=d.display_name or d.name,
            file=d.name,
            kind=d.kind.value if d.kind else "",
            parser=d.parser,
            reader=registry.label(d.parser) if d.parser else "",
            status=d.status.value,
            reason=d.reason,
            verified=d.verified,
            period_start=d.period_start.isoformat() if d.period_start else "",
            period_end=d.period_end.isoformat() if d.period_end else "",
            sources=[k.value for k in kinds[d.sha256]],
            added_at=d.added_at,
            size=d.size,
        )
        for d in shown
    ]
    more = len(rows) > size
    return Page(items, _encode(shown[-1].added_at, shown[-1].sha256) if more and shown else "")


def _encode(added_at: str, sha256: str) -> str:
    return base64.urlsafe_b64encode(f"{added_at}|{sha256}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[str, str]:
    try:
        text = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise BadCursor("geçersiz sayfa imleci") from exc
    added_at, _, sha256 = text.partition("|")
    if not added_at or len(sha256) != 64:
        raise BadCursor("geçersiz sayfa imleci")
    return added_at, sha256
