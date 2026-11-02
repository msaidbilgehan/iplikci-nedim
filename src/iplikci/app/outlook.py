"""The regular payments, the next 60 days and the balances ahead (F08, F09): what /api/subscriptions, /api/calendar
and /api/forecast answer and the MCP tools of the same names tell. They read the analysis the service keeps
(analysis.Current) and work the days ahead out on request, as of the day asked: the analysis is made again only when
the documents change, while the days ahead move every day."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..analysis import Dataset
from ..domain.codes import AccountType, Certainty, Necessity, PaymentKind, SeriesPeriod, SeriesStatus, TransactionKind
from ..domain.models import TRY, Statement, Transaction
from ..domain.money import Money, round_half_up
from ..domain.text import fold
from ..forecast import AccountForecast, Forecast, Spread, Start, counted_from, forecast
from ..insights import V1_STATUS, PeriodicSeries, Series, listed, month_name, paid_after
from ..upcoming import (
    CardDue,
    Due,
    Installment,
    expected_amount,
    horizon_end,
    income_amount,
    installments_left,
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
    listed: bool  # on the list of regular payments: running, or a commitment that ended within the window
    rows: tuple[Row, ...]


@dataclass(frozen=True, slots=True)
class Subscriptions:
    window: list[str]  # the complete months the statuses and the list look back on
    as_of: date  # the newest statement's end
    series: list[SeriesView]  # the monthly payments, then the periodic ones; running and larger ones first
    income: list[SeriesView]
    installments: list[Installment]
    labels: dict[str, str]  # the accounts' labels by id


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
    """docs/domain/interpretation.md: an ended required bill reads "not in the documents"; a cancelled one names the
    month the user wrote, and a payment after it is a warning."""
    status = V1_STATUS[s.status]
    cancelled = ds.ended.get(fold(s.merchant))
    if status == SeriesStatus.ENDED and s.last.necessity == Necessity.REQUIRED:
        return "Belgelerde yok: belgesi olmayan bir hesaptan ödeniyor olabilir."
    if status == SeriesStatus.CANCELLED and cancelled:
        return f"Kişisel kurallarınızda son ödeme ayı {month_name(cancelled)}."
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
        listed=s.running if income else listed(s, ds, window),
        rows=tuple(_row(t) for t in s.payments),
    )


def subscriptions(a: Analysis) -> Subscriptions:
    """The monthly and periodic series with their statuses and next payments, the regular income, and the card
    purchases with installments still to come (F08)."""
    ds, ins = a.dataset, a.insights
    window = ins.timeline.window
    series = [_view(s, ds, window) for s in [*ins.series, *ins.periodic]]
    income = [_view(s, ds, window, income=True) for s in ins.income]
    return Subscriptions(window, ins.timeline.as_of, series, income, installments_left(ds), _labels(ds))


def card_dues(ds: Dataset) -> list[CardDue]:
    """The credit cards' due dates and what their newest statements still ask: the statement's balance and its
    minimum payment less what was paid on the card since the cut (insights.paid_after), which the bank accounts'
    balances already count. A statement that prints no due date, or is paid off, asks nothing."""
    newest: dict[str, Statement] = {}
    for s in ds.statements:
        account = ds.accounts.get(s.account)
        if s.is_account or s.currency != TRY or account is None or account.type != AccountType.CREDIT_CARD:
            continue
        if s.account not in newest or s.cut_date > newest[s.account].cut_date:
            newest[s.account] = s
    dues: list[CardDue] = []
    for card, s in sorted(newest.items()):
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
