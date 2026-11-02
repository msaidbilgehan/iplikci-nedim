"""Reading documents (the reading job of architecture §7): what a reader makes of a document, and reading the
stored ones again when that may have changed.

A document is read again when it was never read, when the reader that read it got a new version (ADR-0005), when
no reader took it and the readers changed, or when the company names in the settings changed: another name can make
a kept document a company one. Such a document leaves the vault for the system Trash and its rows go (ADR-0003); the
audit log says so. Every reading records its outcome in the event log (document.processed, .unprocessed or
.unreadable; the same outcome again adds nothing), and one that suggests the bank changed its format also raises
parser.format_alarm.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass

from ..domain.codes import Actor, DocumentKind, DocumentStatus
from ..domain.models import ParseResult
from ..parsers import Skipped, Unreadable, registry
from ..parsers.common import BUSINESS_REASON, business_check, business_names_signature
from ..parsers.contract import Document
from ..parsers.worker import parse_document
from ..storage import audit, documents, events, readings
from ..storage.db import Database
from ..vault.names import display_name
from .workspace import Workspace

type Progress = Callable[[int, int, str], None]

FORMAT_ALARM = "parser.format_alarm"


@dataclass
class Outcome:
    """What reading one document found."""

    status: DocumentStatus
    reason: str = ""
    business: bool = False  # a company document: never kept
    result: ParseResult | None = None
    parser: str = ""  # the reader that recognised the document and then gave up on it
    # The signature of the company names it was read with (business_check): the reading is kept under it, so one
    # made before the names changed is stale, however late it is recorded (an upload's plan waits for the user).
    business_sig: str = ""

    def format_alarm(self) -> dict[str, object] | None:
        """What says the bank may have changed its format (ADR-0005): the reader recognised the document and then
        could not read it, or read a statement that does not verify. An account list with too few rows to check its
        balances says nothing either way."""
        if self.result is not None:
            failing = [
                s.account
                for s in self.result.statements
                if not s.verified and not (s.is_account and s.checks_total == 0)
            ]
            if not failing:
                return None
            return {"parser": self.result.parser, "version": _version(self.result.parser), "unverified": failing}
        if self.parser and not self.business:
            return {"parser": self.parser, "version": _version(self.parser), "reason": self.reason}
        return None

    def event(self) -> dict[str, object]:
        """What the document event of this reading says (architecture §13: processed, unprocessed, unreadable)."""
        if self.result is not None:
            return {"parser": self.result.parser, "kind": str(self.kind)}
        return {"parser": self.parser, "reason": self.reason}

    @property
    def kind(self) -> DocumentKind | None:
        if self.result is None:
            return None
        if not self.result.statements:
            # A bank's notice brings rows the way a receipt does, a non-bank sender's bill none; its reader says which.
            kind = registry.document_type(self.result.parser)
            return kind if kind in (DocumentKind.NOTICE, DocumentKind.INVOICE) else DocumentKind.RECEIPT
        return DocumentKind.ACCOUNT_STATEMENT if self.result.statements[0].is_account else DocumentKind.CARD_STATEMENT

    def reading(self, name: str) -> documents.Reading:
        r = self.result
        if r is None:
            return documents.Reading(
                self.status,
                self.reason,
                parser=self.parser,
                parser_version=_version(self.parser),
                business_sig=self.business_sig or business_names_signature(),
            )
        first = r.statements[0] if r.statements else None
        return documents.Reading(
            self.status,
            kind=self.kind,
            parser=r.parser,
            parser_version=_version(r.parser),
            business_sig=self.business_sig or business_names_signature(),
            holder=r.holder,
            receipt_key=r.receipt_key,
            title=r.title,
            verified=first.verified if first else None,
            period_start=(first.start if first else None),
            period_end=first.cut_date
            if first
            else r.transactions[0].date
            if r.transactions
            else r.invoices[0].issued
            if r.invoices
            else None,
            display_name=display_name(r, os.path.splitext(name)[1].lower() or ".pdf", self.kind),
        )


def _version(parser_id: str) -> str:
    """What a reading keeps to tell later whether it is current: its reader's version, or with no reader the
    signature of them all."""
    reader = registry.find(parser_id) if parser_id else None
    return registry.version_of(reader) if reader else registry.signature()


def read(name: str, data: bytes, sha256: str, origin: str = "") -> Outcome:
    """Read one document in the reading process (ADR-0005). A broken document never stops the others: it is
    unreadable, with the reason. Only a reading process that cannot start stops the run (worker.WorkerError)."""
    names, sig = business_check()
    try:
        result = parse_document(Document(name=name, origin=origin, data=data, sha256=sha256), names)
    except Skipped as exc:
        if exc.business:
            return Outcome(DocumentStatus.UNPROCESSED, str(exc), business=True, business_sig=sig)
        return Outcome(DocumentStatus.UNPROCESSED, str(exc), parser=exc.parser, business_sig=sig)
    except Unreadable as exc:
        return Outcome(DocumentStatus.UNREADABLE, str(exc), parser=exc.parser, business_sig=sig)
    return Outcome(DocumentStatus.PROCESSED, result=result, business_sig=sig)


def record(db: Database, sha256: str, name: str, outcome: Outcome) -> None:
    """Keep what reading found: the document's status and, for a processed one, its rows; and a format alarm when
    the reading raises one."""
    with db.transaction():
        documents.record_reading(db, sha256, outcome.reading(name))
        if outcome.result is not None:
            readings.save(db, sha256, outcome.result)
        else:
            readings.clear(db, sha256)
        events.record(db, f"document.{outcome.status}", sha256, **outcome.event())
        if (alarm := outcome.format_alarm()) is not None:
            events.record(db, FORMAT_ALARM, sha256, **alarm)


def stale(doc: documents.DocumentRow) -> bool:
    return doc.status is not DocumentStatus.REMOVED and (
        not doc.read_at
        or not registry.current(doc.parser, doc.parser_version)
        or doc.business_sig != business_names_signature()
    )


def read_pending(ws: Workspace, db: Database, progress: Progress | None = None, every: bool = False) -> int:
    """Read the stored documents whose reading is missing or out of date (every=True: all of them); returns how
    many were read."""
    todo = [d for d in documents.every(db) if d.status is not DocumentStatus.REMOVED and (every or stale(d))]
    removed: set[str] = set()
    for i, doc in enumerate(todo, 1):
        if progress:
            progress(i, len(todo), doc.name)
        if doc.sha256 in removed:
            continue
        outcome = read(doc.name, ws.vault.read(doc.sha256), doc.sha256)
        if outcome.business:
            removed |= remove_company(ws, db, doc, outcome.reason)
        else:
            record(db, doc.sha256, doc.name, outcome)
    return len(todo)


def remove_company(ws: Workspace, db: Database, doc: documents.DocumentRow, reason: str = BUSINESS_REASON) -> set[str]:
    """A kept document that turned out to be a company's goes, and so do the attachments of a company's message:
    they are the company's too. The sha256s of the attachments that went."""
    _remove_business(ws, db, doc, reason)
    attached = [d for d in documents.every(db) if d.parent == doc.sha256 and d.status is not DocumentStatus.REMOVED]
    for child in attached:
        _remove_business(ws, db, child, BUSINESS_REASON)
    return {d.sha256 for d in attached}


def _remove_business(ws: Workspace, db: Database, doc: documents.DocumentRow, reason: str) -> None:
    """A kept document that turned out to be a company's (ADR-0003): to the Trash, its rows gone, recorded. A
    read-only workspace (the rebuild check) only marks it."""
    where = None if ws.read_only else ws.vault.remove(doc.sha256)
    with db.transaction():
        readings.clear(db, doc.sha256)
        documents.set_status(db, doc.sha256, DocumentStatus.REMOVED, reason)
        audit.record(db, Actor.SYSTEM, "document.business", doc.sha256, stage="reread")
        audit.record(db, Actor.SYSTEM, "document.removed", doc.sha256, trash=where.parent.name if where else "")
