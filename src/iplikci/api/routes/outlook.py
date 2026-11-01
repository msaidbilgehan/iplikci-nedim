"""The regular payments, the calendar and the cash-flow forecast (F08, F09), for the Subscriptions and Calendar
screens: the analysis the service keeps, the days ahead worked out as of today. Amounts are minor units with their
currency; money in or out is said in words, not by a sign (architecture §16)."""

from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...app import outlook
from ...app.analysis import Analysis
from ...app.outlook import (
    AccountForecast,
    Certainty,
    Due,
    Installment,
    Necessity,
    PaymentKind,
    SeriesPeriod,
    SeriesStatus,
    SeriesView,
    Spread,
    TransactionKind,
)
from ...app.workspace import Busy
from ..context import Context, context_of
from ..guard import Principal
from ..models import AccountRefOut, MoneyOut
from ..problems import Problem
from .deps import only

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])


class PaymentOut(BaseModel):
    """A row a series rests on, and the document it is printed in."""

    fingerprint: str
    day: date
    amount: MoneyOut
    document: str
    certainty: Certainty


class PriceChangeOut(BaseModel):
    before: MoneyOut
    after: MoneyOut
    since: date  # the first payment at the new price


class SeriesOut(BaseModel):
    id: str  # the calendar's items name the series they continue by it
    payee: str  # the payer, for regular income
    period: SeriesPeriod
    status: SeriesStatus
    note: str  # what the status means here; "" when nothing needs saying
    category: str
    necessity: Necessity | None
    kind: TransactionKind
    account: AccountRefOut  # where it was last paid from (income: into)
    amount: MoneyOut  # the next payment expected: per month for a monthly series, per period for a periodic one
    last_day: date
    last_amount: MoneyOut
    next_day: date | None  # a running series' next payment; a past day when the documents end before it came
    price_change: PriceChangeOut | None
    listed: bool  # on the list of regular payments: running, or a commitment that ended within the window
    payments: list[PaymentOut]


class InstallmentOut(BaseModel):
    """A card purchase in installments with some still to come: the card's newest statement billed `number`."""

    card: AccountRefOut
    title: str
    number: int
    count: int
    amount: MoneyOut  # one installment
    left: int
    remaining: MoneyOut
    last_day: date  # the cut date of the statement that bills the last one
    fingerprint: str


class SubscriptionsOut(BaseModel):
    window: list[str]  # the complete months the statuses and the list look back on
    as_of: date  # the newest statement's end
    series: list[SeriesOut]  # monthly payments, then periodic ones
    income: list[SeriesOut]
    installments: list[InstallmentOut]


class CalendarItemOut(BaseModel):
    """A payment or an income expected on a day, with what the day and the amount rest on."""

    day: date
    kind: PaymentKind
    title: str
    account: AccountRefOut  # the account it leaves or enters; a card for its installments and its due date
    direction: Literal["out", "in"]
    amount: MoneyOut  # above zero; direction says which way the money goes
    minimum: MoneyOut | None  # a card due's minimum payment
    basis: str
    series: str  # the series it continues (SeriesOut.id); "" for other items
    fingerprints: list[str]  # the rows it rests on


class CalendarOut(BaseModel):
    today: date
    end: date  # the last day it looks at
    items: list[CalendarItemOut]


class BalanceOut(BaseModel):
    day: date
    balance: MoneyOut  # below zero: overdrawn


class StartOut(BaseModel):
    """Where an account's forecast starts: the newest balance a document prints, moved by the evidence after it."""

    balance: MoneyOut
    stated: MoneyOut  # the balance the document printed
    day: date  # the day of that balance
    source: Literal["statement", "notice"]
    moves: int  # receipt and notice rows after it, counted in the balance
    through: date  # the newest day the balance knows of


class SpreadOut(BaseModel):
    """Money out tied to no day: the median month of the complete months named, spread over each month's days."""

    monthly: MoneyOut
    months: list[str]
    after: date | None  # spread only after this day


class AccountForecastOut(BaseModel):
    account: AccountRefOut
    start: StartOut
    end_balance: MoneyOut
    lowest: BalanceOut
    negative: BalanceOut | None  # the first day below zero
    spend: SpreadOut | None  # money out outside the series, card payments apart
    cards: SpreadOut | None  # card payments beyond the due dates known
    interest: MoneyOut | None  # overdraft interest, only at a rate a document prints
    items: list[CalendarItemOut]  # as counted: a card due at the share the user pays
    days: list[BalanceOut]  # each day's closing balance, from today
    notes: list[str]  # what it assumes, with its windows and numbers


class SkippedOut(BaseModel):
    account: AccountRefOut
    reason: str


class ForecastOut(BaseModel):
    label: str  # "tahmin": always an estimate
    today: date
    end: date
    accounts: list[AccountForecastOut]
    elsewhere: list[CalendarItemOut]  # items no account's forecast takes: paid by card, or from an unknown account
    skipped: list[SkippedOut]  # accounts without a forecast, and why
    notes: list[str]


