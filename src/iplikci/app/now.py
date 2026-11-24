"""What stands now (F05's "Şu an" and "Yaklaşanlar", F06's month card): each account's balance today as far as the
documents tell, each card's newest statement and the spending of the period it is in, the month's spending so far
against the typical month, and what the next days hold.

Nothing here is more certain than its documents: a balance moved by receipts and notices after the document that
printed it is provisional and says so; the current month is partial, and the typical month comes from complete months
only (docs/domain/interpretation.md).
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from statistics import median

from .. import month_end
from ..analysis import Dataset, DatedRate, start_of, statement_periods
from ..domain.codes import CARD_TYPES, DEFAULT_EXPENSE_KINDS, AccountType, Certainty, RateSource
from ..domain.labels import format_amount, format_rate
from ..domain.models import TRY, Statement, Transaction
from ..domain.money import round_half_up
from ..forecast import STALE_DAYS, Forecast
from ..fx.book import to_tl
from ..insights import (
    balance_rate,
    complete_months,
    drawn_note,
    month_name,
    month_of,
    payments_after,
    pct,
    provider_rate_said,
    sent_after_note,
)
from ..upcoming import Due
from . import outlook, reach
from .analysis import Analysis

# What the API names from here: the use cases, their records and the codes they carry.
__all__ = [
    "AccountType",
    "Balance",
    "BalanceSource",
    "Card",
    "Certainty",
    "Now",
    "Pace",
    "Period",
    "RateSource",
    "Unknown",
    "balances",
    "cards",
    "now",
    "outside",
    "pace",
    "upcoming",
]

UPCOMING_DAYS = 14  # the days "Yaklaşanlar" looks at, today the first (F05)
GOLD = "GR"  # gold accounts count grams (parsers.accounts)
ZERO = Decimal(0)
# The order the balances are listed in: cash first, what moves with a rate or a market after.
_ORDER = (
    AccountType.CURRENT,
    AccountType.OVERDRAFT,
    AccountType.DEPOSIT,
    AccountType.FX,
    AccountType.GOLD,
    AccountType.BROKERAGE,
)


class BalanceSource(StrEnum):
    """What printed the balance an estimate starts from."""

    STATEMENT = "statement"  # an account list's closing balance
    NOTICE = "notice"  # a bank notice's balance after its row
    PORTFOLIO = "portfolio"  # a brokerage statement: its cash and its securities at the market value it prints


@dataclass(frozen=True, slots=True)
class Balance:
    """An account's balance today as far as the documents tell."""

    account: str
    type: AccountType
    currency: str  # of balance and stated: TRY, a foreign currency, or GR (grams of gold)
    balance: Decimal  # below zero: overdrawn
    # In TL: a TL balance itself; a foreign one at the providers' newest rate, buying for an asset and selling for a
    # debt, else at the documents' newest (insights.balance_rate); None without one.
    value: Decimal | None
    rate: Decimal | None  # that rate, TL for one unit
    rate_day: date | None  # the day it is of: the providers' bulletin, or the document that printed it
    rate_source: RateSource | None
    stated: Decimal  # the balance the newest document printed
    on: date  # that document's day
    source: BalanceSource
    moves: int  # the receipt and notice rows after it, counted in balance
    through: date  # the newest day the balance knows of
    certainty: Certainty  # confirmed: a document printed it; provisional: receipts and notices moved it since
    note: str  # what it rests on, in Turkish
    # In TL: money that came in which no document tells yet (forecast.Start.untold): the receipts and notices after
    # the balance took an account that cannot go below zero this far below it, so the balance is zero. The totals take
    # it off (app.holdings.worth): the documents most likely still count it where it came from.
    untold: Decimal = ZERO


@dataclass(frozen=True, slots=True)
class Untold:
    """Money that came into an account which no document tells yet (Balance.untold): the account paid out more than
    its documents show it held, so the money came in first, from where the documents most likely still count it
    (another own account: an FX sale, a transfer). The totals take it off, so it is not counted twice and a transfer
    between own accounts does not raise them."""

    account: str
    value: Decimal  # in TL, above zero
    day: date  # the newest day the account's balance knows of


