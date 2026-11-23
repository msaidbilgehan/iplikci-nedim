"""The feed's view of an analysis: which rows exist, where each receipt row stands, how each month closes, and what
the analysis found to tell (news.py). Comparing two snapshots gives the events (architecture §13):

- `transaction.created` for every new row; more than BULK new rows at once (the first mailbox read, an old archive)
  make one event with their number and dates instead;
- `transaction.confirmed` when a statement shows a receipt's row that only the receipt showed before;
- `month.ended` when the month that just ended has its page and still waits for documents, `month.closed` when its
  statements close it, `month.needs_check` when its documents disagree; only the last three months speak, as the
  MVP's month-end news did;
- `invoice.pending`, `invoice.matched` and `invoice.unmatched` when a non-bank bill or receipt arrives or its status
  changes (F14); more than BULK at once make one event of each with their number;
- the payments due soon, the balances going below zero, the payments and income that did not come, the new prices,
  the payments after a cancellation, the income received, the large purchases and the receipt rows no statement
  shows (news.py); more than BULK of a kind at once make one event of that kind with their number.

The first snapshot only takes note: nothing before it is news, but for the payments due within the week (FIRST_TOLD),
which are the days ahead, not history. A data folder that starts empty tells them as its documents arrive anyway; one
whose first analysis already holds its documents (the demo's) would otherwise never tell those near at its start. A
kind told once per occurrence that the snapshot before did not keep yet (one saved by an older version) only takes
note too: an update tells no old price change.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, cast

from ..analysis import Dataset
from ..domain.codes import EvidenceStatus, InvoiceStatus, MonthStatus
from ..insights import Insights, month_of, shift
from ..month_end import MonthEnd
from ..upcoming import CardDue
from .news import DUE_SOON, NEGATIVE, OCCURRENCES, UNMATCHED, ZERO, Found, find

BULK = 50
# What the first snapshot tells all the same: a payment due within the week is still ahead. The forecast's balance
# below zero, the payments and income that did not come and the new prices rest on documents a first read may not
# have all of yet: there the first snapshot only takes note.
FIRST_TOLD = frozenset({DUE_SOON})
MONTHS_SPOKEN = 3
REMEMBERED = timedelta(days=365)  # an occurrence is remembered for a year after an analysis last found it


@dataclass(frozen=True, slots=True)
class Change:
    kind: str
    target: str
    detail: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass(frozen=True)
class Snapshot:
    month: str  # the month it was taken in
    rows: dict[str, tuple[str, str]]  # fingerprint -> (account, date)
    receipts: dict[str, str]  # a receipt row's fingerprint -> its EvidenceStatus
    months: dict[str, str]  # month -> its MonthStatus
    invoices: dict[str, str] = field(default_factory=dict[str, str])  # a bill's or receipt's key -> its InvoiceStatus
    day: str = ""  # the day it was taken on
    # Of each kind told once per occurrence (news.OCCURRENCES): its occurrences' keys -> the last day an analysis
    # found each, told or only noted.
    told: dict[str, dict[str, str]] = field(default_factory=dict[str, dict[str, str]])
    negative: dict[str, str] = field(default_factory=dict[str, str])  # bank account -> first day its forecast is < 0
    found: tuple[Found, ...] = field(default=(), compare=False)  # what the analysis found to tell; never saved

    def dump(self) -> dict[str, Any]:
        return {
            "month": self.month,
            "rows": {fp: list(where) for fp, where in self.rows.items()},
            "receipts": self.receipts,
            "months": self.months,
            "invoices": self.invoices,
            "day": self.day,
            "told": self.told,
            "negative": self.negative,
        }

    @classmethod
    def load(cls, value: Any) -> "Snapshot | None":
        """A saved snapshot; None when there is none or it is not one (then the next one only takes note)."""
        if not isinstance(value, dict):
            return None
        data = cast(dict[str, Any], value)
        try:
            rows = cast(dict[str, list[str]], data["rows"])
            told = cast(dict[str, dict[str, Any]], data.get("told", {}))
            return cls(
                str(data["month"]),
                {str(fp): (str(where[0]), str(where[1])) for fp, where in rows.items()},
                {str(k): str(v) for k, v in cast(dict[str, Any], data["receipts"]).items()},
                {str(k): str(v) for k, v in cast(dict[str, Any], data["months"]).items()},
                # A snapshot saved before Phase 4 knew no bills: every bill it did not know is news. One saved before
                # Phase 5 kept no occurrences: their kinds only take note (diff).
                {str(k): str(v) for k, v in cast(dict[str, Any], data.get("invoices", {})).items()},
                str(data.get("day", "")),
                {str(kind): {str(k): str(v) for k, v in keys.items()} for kind, keys in told.items()},
                {str(k): str(v) for k, v in cast(dict[str, Any], data.get("negative", {})).items()},
            )
        except (KeyError, IndexError, TypeError, AttributeError):
            return None

    def keeping(self, before: "Snapshot | None") -> "Snapshot":
        """The snapshot to save: what this analysis found, with what the snapshot before remembered that an analysis
        found within REMEMBERED. Remembered, an occurrence is told once however often it comes and goes; after that
        time it cannot come again (a day has passed) or has been gone for long."""
        if before is None:
            return self
        since = (date.fromisoformat(self.day) - REMEMBERED).isoformat() if self.day else ""
        told = {
            kind: {**{key: day for key, day in before.told.get(kind, {}).items() if day >= since}, **keys}
            for kind, keys in self.told.items()
        }
        return replace(self, told=told)


def take(
    ds: Dataset,
    ins: Insights,
    months: list[MonthEnd],
    today: date,
    dues: Sequence[CardDue] = (),
    cover: Decimal = ZERO,
) -> Snapshot:
    """The snapshot of an analysis made on today; dues are the cards' due dates the outlook reads (app.outlook), cover
    what the foreign currency and investments are worth in TL today (app.now.cover)."""
    # A split row's parts are the one row the documents brought: its fingerprint is what news compares (F04).
    rows = {t.split_of or t.fingerprint: (t.account, t.date.isoformat()) for t in ds.transactions if t.fingerprint}
    receipts = {line.txn.fingerprint: str(line.status) for line in ds.receipts if line.txn.fingerprint}
    invoices = {found.key: str(found.status) for found in ds.invoices}
    found = find(ds, ins, today, dues, cover)
    day = today.isoformat()
    told = {kind: {f.key: day for f in found if f.kind == kind} for kind in OCCURRENCES}
    negative = {str(f.detail["account"]): str(f.detail["day"]) for f in found if f.kind == NEGATIVE}
    return Snapshot(
        month_of(today),
        rows,
        receipts,
        {m.month: str(m.status) for m in months},
        invoices,
        day,
        told,
        negative,
        tuple(found),
    )


def diff(before: Snapshot | None, after: Snapshot) -> list[Change]:
    if before is None:
        return _told([found for found in after.found if found.kind in FIRST_TOLD])
    return [
        *_new_rows(before, after),
        *_confirmed(before, after),
        *_months(before, after),
        *_invoices(before, after),
        *_news(before, after),
    ]


def _invoices(before: Snapshot, after: Snapshot) -> list[Change]:
    """A bill or receipt that arrived, or whose status changed: one event each, or one per status beyond BULK."""
    changed: dict[str, list[str]] = {}
    for key, status in sorted(after.invoices.items()):
        if before.invoices.get(key) != status:
            changed.setdefault(status, []).append(key)
    changes: list[Change] = []
    for status, keys in changed.items():
        kind = f"invoice.{InvoiceStatus(status)}"
        if len(keys) > BULK:
            changes.append(Change(kind, "", {"count": len(keys)}))
        else:
            changes += [Change(kind, key) for key in keys]
    return changes


def _new_rows(before: Snapshot, after: Snapshot) -> list[Change]:
    new = sorted((where[1], fp) for fp, where in after.rows.items() if fp not in before.rows)
    if len(new) > BULK:
        return [Change("transaction.created", "", {"count": len(new), "from": new[0][0], "to": new[-1][0]})]
    return [
        Change(
            "transaction.created", fp, {"account": after.rows[fp][0], "date": day, "provisional": fp in after.receipts}
        )
        for day, fp in new
    ]


def _confirmed(before: Snapshot, after: Snapshot) -> list[Change]:
    return [
        Change("transaction.confirmed", fp)
        for fp, status in sorted(after.receipts.items())
        if status == EvidenceStatus.MATCHED and before.receipts.get(fp) == EvidenceStatus.PROVISIONAL
    ]


def _months(before: Snapshot, after: Snapshot) -> list[Change]:
    ended = shift(after.month, -1)
    changes: list[Change] = []
    for month in sorted(after.months)[-MONTHS_SPOKEN:]:
        status, was = after.months[month], before.months.get(month)
        if month == ended and was in (None, MonthStatus.RUNNING) and status != MonthStatus.CLOSED:
            changes.append(Change("month.ended", month, {"status": status}))
        elif status == MonthStatus.CLOSED and was != MonthStatus.CLOSED:
            changes.append(Change("month.closed", month))
        elif status == MonthStatus.CHECK and was != MonthStatus.CHECK:
            changes.append(Change("month.needs_check", month))
    return changes


def _news(before: Snapshot, after: Snapshot) -> list[Change]:
    """What the analysis found that is news against the snapshot before."""
    return _told([found for found in after.found if _is_news(before, found)])


def _told(found: Sequence[Found]) -> list[Change]:
    """What is news: one event each, or one of a kind with their number beyond BULK."""
    news: dict[str, list[Found]] = {}
    for item in found:
        news.setdefault(item.kind, []).append(item)
    changes: list[Change] = []
    for kind, items in news.items():
        if len(items) > BULK:
            changes.append(Change(kind, "", {"count": len(items)}))
        else:
            changes += [Change(f.kind, f.target, f.detail) for f in items]
    return changes


def _is_news(before: Snapshot, found: Found) -> bool:
    """An occurrence is news when the snapshot before neither told nor noted it; of a kind that snapshot did not keep
    yet, it only takes note. A forecast's first day below zero that only moved later is no news: with no new
    document, each day's forecast starts from the same balance, so a day the spread over the days decides moves on by
    one every day; one that came sooner is news. A row is news when no fingerprint it may have been known by was
    there before; a receipt's row when it became unmatched."""
    if found.kind in OCCURRENCES:
        told = before.told.get(found.kind)
        if told is None or found.key in told:
            return False
        if found.kind == NEGATIVE:
            was = before.negative.get(str(found.detail["account"]))
            return was is None or str(found.detail["day"]) < was
        return True
    if found.kind == UNMATCHED:
        return before.receipts.get(found.target) != EvidenceStatus.UNMATCHED
    return not any(fp in before.rows for fp in found.rows)