def _analysis(context: Context) -> Analysis:
    try:
        return context.analysis.get()
    except Busy as exc:
        raise Problem(503, "busy", str(exc)) from exc


def _money(value: Decimal) -> MoneyOut:
    return MoneyOut(minor=outlook.minor(value), currency="TRY")


def _account(account: str, labels: dict[str, str]) -> AccountRefOut:
    return AccountRefOut(id=account, label=labels.get(account, account))


def _series(view: SeriesView, labels: dict[str, str]) -> SeriesOut:
    change = view.price_change
    return SeriesOut(
        id=view.id,
        payee=view.payee,
        period=view.period,
        status=view.status,
        note=view.note,
        category=view.category,
        necessity=view.necessity,
        kind=view.kind,
        account=_account(view.account, labels),
        amount=_money(view.amount),
        last_day=view.last_day,
        last_amount=_money(view.last_amount),
        next_day=view.next_day,
        price_change=(
            PriceChangeOut(before=_money(change.before), after=_money(change.after), since=change.since)
            if change
            else None
        ),
        listed=view.listed,
        payments=[
            PaymentOut(
                fingerprint=r.fingerprint,
                day=r.day,
                amount=_money(abs(r.amount)),
                document=r.document,
                certainty=r.certainty,
            )
            for r in view.rows
        ],
    )


def _installment(i: Installment, labels: dict[str, str]) -> InstallmentOut:
    return InstallmentOut(
        card=_account(i.account, labels),
        title=i.title,
        number=i.number,
        count=i.count,
        amount=_money(i.amount),
        left=i.left,
        remaining=_money(i.remaining),
        last_day=i.last,
        fingerprint=i.row,
    )


def _item(item: Due, labels: dict[str, str]) -> CalendarItemOut:
    return CalendarItemOut(
        day=item.day,
        kind=item.kind,
        title=item.title,
        account=_account(item.account, labels),
        direction="in" if item.amount < 0 else "out",
        amount=_money(abs(item.amount)),
        minimum=_money(item.minimum) if item.minimum is not None else None,
        basis=item.basis,
        series=item.series,
        fingerprints=list(item.rows),
    )


def _spread(spread: Spread | None) -> SpreadOut | None:
    if spread is None:
        return None
    return SpreadOut(monthly=_money(spread.monthly), months=list(spread.months), after=spread.after)


def _balance(point: tuple[date, Decimal]) -> BalanceOut:
    return BalanceOut(day=point[0], balance=_money(point[1]))


def _forecast(found: AccountForecast, labels: dict[str, str]) -> AccountForecastOut:
    start = found.start
    return AccountForecastOut(
        account=_account(found.account, labels),
        start=StartOut(
            balance=_money(start.balance),
            stated=_money(start.stated),
            day=start.on,
            source="notice" if start.notice else "statement",
            moves=start.moves,
            through=start.through,
        ),
        end_balance=_money(found.end),
        lowest=_balance(found.lowest),
        negative=_balance(found.negative) if found.negative else None,
        spend=_spread(found.spend),
        cards=_spread(found.cards),
        interest=_money(found.interest) if found.interest is not None else None,
        items=[_item(item, labels) for item in found.items],
        days=[_balance(point) for point in found.days],
        notes=found.notes,
    )


@router.get("/api/subscriptions")
def subscriptions(request: Request) -> SubscriptionsOut:
    """The monthly and periodic payments with their statuses and next payments, the regular income and the card
    purchases with installments still to come (F08)."""
    found = outlook.subscriptions(_analysis(context_of(request)))
    labels = found.labels
    return SubscriptionsOut(
        window=found.window,
        as_of=found.as_of,
        series=[_series(view, labels) for view in found.series],
        income=[_series(view, labels) for view in found.income],
        installments=[_installment(i, labels) for i in found.installments],
    )


@router.get("/api/calendar")
def calendar(request: Request) -> CalendarOut:
    """What is expected from today on, for the next 60 days, by day (F09)."""
    context = context_of(request)
    found = outlook.calendar(_analysis(context), context.today())
    return CalendarOut(today=found.today, end=found.end, items=[_item(item, found.labels) for item in found.items])


@router.get("/api/forecast")
def forecast(request: Request) -> ForecastOut:
    """Each bank account's balance day by day from today on, for the next 60 days: an estimate (F09)."""
    context = context_of(request)
    found = outlook.cash_flow(_analysis(context), context.today())
    result, labels = found.forecast, found.labels
    return ForecastOut(
        label=result.label,
        today=result.today,
        end=result.end,
        accounts=[_forecast(account, labels) for account in result.accounts],
        elsewhere=[_item(item, labels) for item in result.elsewhere],
        skipped=[SkippedOut(account=_account(account, labels), reason=why) for account, why in result.skipped],
        notes=result.notes,
    )
