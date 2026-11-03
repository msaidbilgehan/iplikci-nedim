"""The foreign currency and assets screen (F12) for Döviz: the TL rates, the net worth in TL, EUR, USD and gram gold
with each holding's value and, where the documents tell, its cost, how the assets spread over currencies, the spread
the banks' rates cost and the income that comes in a foreign currency. The rates are the providers' as stored (TCMB,
else ECB), else the documents' own; nothing is fetched here. Amounts are minor units with their currency; rates are
decimal numbers as text (architecture §16)."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...app import holdings
from ...app.analysis import Analysis, account_labels
from ...app.holdings import AccountGroup, Certainty, RateSource, TradeSide
from ...app.workspace import Busy
from ..context import Context, context_of
from ..guard import Principal
from ..models import AccountRefOut, MoneyOut, account_ref, money
from ..problems import Problem
from .dashboard import InCurrencyOut, PartOut
from .deps import only
from .feed import UnknownOut

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])


class FxRateOut(BaseModel):
    day: date  # the day it is of: the providers' bulletin, or the row that printed it
    rate: str  # TL for one unit, as a decimal number ("36.50"): a provider's buying rate, or a document's own
    source: RateSource
    # A provider's two sides, assets valued at buying and debts at selling; null for a document's, one trade's rate.
    buying: str | None = None
    selling: str | None = None


class FxCurrencyOut(BaseModel):
    currency: str
    newest: FxRateOut  # the one the screens value with: the providers' newest, else the documents' newest
    history: list[FxRateOut]  # the providers' quotes of the last 90 days and every document rate, the oldest first


class FxOut(BaseModel):
    currencies: list[FxCurrencyOut]  # by currency code
    missing: list[str]  # the currencies held that no provider or document gives a rate for (gold has none)
    note: str


class FxSpreadRowOut(BaseModel):
    """A row that shows a bank's rate, against TCMB's of its day in the trade's direction."""

    fingerprint: str  # the row
    day: date
    account: AccountRefOut
    title: str  # a card purchase's merchant, else what the bank printed
    side: TradeSide  # buy: against TCMB's forex selling rate; sell: against its forex buying rate
    amount: MoneyOut  # in the currency
    tl: MoneyOut  # the TL paid for it (a buy) or received (a sale)
    rate: str  # the bank's rate, TL for one unit: printed, or a card purchase's TL over its foreign amount
    tcmb_rate: str  # TCMB's rate in the trade's direction
    tcmb_day: date  # that bulletin's day: the row's own, or the latest one before it within a week
    cost: MoneyOut  # in TL; below zero where the bank's rate was the better one


class FxSpreadOut(BaseModel):
    """What the banks' rates cost against TCMB's in the last 12 months (F12)."""

    start: date  # the window: the last 12 months up to today
    end: date
    total: MoneyOut  # both groups, in TL
    trades: list[FxSpreadRowOut]  # currencies bought or sold between own accounts, by day
    trades_total: MoneyOut
    purchases: list[FxSpreadRowOut]  # card purchases in a foreign currency, by day
    purchases_total: MoneyOut
    left_out: int  # the window's rows with no TCMB rate for their day: in no total
    note: str  # the window and the numbers


class FxIncomeRowOut(BaseModel):
    fingerprint: str
    day: date
    account: AccountRefOut
    title: str  # the payer as the rules name it, else what the bank printed
    amount: MoneyOut  # in the currency
    counted: MoneyOut  # in TL as the ledger counts it: at the rate of its day
    worth: MoneyOut | None  # in TL at the current rate; null without one


class FxConversionOut(BaseModel):
    """A sale of the currency for TL."""

    fingerprint: str
    day: date
    account: AccountRefOut  # the TL account the money came into
    amount: MoneyOut  # in the currency
    tl: MoneyOut  # the TL received
    rate: str  # the bank's rate, TL for one unit


class FxSensitivityOut(BaseModel):
    """What a 5% move of the rate does to the monthly income: the average of complete months only."""

    months: list[str]  # the complete months, YYYY-MM, oldest first
    received: MoneyOut  # the income of those months, in the currency
    monthly: MoneyOut  # their average month, in the currency
    monthly_tl: MoneyOut | None  # at the current rate; null without one
    change: MoneyOut | None  # in TL, what a 5% move of the rate takes from (or adds to) the monthly income
    say: str  # "EUR/TRY %5 düşerse aylık gelir … TL azalır", with the months it is over


