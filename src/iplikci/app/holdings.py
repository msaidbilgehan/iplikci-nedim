"""The assets and debts and the foreign currency (F12): the net worth in TL, EUR, USD and gram gold, each holding with
its value and, where the documents tell, what was paid for it, how the assets spread over currencies, the TL rates,
the spread the banks' rates cost and the income that comes in a foreign currency (exchange).

The MVP's rules hold (docs/domain/interpretation.md, "Varlıklar ve borçlar"), on the balances "Şu an" shows
(app.now), so the dashboard's net worth, the Accounts screen's totals and this screen tell the same numbers. A foreign
balance is valued at the providers' newest rate (architecture §15): an asset at the forex buying rate, a debt at the
selling rate; the net worth is told in EUR and USD at their selling rate, what buying them would cost. Without the
network only the documents' own rates are used (the newest, its day written). Gold has no price in the documents: it
shows its grams and the TL paid for it, never a guessed value. What was paid for a foreign currency is not shown: the
documents do not tie a purchase in TL to the currency it bought.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .. import exchange
from ..analysis import Dataset, DatedRate
from ..domain.codes import AccountGroup, Certainty, RateSource, TradeSide
from ..domain.labels import format_amount
from ..domain.models import TRY
from ..domain.money import round_half_up
from ..exchange import Conversion, CurrencyIncome, ForeignIncome, IncomeRow, Sensitivity, Spread, SpreadRow
from ..fx.book import Quote, from_tl
from ..insights import billed, provider_rate_said
from . import now
from .account_pages import gold_cost
from .accounts import GROUP_OF
from .analysis import Analysis

# What the API names from here: the use cases, their records and the codes they carry.
__all__ = [
    "AccountGroup",
    "Certainty",
    "Conversion",
    "CurrencyIncome",
    "CurrencyRates",
    "CurrencyShare",
    "ForeignIncome",
    "Holding",
    "Holdings",
    "InCurrency",
    "IncomeRow",
    "Part",
    "Rate",
    "RateSource",
    "Rates",
    "Sensitivity",
    "Spread",
    "SpreadRow",
    "TradeSide",
    "Worth",
    "foreign_income",
    "holdings",
    "rates",
    "spread",
    "worth",
]

CURRENCIES = ("EUR", "USD", now.GOLD)  # the net worth in other units besides TL (F12): gram gold last
HISTORY_DAYS = 90  # the providers' quotes a rate's history shows: the 90 days up to the currency's newest
ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class Part:
    """An account's share of the net worth."""

    account: str
    value: Decimal  # in TL; below zero for a debt (a card's, an overdraft)
    certainty: Certainty


@dataclass(frozen=True, slots=True)
class InCurrency:
    """The net worth in another unit: at the providers' newest selling rate, else at the newest rate the documents
    print."""

    currency: str  # EUR, USD, or GR: grams of gold
    amount: Decimal | None  # None without a rate
    rate: Decimal | None  # TL for one unit
    rate_day: date | None  # the day it is of: the providers' bulletin, or the row that printed it
    rate_source: RateSource | None
    note: str  # where the rate comes from, or why there is none


@dataclass(frozen=True, slots=True)
class Worth:
    total: Decimal  # the assets less the debts, of what has a TL value
    assets: Decimal
    debts: Decimal  # above zero
    certainty: Certainty  # provisional when a part is
    parts: list[Part]  # the largest first
    left_out: list[now.Unknown]  # the accounts without a TL value, and why
    currencies: list[InCurrency]
    note: str  # what it rests on


@dataclass(frozen=True, slots=True)
class Holding:
    """An asset or a debt."""

    account: str
    group: AccountGroup
    currency: str  # of amount: TRY, a foreign currency, or GR (grams of gold)
    amount: Decimal  # below zero: a debt
    value: Decimal | None  # in TL; None without a rate (gold)
    rate: Decimal | None  # the rate it is valued at, TL for one unit: buying for an asset, selling for a debt
    rate_day: date | None  # the day it is of: the providers' bulletin, or the row that printed it
    rate_source: RateSource | None
    cost: Decimal | None  # TL paid for it where the documents tell: gold bought from a TL account of the same bank
    gain: Decimal | None  # value less cost, when both are known
    day: date  # the newest day it knows of
    certainty: Certainty
    note: str