def untold(balances: list[Balance]) -> list[Untold]:
    """The money in no document tells yet of the balances with a TL value, which the totals take off."""
    return [Untold(b.account, b.untold, b.through) for b in balances if b.untold > 0 and b.value is not None]


# Why the totals take the money in no document tells yet off: the net worth's, the Accounts screen's.
UNTOLD_NOTE = (
    "Bir hesap belgelerde görünen bakiyesinden fazlasını ödediyse aradaki para önce o hesaba girmiş olmalı, ama "
    "henüz hiçbir belgede yok. Başka bir hesabınızdan geldiyse o hesap belgelerde hâlâ eski bakiyesiyle duruyor: iki "
    "kez sayılmasın diye bu tutar toplamdan düşüldü."
)


@dataclass(frozen=True, slots=True)
class Unknown:
    """An account with no balance to show today, and why."""

    account: str
    reason: str


@dataclass(frozen=True, slots=True)
class Period:
    """A card's statement period and the spending in it (purchases, refunds, interest and fees)."""

    start: date
    end: date  # a statement's cut date; for the period the card is in, the next cut (Statement.cut_after)
    spent: Decimal
    rows: int  # its rows known so far


@dataclass(frozen=True, slots=True)
class Card:
    """A card's newest statement, what it still asks, and the period the card is in now."""

    account: str
    type: AccountType  # a credit card has a debt; a debit card's statement only lists what it spent
    cut: date  # the newest statement's cut date
    total: Decimal | None  # its balance (dönem borcu); a debit card's: the sum of its purchases
    due: date | None  # its due date, when it prints one
    minimum: Decimal | None  # its minimum payment, when it prints one
    limit: Decimal | None  # the card's limit, when it prints one
    paid: Decimal  # paid on the card since the cut
    debt: Decimal | None  # a credit card's: the balance less what was paid since, never below zero
    last: Period  # the newest statement's period
    current: Period  # the period the card is in now: rows dated after the cut, as far as notices tell
    certainty: Certainty  # provisional when a payment since the cut or a row of the period is
    note: str


@dataclass(frozen=True, slots=True)
class Pace:
    """The month's spending so far against the typical month."""

    month: str  # the current month, YYYY-MM: partial by nature
    day: int  # today's day of it
    days: int  # its days
    spent: Decimal  # spending dated in it up to today, as far as the documents tell
    provisional: Decimal  # of that, what only receipts and notices show yet
    typical: Decimal | None  # the median month of up to six complete months before it; None with fewer than three
    by_day: Decimal | None  # the median of the same months' spending up to the same day of the month
    months: tuple[str, ...]  # those complete months
    covered: float  # the share of the month's days so far the accounts' documents cover
    note: str


@dataclass(frozen=True, slots=True)
class Now:
    today: date
    balances: list[Balance]
    unknown: list[Unknown]
    cards: list[Card]
    pace: Pace
    upcoming: list[Due]  # from today on, by day: the calendar's items (app.outlook.calendar)
    end: date  # the last day upcoming looks at


def _amount(value: Decimal, currency: str) -> str:
    unit = {TRY: "TL", GOLD: "gr"}.get(currency, currency)
    return f"{format_amount(value)} {unit}"


def _signed(value: Decimal, currency: str) -> str:
    return ("+" if value > 0 else "−" if value < 0 else "") + _amount(abs(value), currency)


def _day(d: date) -> str:
    return f"{d:%d.%m.%Y}"


def newest_rate(ds: Dataset, currency: str) -> tuple[date, Decimal] | None:
    """The newest TL rate of currency the documents print (docs/domain/interpretation.md, "Varlıklar ve borçlar")."""
    found = ds.rates.get(currency)
    return max(found) if found else None


def rate_text(r: DatedRate, debt: bool = False) -> str:
    """A balance's rate and where it comes from, as the notes write it: "37,00 (20.10.2026 belgesinden)", "36,4521
    (TCMB 03.11.2026 döviz alış kuru)"."""
    if r.source is RateSource.DOCUMENT:
        return f"{format_amount(r.rate)} ({_day(r.day)} belgesinden)"
    return f"{format_rate(r.rate)} ({provider_rate_said(r, debt)})"


