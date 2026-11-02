"""The analysis, fed from the database (architecture §11, §12): the stored readings are combined into the
ledger and interpreted in memory, as in the MVP; the report, the exports and the month-end pages are written on
request.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .. import month_end
from ..analysis import CONFIRMED, NOT_ON_STATEMENT, PROVISIONAL, Dataset, build
from ..categorize import Categorizer
from ..domain.codes import DocumentStatus
from ..domain.models import ParseResult
from ..insights import FULL, Insights, interpret, month_of, shift
from ..parsers.common import BUSINESS_REASON
from ..report import build_payload, write_csv, write_html, write_xlsx
from ..storage import aliases, annotations, audit, documents, readings
from ..storage.annotations import Annotation
from ..storage.db import Database
from . import annotate, reading
from .workspace import Workspace

BUSINESS_NAME = "şirket belgesi"  # a company document is never kept, its name neither


@dataclass(frozen=True)
class StoredDocument:
    """What the ledger needs to know of a document besides its reading."""

    name: str
    origin: str
    sha256: str


type LedgerInput = list[tuple[StoredDocument, ParseResult | None, list[str] | None]]


def ledger_input(db: Database) -> tuple[LedgerInput, dict[str, int]]:
    """Every document as the ledger takes it (reading, or why there is none) and the counts of documents and of
    second arrivals. Company documents count by their audit entries: they are never kept."""
    docs = documents.every(db)
    kept = [d for d in docs if d.status is not DocumentStatus.REMOVED]
    # SQLite takes a bare column from the row min() picked: each document's first arrival.
    origins = {r[0]: r[1] for r in db.rows("SELECT sha256, origin, min(id) FROM document_sources GROUP BY sha256")}
    results = readings.load(db, [d for d in kept if d.status is DocumentStatus.PROCESSED])
    found: LedgerInput = []
    for d in kept:
        view = StoredDocument(d.name, origins.get(d.sha256, ""), d.sha256)
        if d.status is DocumentStatus.PROCESSED:
            found.append((view, results[d.sha256], None))
        elif d.status is DocumentStatus.UNREADABLE:
            found.append((view, None, ["hata", d.reason]))
        else:
            found.append((view, None, ["atlandi", d.reason]))
    business = sorted(audit.targets(db, "document.business"))
    found += [(StoredDocument(BUSINESS_NAME, "", sha), None, ["is", BUSINESS_REASON]) for sha in business]
    arrivals = documents.source_counts(db)
    stats = {
        "documents": len(kept) + len(business),
        "duplicates": sum(max(0, arrivals.get(d.sha256, 0) - 1) for d in kept),
    }
    return found, stats


# --- outputs ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Outputs:
    html: Path
    csv: Path
    xlsx: Path
    month_end: Path  # folder of the month-end pages; index.html lists them


def write_outputs(
    output: Path, ds: Dataset, ins: Insights, payload: dict[str, Any], months: list[month_end.MonthEnd]
) -> Outputs:
    """The report, the CSV and Excel exports and the month-end pages, side by side in output."""
    outputs = Outputs(
        output / "gider_raporu.html", output / "islemler.csv", output / "islemler.xlsx", output / month_end.FOLDER
    )
    output.mkdir(parents=True, exist_ok=True)
    write_html(payload, outputs.html)
    write_csv(ds, outputs.csv)
    write_xlsx(ds, outputs.xlsx, ins, months)
    month_end.write_all(months, ds, outputs.month_end)
    return outputs


@dataclass
class Analysis:
    dataset: Dataset
    stats: dict[str, int]
    insights: Insights
    payload: dict[str, Any]
    signature: tuple[object, ...]
    made: datetime
    outputs: Outputs | None = None
    # The month-end closing, oldest first, and the annotations no row carries any more.
    months: list[month_end.MonthEnd] = field(default_factory=list[month_end.MonthEnd])
    orphans: list[Annotation] = field(default_factory=list[Annotation])
    # The names the user gave accounts (F07), by id: the screens show them; the bank's label stays the account's own.
    aliases: dict[str, str] = field(default_factory=dict[str, str])


def account_labels(a: Analysis) -> dict[str, str]:
    """Every account's name as the screens show it, by id: the name the user gave it, else the bank's label. The
    baseline, the report, the exports and the MCP tools keep the bank's label."""
    return {account.id: a.aliases.get(account.id) or account.label for account in a.dataset.accounts.values()}