class FxCurrencyIncomeOut(BaseModel):
    currency: str
    rate: FxRateOut | None  # the current rate: the providers' newest buying rate, else the documents' newest
    rows: list[FxIncomeRowOut]  # the window's income, the oldest first
    received: MoneyOut  # the rows' total, in the currency
    worth: MoneyOut | None  # in TL at the current rate
    sold: list[FxConversionOut]  # the window's sales of the currency for TL, the oldest first
    sensitivity: FxSensitivityOut | None  # null without a complete month with this income
    note: str


class FxIncomeOut(BaseModel):
    """The income that comes in a foreign currency (F12), by currency."""

    start: date  # the window of the rows and the sales: the last 12 months up to today
    end: date
    currencies: list[FxCurrencyIncomeOut]  # by currency code; none without a foreign income
    note: str


class WorthOut(BaseModel):
    """The assets less the debts, of what has a TL value: the dashboard's net worth."""

    total: MoneyOut
    assets: MoneyOut
    debts: MoneyOut  # above zero
    certainty: Certainty  # provisional when a part is
    parts: list[PartOut]  # the largest first
    left_out: list[UnknownOut]  # the accounts without a TL value, and why
    currencies: list[InCurrencyOut]  # the total in EUR, USD and gram gold, null without a rate
    note: str


class AssetOut(BaseModel):
    """An asset or a debt."""

    account: AccountRefOut
    group: AccountGroup
    amount: MoneyOut  # in its currency (gold as "GR"); below zero: a debt
    value: MoneyOut | None  # in TL; null without a rate (gold)
    rate: str | None  # the rate it is valued at, TL for one unit: buying for an asset, selling for a debt
    rate_day: date | None
    cost: MoneyOut | None  # TL paid for it where the documents tell: gold bought from a TL account of the same bank
    gain: MoneyOut | None  # value less cost, when both are known
    day: date  # the newest day it knows of
    certainty: Certainty
    note: str
    rate_source: RateSource | None = None  # a provider's newest rate, or the documents'; null without one


class CurrencyShareOut(BaseModel):
    """The assets held in one currency."""

    currency: str  # TRY (cash and the shares a brokerage statement values in TL), a foreign currency, or GR
    amount: MoneyOut  # in that currency
    value: MoneyOut | None  # in TL; null without a rate (gold)
    share: float | None  # of the assets with a TL value, 0–1
    accounts: list[AccountRefOut]


class HoldingsOut(BaseModel):
    today: date
    worth: WorthOut
    holdings: list[AssetOut]  # the assets by TL value, those without one after them, then the debts
    spread: list[CurrencyShareOut]  # the largest TL value first
    note: str


def _analysis(context: Context) -> Analysis:
    try:
        return context.analysis.get()
    except Busy as exc:
        raise Problem(503, "busy", str(exc)) from exc


def _rate(found: holdings.Rate) -> FxRateOut:
    return FxRateOut(
        day=found.day,
        rate=str(found.rate),
        source=found.source,
        buying=None if found.buying is None else str(found.buying),
        selling=None if found.selling is None else str(found.selling),
    )


@router.get("/api/fx")
def fx_rates(request: Request) -> FxOut:
    """The TL rates by currency: the providers' newest in use, else the documents' newest; with their history."""
    found = holdings.rates(_analysis(context_of(request)))
    return FxOut(
        currencies=[
            FxCurrencyOut(currency=c.currency, newest=_rate(c.newest), history=[_rate(r) for r in c.history])
            for c in found.currencies
        ],
        missing=found.missing,
        note=found.note,
    )


def _spread_row(r: holdings.SpreadRow, labels: dict[str, str]) -> FxSpreadRowOut:
    return FxSpreadRowOut(
        fingerprint=r.fingerprint,
        day=r.day,
        account=account_ref(r.account, labels),
        title=r.title,
        side=r.side,
        amount=money(r.amount, r.currency),
        tl=money(r.tl),
        rate=str(r.rate),
        tcmb_rate=str(r.tcmb),
        tcmb_day=r.tcmb_day,
        cost=money(r.cost),
    )


@router.get("/api/fx/spread")
def fx_spread(request: Request) -> FxSpreadOut:
    """The last 12 months' currency trades and card purchases abroad, each against TCMB's rate of its day in the
    trade's direction, and what the banks' rates cost."""
    context = context_of(request)
    a = _analysis(context)
    found = holdings.spread(a, context.today())
    labels = account_labels(a)
    return FxSpreadOut(
        start=found.start,
        end=found.end,
        total=money(found.total),
        trades=[_spread_row(r, labels) for r in found.trades],
        trades_total=money(found.trades_cost),
        purchases=[_spread_row(r, labels) for r in found.purchases],
        purchases_total=money(found.purchases_cost),
        left_out=found.left_out,
        note=found.note,
    )