def _portfolio(account: str, s: Statement) -> Balance:
    """A brokerage account: its cash and its securities at the market value its newest statement prints."""
    cash = s.total or ZERO
    held = round_half_up(sum((x.value for x in s.securities), ZERO))
    worth = round_half_up(cash + held)
    on = max((x.as_of for x in s.securities), default=s.cut_date)
    note = f"{_day(on)} ekstresindeki piyasa değeriyle: hisseler {_amount(held, TRY)}, nakit {_amount(cash, TRY)}"
    return Balance(
        account=account,
        type=AccountType.BROKERAGE,
        currency=TRY,
        balance=worth,
        value=worth,
        rate=None,
        rate_day=None,
        rate_source=None,
        stated=worth,
        on=on,
        source=BalanceSource.PORTFOLIO,
        moves=0,
        through=on,
        certainty=Certainty.CONFIRMED,
        note=note,
    )


def _balance(ds: Dataset, account: str, newest: date | None) -> Balance | Unknown:
    found = ds.accounts[account]
    if found.type == AccountType.BROKERAGE:
        lists = [s for s in ds.statements if s.account == account and s.total is not None]
        if lists:
            return _portfolio(account, max(lists, key=lambda s: s.cut_date))
    start = start_of(ds, account)
    if start is None:
        return Unknown(account, "bakiyesi hiçbir belgede yazmıyor")
    if newest is not None and (newest - start.on).days > STALE_DAYS:
        return Unknown(account, f"son bakiye {_day(start.on)} tarihli; bugünkü bakiyesi belgelerde yok")
    currency = found.currency
    rate = balance_rate(ds, currency, start.balance) if currency not in (TRY, GOLD) else None
    value = start.balance if currency == TRY else to_tl(start.balance, rate.rate) if rate else None
    where = "banka bildiriminde" if start.notice else "dökümünde"
    note = f"{_day(start.on)} {where} {_amount(start.stated, currency)}"
    gone = f"; {drawn_note(ds, account)}" if start.drawn else ""
    if start.untold:
        moved = f"; sonraki {start.moves} dekont ve bildirimle {_signed(start.told - start.stated, currency)}"
        note += (
            f"{moved if start.moves else ''}{gone}. Ek hesabı "
            f"olmayan bir hesap eksiye düşmez: arada belgelerde olmayan en az {_amount(start.untold, currency)} "
            "girmiş olmalı (faiz, başka bir hesabınızdan aktarılan para ya da bir döviz alım-satımı olabilir). Bakiye "
            f"{_amount(start.balance, currency)} sayıldı (geçici: ekstre ya da döküm gelince kesinleşir)"
        )
    elif start.moves:
        moved = start.told - start.stated
        note += (
            f"; sonraki {start.moves} dekont ve bildirimle {_signed(moved, currency)} (geçici: ekstre ya da döküm "
            "gelince kesinleşir)"
        ) + gone
    else:
        note += gone
    if currency == GOLD:
        note += "; güncel altın fiyatı belgelerde yok"
    elif currency != TRY:
        note += f"; kur {rate_text(rate, start.balance < 0)}" if rate else "; kur bulunamadı"
    if sent := sent_after_note(ds, account, start.through):
        note += f"; {sent}"
    return Balance(
        account=account,
        type=found.type,
        currency=currency,
        balance=start.balance,
        value=value,
        rate=rate.rate if rate else None,
        rate_day=rate.day if rate else None,
        rate_source=rate.source if rate else None,
        stated=start.stated,
        on=start.on,
        source=BalanceSource.NOTICE if start.notice else BalanceSource.STATEMENT,
        moves=start.moves,
        through=start.through,
        certainty=Certainty.PROVISIONAL if start.moves else Certainty.CONFIRMED,
        note=note,
        untold=(start.untold if currency == TRY else to_tl(start.untold, rate.rate) if rate else ZERO),
    )


