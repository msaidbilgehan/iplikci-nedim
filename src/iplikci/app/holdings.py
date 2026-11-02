"""The assets and debts (F12, its Phase 6 part): the net worth in TL, EUR, USD and gram gold, each holding with its
value and, where the documents tell, what was paid for it, how the assets spread over currencies, and the TL rates
the documents print.

The MVP's rules hold (docs/domain/interpretation.md, "Varlıklar ve borçlar"), on the balances "Şu an" shows
(app.now), so the dashboard's net worth, the Accounts screen's totals and this screen tell the same numbers. Without
the network only the documents' own rates are used (the newest, its day written); the rate services come with
Phase 8. Gold has no price in the documents: it shows its grams and the TL paid for it, never a guessed value. What
was paid for a foreign currency is not shown: the documents do not tie a purchase in TL to the currency it bought.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..analysis import Dataset
from ..domain.codes import AccountGroup, Certainty, RateSource
from ..domain.labels import format_amount
from ..domain.models import TRY
from ..domain.money import round_half_up
from . import now
from .account_pages import gold_cost
from .accounts import GROUP_OF
from .analysis import Analysis

# What the API names from here: the use cases, their records and the codes they carry.
__all__ = [
    "AccountGroup",
    "Certainty",
    "CurrencyRates",
    "CurrencyShare",
    "Holding",
    "Holdings",
    "InCurrency",
    "Part",
    "Rate",
    "RateSource",
    "Rates",
    "Worth",
    "holdings",
    "rates",
    "worth",
]

CURRENCIES = ("EUR", "USD", now.GOLD)  # the net worth in other units besides TL (F12): gram gold last
ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class Part:
    """An account's share of the net worth."""

    account: str
    value: Decimal  # in TL; below zero for a debt (a card's, an overdraft)
    certainty: Certainty


@dataclass(frozen=True, slots=True)
class InCurrency:
    """The net worth in another unit, at the newest rate the documents print."""

    currency: str  # EUR, USD, or GR: grams of gold
    amount: Decimal | None  # None without a rate
    rate: Decimal | None  # TL for one unit
    rate_day: date | None  # the day of the row that printed it
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
    rate: Decimal | None  # the rate it is valued at, TL for one unit
    rate_day: date | None  # the day of the row that printed it
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
    day: date  # the day of the row that printed it
    rate: Decimal  # TL for one unit
    source: RateSource


@dataclass(frozen=True, slots=True)
class CurrencyRates:
    currency: str
    newest: Rate  # the one the screens value with
    history: list[Rate]  # every rate the documents print, the oldest first


@dataclass(frozen=True, slots=True)
class Rates:
    currencies: list[CurrencyRates]  # by currency code
    missing: list[str]  # the currencies held whose rate no document prints: EUR, USD; and gold, which has none
    note: str


def _amount(value: Decimal, currency: str = TRY) -> str:
    unit = {TRY: "TL", now.GOLD: "gr"}.get(currency, currency)
    return f"{format_amount(value)} {unit}"


def _day(d: date) -> str:
    return f"{d:%d.%m.%Y}"


# --- the net worth ---------------------------------------------------------------------------------------------------


def _in_currency(ds: Dataset, total: Decimal, currency: str) -> InCurrency:
    if currency == now.GOLD:
        return InCurrency(currency, None, None, None, "gram altının TL fiyatı belgelerde yok")
    found = now.newest_rate(ds, currency)
    if found is None:
        return InCurrency(currency, None, None, None, f"belgelerde {currency} kuru yok")
    day, rate = found
    return InCurrency(currency, round_half_up(total / rate), rate, day, f"{_day(day)} belgesindeki kurla")


def worth(ds: Dataset, balances: list[now.Balance], cards: list[now.Card], unknown: list[now.Unknown]) -> Worth:
    """The balances and the cards' debts of "Şu an", added up in TL, and the total in the other units."""
    parts: list[Part] = []
    left: list[now.Unknown] = []
    for b in balances:
        if b.value is not None:
            parts.append(Part(b.account, b.value, b.certainty))
            continue
        why = "güncel altın fiyatı belgelerde yok" if b.currency == now.GOLD else f"belgelerde {b.currency} kuru yok"
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
    note = (
        "Kurlar belgelerdeki döviz işlemlerinden, en yenisiyle; ağdan kur alınmıyor. Altının fiyatı belgelerde "
        "yazmadığından TL değeri yok; dövizin alış maliyeti belgelerden eşleştirilemediği için kur farkı "
        "gösterilmiyor."
    )
    return Holdings(today, worth(ds, balances, cards, [*unknown, *without]), found, _spread(found), note)


# --- the rates -------------------------------------------------------------------------------------------------------


def rates(a: Analysis) -> Rates:
    """The TL rates the documents print, by currency, and the currencies held without one."""
    ds = a.dataset
    found = [
        CurrencyRates(
            currency,
            Rate(*max(printed), RateSource.DOCUMENT),
            [Rate(day, rate, RateSource.DOCUMENT) for day, rate in sorted(printed)],
        )
        for currency, printed in sorted(ds.rates.items())
        if printed
    ]
    held = {account.currency for account in ds.accounts.values() if account.currency != TRY}
    missing = sorted(held - {c.currency for c in found})
    note = (
        "Kurlar bankaların belgelerindeki döviz alım-satım satırlarından; ağ bağlantısı olmadan bunlar kullanılır. "
        "TCMB ve ECB kurları henüz alınmıyor."
    )
    return Rates(found, missing, note)
