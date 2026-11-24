"""How far each account's documents reach, which accounts are closed and which months their statements cover (F05,
F06, F07, F10). An account whose documents stopped more than 180 days before the newest document is closed or no
longer followed, and so is one the user says they closed (Dataset.closed): the screens list it apart and leave it out
of every total (F07)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from ..analysis import ACTIVE_DAYS, Dataset
from ..domain.text import fold
from ..insights import span


@dataclass(frozen=True, slots=True)
class Cover:
    """How much of each month an account's statements and account lists cover."""

    account: str
    closed: bool
    shares: tuple[float, ...]  # one per month of the coverage: the share of its days covered, 0 to 1


@dataclass(frozen=True, slots=True)
class Coverage:
    months: tuple[str, ...]  # from the first month any account's documents cover to the last
    accounts: list[Cover]  # with a statement or an account list (receipts cover no month): the open first, by name


def last_seen(ds: Dataset) -> dict[str, date]:
    """Each account's newest day its documents reach: a statement's or a list's last day, a receipt's or a bank
    notice's row."""
    seen: dict[str, date] = {}
    for s in ds.statements:
        seen[s.account] = max(seen.get(s.account, s.cut_date), s.cut_date)
    for line in ds.receipts:
        account, day = line.txn.account, line.txn.date
        seen[account] = max(seen.get(account, day), day)
    return seen


def closed(seen: Mapping[str, date], marked: Mapping[str, date]) -> set[str]:
    """The accounts whose documents stopped more than ACTIVE_DAYS before the newest document, and those the user marked
    closed (marked: Dataset.closed)."""
    newest = max(seen.values(), default=None)
    stopped = {account for account, day in seen.items() if newest is not None and (newest - day).days > ACTIVE_DAYS}
    return stopped | set(marked)


def coverage(ds: Dataset, labels: Mapping[str, str]) -> Coverage:
    """Each account's months as its statements and account lists cover them: the MVP report's coverage grid. A month
    outside an account's first and last statement is not covered (0). The accounts come by the names the screens show
    (labels), the closed ones after the open."""
    covered = {account: months for account, months in ds.coverage.items() if months}
    if not covered:
        return Coverage((), [])
    months = tuple(span(min(min(m) for m in covered.values()), max(max(m) for m in covered.values())))
    gone = closed(last_seen(ds), ds.closed)
    found = [
        Cover(account, account in gone, tuple(cover.get(m, 0.0) for m in months)) for account, cover in covered.items()
    ]
    return Coverage(months, sorted(found, key=lambda c: (c.closed, fold(labels.get(c.account, c.account)))))