def balances(a: Analysis) -> tuple[list[Balance], list[Unknown]]:
    """Every open account's balance today as far as the documents tell (forecast.start_of: the newest balance a
    document prints, moved by the receipt and notice rows after it), and the accounts without one with why. Cards
    have their statements instead (cards); a closed account is listed on the Accounts screen only."""
    ds = a.dataset
    seen = reach.last_seen(ds)
    gone = reach.closed(seen)
    newest = max(seen.values(), default=None)
    found: list[Balance] = []
    unknown: list[Unknown] = []
    for account in sorted(ds.accounts.values(), key=lambda x: x.label):
        if account.id in gone or account.type in CARD_TYPES:
            continue
        if account.type == AccountType.LOAN:
            unknown.append(Unknown(account.id, "kredinin kalan anaparası belgelerde yok"))
            continue
        result = _balance(ds, account.id, newest)
        if isinstance(result, Balance):
            found.append(result)
        else:
            unknown.append(result)
    order = {kind: i for i, kind in enumerate(_ORDER)}
    found.sort(key=lambda b: order.get(b.type, len(order)))
    return found, unknown


# What the cash-flow forecast leaves out but the user holds: their value moves with a rate or a market (forecast).
_OUTSIDE = frozenset({AccountType.FX, AccountType.GOLD, AccountType.BROKERAGE})


def outside(a: Analysis, fc: Forecast) -> list[Balance]:
    """The foreign currency, gold and brokerage accounts the forecast leaves out, each with its value in TL today when
    a rate or a market value gives one: the forecast counts TL accounts only, and says what it does not count."""
    counted = {account.account for account in fc.accounts}
    found, _ = balances(a)
    return [b for b in found if b.type in _OUTSIDE and b.account not in counted]


def cover(a: Analysis) -> Decimal:
    """What the foreign currency and the investments the forecast leaves out (outside) are worth in TL today: what
    converting them would bring to the TL accounts when their total falls short. Gold without a price and debts count
    nothing."""
    found, _ = balances(a)
    return sum((b.value for b in found if b.type in _OUTSIDE and b.value is not None and b.value > 0), ZERO)


def _spent(rows: list[Transaction]) -> Decimal:
    return sum((t.amount for t in rows if t.kind in DEFAULT_EXPENSE_KINDS), ZERO)


def _card(ds: Dataset, account: str, statements: list[Statement]) -> Card:
    periods = {id(s): (start, end) for s, start, end in statement_periods(statements)}
    newest = max(statements, key=lambda s: s.cut_date)
    start, end = periods[id(newest)]
    type_ = ds.accounts[account].type
    credit = type_ == AccountType.CREDIT_CARD
    paying = payments_after(ds, account, newest.cut_date) if credit else []
    paid = sum((t.amount for t in paying), ZERO)
    debt = max(ZERO, newest.total - paid) if credit and newest.total is not None else None
    later = [t for t in ds.transactions if t.account == account and t.date > newest.cut_date]
    made = len({t.split_of or id(t) for t in later})  # payments: a split row's parts are one
    cut = newest.cut_after()
    current = Period(newest.cut_date + timedelta(days=1), cut.day, _spent(later), made)
    provisional = any(t.provisional for t in [*paying, *later])
    note = f"{_day(newest.cut_date)} ekstresi"
    if newest.total is not None:
        note += f" {_amount(newest.total, TRY)}"
    if paid:
        note += f"; sonra {_amount(paid, TRY)} ödendi" + (" (geçici)" if any(t.provisional for t in paying) else "")
    if later:
        note += f"; bu dönemden şimdiye dek {made} işlem biliniyor, tamamı ekstreyle gelir"
    else:
        when = _day(cut.day) if cut.printed else f"~{_day(cut.day)}"
        note += f"; bu dönemin harcamaları {when} kesimli ekstreyle gelir"
    return Card(
        account=account,
        type=type_,
        cut=newest.cut_date,
        total=newest.total,
        due=newest.due_date,
        minimum=newest.minimum_payment,
        limit=newest.credit_limit,
        paid=paid,
        debt=debt,
        last=Period(start, end, _spent(newest.transactions), len(newest.transactions)),
        current=current,
        certainty=Certainty.PROVISIONAL if provisional else Certainty.CONFIRMED,
        note=note,
    )


