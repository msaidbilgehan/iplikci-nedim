"""Reading documents (the reading job of architecture §7): what a reader makes of a document, and reading the
stored ones again when that may have changed.

A document is read again when it was never read, when the readers changed (PARSER_VERSION) or when the company
names in the settings changed: another name can make a kept document a company one. Such a document leaves the
vault for the system Trash and its rows go (ADR-0003); the audit log says so.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass

from ..domain.codes import Actor, DocumentKind, DocumentStatus
from ..models import ParseResult
from ..parsers import PARSER_VERSION, Skipped, Unreadable, parse_document
from ..parsers.common import business_names_signature
from ..sources import Document
from ..storage import audit, documents, readings
from ..storage.db import Database
from ..vault.names import display_name
from .workspace import Workspace

type Progress = Callable[[int, int, str], None]


@dataclass
class Outcome:
    """What reading one document found."""

    status: DocumentStatus
    reason: str = ""
    business: bool = False  # a company document: never kept
    result: ParseResult | None = None

    @property
    def kind(self) -> DocumentKind | None:
        if self.result is None:
            return None
        if not self.result.statements:
            return DocumentKind.RECEIPT
        return DocumentKind.ACCOUNT_STATEMENT if self.result.statements[0].is_account else DocumentKind.CARD_STATEMENT

    def reading(self, name: str) -> documents.Reading:
        r = self.result
        if r is None:
            return documents.Reading(
                self.status,
                self.reason,
                parser_version=PARSER_VERSION,
                business_sig=business_names_signature(),
            )
        first = r.statements[0] if r.statements else None
        return documents.Reading(
            self.status,
            kind=self.kind,
            parser=r.parser,
            parser_version=PARSER_VERSION,
            business_sig=business_names_signature(),
            holder=r.holder,
            receipt_key=r.receipt_key,
            title=r.title,
            verified=first.verified if first else None,
            period_start=(first.start if first else None),
            period_end=first.cut_date if first else (r.transactions[0].date if r.transactions else None),
            display_name=display_name(r, os.path.splitext(name)[1].lower() or ".pdf"),
        )


def read(name: str, data: bytes, sha256: str, origin: str = "") -> Outcome:
    """Read one document in memory. A broken document never stops the others: it is unreadable, with the
    reason."""
    try:
        result = parse_document(Document(name=name, origin=origin, data=data, sha256=sha256))
    except Skipped as exc:
        if exc.business:
            return Outcome(DocumentStatus.UNPROCESSED, str(exc), business=True)
        return Outcome(DocumentStatus.UNPROCESSED, str(exc))
    except Unreadable as exc:
        return Outcome(DocumentStatus.UNREADABLE, str(exc))
    except Exception as exc:  # a reader that fails on one document must not stop the run  # noqa: BLE001
        return Outcome(DocumentStatus.UNREADABLE, f"{type(exc).__name__}: {exc}")
    return Outcome(DocumentStatus.PROCESSED, result=result)


def record(db: Database, sha256: str, name: str, outcome: Outcome) -> None:
    """Keep what reading found: the document's status and, for a processed one, its rows."""
    with db.transaction():
        documents.record_reading(db, sha256, outcome.reading(name))
        if outcome.result is not None:
            readings.save(db, sha256, outcome.result)
        else:
            readings.clear(db, sha256)


def stale(doc: documents.DocumentRow) -> bool:
    return doc.status is not DocumentStatus.REMOVED and (
        not doc.read_at or doc.parser_version != PARSER_VERSION or doc.business_sig != business_names_signature()
    )


def read_pending(ws: Workspace, db: Database, progress: Progress | None = None, every: bool = False) -> int:
    """Read the stored documents whose reading is missing or out of date (every=True: all of them); returns how
    many were read."""
    todo = [d for d in documents.every(db) if d.status is not DocumentStatus.REMOVED and (every or stale(d))]
    for i, doc in enumerate(todo, 1):
        if progress:
            progress(i, len(todo), doc.name)
        outcome = read(doc.name, ws.vault.read(doc.sha256), doc.sha256)
        if outcome.business:
            _remove_business(ws, db, doc, outcome.reason)
        else:
            record(db, doc.sha256, doc.name, outcome)
    return len(todo)


def _remove_business(ws: Workspace, db: Database, doc: documents.DocumentRow, reason: str) -> None:
    """A kept document that turned out to be a company's (ADR-0003): to the Trash, its rows gone, recorded. A
    read-only workspace (the rebuild check) only marks it."""
    where = None if ws.read_only else ws.vault.remove(doc.sha256)
    with db.transaction():
        readings.clear(db, doc.sha256)
        documents.set_status(db, doc.sha256, DocumentStatus.REMOVED, reason)
        audit.record(db, Actor.SYSTEM, "document.business", doc.sha256, stage="reread")
        audit.record(db, Actor.SYSTEM, "document.removed", doc.sha256, trash=where.parent.name if where else "")