def analyze(
    ws: Workspace,
    progress: reading.Progress | None = None,
    write: bool = False,
    today: date | None = None,
    reread: bool = False,
) -> Analysis:
    """Read what needs reading, combine and interpret everything; write=True also writes the report, the CSV and
    Excel exports and the month-end pages (today decides which month is the current one). reread=True reads every
    document again, whatever its reading says."""
    with ws.lock():
        settings = ws.fresh_settings()  # the company names the documents are read with, as the file says now
        with ws.db() as db:
            reading.read_pending(ws, db, progress, every=reread)
            found, stats = ledger_input(db)
            notes = annotations.every(db)
            names_given = {account: given.alias for account, given in aliases.every(db).items()}
        signature = ws.signature()
    names = list(settings.identity.names)
    categorizer = Categorizer.layered(ws.rules)
    ds = build(found, categorizer, {"ad_soyad": names} if names else {})
    orphans = annotate.apply(ds, notes, categorizer)
    ins = interpret(ds)
    months = month_end.build(ds, ins, today)
    payload = build_payload(ds, stats, ins, months)
    outputs = write_outputs(ws.exports, ds, ins, payload, months) if write else None
    return Analysis(ds, stats, ins, payload, signature, datetime.now(), outputs, months, orphans, names_given)


class Current:
    """The latest analysis, redone when the documents, the annotations, the rules or the settings changed."""

    def __init__(self, ws: Workspace, write: bool):
        self.ws = ws
        self.write = write
        self._lock = threading.Lock()
        self._analysis: Analysis | None = None

    def get(self, progress: Callable[[int, int, str], None] | None = None) -> Analysis:
        with self._lock:
            if self._analysis is None or self._analysis.signature != self.ws.signature():
                self._analysis = analyze(self.ws, progress, write=self.write)
            return self._analysis

    def refresh(self, write: bool = True) -> Analysis:
        with self._lock:
            self._analysis = analyze(self.ws, write=write)
            return self._analysis


def summary(a: Analysis) -> dict[str, Any]:
    """What a run read and how much of it checked out: the numbers the CLI prints."""
    ds = a.dataset
    statuses = [d.status for d in ds.documents]
    cards = [s for s in ds.statements if not s.is_account]
    lists = [s for s in ds.statements if s.is_account]
    unverified = [
        {
            "account": ds.accounts[s.account].label,
            "cut": s.cut_date.isoformat(),
            "file": s.source,
            "detail": f"bakiye {s.checks_ok}/{s.checks_total}" if s.is_account else f"fark {s.difference}",
        }
        for s in ds.statements
        if not s.verified
    ]
    return {
        "documents": a.stats["documents"],
        "duplicates": a.stats["duplicates"],
        "cardStatements": len(cards),
        "cardStatementsVerified": sum(s.verified for s in cards),
        "accountStatements": len(lists),
        "accountStatementsVerified": sum(s.verified for s in lists),
        "receipts": statuses.count("dekont"),
        "notices": statuses.count("bildirim"),
        "invoices": statuses.count("fatura"),
        "business": statuses.count("is"),
        "skipped": statuses.count("atlandi"),
        "errors": statuses.count("hata"),
        "unverified": unverified,
        "unreadable": [{"name": d.name, "detail": d.detail} for d in ds.documents if d.status == "hata"],
        # Receipt rows: waiting for their statement (counted), found on it, or covered by one that does not show them.
        "receiptRows": {
            "provisional": sum(line.status == PROVISIONAL for line in ds.receipts),
            "confirmed": sum(line.status == CONFIRMED for line in ds.receipts),
            "notOnStatement": sum(line.status == NOT_ON_STATEMENT for line in ds.receipts),
        },
        "warnings": ds.warnings,
        "transactions": len(ds.transactions),
        "period": (
            [ds.transactions[0].date.isoformat(), ds.transactions[-1].date.isoformat()] if ds.transactions else None
        ),
    }


# --- what documents are missing ------------------------------------------------------------------------


@dataclass(frozen=True)
class Gap:
    """An account whose statements stop early or skip a month: what to download next."""

    account: str
    kind: str  # "ekstre" (card statements) or "hesap" (account movement lists)
    last: date  # newest statement end of the account
    behind: int  # days from that to today
    months: tuple[str, ...]  # months inside the account's statements they cover only partly or not
    id: str  # the account's id (account is its label)


_CLOSED_DAYS = 180  # statements that stopped this long before the other accounts': probably closed
_BEHIND_DAYS = 35  # a card prints a statement a month


def document_gaps(ds: Dataset, today: date | None = None, horizon: int = 12) -> list[Gap]:
    today = today or date.today()
    seen: dict[str, date] = {}
    kind: dict[str, str] = {}
    for s in ds.statements:
        seen[s.account] = max(seen.get(s.account, s.cut_date), s.cut_date)
        kind[s.account] = "hesap" if s.is_account else "ekstre"
    if not seen:
        return []
    newest = max(seen.values())
    oldest = shift(month_of(newest), -horizon)
    gaps: list[Gap] = []
    for account, last in seen.items():
        if (newest - last).days > _CLOSED_DAYS:
            continue
        cov = ds.coverage.get(account, {})
        months = sorted(cov)
        inner = months[1:-1]  # the first and the last month are partial by nature
        holes = tuple(m for m in inner if m >= oldest and cov[m] < FULL)
        behind = (today - last).days
        if holes or behind > _BEHIND_DAYS:
            gaps.append(Gap(ds.accounts[account].label, kind[account], last, behind, holes, account))
    return sorted(gaps, key=lambda g: (-g.behind, g.account))