def _sensitivity(s: holdings.Sensitivity | None, currency: str) -> FxSensitivityOut | None:
    if s is None:
        return None
    return FxSensitivityOut(
        months=list(s.months),
        received=money(s.received, currency),
        monthly=money(s.monthly, currency),
        monthly_tl=None if s.monthly_tl is None else money(s.monthly_tl),
        change=None if s.change is None else money(s.change),
        say=s.say,
    )


def _currency_income(c: holdings.CurrencyIncome, labels: dict[str, str]) -> FxCurrencyIncomeOut:
    return FxCurrencyIncomeOut(
        currency=c.currency,
        rate=None if c.rate is None else FxRateOut(day=c.rate.day, rate=str(c.rate.rate), source=c.rate.source),
        rows=[
            FxIncomeRowOut(
                fingerprint=r.fingerprint,
                day=r.day,
                account=account_ref(r.account, labels),
                title=r.title,
                amount=money(r.amount, c.currency),
                counted=money(r.counted),
                worth=None if r.worth is None else money(r.worth),
            )
            for r in c.rows
        ],
        received=money(c.received, c.currency),
        worth=None if c.worth is None else money(c.worth),
        sold=[
            FxConversionOut(
                fingerprint=s.fingerprint,
                day=s.day,
                account=account_ref(s.account, labels),
                amount=money(s.amount, c.currency),
                tl=money(s.tl),
                rate=str(s.rate),
            )
            for s in c.sold
        ],
        sensitivity=_sensitivity(c.sensitivity, c.currency),
        note=c.note,
    )


@router.get("/api/fx/income")
def fx_income(request: Request) -> FxIncomeOut:
    """The income that comes in a foreign currency: the last 12 months' rows at the current rate, the sales of the
    currency for TL, and what a 5% move of the rate does to the monthly income, over complete months only."""
    context = context_of(request)
    a = _analysis(context)
    found = holdings.foreign_income(a, context.today())
    labels = account_labels(a)
    return FxIncomeOut(
        start=found.start,
        end=found.end,
        currencies=[_currency_income(c, labels) for c in found.currencies],
        note=found.note,
    )


def _worth(w: holdings.Worth, labels: dict[str, str]) -> WorthOut:
    return WorthOut(
        total=money(w.total),
        assets=money(w.assets),
        debts=money(w.debts),
        certainty=w.certainty,
        parts=[
            PartOut(account=account_ref(p.account, labels), value=money(p.value), certainty=p.certainty)
            for p in w.parts
        ],
        left_out=[UnknownOut(account=account_ref(u.account, labels), reason=u.reason) for u in w.left_out],
        currencies=[
            InCurrencyOut(
                currency=c.currency,
                amount=None if c.amount is None else money(c.amount, c.currency),
                rate=None if c.rate is None else str(c.rate),
                rate_day=c.rate_day,
                note=c.note,
                rate_source=c.rate_source,
            )
            for c in w.currencies
        ],
        note=w.note,
    )


@router.get("/api/holdings")
def holding_list(request: Request) -> HoldingsOut:
    """The net worth in TL and the other units, every asset and debt with its value and cost where known, and how the
    assets spread over currencies."""
    context = context_of(request)
    a = _analysis(context)
    found = holdings.holdings(a, context.today())
    labels = account_labels(a)
    return HoldingsOut(
        today=found.today,
        worth=_worth(found.worth, labels),
        holdings=[
            AssetOut(
                account=account_ref(h.account, labels),
                group=h.group,
                amount=money(h.amount, h.currency),
                value=None if h.value is None else money(h.value),
                rate=None if h.rate is None else str(h.rate),
                rate_day=h.rate_day,
                cost=None if h.cost is None else money(h.cost),
                gain=None if h.gain is None else money(h.gain),
                day=h.day,
                certainty=h.certainty,
                note=h.note,
                rate_source=h.rate_source,
            )
            for h in found.holdings
        ],
        spread=[
            CurrencyShareOut(
                currency=s.currency,
                amount=money(s.amount, s.currency),
                value=None if s.value is None else money(s.value),
                share=s.share,
                accounts=[account_ref(account, labels) for account in s.accounts],
            )
            for s in found.spread
        ],
        note=found.note,
    )
