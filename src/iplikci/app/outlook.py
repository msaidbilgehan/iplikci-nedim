"""The regular payments, the next 60 days and the balances ahead (F08, F09): what /api/subscriptions, /api/calendar
and /api/forecast answer and the MCP tools of the same names tell. They read the analysis the service keeps
(analysis.Current) and work the days ahead out on request, as of the day asked: the analysis is made again only when
the documents change, while the days ahead move every day."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from ..analysis import Dataset, payments
from ..domain.codes import (
    CARD_TYPES,
    AccountType,
    Certainty,
    Necessity,
    PaymentKind,
    SeriesPeriod,
    SeriesStatus,
    TransactionKind,
)
from ..domain.models import TRY, DeclaredIncome, Transaction
from ..domain.money import Money, round_half_up
from ..domain.text import fold
from ..forecast import AccountForecast, Forecast, Spread, Start, counted_from, forecast
from ..insights import (
    V1_STATUS,
    PeriodicSeries,
    Series,
    brought,
    listed,
    month_name,
    month_of,
    paid_after,
    row_currency,
)
from ..upcoming import (
    CardDue,
    Due,
    Installment,
    expected_amount,
    horizon_end,
    income_amount,
    installments_left,
    newest_statements,
    next_day,
    series_id,
    upcoming,
)
from .analysis import Analysis

# What the API and the MCP tools name from here: the codes their answers carry and the records they are made from.
__all__ = [
    "AccountForecast",
    "Calendar",
    "CashFlow",
    "Certainty",
    "Due",
    "Forecast",
    "Installment",
    "Necessity",
    "PaymentKind",
    "PriceChange",
    "Row",
    "SeriesPeriod",
    "SeriesStatus",
    "SeriesView",
    "Spread",
    "Start",
    "Subscriptions",
    "TransactionKind",
    "calendar",
    "card_dues",
    "cash_flow",
    "minor",
    "subscriptions",
]


@dataclass(frozen=True, slots=True)
class Row:
    """A row a series rests on, and the document it is printed in."""

    fingerprint: str
    day: date
    amount: Decimal  # in TL as the ledger counts it: money out above zero, money in below
    document: str  # the file's name, as its reader saw it
    sha256: str  # the very document it is printed in, for the viewer
    certainty: Certainty


@dataclass(frozen=True, slots=True)
class PriceChange:
    before: Decimal
    after: Decimal
    since: date  # the first payment at the new price


@dataclass(frozen=True, slots=True)
class SeriesView:
    """A regular, periodic or income series as the Subscriptions screen shows it."""

    id: str  # its first payment's fingerprint (upcoming.series_id), as the calendar's items name it
    payee: str  # the payer, for an income series
    period: SeriesPeriod
    status: SeriesStatus
    note: str  # what the status means here, in Turkish; "" when nothing needs saying
    category: str
    necessity: Necessity | None
    kind: TransactionKind
    account: str  # the account it was last paid from (an income series': into)
    amount: Decimal  # the next payment expected: per month for a monthly series, per period for a periodic one
    last_day: date
    last_amount: Decimal
    next_day: date | None  # a running series' next payment; a past day when the documents end before it came
    price_change: PriceChange | None
    listed: bool  # on the list: running, or a commitment that ended or an income the user ended within the window
    rows: tuple[Row, ...]
    declared: DeclaredIncome | None = None  # an income the user's rules say comes every month (`_düzenli_gelir`)


@dataclass(frozen=True, slots=True)
class IncomeCandidate:
    """A payer whose income came lately and makes no running series: what declaring it as monthly would start from."""

    payee: str
    account: str  # where its newest income came
    currency: str  # its newest income's
    month: str  # the newest month it came in, YYYY-MM
    parts: tuple[Decimal, ...]  # that month's payments in currency, oldest first
    day: int  # the day of the month its largest payment of that month came on
    total: Decimal  # in TL, all it brought within CANDIDATE_DAYS


@dataclass(frozen=True, slots=True)
class Subscriptions:
    window: list[str]  # the complete months the statuses and the list look back on
    as_of: date  # the newest statement's end
    series: list[SeriesView]  # the monthly payments, then the periodic ones; running and larger ones first
    income: list[SeriesView]
    installments: list[Installment]
    labels: dict[str, str]  # the accounts' labels by id
    candidates: list[IncomeCandidate] = field(default_factory=list[IncomeCandidate])  # the most it brought first


@dataclass(frozen=True, slots=True)
class Calendar:
    today: date
    end: date  # the last day it looks at
    items: list[Due]
    labels: dict[str, str]


@dataclass(frozen=True, slots=True)
class CashFlow:
    forecast: Forecast
    labels: dict[str, str]


def minor(value: Decimal, currency: str = TRY) -> int:
    """An amount in its currency's smallest unit, as the API carries it (ADR-0006), rounded half up to it."""
    return Money(round_half_up(value), currency).to_minor()


