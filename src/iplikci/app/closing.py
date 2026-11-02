"""The month-end closing (F11) for the Ay sonu screen and the MCP server's month_end tool: the months with their
statuses, and one month in full: each account's closing and what it waits for, the totals against the month before
and the typical month, where the money went, the regular payments, the rows only receipts and notices show yet and
the receipts' rows no statement shows. The months' script-free pages (the MVP's) are the exports' (app.exports).

The months are closed on the day the screens compute from: the analysis' own closing when it was made on that day,
built again otherwise (month_end.build).
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .. import month_end
from ..domain.codes import Certainty, EvidenceStatus, MonthStatus, StatementCheck
from ..domain.models import Statement
from ..insights import shift
from ..month_end import ACCOUNT_STATUS, AccountClose, MonthEnd, Totals
from .analysis import Analysis
from .rows import Rows, RowView, certainty_of, view

# What the API names from here: the use cases, their records and the codes they carry.
__all__ = [
    "ACCOUNT_STATUS",
    "AccountClose",
    "Certainty",
    "EvidenceStatus",
    "MonthEnd",
    "MonthRows",
    "MonthStatus",
    "Regular",
    "StatementCheck",
    "Totals",
    "check_of",
    "month",
    "months",
    "rows_of",
    "shift",
]

MONTH = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class Regular:
    """A regular payment in a month: paid, or expected and not seen yet."""

    payee: str
    category: str
    paid: list[RowView]  # its payments this month
    expected: date | None  # the day it was expected, while it is not paid
    this_month: Decimal  # what was paid this month
    monthly: Decimal  # what it costs a month


@dataclass(frozen=True, slots=True)
class MonthRows:
    """The rows a month shows as rows."""

    big: list[RowView]  # its big one-off spending
    provisional: list[RowView]  # the rows only receipts and notices show yet: counted, provisional
    unmatched: list[RowView]  # the receipts' rows no statement covering their days shows: excluded
    regular: list[Regular]


def _closed(a: Analysis, today: date) -> list[MonthEnd]:
    return a.months if a.today == today else month_end.build(a.dataset, a.insights, today)


def months(a: Analysis, today: date) -> list[MonthEnd]:
    """The current month and the twelve before it, from the first month with any document; the newest first."""
    return list(reversed(_closed(a, today)))


def month(a: Analysis, month_: str, today: date) -> MonthEnd:
    """One month's closing, an older month's built on request. ValueError for what is not a YYYY-MM month."""
    if not MONTH.fullmatch(month_):
        raise ValueError(month_)
    found = next((m for m in _closed(a, today) if m.month == month_), None)
    if found is None:
        [found] = month_end.build(a.dataset, a.insights, today, months=[month_])
    return found


def check_of(s: Statement) -> StatementCheck:
    """A statement's own check, as the month-end page marks it (month_end.statement_check)."""
    style, _, _ = month_end.statement_check(s)
    return {"ok": StatementCheck.VERIFIED, "fail": StatementCheck.FAILED}.get(style, StatementCheck.NOTHING)


def rows_of(a: Analysis, me: MonthEnd) -> MonthRows:
    """A month's rows as the screens list them, each with its certainty: a receipt's row no statement shows is
    excluded, never counted."""
    found = Rows(a.dataset)
    unmatched = [
        view(line.txn, Certainty.EXCLUDED, found.currency(line.txn.account), counted=False) for line in me.unmatched
    ]
    regular = [
        Regular(
            payee=series.merchant,
            category=series.last.category,
            paid=[view(t, certainty_of(t)) for t in paid],
            expected=None if paid else expected,
            this_month=sum((abs(t.amount) for t in paid), ZERO),
            monthly=series.monthly,
        )
        for series, paid, expected in me.regular
    ]
    return MonthRows(
        [view(t, certainty_of(t)) for t in me.big],
        [view(t, certainty_of(t)) for t in me.provisional],
        unmatched,
        regular,
    )
