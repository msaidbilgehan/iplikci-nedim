"""Making the database again from the vault and the primary data (ADR-0004), and checking that it comes out the
same (`iplikci dogrula --yeniden-kur`).

What the readers read is derived: every document is read again from the vault. What nothing else knows is primary:
each document's name and arrivals, the user's annotations and account names, Claude's notes, the audit log (which, among
others, counts the company documents that were never kept), the event log and the notifications. It is dumped as JSON,
the dump is read back into a new database beside the real one, the documents are read again, and both are analysed and
compared. The vault is only read: a company document found on the way is marked in the new database, never moved.

The exchange rates the providers gave are not primary, but they came from the network and may not come again: the
dump carries them and the days each provider was asked for, so that both analyses use the same rates. A history of
years holds tens of thousands of quotes, so each is one line of text: "2026-11-02 tcmb USD 49.8827 49.9726".
"""

import json
import tempfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from .. import baseline
from ..domain.codes import Actor, DocumentStatus, MemoryKind, Necessity, RateSource, SourceKind
from ..fx.book import Quote
from ..storage import aliases, annotations, audit, documents, events, fx_rates, memories, notifications
from ..storage.aliases import Alias
from ..storage.annotations import Annotation, Subject, parts_of
from ..storage.audit import Entry
from ..storage.db import Database
from ..storage.documents import DocumentRow, Source
from ..storage.events import Event
from ..storage.fx_rates import Asked
from ..storage.memories import Memory
from ..storage.notifications import Notification
from . import reading
from .analysis import Analysis, analyze
from .workspace import Workspace

FORMAT = "iplikci-birincil-veri"
# 2: the event log; 3: the notifications; 4: the accounts' names; 5: the split rows' parts; 6: the exchange rates;
# 7: Claude's notes
VERSION = 7
# A version 2 dump has no notifications, a version 3 one no account names, a version 4 one no parts, a version 5 one
# no exchange rates, a version 6 one no notes of Claude's.
_READS = (2, 3, 4, 5, 6, 7)


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
    notifications: list[Notification] = field(default_factory=list[Notification])
    aliases: list[Alias] = field(default_factory=list[Alias])
    rates: list[Quote] = field(default_factory=list[Quote])
    rate_days: list[Asked] = field(default_factory=list[Asked])
    memories: list[Memory] = field(default_factory=list[Memory])


def export(db: Database) -> Primary:
    return Primary(
        [Kept(d, documents.sources(db, d.sha256)) for d in documents.every(db)],
        list(annotations.every(db).values()),
        audit.entries(db),
        events.entries(db),
        notifications.every(db),
        list(aliases.every(db).values()),
        fx_rates.every(db),
        fx_rates.asked_days(db),
        memories.every(db),
    )


def _rate_line(q: Quote) -> str:
    return f"{q.day.isoformat()} {q.source.value} {q.currency} {q.buying} {q.selling}"


def _rate(line: str) -> Quote:
    day, source, currency, buying, selling = line.split(" ")
    return Quote(date.fromisoformat(day), currency, Decimal(buying), Decimal(selling), RateSource(source))


def _day_line(a: Asked) -> str:
    return f"{a.day.isoformat()} {a.source.value} {int(a.published)} {a.asked_at}"


def _day(line: str) -> Asked:
    day, source, published, asked_at = line.split(" ")
    return Asked(date.fromisoformat(day), RateSource(source), published == "1", asked_at)


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
            asdict(a)
            | {
                "tags": list(a.tags),
                "necessity": a.necessity or "",
                "parts": [asdict(p) | {"necessity": p.necessity or ""} for p in a.parts],
            }
            for a in primary.annotations
        ],
        "audit": [asdict(e) for e in primary.audit],
        "events": [asdict(e) for e in primary.events],
        "notifications": [asdict(n) for n in primary.notifications],
        "aliases": [asdict(a) for a in primary.aliases],
        "rates": [_rate_line(q) for q in primary.rates],
        "rate_days": [_day_line(a) for a in primary.rate_days],
        "memories": [asdict(m) for m in primary.memories],
    }
    return json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True)


def load(text: str) -> Primary:
    value: dict[str, Any] = json.loads(text)
    if value.get("format") != FORMAT or value.get("version") not in _READS:
        raise ValueError(f"bu dosya bir {FORMAT} sürüm {' ya da '.join(map(str, _READS))} dökümü değil")
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
            parts=parts_of(a.get("parts", [])),
        )
        for a in value["annotations"]
    ]
    entries = [Entry(e["at"], Actor(e["actor"]), e["action"], e["target"], e["detail"]) for e in value["audit"]]
    happened = [Event(e["at"], e["kind"], e["target"], e["detail"]) for e in value["events"]]
    told = [Notification(**n) for n in value.get("notifications", [])]
    names = [Alias(a["account"], a["alias"], a["updated_at"], Actor(a["actor"])) for a in value.get("aliases", [])]
    rates = [_rate(line) for line in value.get("rates", [])]
    rate_days = [_day(line) for line in value.get("rate_days", [])]
    remembered = [
        Memory(**(m | {"kind": MemoryKind(m["kind"]), "actor": Actor(m["actor"])})) for m in value.get("memories", [])
    ]
    return Primary(kept, notes, entries, happened, told, names, rates, rate_days, remembered)


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
        for n in primary.notifications:
            notifications.restore(db, n)
        for name in primary.aliases:
            aliases.restore(db, name)
        # A dump keeps no fetch time of its own: the rates count as fetched when their newest day was asked for.
        fetched = max((a.asked_at for a in primary.rate_days), default="")
        fx_rates.restore(db, primary.rates, primary.rate_days, fetched)
        for memory in primary.memories:
            memories.restore(db, memory)


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
    memories: int = 0  # Claude's notes

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
    if live.aliases != again.aliases:
        out.append(f"hesap adları: {len(live.aliases)} → {len(again.aliases)}")
    return out


def rates_carried(primary: Primary, db: Database) -> list[str]:
    """What differs between the exchange rates the dump carried and those of the rebuilt database db."""
    rates, days = fx_rates.every(db), fx_rates.asked_days(db)
    if rates == primary.rates and days == primary.rate_days:
        return []
    carried = f"{len(primary.rates)} kur ve {len(primary.rate_days)} gün"
    return [f"kurlar: dökümde {carried}, yeniden kurulanda {len(rates)} kur ve {len(days)} gün"]


def notes_carried(kept: list[Memory], db: Database) -> list[str]:
    """What differs between Claude's notes in the real database (kept) and those of the rebuilt database db."""
    differ = {m.name for m in set(kept) ^ set(memories.every(db))}
    return [f"hafıza: {len(differ)} not yeniden kurulanda aynı değil"] if differ else []


def check(ws: Workspace, today: date | None = None, progress: reading.Progress | None = None) -> Report:
    """Dump the primary data, make the database again from it and the vault, and compare the two analyses."""
    today = today or date.today()
    live = analyze(ws, progress, today=today)
    with tempfile.TemporaryDirectory(prefix=".yeniden-kur-", dir=ws.run) as folder:
        with ws.lock():
            with ws.db() as db:
                primary = load(dump(export(db)))  # through the dump: it must carry everything
                kept = memories.every(db)
            shadow = rebuild(ws, Path(folder), primary, progress)
        again = analyze(shadow, today=today)
        with ws.db() as db, shadow.db() as other:
            differences = compare(live, again, documents.every(db), documents.every(other), today)
            differences += rates_carried(primary, other)
            differences += notes_carried(kept, other)
    return Report(len(primary.documents), len(primary.annotations), differences, len(primary.memories))
