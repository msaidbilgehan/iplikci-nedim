"""The dashboard (F06) for the Pano screen: the net worth, this month against the typical month, the payments due
within a week, the open alerts, the last seven months' closing, how fresh each account's documents are and how much
there is to see to. Every card says what it shows in one Turkish sentence (`say`, the plain view's comment) and where
it leads (`link`). Amounts are minor units with their currency (architecture §16)."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...app import dashboard
from ...app.analysis import Analysis, account_labels
from ...app.dashboard import AlertKind, AlertLevel, MonthStatus, TodoKind
from ...app.links import Link
from ...app.now import Certainty, RateSource
from ...app.workspace import Busy
from ..context import Context, context_of
from ..guard import Principal
from ..models import AccountRefOut, LinkOut, MoneyOut, PaceOut, account_ref, link_out, money, pace_out
from ..problems import Problem
from .accounts import FreshnessOut, freshness_out
from .deps import only
from .feed import UnknownOut
from .outlook import CalendarItemOut, calendar_item

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])


class PartOut(BaseModel):
    """An account's share of the net worth."""

    account: AccountRefOut
    value: MoneyOut  # in TL; below zero for a debt (a card's, an overdraft)
    certainty: Certainty


class InCurrencyOut(BaseModel):
    """The net worth in another unit: at the providers' newest selling rate (what buying it would cost), else at the
    newest rate the documents print."""

    currency: str  # EUR, USD, or GR: grams of gold
    amount: MoneyOut | None  # null without a rate
    rate: str | None  # TL for one unit, as a decimal number ("34.5012")
    rate_day: date | None  # the day it is of: the providers' bulletin, or the row that printed it
    note: str  # where the rate comes from, or why there is none
    rate_source: RateSource | None = None  # null without a rate


class NetWorthOut(BaseModel):
    """The balances of "Şu an" and the cards' debts, added up: the assets less the debts, of what has a TL value."""

    total: MoneyOut
    assets: MoneyOut
    debts: MoneyOut  # above zero
    certainty: Certainty  # provisional when a part is
    parts: list[PartOut]  # the largest first
    left_out: list[UnknownOut]  # the accounts without a TL value (gold has no price in the documents), and why
    currencies: list[InCurrencyOut]  # EUR, USD, gram gold
    note: str  # what it rests on
    say: str
    link: LinkOut  # the accounts


class ThisMonthOut(BaseModel):
    """The month's spending so far against the typical month (complete months only)."""

    pace: PaceOut
    say: str
    link: LinkOut  # the month's page


class DueSoonOut(BaseModel):
    """The calendar's payments within a week that the user sees to: a card's due date, a bill, a loan's installment, a
    regular or periodic payment made from an account (one a card pays comes with its statement)."""

    items: list[CalendarItemOut]  # by day
    total: MoneyOut
    end: date  # the last day looked at
    say: str
    link: LinkOut  # the calendar


class AlertOut(BaseModel):
    """Something that asks for attention now."""

    kind: AlertKind
    level: AlertLevel
    title: str
    text: str  # what is wrong and what to do, in Turkish, with its numbers
    count: int  # how many things it stands for: documents, accounts
    account: AccountRefOut | None  # the account it concerns
    link: LinkOut


class OpenAlertsOut(BaseModel):
    items: list[AlertOut]  # the critical first
    say: str
    link: LinkOut  # the notifications


class WaitingOut(BaseModel):
    account: AccountRefOut
    waiting_for: str  # the document that closes the account's month, in a few Turkish words


class ClosingOut(BaseModel):
    """A month's closing (F11)."""

    month: str  # YYYY-MM
    status: MonthStatus
    summary: str  # the closing in one Turkish sentence, after the status' label
    expense: MoneyOut
    income: MoneyOut | None  # null when no account list covers enough of the month to know it
    left: MoneyOut | None  # the income less what went out; below zero when more went out
    # Where the income comes from, or why it may be short ("gelir eksik olabilir: …"): a month a list covers only in
    # part has an income, but not a certain one.
    income_note: str
    provisional: int  # rows only receipts and notices show
    unmatched: int  # receipt and notice rows the statements covering their days do not show
    waiting: list[WaitingOut]  # the accounts that hold the month open
    link: LinkOut


class LastMonthsOut(BaseModel):
    months: list[ClosingOut]  # the current month and the six before it with documents, the oldest first
    say: str
    link: LinkOut  # the oldest ended month still open, else the newest ended one