def cards(a: Analysis) -> tuple[list[Card], list[Unknown]]:
    """Every open card's newest TL statement and the period it is in now; a card known from no statement, with
    why."""
    ds = a.dataset
    gone = reach.closed(reach.last_seen(ds))
    found: list[Card] = []
    unknown: list[Unknown] = []
    for account in sorted(ds.accounts.values(), key=lambda x: x.label):
        if account.type not in CARD_TYPES or account.id in gone:
            continue
        statements = [s for s in ds.statements if s.account == account.id and not s.is_account and s.currency == TRY]
        if statements:
            found.append(_card(ds, account.id, statements))
        else:
            unknown.append(Unknown(account.id, "kartın hiçbir ekstresi yok; yalnızca ödeme dekontlarından biliniyor"))
    return found, unknown


def _expense_until(rows: list[Transaction], month: str, last: int) -> Decimal:
    """The spending of a month's rows dated up to its day last (its last day, in a shorter month)."""
    day = min(last, monthrange(int(month[:4]), int(month[5:]))[1])
    return sum((t.amount for t in rows if t.kind in DEFAULT_EXPENSE_KINDS and t.date.day <= day), ZERO)


def pace(a: Analysis, today: date) -> Pace:
    """The month's spending up to today against the typical month: the month-end page's typical month (the median of
    up to six complete months before this one, three at least), and the median of the same months up to today's
    day of the month, which is what the month so far compares with."""
    ds, month = a.dataset, month_of(today)
    [current] = month_end.build(ds, a.insights, today, months=[month])
    by_month: dict[str, list[Transaction]] = {}
    for t in ds.transactions:
        by_month.setdefault(month_of(t.date), []).append(t)
    rows = [t for t in by_month.get(month, []) if t.date <= today]
    prior = [m for m in sorted(complete_months(ds)) if m < month][-6:]
    enough = current.typical is not None
    by_day = median(_expense_until(by_month.get(m, []), m, today.day) for m in prior) if enough else None
    needed = sum(ac.needed for ac in current.accounts if ac.blocking)
    covered = sum(ac.covered for ac in current.accounts if ac.blocking) / needed if needed else 0.0
    so_far = (
        f"Bugüne kadarki günlerin {pct(covered)} belgelerle kapsandı."
        if covered
        else "Bu ayın günlerini kapsayan ekstre ya da döküm henüz gelmedi."
    )
    note = (
        f"{month_name(month)} sürüyor: rakamlar bugüne kadar gelen belgelerden; kart harcamaları ekstre kesiminden "
        f"sonra eklenir. {so_far}"
    )
    if enough:
        window = month_name(prior[0]) if len(prior) == 1 else f"{month_name(prior[0])} – {month_name(prior[-1])}"
        note += f" Tipik ay: {window} arasındaki {len(prior)} tam ayın medyanı."
    else:
        note += f" Tipik ay için en az 3 tam ay gerekiyor; şimdilik {len(prior)} tam ay var."
    return Pace(
        month=month,
        day=today.day,
        days=monthrange(today.year, today.month)[1],
        spent=_spent(rows),
        provisional=_spent([t for t in rows if t.provisional]),
        typical=current.typical,
        by_day=by_day,
        months=tuple(prior) if enough else (),
        covered=round(covered, 3),
        note=note,
    )


def upcoming(a: Analysis, today: date, days: int = UPCOMING_DAYS) -> tuple[list[Due], date]:
    """The calendar's items from today on for days days (app.outlook.calendar), and the last of those days."""
    end = today + timedelta(days=days - 1)
    return [item for item in outlook.calendar(a, today).items if item.day <= end], end


def now(a: Analysis, today: date) -> Now:
    found, unknown = balances(a)
    statements, without = cards(a)
    items, end = upcoming(a, today)
    return Now(today, found, unknown + without, statements, pace(a, today), items, end)