@dataclass(frozen=True, slots=True)
class CurrencyShare:
    """The assets held in one currency."""

    currency: str  # TRY (cash and the shares a brokerage statement values in TL), a foreign currency, or GR
    amount: Decimal  # in that currency
    value: Decimal | None  # in TL; None without a rate (gold)
    share: float | None  # of the assets with a TL value; None without one
    accounts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Holdings:
    today: date
    worth: Worth
    holdings: list[Holding]  # the assets by TL value, those without one after them, then the debts
    spread: list[CurrencyShare]  # the largest TL value first
    note: str


@dataclass(frozen=True, slots=True)
class Rate:
    day: date  # the providers' bulletin, or the row that printed it
    rate: Decimal  # TL for one unit: a provider's buying rate (assets are valued at it), or a document's own
    source: RateSource
    buying: Decimal | None = None  # a provider's two sides; None for a document's rate, which is one trade's
    selling: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CurrencyRates:
    currency: str
    newest: Rate  # the one the screens value with: the providers' newest, else the documents' newest
    history: list[Rate]  # the providers' quotes of the HISTORY_DAYS up to their newest and every document rate, by day


@dataclass(frozen=True, slots=True)
class Rates:
    currencies: list[CurrencyRates]  # by currency code
    missing: list[str]  # the currencies held that no provider or document gives a rate for; and gold, which has none
    note: str


def _amount(value: Decimal, currency: str = TRY) -> str:
    unit = {TRY: "TL", now.GOLD: "gr"}.get(currency, currency)
    return f"{format_amount(value)} {unit}"


def _day(d: date) -> str:
    return f"{d:%d.%m.%Y}"


# --- the net worth ---------------------------------------------------------------------------------------------------


def _no_rate(ds: Dataset, currency: str) -> str:
    """Why a currency has no TL value: no document prints its rate, nor did a provider give one."""
    if not ds.book:  # no provider rate at all: the network was never reached
        return f"belgelerde {currency} kuru yok"
    return f"{currency} kuru yok: TCMB ya da ECB vermedi, belgelerde de yazmıyor"


def _in_currency(ds: Dataset, total: Decimal, currency: str) -> InCurrency:
    if currency == now.GOLD:
        return InCurrency(currency, None, None, None, None, "gram altının TL fiyatı belgelerde yok")
    quote = ds.book.newest(currency)
    if quote is not None:
        # The net worth in a currency is what it would buy of it, and buying a currency costs its selling rate.
        said = provider_rate_said(DatedRate(quote.selling, quote.day, quote.source), selling=True)
        amount = from_tl(total, quote.selling)
        return InCurrency(currency, amount, quote.selling, quote.day, quote.source, f"{said}yla")
    found = now.newest_rate(ds, currency)
    if found is None:
        return InCurrency(currency, None, None, None, None, _no_rate(ds, currency))
    day, rate = found
    note = f"{_day(day)} belgesindeki kurla"
    return InCurrency(currency, round_half_up(total / rate), rate, day, RateSource.DOCUMENT, note)


