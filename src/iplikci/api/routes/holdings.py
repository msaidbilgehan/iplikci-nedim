"""The foreign currency and assets screen (F12, its Phase 6 part) for Döviz: the TL rates the documents print, and
the net worth in TL, EUR, USD and gram gold with each holding's value and, where the documents tell, its cost, and
how the assets spread over currencies. Only the documents' own rates are used: nothing is fetched from the network.
Amounts are minor units with their currency; rates are decimal numbers as text (architecture §16)."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...app import holdings
from ...app.analysis import Analysis, account_labels
from ...app.holdings import AccountGroup, Certainty, RateSource
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
    day: date  # the day of the row that printed it
    rate: str  # TL for one unit, as a decimal number ("36.50")
    source: RateSource


class FxCurrencyOut(BaseModel):
    currency: str
    newest: FxRateOut  # the one the screens value with
    history: list[FxRateOut]  # every rate the documents print, the oldest first


class FxOut(BaseModel):
    currencies: list[FxCurrencyOut]  # by currency code
    missing: list[str]  # the currencies held whose rate no document prints (gold has none)
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
    rate: str | None  # the rate it is valued at, TL for one unit
    rate_day: date | None
    cost: MoneyOut | None  # TL paid for it where the documents tell: gold bought from a TL account of the same bank
    gain: MoneyOut | None  # value less cost, when both are known
    day: date  # the newest day it knows of
    certainty: Certainty
    note: str


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
    return FxRateOut(day=found.day, rate=str(found.rate), source=found.source)


@router.get("/api/fx")
def fx_rates(request: Request) -> FxOut:
    """The TL rates the documents print, by currency, the newest first in use."""
    found = holdings.rates(_analysis(context_of(request)))
    return FxOut(
        currencies=[
            FxCurrencyOut(currency=c.currency, newest=_rate(c.newest), history=[_rate(r) for r in c.history])
            for c in found.currencies
        ],
        missing=found.missing,
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
