"""Making the database again from the vault and the primary data (ADR-0004), and checking that it comes out the
same (`iplikci dogrula --yeniden-kur`).

What the readers read is derived: every document is read again from the vault. What nothing else knows is primary:
each document's name and arrivals, the user's annotations, the audit log (which, among others, counts the company
documents that were never kept) and the event log. It is dumped as JSON, the dump is read back into a new database beside
the real one, the documents are read again, and both are analysed and compared. The vault is only read: a company
document found on the way is marked in the new database, never moved.
"""

import json
import tempfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

from .. import baseline
from ..domain.codes import Actor, DocumentStatus, Necessity, SourceKind
from ..storage import annotations, audit, documents, events
from ..storage.annotations import Annotation, Subject
from ..storage.audit import Entry
from ..storage.db import Database
from ..storage.documents import DocumentRow, Source
from ..storage.events import Event
from . import reading
from .analysis import Analysis, analyze
from .workspace import Workspace

FORMAT = "iplikci-birincil-veri"
VERSION = 2  # 2: the event log


@dataclass(frozen=True)
class Kept:
    """A document as the primary data knows it: its row (only a removal is primary there) and its arrivals."""

    row: DocumentRow
    sources: list[Source]


@dataclass(frozen=True)
class Primary:
    documents: list[Kept] = field(default_factory=list[Kept])
    annotations: list[Annotation] = field(default_factory=list[Annotation])
    audit: list[Entry] = field(default_factory=list[Entry])
    events: list[Event] = field(default_factory=list[Event])


def export(db: Database) -> Primary:
    return Primary(
        [Kept(d, documents.sources(db, d.sha256)) for d in documents.every(db)],
        list(annotations.every(db).values()),
        audit.entries(db),
        events.entries(db),
    )


def dump(primary: Primary) -> str:
    """The primary data as JSON: what a backup keeps besides the vault and the rule files."""
    value = {
        "format": FORMAT,
        "version": VERSION,
        "documents": [
            {
                "sha256": k.row.sha256,
                "name": k.row.name,
                "size": k.row.size,
                "added_at": k.row.added_at,
                "parent": k.row.parent,
                "removed": k.row.status is DocumentStatus.REMOVED,
                "reason": k.row.reason if k.row.status is DocumentStatus.REMOVED else "",
                "sources": [asdict(s) for s in k.sources],
            }
            for k in primary.documents
        ],
        "annotations": [
            asdict(a) | {"tags": list(a.tags), "necessity": a.necessity or ""} for a in primary.annotations
        ],
        "audit": [asdict(e) for e in primary.audit],
        "events": [asdict(e) for e in primary.events],
    }
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True)


def load(text: str) -> Primary:
    value: dict[str, Any] = json.loads(text)
    if value.get("format") != FORMAT or value.get("version") != VERSION:
        raise ValueError(f"bu dosya bir {FORMAT} sürüm {VERSION} dökümü değil")
    kept = [
        Kept(
            DocumentRow(
                sha256=d["sha256"],
                name=d["name"],
                size=d["size"],
                status=DocumentStatus.REMOVED if d["removed"] else DocumentStatus.UNPROCESSED,
                reason=d["reason"],
                parent=d["parent"],
                added_at=d["added_at"],
            ),
            [Source(**(s | {"kind": SourceKind(s["kind"])})) for s in d["sources"]],
        )
        for d in value["documents"]
    ]
    notes = [
        Annotation(
            fingerprint=a["fingerprint"],
            subject=Subject(**a["subject"]),
            note=a["note"],
            tags=tuple(a["tags"]),
            category=a["category"],
            necessity=Necessity(a["necessity"]) if a["necessity"] else None,
            created_at=a["created_at"],
            updated_at=a["updated_at"],
            actor=Actor(a["actor"]),
        )
        for a in value["annotations"]
    ]
    entries = [Entry(e["at"], Actor(e["actor"]), e["action"], e["target"], e["detail"]) for e in value["audit"]]
    happened = [Event(e["at"], e["kind"], e["target"], e["detail"]) for e in value["events"]]
    return Primary(kept, notes, entries, happened)