def worth(ds: Dataset, balances: list[now.Balance], cards: list[now.Card], unknown: list[now.Unknown]) -> Worth:
    """The balances and the cards' debts of "Şu an", added up in TL, and the total in the other units."""
    parts: list[Part] = []
    left: list[now.Unknown] = []
    for b in balances:
        if b.value is not None:
            parts.append(Part(b.account, b.value, b.certainty))
            continue
        why = "güncel altın fiyatı belgelerde yok" if b.currency == now.GOLD else _no_rate(ds, b.currency)
        left.append(now.Unknown(b.account, f"{_amount(b.balance, b.currency)}; {why}"))
    parts += [Part(c.account, -c.debt, c.certainty) for c in cards if c.debt is not None]
    parts.sort(key=lambda p: -abs(p.value))
    assets = sum((p.value for p in parts if p.value > 0), ZERO)
    debts = -sum((p.value for p in parts if p.value < 0), ZERO)
    total = assets - debts
    provisional = any(p.certainty == Certainty.PROVISIONAL for p in parts)
    note = (
        "Hesapların son belgelerindeki bakiyeler, sonraki dekont ve bildirimlerle; kart borçları son ekstreden, "
        "kesimden sonraki ödemeler düşülerek. Değeri bilinmeyenler toplama girmedi."
    )
    return Worth(
        total=total,
        assets=assets,
        debts=debts,
        certainty=Certainty.PROVISIONAL if provisional else Certainty.CONFIRMED,
        parts=parts,
        left_out=left + unknown,
        currencies=[_in_currency(ds, total, c) for c in CURRENCIES],
        note=note,
    )


# --- the holdings ----------------------------------------------------------------------------------------------------


def _holding(ds: Dataset, b: now.Balance) -> Holding:
    account = ds.accounts[b.account]
    cost = gold_cost(ds, b.account) if b.currency == now.GOLD else None
    note = b.note
    if cost is not None:
        note += f"; alışta ödenen {_amount(cost)} (aynı bankanın TL hesaplarından, satışlar düşülerek)"
    return Holding(
        account=b.account,
        group=GROUP_OF[account.type],
        currency=b.currency,
        amount=b.balance,
        value=b.value,
        rate=b.rate,
        rate_day=b.rate_day,
        rate_source=b.rate_source,
        cost=cost,
        gain=b.value - cost if b.value is not None and cost is not None else None,
        day=b.through,
        certainty=b.certainty,
        note=note,
    )


def _debt(card: now.Card, debt: Decimal) -> Holding:
    return Holding(
        account=card.account,
        group=AccountGroup.CARDS,
        currency=TRY,
        amount=-debt,
        value=-debt,
        rate=None,
        rate_day=None,
        rate_source=None,
        cost=None,
        gain=None,
        day=card.cut,
        certainty=card.certainty,
        note=card.note,
    )


def _spread(found: list[Holding]) -> list[CurrencyShare]:
    assets = [h for h in found if h.amount > 0]
    valued = sum((h.value for h in assets if h.value is not None), ZERO)
    shares: list[CurrencyShare] = []
    for currency in dict.fromkeys(h.currency for h in assets):
        held = [h for h in assets if h.currency == currency]
        known = all(h.value is not None for h in held)
        value = sum((h.value for h in held if h.value is not None), ZERO) if known else None
        share = float(round(value / valued, 3)) if value is not None and valued else None
        amount = sum((h.amount for h in held), ZERO)
        shares.append(CurrencyShare(currency, amount, value, share, tuple(h.account for h in held)))
    return sorted(shares, key=lambda s: (s.value is None, -(s.value or ZERO), s.currency))


def holdings(a: Analysis, today: date) -> Holdings:
    """Every open account's asset or debt, valued in TL as far as the documents tell; the net worth and the spread."""
    ds = a.dataset
    balances, unknown = now.balances(a)
    cards, without = now.cards(a)
    found = [_holding(ds, b) for b in balances]
    found += [_debt(c, c.debt) for c in cards if c.debt is not None and c.debt > 0]
    found.sort(key=lambda h: (h.amount < 0, h.value is None, -abs(h.value if h.value is not None else ZERO)))
    if ds.book:
        rated = (
            "Döviz varlıklar TCMB'nin (ulaşılamayan günlerde ECB'nin) en yeni döviz alış kuruyla, döviz borçları satış "
            "kuruyla değerlenir; kurun günü ve kaynağı her satırda yazar. Bu kurların vermediği birimlerde belgelerdeki "
            "en yeni kur kullanılır."
        )
    else:
        rated = "Kurlar belgelerdeki döviz işlemlerinden, en yenisiyle: TCMB ya da ECB kuru henüz alınmadı."
    note = (
        f"{rated} Altının fiyatı belgelerde yazmadığından TL değeri yok; dövizin alış maliyeti belgelerden "
        "eşleştirilemediği için kur farkı gösterilmiyor."
    )
    return Holdings(today, worth(ds, balances, cards, [*unknown, *without]), found, _spread(found), note)