class DataFreshnessOut(BaseModel):
    accounts: list[FreshnessOut]  # the open accounts, the most behind first
    say: str
    link: LinkOut  # the accounts


class TodoCountOut(BaseModel):
    kind: TodoKind
    count: int  # the to-do list's items of the kind
    link: LinkOut


class TodoSummaryOut(BaseModel):
    kinds: list[TodoCountOut]  # only the kinds with something to see to, in the list's order
    total: int  # the items on the to-do list, as /api/todos counts them
    say: str
    link: LinkOut  # the to-do list


class DashboardOut(BaseModel):
    today: date
    as_of: date  # the newest statement's end
    net_worth: NetWorthOut
    month: ThisMonthOut
    due: DueSoonOut
    alerts: OpenAlertsOut
    closing: LastMonthsOut
    freshness: DataFreshnessOut
    todo: TodoSummaryOut


def _analysis(context: Context) -> Analysis:
    try:
        return context.analysis.get()
    except Busy as exc:
        raise Problem(503, "busy", str(exc)) from exc


def _link(found: Link) -> LinkOut:
    out = link_out(found)
    assert out is not None  # link_out gives None only for no link, and every card has one
    return out


def _net_worth(found: dashboard.NetWorth, labels: dict[str, str]) -> NetWorthOut:
    return NetWorthOut(
        total=money(found.total),
        assets=money(found.assets),
        debts=money(found.debts),
        certainty=found.certainty,
        parts=[
            PartOut(account=account_ref(p.account, labels), value=money(p.value), certainty=p.certainty)
            for p in found.parts
        ],
        left_out=[UnknownOut(account=account_ref(u.account, labels), reason=u.reason) for u in found.left_out],
        currencies=[
            InCurrencyOut(
                currency=c.currency,
                amount=None if c.amount is None else money(c.amount, c.currency),
                rate=None if c.rate is None else str(c.rate),
                rate_day=c.rate_day,
                note=c.note,
                rate_source=c.rate_source,
            )
            for c in found.currencies
        ],
        note=found.note,
        say=found.say,
        link=_link(found.link),
    )


def _alerts(found: dashboard.OpenAlerts, labels: dict[str, str]) -> OpenAlertsOut:
    return OpenAlertsOut(
        items=[
            AlertOut(
                kind=alert.kind,
                level=alert.level,
                title=alert.title,
                text=alert.text,
                count=alert.count,
                account=account_ref(alert.account, labels) if alert.account else None,
                link=_link(alert.link),
            )
            for alert in found.items
        ],
        say=found.say,
        link=_link(found.link),
    )


def _closing(c: dashboard.Closing, labels: dict[str, str]) -> ClosingOut:
    return ClosingOut(
        month=c.month,
        status=c.status,
        summary=c.summary,
        expense=money(c.expense),
        income=None if c.income is None else money(c.income),
        left=None if c.left is None else money(c.left),
        income_note=c.income_note,
        provisional=c.provisional,
        unmatched=c.unmatched,
        waiting=[WaitingOut(account=account_ref(a, labels), waiting_for=why) for a, why in c.waiting],
        link=_link(c.link),
    )


@router.get("/api/dashboard")
def dashboard_now(request: Request) -> DashboardOut:
    """The dashboard's cards as of today."""
    context = context_of(request)
    a = _analysis(context)
    found = dashboard.dashboard(context.ws, a, context.today())
    labels = account_labels(a)
    month, due, closing, fresh, todo = found.month, found.due, found.closing, found.freshness, found.todo
    return DashboardOut(
        today=found.today,
        as_of=found.as_of,
        net_worth=_net_worth(found.net_worth, labels),
        month=ThisMonthOut(pace=pace_out(month.pace), say=month.say, link=_link(month.link)),
        due=DueSoonOut(
            items=[calendar_item(item, labels) for item in due.items],
            total=money(due.total),
            end=due.end,
            say=due.say,
            link=_link(due.link),
        ),
        alerts=_alerts(found.alerts, labels),
        closing=LastMonthsOut(
            months=[_closing(c, labels) for c in closing.months], say=closing.say, link=_link(closing.link)
        ),
        freshness=DataFreshnessOut(
            accounts=[freshness_out(f, labels) for f in fresh.accounts], say=fresh.say, link=_link(fresh.link)
        ),
        todo=TodoSummaryOut(
            kinds=[TodoCountOut(kind=t.kind, count=t.count, link=_link(t.link)) for t in todo.kinds],
            total=todo.total,
            say=todo.say,
            link=_link(todo.link),
        ),
    )
