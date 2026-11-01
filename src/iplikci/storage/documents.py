"""The documents table and where each document came from (ADR-0003)."""

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from ..domain.codes import DocumentKind, DocumentStatus, SourceKind
from ..domain.text import fold
from .db import Database, now


@dataclass(frozen=True, slots=True)
class DocumentRow:
    sha256: str
    name: str
    size: int
    status: DocumentStatus
    reason: str = ""
    kind: DocumentKind | None = None
    parser: str = ""
    parser_version: str = ""
    business_sig: str = ""
    holder: str = ""
    receipt_key: str = ""
    title: str = ""
    verified: bool | None = None
    period_start: date | None = None
    period_end: date | None = None
    display_name: str = ""
    parent: str = ""
    added_at: str = ""
    read_at: str = ""

    @property
    def ext(self) -> str:
        dot = self.name.rfind(".")
        return self.name[dot:].lower() if dot > 0 else ""


@dataclass(frozen=True, slots=True)
class Source:
    kind: SourceKind
    original: str = ""
    origin: str = ""
    message_id: str = ""
    sender: str = ""
    subject: str = ""
    sent_at: str = ""
    received_at: str = ""


@dataclass(frozen=True, slots=True)
class Reading:
    """What reading a document decided about it."""

    status: DocumentStatus
    reason: str = ""
    kind: DocumentKind | None = None
    parser: str = ""
    parser_version: str = ""
    business_sig: str = ""
    holder: str = ""
    receipt_key: str = ""
    title: str = ""
    verified: bool | None = None
    period_start: date | None = None
    period_end: date | None = None
    display_name: str = ""


def _day(text: str) -> date | None:
    return date.fromisoformat(text) if text else None


def _row(row: sqlite3.Row) -> DocumentRow:
    verified = row["verified"]
    return DocumentRow(
        sha256=row["sha256"],
        name=row["name"],
        size=row["size"],
        status=DocumentStatus(row["status"]),
        reason=row["reason"],
        kind=DocumentKind(row["kind"]) if row["kind"] else None,
        parser=row["parser"],
        parser_version=row["parser_version"],
        business_sig=row["business_sig"],
        holder=row["holder"],
        receipt_key=row["receipt_key"],
        title=row["title"],
        verified=None if verified is None else bool(verified),
        period_start=_day(row["period_start"]),
        period_end=_day(row["period_end"]),
        display_name=row["display_name"],
        parent=row["parent"],
        added_at=row["added_at"],
        read_at=row["read_at"],
    )


def add(db: Database, sha256: str, name: str, size: int, parent: str = "") -> bool:
    """A new document, not read yet; False when the vault already had these bytes."""
    with db.transaction():
        cursor = db.execute(
            "INSERT OR IGNORE INTO documents (sha256, name, size, status, parent, added_at) VALUES (?, ?, ?, ?, ?, ?)",
            (sha256, name, size, DocumentStatus.UNPROCESSED, parent, now()),
        )
        if cursor.rowcount:
            _index(db, sha256, name)
    return bool(cursor.rowcount)


def get(db: Database, sha256: str) -> DocumentRow | None:
    row = db.one("SELECT * FROM documents WHERE sha256 = ?", (sha256,))
    return None if row is None else _row(row)


def every(db: Database, statuses: Iterable[DocumentStatus] | None = None) -> list[DocumentRow]:
    """The documents in the order they arrived, optionally only those with one of statuses."""
    rows = db.rows("SELECT * FROM documents ORDER BY added_at, rowid")
    wanted = None if statuses is None else set(statuses)
    return [doc for doc in map(_row, rows) if wanted is None or doc.status in wanted]


def add_source(db: Database, sha256: str, source: Source) -> bool:
    """Record one arrival of a document; False when exactly this arrival was recorded before."""
    with db.transaction():
        cursor = db.execute(
            "INSERT OR IGNORE INTO document_sources "
            "(sha256, kind, original, origin, message_id, sender, subject, sent_at, received_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sha256,
                source.kind,
                source.original,
                source.origin,
                source.message_id,
                source.sender,
                source.subject,
                source.sent_at,
                source.received_at or now(),
            ),
        )
    return bool(cursor.rowcount)


def has_source(db: Database, sha256: str, source: Source) -> bool:
    """Whether exactly this arrival (kind, name, origin, e-mail) is recorded."""
    return bool(
        db.scalar(
            "SELECT count(*) FROM document_sources WHERE sha256 = ? AND kind = ? AND original = ? AND origin = ? "
            "AND message_id = ?",
            (sha256, source.kind, source.original, source.origin, source.message_id),
        )
    )


def sources(db: Database, sha256: str) -> list[Source]:
    rows = db.rows("SELECT * FROM document_sources WHERE sha256 = ? ORDER BY id", (sha256,))
    return [
        Source(
            kind=SourceKind(r["kind"]),
            original=r["original"],
            origin=r["origin"],
            message_id=r["message_id"],
            sender=r["sender"],
            subject=r["subject"],
            sent_at=r["sent_at"],
            received_at=r["received_at"],
        )
        for r in rows
    ]


def source_counts(db: Database) -> dict[str, int]:
    """How many times each document arrived."""
    return {r[0]: r[1] for r in db.rows("SELECT sha256, count(*) FROM document_sources GROUP BY sha256")}


def record_reading(db: Database, sha256: str, reading: Reading) -> None:
    with db.transaction():
        db.execute(
            "UPDATE documents SET status = ?, reason = ?, kind = ?, parser = ?, parser_version = ?, "
            "business_sig = ?, holder = ?, receipt_key = ?, title = ?, verified = ?, period_start = ?, "
            "period_end = ?, display_name = ?, read_at = ? WHERE sha256 = ?",
            (
                reading.status,
                reading.reason,
                reading.kind or "",
                reading.parser,
                reading.parser_version,
                reading.business_sig,
                reading.holder,
                reading.receipt_key,
                reading.title,
                None if reading.verified is None else int(reading.verified),
                reading.period_start.isoformat() if reading.period_start else "",
                reading.period_end.isoformat() if reading.period_end else "",
                reading.display_name,
                now(),
                sha256,
            ),
        )
        doc = get(db, sha256)
        if doc is not None:
            _index(db, sha256, f"{doc.name} {reading.display_name} {reading.title}")


def set_status(db: Database, sha256: str, status: DocumentStatus, reason: str) -> None:
    with db.transaction():
        db.execute("UPDATE documents SET status = ?, reason = ? WHERE sha256 = ?", (status, reason, sha256))


def _index(db: Database, sha256: str, text: str) -> None:
    db.execute("DELETE FROM search WHERE kind = 'document' AND ref = ?", (sha256,))
    db.execute(
        "INSERT INTO search (text, sha256, kind, ref) VALUES (?, ?, 'document', ?)", (fold(text), sha256, sha256)
    )