# --- the rates -------------------------------------------------------------------------------------------------------


def _quoted(q: Quote) -> Rate:
    """A provider's quote: at its buying rate, what an asset is valued at, with both sides beside it."""
    return Rate(q.day, q.buying, q.source, q.buying, q.selling)


def _listed(ds: Dataset) -> list[str]:
    """The currencies the rates are given for: every one a document prints a rate for, and of those the providers
    give, the ones that matter here: held in an account, billed on a card, or a unit the net worth is told in (TCMB
    publishes some twenty, most of them nothing to the user)."""
    printed = {currency for currency, found in ds.rates.items() if found}
    held = {account.currency for account in ds.accounts.values() if account.currency != TRY}
    billed_in = {found[1] for t in ds.transactions if (found := billed(t)) is not None}
    wanted = (held | billed_in | set(CURRENCIES)) & set(ds.book.currencies())
    return sorted(printed | wanted)


def rates(a: Analysis) -> Rates:
    """The TL rates by currency: the providers' newest first, the documents' newest where no provider gives one, and
    a history of the providers' recent quotes and every rate the documents print; the currencies held without one."""
    ds = a.dataset
    found: list[CurrencyRates] = []
    for currency in _listed(ds):
        printed = [Rate(day, rate, RateSource.DOCUMENT) for day, rate in sorted(ds.rates.get(currency, []))]
        newest = ds.book.newest(currency)
        quotes = (
            [_quoted(q) for q in ds.book.history(currency) if (newest.day - q.day).days < HISTORY_DAYS]
            if newest is not None
            else []
        )
        # By day; on a day with both, the provider's first.
        history = sorted([*quotes, *printed], key=lambda r: (r.day, r.source is RateSource.DOCUMENT))
        found.append(CurrencyRates(currency, _quoted(newest) if newest is not None else printed[-1], history))
    held = {account.currency for account in ds.accounts.values() if account.currency != TRY}
    missing = sorted(held - {c.currency for c in found})
    if ds.book:
        note = (
            "Kurlar TCMB'nin günlük kurlarından, TCMB'ye ulaşılamayan günlerde ECB'nin referans kurundan. Varlıklar "
            "döviz alış, borçlar döviz satış kuruyla değerlenir; bu kurların vermediği birimlerde bankaların "
            f"belgelerindeki en yeni kur kullanılır. Tarihçede sağlayıcıların son {HISTORY_DAYS} günü ve belgelerdeki "
            "bütün kurlar var."
        )
    else:
        note = (
            "Kurlar bankaların belgelerindeki döviz alım-satım satırlarından: TCMB ya da ECB kuru henüz alınmadı. Ağ "
            "bağlantısı olmadan belgelerdeki kurlar kullanılır."
        )
    return Rates(found, missing, note)


# --- the spread and the foreign income -------------------------------------------------------------------------------


def spread(a: Analysis, today: date) -> Spread:
    """What the banks' rates cost against TCMB's in the last 12 months (exchange.spread)."""
    return exchange.spread(a.dataset, today)


def foreign_income(a: Analysis, today: date) -> ForeignIncome:
    """The income that comes in a foreign currency, at the current rate, its sales for TL and the sensitivity of the
    monthly income to the rate (exchange.foreign_income)."""
    return exchange.foreign_income(a.dataset, today)
