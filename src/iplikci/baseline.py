"""The verification baseline of a workspace, and how it moved since the last one.

Verification is the safety net (docs/domain/ledger.md): after a change to a reader or the analysis, fewer
verified statements, a new unreadable document or a closed month that reopens without new documents is a
regression to fix first. A baseline records what the documents verify to as on one day; comparing it with
the previous one shows what moved. The demo workspace's baseline is a golden file in the tests.
"""

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .analysis import RECEIPT_STATUS, Dataset
from .insights import month_name, month_of, shift
from .models import DEFAULT_EXPENSE_KINDS, Statement
from .month_end import CLOSED, MONTH_STATUS, MonthEnd
from .textutil import format_tr_amount

VERSION = 1
UNREADABLE = "hata"
DOCUMENT_STATUS = {
    "ekstre": "kart ekstresi",
    "hesap": "hesap dökümü",
    "dekont": "dekont",
    "atlandi": "kullanılmayan",
    "is": "şirket belgesi",
    UNREADABLE: "okunamadı",
}
_MONTHS = 12  # the expense total covers the month of the day and the eleven before it


def take(ds: Dataset, stats: dict, months: list[MonthEnd], day: date) -> dict:
    """The baseline of an analysis whose months were closed as on day."""
    cards = [s for s in ds.statements if not s.is_account]
    lists = [s for s in ds.statements if s.is_account]
    spent = dict.fromkeys((shift(month_of(day), -n) for n in range(_MONTHS - 1, -1, -1)), 0.0)
    for t in ds.transactions:
        month = month_of(t.date)
        if month in spent and t.kind in DEFAULT_EXPENSE_KINDS:
            spent[month] += t.amount
    return {
        "version": VERSION,
        "day": day.isoformat(),
        "documents": {
            "unique": stats["documents"],
            "duplicates": stats["duplicates"],
            "by_status": _counts(d.status for d in ds.documents),
            "unreadable": sorted(f"{d.name}: {d.detail}" for d in ds.documents if d.status == UNREADABLE),
        },
        "statements": {
            "cards": {"verified": sum(s.verified for s in cards), "total": len(cards)},
            "lists": {
                "verified": sum(s.verified for s in lists),
                "total": len(lists),
                "by_account_type": _counts(ds.accounts[s.account].type for s in lists),
            },
            "unverified": sorted(_unverified(ds, s) for s in ds.statements if not s.verified),
        },
        "receipt_rows": _counts(line.status for line in ds.receipts),
        "months": {me.month: me.status for me in months},
        "expenses": {"total": _money(sum(spent.values())), "by_month": {m: _money(v) for m, v in spent.items()}},
    }


def _counts(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _money(value: float) -> str:
    return f"{round(value, 2) + 0.0:.2f}"  # + 0.0 turns -0.0 into 0.0


def _unverified(ds: Dataset, s: Statement) -> str:
    detail = f"bakiye {s.checks_ok}/{s.checks_total}" if s.is_account else f"fark {_money(s.difference or 0.0)}"
    return f"{ds.accounts[s.account].label} {s.cut_date}: {detail} ({Path(s.source).name})"


@dataclass(frozen=True)
class Change:
    label: str
    before: object
    after: object
    regression: bool = False


def compare(before: dict, after: dict) -> list[Change]:
    """What moved between two baselines of the same workspace, regressions marked."""
    changes: list[Change] = []

    def note(label: str, old: object, new: object, regression: bool = False) -> None:
        if old != new:
            changes.append(Change(label, old, new, regression))

    old_docs, new_docs = before["documents"], after["documents"]
    note("Benzersiz belge", old_docs["unique"], new_docs["unique"])
    note("Kopya", old_docs["duplicates"], new_docs["duplicates"])
    for status in sorted(old_docs["by_status"].keys() | new_docs["by_status"].keys()):
        old, new = old_docs["by_status"].get(status, 0), new_docs["by_status"].get(status, 0)
        note(f"Belge: {DOCUMENT_STATUS.get(status, status)}", old, new, regression=status == UNREADABLE and new > old)
    for name in sorted(set(new_docs["unreadable"]) - set(old_docs["unreadable"])):
        note("Yeni okunamayan belge", None, name, regression=True)
    for kind, label in (("cards", "Kart ekstreleri"), ("lists", "Hesap dökümleri")):
        old, new = before["statements"][kind], after["statements"][kind]
        note(f"{label}: doğrulanan", old["verified"], new["verified"], regression=new["verified"] < old["verified"])
        note(f"{label}: toplam", old["total"], new["total"])
    for line in sorted(set(after["statements"]["unverified"]) - set(before["statements"]["unverified"])):
        note("Doğrulanamayan ekstre", None, line, regression=True)
    old_rows, new_rows = before["receipt_rows"], after["receipt_rows"]
    for status in sorted(old_rows.keys() | new_rows.keys()):
        note(f"Dekont satırı: {RECEIPT_STATUS.get(status, status)}", old_rows.get(status, 0), new_rows.get(status, 0))
    # A closed month reopens rightly only when new documents came (a new account's lists, a late statement).
    more_documents = new_docs["unique"] > old_docs["unique"]
    for month in sorted(before["months"].keys() & after["months"].keys()):
        old, new = before["months"][month], after["months"][month]
        reopened = old == CLOSED and new != CLOSED
        note(month_name(month), _status(old), _status(new), regression=reopened and not more_documents)
    note("Son 12 ay gider", before["expenses"]["total"], after["expenses"]["total"])
    return changes


def _status(code: str) -> str:
    return MONTH_STATUS.get(code, code)


def describe(baseline: dict) -> list[str]:
    """The baseline in a few lines of Turkish, for the terminal."""
    docs, statements = baseline["documents"], baseline["statements"]
    by_status = " · ".join(f"{DOCUMENT_STATUS.get(k, k)} {v}" for k, v in docs["by_status"].items())
    cards, lists = statements["cards"], statements["lists"]
    rows = " · ".join(f"{RECEIPT_STATUS.get(k, k).lower()} {v}" for k, v in baseline["receipt_rows"].items())
    months = " · ".join(f"{m} {_status(s)}" for m, s in baseline["months"].items())
    lines = [
        f"Doğrulama tabanı ({date.fromisoformat(baseline['day']):%d.%m.%Y})",
        f"  Belgeler: {docs['unique']} benzersiz, {docs['duplicates']} kopya"
        + (f" — {by_status}" if by_status else ""),
        (
            f"  Kart ekstreleri: {cards['verified']}/{cards['total']} doğrulandı · "
            f"hesap dökümleri: {lists['verified']}/{lists['total']} doğrulandı"
        ),
        f"  Dekont satırları: {rows or 'yok'}",
        f"  Aylar: {months or 'yok'}",
        f"  Son 12 ay gider: {format_tr_amount(float(baseline['expenses']['total']))} TL",
    ]
    lines += [f"  ! doğrulanamadı: {line}" for line in statements["unverified"]]
    lines += [f"  ! okunamadı: {line}" for line in docs["unreadable"]]
    return lines


def load(path: Path) -> dict | None:
    """The saved baseline, or None when there is none yet (or it was written by another version)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    return data if isinstance(data, dict) and data.get("version") == VERSION else None


def save(path: Path, baseline: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(dumps(baseline), encoding="utf-8")
    tmp.replace(path)


def dumps(baseline: dict) -> str:
    return json.dumps(baseline, ensure_ascii=False, indent=2) + "\n"