def _labels(ds: Dataset) -> dict[str, str]:
    return {account.id: account.label for account in ds.accounts.values()}


def _row(t: Transaction) -> Row:
    certainty = Certainty.PROVISIONAL if t.provisional else Certainty.CONFIRMED
    return Row(t.fingerprint, t.date, t.amount, t.source, t.document, certainty)


def _note(s: Series, ds: Dataset) -> str:
    """docs/domain/interpretation.md: an ended required bill reads "not in the documents"; one the user ended names
    the month they wrote, a payment's or an income's last, whose payment may still be to come; a payment after it is a
    warning."""
    status = V1_STATUS[s.status]
    cancelled = ds.ended.get(fold(s.merchant))
    last = "son geliş ayı" if s.last.kind == TransactionKind.INCOME else "son ödeme ayı"
    if status == SeriesStatus.ENDED and s.last.necessity == Necessity.REQUIRED:
        return "Belgelerde yok: belgesi olmayan bir hesaptan ödeniyor olabilir."
    if status == SeriesStatus.ACTIVE and cancelled:
        return f"Kişisel kurallarınızda {last} {month_name(cancelled)}: o ayınki bekleniyor, sonrası beklenmiyor."
    if status == SeriesStatus.CANCELLED and cancelled:
        return f"Kişisel kurallarınızda {last} {month_name(cancelled)}."
    if status == SeriesStatus.PAID_AFTER_CANCEL and cancelled:
        return (
            f"Kişisel kurallarınızda son ödeme ayı {month_name(cancelled)}, ama sonrasında da ödendi: aboneliği kontrol "
            "edin."
        )
    return ""


def _view(s: Series, ds: Dataset, window: list[str], income: bool = False) -> SeriesView:
    change = s.price_change()
    return SeriesView(
        id=series_id(s),
        payee=s.merchant,
        period=s.period if isinstance(s, PeriodicSeries) else SeriesPeriod.MONTH,
        status=V1_STATUS[s.status],
        note=_note(s, ds),
        category=s.last.category,
        necessity=s.last.necessity,
        kind=s.last.kind,
        account=s.last.account,
        amount=income_amount(s) if income else expected_amount(s),
        last_day=s.last.date,
        last_amount=abs(s.last.amount),
        next_day=next_day(s) if s.running else None,
        price_change=PriceChange(change[0], change[1], change[2]) if change else None,
        listed=listed(s, ds, window),
        rows=tuple(_row(t) for t in s.payments),
        declared=s.declared,
    )


def subscriptions(a: Analysis) -> Subscriptions:
    """The monthly and periodic series with their statuses and next payments, the regular income, and the card
    purchases with installments still to come (F08)."""
    ds, ins = a.dataset, a.insights
    window = ins.timeline.window
    series = [_view(s, ds, window) for s in [*ins.series, *ins.periodic]]
    income = [_view(s, ds, window, income=True) for s in ins.income]
    candidates = income_candidates(ds, ins.income, ins.timeline.as_of)
    return Subscriptions(window, ins.timeline.as_of, series, income, installments_left(ds), _labels(ds), candidates)


