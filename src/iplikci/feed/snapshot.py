"""The feed's view of an analysis: which rows exist, where each receipt row stands, and how each month closes.
Comparing two snapshots gives the events (architecture §13):

- `transaction.created` for every new row; more than BULK new rows at once (the first mailbox read, an old archive)
  make one event with their number and dates instead;
- `transaction.confirmed` when a statement shows a receipt's row that only the receipt showed before;
- `month.ended` when the month that just ended has its page and still waits for documents, `month.closed` when its
  statements close it, `month.needs_check` when its documents disagree; only the last three months speak, as the
  MVP's month-end news did;
- `invoice.pending`, `invoice.matched` and `invoice.unmatched` when a non-bank bill or receipt arrives or its status
  changes (F14); more than BULK at once make one event of each with their number.

The first snapshot only takes note: nothing before it is news.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, cast

from ..analysis import Dataset
from ..domain.codes import EvidenceStatus, InvoiceStatus, MonthStatus
from ..insights import month_of, shift
from ..month_end import MonthEnd

BULK = 50
MONTHS_SPOKEN = 3


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

    def dump(self) -> dict[str, Any]:
        return {
            "month": self.month,
            "rows": {fp: list(where) for fp, where in self.rows.items()},
            "receipts": self.receipts,
            "months": self.months,
            "invoices": self.invoices,
        }

    @classmethod
    def load(cls, value: Any) -> "Snapshot | None":
        """A saved snapshot; None when there is none or it is not one (then the next one only takes note)."""
        if not isinstance(value, dict):
            return None
        data = cast(dict[str, Any], value)
        try:
            rows = cast(dict[str, list[str]], data["rows"])
            return cls(
                str(data["month"]),
                {str(fp): (str(where[0]), str(where[1])) for fp, where in rows.items()},
                {str(k): str(v) for k, v in cast(dict[str, Any], data["receipts"]).items()},
                {str(k): str(v) for k, v in cast(dict[str, Any], data["months"]).items()},
                # A snapshot saved before Phase 4 knew no bills: every bill it did not know is news.
                {str(k): str(v) for k, v in cast(dict[str, Any], data.get("invoices", {})).items()},
            )
        except (KeyError, IndexError, TypeError, AttributeError):
            return None


def take(ds: Dataset, months: list[MonthEnd], today: date) -> Snapshot:
    rows = {t.fingerprint: (t.account, t.date.isoformat()) for t in ds.transactions if t.fingerprint}
    receipts = {line.txn.fingerprint: str(line.status) for line in ds.receipts if line.txn.fingerprint}
    invoices = {found.key: str(found.status) for found in ds.invoices}
    return Snapshot(month_of(today), rows, receipts, {m.month: str(m.status) for m in months}, invoices)


def diff(before: Snapshot | None, after: Snapshot) -> list[Change]:
    if before is None:
        return []
    return [*_new_rows(before, after), *_confirmed(before, after), *_months(before, after), *_invoices(before, after)]


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