def restore(db: Database, primary: Primary) -> None:
    """Put the primary data into an empty database; the documents wait to be read."""
    with db.transaction():
        for k in primary.documents:
            documents.restore(db, k.row)
            for source in k.sources:
                documents.add_source(db, k.row.sha256, source)
        for a in primary.annotations:
            annotations.restore(db, a)
        for e in primary.audit:
            audit.restore(db, e)
        for event in primary.events:
            events.restore(db, event)


def rebuild(ws: Workspace, folder: Path, primary: Primary, progress: reading.Progress | None = None) -> Workspace:
    """A database made again in folder from the vault and primary; the returned workspace uses it and only reads
    the vault."""
    shadow = replace(ws, database=folder / "iplikci.db", read_only=True)
    with shadow.db() as db:
        restore(db, primary)
        reading.read_pending(shadow, db, progress, every=True)
    return shadow


# --- the check ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Report:
    documents: int  # in the primary data
    annotations: int
    differences: list[str]

    @property
    def ok(self) -> bool:
        return not self.differences


def _document_view(d: DocumentRow) -> tuple[object, ...]:
    return (d.status, d.reason, d.kind, d.parser, d.verified, d.period_start, d.period_end, d.display_name)


def _ledger_view(a: Analysis) -> set[tuple[object, ...]]:
    return {
        (t.fingerprint, t.date, round(t.amount * 100), t.kind, t.category, t.necessity, t.note, t.tags)
        for t in a.dataset.transactions
    }


def compare(
    live: Analysis, again: Analysis, live_docs: Iterable[DocumentRow], again_docs: Iterable[DocumentRow], day: date
) -> list[str]:
    """What differs between the analysis of the real database and that of the rebuilt one (day: the baselines')."""
    out: list[str] = []
    before, after = ({d.sha256: _document_view(d) for d in docs} for docs in (live_docs, again_docs))
    for sha in sorted(before.keys() | after.keys()):
        if before.get(sha) != after.get(sha):
            out.append(f"belge {sha[:12]}: {before.get(sha)} → {after.get(sha)}")
    rows_before, rows_after = _ledger_view(live), _ledger_view(again)
    if rows_before != rows_after:
        out.append(
            f"işlemler: {len(rows_before - rows_after)} işlem yalnızca gerçek veritabanında, "
            f"{len(rows_after - rows_before)} işlem yalnızca yeniden kurulanda"
        )
    for c in baseline.compare(
        baseline.take(live.dataset, live.stats, live.months, day),
        baseline.take(again.dataset, again.stats, again.months, day),
    ):
        out.append(f"taban — {c.label}: {c.before} → {c.after}")
    orphans_before = sorted(o.fingerprint for o in live.orphans)
    orphans_after = sorted(o.fingerprint for o in again.orphans)
    if orphans_before != orphans_after:
        out.append(f"yetim düzeltmeler: {len(orphans_before)} → {len(orphans_after)}")
    return out


def check(ws: Workspace, today: date | None = None, progress: reading.Progress | None = None) -> Report:
    """Dump the primary data, make the database again from it and the vault, and compare the two analyses."""
    today = today or date.today()
    live = analyze(ws, progress, today=today)
    with tempfile.TemporaryDirectory(prefix=".yeniden-kur-", dir=ws.run) as folder:
        with ws.lock():
            with ws.db() as db:
                primary = load(dump(export(db)))  # through the dump: it must carry everything
            shadow = rebuild(ws, Path(folder), primary, progress)
        again = analyze(shadow, today=today)
        with ws.db() as db, shadow.db() as other:
            differences = compare(live, again, documents.every(db), documents.every(other), today)
    return Report(len(primary.documents), len(primary.annotations), differences)