CANDIDATE_DAYS = 92  # how far back an income counts as recent enough to declare as monthly
# Accounts no salary is paid into: a deposit's, gold's and a brokerage account's income is interest, a dividend or a
# trade, which the forecast counts its own way or not at all.
_NOT_PAID_INTO = frozenset({AccountType.DEPOSIT, AccountType.GOLD, AccountType.BROKERAGE, *CARD_TYPES})


def income_candidates(ds: Dataset, income: Iterable[Series], as_of: date) -> list[IncomeCandidate]:
    """The payers whose income came within CANDIDATE_DAYS of as_of and makes no running series, none the user declared
    or ended: a salary that just started, whose documents cannot make it a series for three months. Each with its
    newest month's payments in its currency, the parts a salary paid in two comes in; the most it brought first."""
    counted = {fold(s.merchant) for s in income if s.running} | set(ds.declared) | set(ds.ended)
    since = as_of - timedelta(days=CANDIDATE_DAYS)
    by_payee: dict[str, list[Transaction]] = defaultdict(list)
    for t in payments(ds):
        account = ds.accounts.get(t.account)
        if (
            t.kind != TransactionKind.INCOME
            or t.amount >= 0
            or not t.merchant
            or t.date < since
            or account is None
            or account.type in _NOT_PAID_INTO
            or fold(t.merchant) in counted
        ):
            continue
        by_payee[fold(t.merchant)].append(t)
    found: list[IncomeCandidate] = []
    for rows in by_payee.values():
        rows.sort(key=lambda t: t.date)
        newest = rows[-1]
        currency, month = row_currency(newest), month_of(newest.date)
        parts = [(t, got) for t in rows if month_of(t.date) == month and (got := brought(t, currency)) is not None]
        largest = max(parts, key=lambda part: part[1])[0]
        total = -sum((t.amount for t in rows), Decimal(0))
        found.append(
            IncomeCandidate(
                newest.merchant,
                newest.account,
                currency,
                month,
                tuple(got for _, got in parts),
                largest.date.day,
                total,
            )
        )
    return sorted(found, key=lambda c: (-c.total, fold(c.payee)))


def card_dues(ds: Dataset) -> list[CardDue]:
    """The credit cards' due dates and what their newest statements still ask: the statement's balance and its
    minimum payment less what was paid on the card since the cut (insights.paid_after), which the bank accounts'
    balances already count. A statement that prints no due date, or is paid off, asks nothing."""
    dues: list[CardDue] = []
    for card, s in sorted(newest_statements(ds).items()):
        if s.due_date is None or s.total is None:
            continue
        paid = paid_after(ds, card, s.cut_date)
        left = s.total - paid
        if left > 0:
            minimum = None if s.minimum_payment is None else max(Decimal(0), s.minimum_payment - paid)
            dues.append(CardDue(card, s.due_date, left, minimum, paid))
    return dues


def calendar(a: Analysis, today: date) -> Calendar:
    """Every payment and income expected from today on, for the next 60 days (F09)."""
    items = upcoming(a.dataset, a.insights, today, card_dues(a.dataset))
    return Calendar(today, horizon_end(today), items, _labels(a.dataset))


def cash_flow(a: Analysis, today: date) -> CashFlow:
    """Each bank account's balance day by day from today on, for the next 60 days, with the calendar's items (from
    the days before today the documents do not reach yet, too): an estimate (F09)."""
    since = counted_from(a.dataset, today)
    items = upcoming(a.dataset, a.insights, today, card_dues(a.dataset), since=since)
    return CashFlow(forecast(a.dataset, a.insights, today, items), _labels(a.dataset))
