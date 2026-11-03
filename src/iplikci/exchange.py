"""What changing money cost and what a foreign income is worth (F12; docs/domain/interpretation.md, "Kur makası" and
"Döviz geliri"): pure over the ledger and the rate book the dataset carries, with no storage, files or network.

The spread is what the banks' rates cost against TCMB's of the same day, in the direction of the trade (architecture
§15): a currency bought is compared with TCMB's forex selling rate, one sold with its forex buying rate. Two kinds of
row show a bank's rate:

- a currency bought or sold between own accounts: the TL account's row prints the rate ("DÖVİZ ALIŞ EUR: 36,50",
  Vakıfbank's "İşlem Kuru"); the currency's own account books its side without one (parsers.movements);
- a card purchase abroad: the TL statement prints the foreign amount beside the TL one ("19,99 USD"), and the TL over
  the foreign amount is the rate the card was charged at.

Only TCMB's bulletins are compared with: ECB's one reference rate a day has no sides. A day without a bulletin (a
weekend, a holiday) takes the latest one within a week before it, as the rate book does; a row with none is left out
and counted.

A foreign income is the income of a foreign-currency account: its rows with what they are worth at the current rate
(the providers' newest buying rate, else the documents' newest), the sales of the currency for TL, and what a 5% move
of the rate does to the monthly income. The month is the average of complete months only, and the note says which.
"""

import calendar
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from .analysis import Dataset, DatedRate, payments, printed_rate
from .domain.codes import RateSource, TradeSide, TransactionKind
from .domain.labels import format_amount, format_rate
from .domain.models import TRY, Transaction
from .domain.money import round_half_up
from .fx.book import RateBook, to_tl
from .insights import balance_rate, billed, complete_months, month_name, month_of, provider_rate_said, timeline

GOLD = "GR"  # a gold account counts grams (parsers.accounts): no provider gives gold a rate
WINDOW_MONTHS = 12  # the spread and the foreign income's rows look back a year (F12: "son 12 ayda")
MOVE = Decimal("0.05")  # the move of the rate the sensitivity tells (F12: "EUR/TRY %5 düşerse")
ZERO = Decimal(0)


def window_of(today: date, months: int = WINDOW_MONTHS) -> tuple[date, date]:
    """The days of the last months months up to today: from the day after the same day months before."""
    year, index = divmod(today.year * 12 + today.month - 1 - months, 12)
    day = min(today.day, calendar.monthrange(year, index + 1)[1])
    return date(year, index + 1, day) + timedelta(days=1), today


def _day(d: date) -> str:
    return f"{d:%d.%m.%Y}"


def _window_said(start: date, end: date) -> str:
    return f"{_day(start)} – {_day(end)}"


# --- the spread ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SpreadRow:
    """A row that shows a bank's rate, against TCMB's of its day in the trade's direction."""

    fingerprint: str
    day: date
    account: str
    title: str  # a card purchase's merchant, else what the bank printed
    side: TradeSide
    currency: str
    amount: Decimal  # in the currency, above zero
    tl: Decimal  # the TL paid for it (a buy) or received (a sale), above zero
    rate: Decimal  # the bank's rate, TL for one unit: printed, or a card purchase's TL over its foreign amount
    tcmb: Decimal  # TCMB's rate in the trade's direction: forex selling for a buy, forex buying for a sale
    tcmb_day: date  # that bulletin's day: the row's own, or the latest one before it within a week
    cost: Decimal  # in TL, what the bank's rate cost against TCMB's; below zero where the bank's was the better


@dataclass(frozen=True, slots=True)
class Spread:
    start: date  # the window: the last 12 months up to today
    end: date
    trades: list[SpreadRow]  # currencies bought or sold between own accounts, by day
    purchases: list[SpreadRow]  # card purchases in a foreign currency, by day
    trades_cost: Decimal  # in TL
    purchases_cost: Decimal
    total: Decimal
    left_out: int  # the window's rows with no TCMB rate for their day: in no total
    note: str


@dataclass(frozen=True, slots=True)
class _Seen:
    """What a row tells of a trade before TCMB's rate is looked up."""

    side: TradeSide
    currency: str
    amount: Decimal
    tl: Decimal
    rate: Decimal
    card: bool  # a card purchase abroad: the rate is TL over the foreign amount


def _trade(ds: Dataset, t: Transaction) -> _Seen | None:
    """A currency bought or sold for TL between own accounts, as the TL account's row prints it: money leaving the TL
    account bought the currency. The foreign amount is printed (Vakıfbank) or the TL over the rate."""
    account = ds.accounts.get(t.account)
    if t.kind != TransactionKind.OWN_TRANSFER or account is None or account.currency != TRY or not t.amount:
        return None
    printed = printed_rate(t)
    if printed is None or printed.rate <= 0:
        return None
    tl = abs(t.amount)
    amount = abs(printed.amount) if printed.amount else round_half_up(tl / printed.rate)
    side = TradeSide.BUY if t.amount > 0 else TradeSide.SELL
    return _Seen(side, printed.currency, amount, tl, printed.rate, card=False)


def _purchase(ds: Dataset, t: Transaction) -> _Seen | None:
    """A card purchase abroad on a TL statement: the foreign amount it prints beside the TL one. An installment's
    TL is a part of the whole, so it tells no rate."""
    account = ds.accounts.get(t.account)
    if t.kind != TransactionKind.PURCHASE or t.amount <= 0 or t.installment or account is None:
        return None
    found = billed(t)
    if account.currency != TRY or found is None or found[1] == TRY or found[0] <= 0:
        return None
    amount, currency = found
    return _Seen(TradeSide.BUY, currency, amount, t.amount, t.amount / amount, card=True)


def _tcmb(book: RateBook, currencies: set[str]) -> dict[str, RateBook]:
    """TCMB's bulletins alone, by currency: where TCMB published, the book holds TCMB's quote."""
    return {c: RateBook(q for q in book.history(c) if q.source is RateSource.TCMB) for c in currencies}


def _cost(seen: _Seen, tcmb: Decimal) -> Decimal:
    if seen.card:  # the bank's rate times the amount is the TL itself
        return round_half_up(seen.tl - tcmb * seen.amount)
    difference = seen.rate - tcmb if seen.side is TradeSide.BUY else tcmb - seen.rate
    return to_tl(seen.amount, difference)


def spread(ds: Dataset, today: date) -> Spread:
    """The last 12 months' rows that show a bank's rate, each against TCMB's rate of its day in the trade's
    direction, and what the difference cost (docs/domain/interpretation.md, "Kur makası")."""
    start, end = window_of(today)
    found: list[tuple[Transaction, _Seen]] = []
    for t in payments(ds):
        if start <= t.date <= end and (seen := _trade(ds, t) or _purchase(ds, t)) is not None:
            found.append((t, seen))
    books = _tcmb(ds.book, {seen.currency for _, seen in found})
    trades: list[SpreadRow] = []
    purchases: list[SpreadRow] = []
    left_out = 0
    for t, seen in found:
        quote = books[seen.currency].on(seen.currency, t.date)
        if quote is None:
            left_out += 1
            continue
        tcmb = quote.selling if seen.side is TradeSide.BUY else quote.buying
        row = SpreadRow(
            fingerprint=t.fingerprint,
            day=t.date,
            account=t.account,
            title=(t.merchant or t.description) if seen.card else t.description,
            side=seen.side,
            currency=seen.currency,
            amount=seen.amount,
            tl=seen.tl,
            rate=round_half_up(seen.rate, 4) if seen.card else seen.rate,
            tcmb=tcmb,
            tcmb_day=quote.day,
            cost=_cost(seen, tcmb),
        )
        (purchases if seen.card else trades).append(row)
    trades_cost = sum((r.cost for r in trades), ZERO)
    purchases_cost = sum((r.cost for r in purchases), ZERO)
    found_spread = Spread(
        start=start,
        end=end,
        trades=trades,
        purchases=purchases,
        trades_cost=trades_cost,
        purchases_cost=purchases_cost,
        total=trades_cost + purchases_cost,
        left_out=left_out,
        note="",
    )
    return replace(found_spread, note=_spread_note(found_spread, tcmb=any(books.values())))


def _spread_note(s: Spread, tcmb: bool) -> str:
    """The window and the numbers in a sentence; tcmb: whether any TCMB bulletin was stored for these currencies."""
    window = _window_said(s.start, s.end)
    compared = len(s.trades) + len(s.purchases)
    if not compared and not s.left_out:
        return f"{window} arasında bankanın kurunu gösteren bir döviz alım-satımı ya da yurt dışı kart harcaması yok."
    note = ""
    if compared:
        note = (
            f"{window} arasındaki {compared} işlemde bankaların kuruyla aynı günün TCMB kuru arasındaki fark "
            f"{format_amount(s.total)} TL. Döviz alımı ve yurt dışı kart harcaması TCMB'nin döviz satış, döviz satışı "
            "döviz alış kuruyla karşılaştırıldı; hafta sonu ve tatilde önceki iş gününün kuru geçerlidir. Eksi bir "
            "fark, bankanın kurunun TCMB'ninkinden iyi olduğunu söyler."
        )
    if s.left_out:
        why = "" if tcmb else " TCMB kurları henüz alınmadı."
        note += f" {window} arasında TCMB kuru bulunmayan {s.left_out} işlem toplama girmedi.{why}"
    return note.strip()


# --- the foreign income --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IncomeRow:
    fingerprint: str
    day: date
    account: str
    title: str  # the payer as the rules name it, else what the bank printed
    amount: Decimal  # in the currency, above zero
    counted: Decimal  # in TL as the ledger counts it: at the rate of its day (the row's reason)
    worth: Decimal | None  # in TL at the current rate; None without one


@dataclass(frozen=True, slots=True)
class Conversion:
    """A sale of the currency for TL, as the TL account's row prints it."""

    fingerprint: str
    day: date
    account: str  # the TL account the money came into
    amount: Decimal  # in the currency
    tl: Decimal  # the TL received
    rate: Decimal  # the bank's rate, TL for one unit


@dataclass(frozen=True, slots=True)
class Sensitivity:
    """What a move of the rate does to the monthly income in TL (F12): the average month of complete months only."""

    months: tuple[str, ...]  # the complete months, YYYY-MM, oldest first
    received: Decimal  # the income of those months, in the currency
    monthly: Decimal  # their average month, in the currency
    monthly_tl: Decimal | None  # at the current rate; None without one
    change: Decimal | None  # in TL, what a 5% move of the rate takes from (or adds to) the monthly income
    say: str


@dataclass(frozen=True, slots=True)
class CurrencyIncome:
    currency: str
    rate: DatedRate | None  # the current rate: the providers' newest buying rate, else the documents' newest
    rows: list[IncomeRow]  # the window's, oldest first
    received: Decimal  # the rows' total, in the currency
    worth: Decimal | None  # in TL at the current rate
    sold: list[Conversion]  # the window's sales of the currency for TL, oldest first
    sensitivity: Sensitivity | None  # None without a complete month with this income
    note: str


@dataclass(frozen=True, slots=True)
class ForeignIncome:
    start: date  # the window of the rows and the sales: the last 12 months up to today
    end: date
    currencies: list[CurrencyIncome]  # by currency code; none without a foreign income
    note: str


def _income_rows(ds: Dataset) -> dict[str, list[Transaction]]:
    """Every income row of a foreign-currency account, by currency: a split row whole."""
    found: dict[str, list[Transaction]] = defaultdict(list)
    for t in payments(ds):
        account = ds.accounts.get(t.account)
        if account is None or account.currency in (TRY, GOLD) or t.reason.native is None:
            continue
        if t.kind == TransactionKind.INCOME and t.amount < 0:
            found[account.currency].append(t)
    return found


def _sold(ds: Dataset, currency: str, start: date, end: date) -> list[Conversion]:
    out: list[Conversion] = []
    for t in payments(ds):
        seen = _trade(ds, t) if start <= t.date <= end else None
        if seen is not None and seen.side is TradeSide.SELL and seen.currency == currency:
            out.append(Conversion(t.fingerprint, t.date, t.account, seen.amount, seen.tl, seen.rate))
    return out


def _months_said(months: tuple[str, ...]) -> str:
    if len(months) == 1:
        return f"{month_name(months[0])} (tek tam ay)"
    return f"{month_name(months[0])} – {month_name(months[-1])} arasındaki {len(months)} tam ay"


def _sensitivity(
    currency: str, rows: list[Transaction], months: tuple[str, ...], rate: DatedRate | None
) -> Sensitivity | None:
    received = sum((-(t.reason.native or ZERO) for t in rows if month_of(t.date) in months), ZERO)
    if not months or received <= 0:
        return None
    monthly = round_half_up(received / len(months))
    said = f"Aylık ortalama {_months_said(months)} üzerinden: {format_amount(monthly)} {currency}"
    if rate is None:
        say = f"{said}. {currency} kuru olmadığından TL karşılığı ve kur duyarlılığı hesaplanamadı."
        return Sensitivity(months, received, monthly, None, None, say)
    monthly_tl = to_tl(monthly, rate.rate)
    change = round_half_up(monthly_tl * MOVE)
    say = (
        f"{said}, bugünkü kurla {format_amount(monthly_tl)} TL. {currency}/TRY %5 düşerse aylık gelir "
        f"{format_amount(change)} TL azalır; %5 yükselirse o kadar artar."
    )
    return Sensitivity(months, received, monthly, monthly_tl, change, say)


def _rate_said(rate: DatedRate) -> str:
    if rate.source is RateSource.DOCUMENT:
        return f"{_day(rate.day)} belgesindeki kurla ({format_amount(rate.rate)})"
    return f"{provider_rate_said(rate)}yla ({format_rate(rate.rate)})"


@dataclass(frozen=True, slots=True)
class _Window:
    start: date  # the rows' and the sales' days: the last 12 months up to today
    end: date
    months: tuple[str, ...]  # the complete months the sensitivity's average is over


def _currency_note(c: CurrencyIncome, start: date, end: date) -> str:
    window = _window_said(start, end)
    if c.rows:
        note = f"{window} arasında {len(c.rows)} gelir: {format_amount(c.received)} {c.currency}"
        note += f", bugünkü kurla {format_amount(c.worth)} TL." if c.worth is not None else "."
    else:
        note = f"{window} arasında {c.currency} geliri yok."
    if c.sold:
        note += f" Bu dönemde {len(c.sold)} kez TL'ye çevrildi."
    if c.rate is not None:
        note += f" Bugünkü değer {_rate_said(c.rate)}."
    else:
        note += f" {c.currency} kuru ne TCMB ya da ECB'den geldi ne belgelerde yazıyor: TL değeri bilinmiyor."
    if c.sensitivity is None:
        note += " Kur duyarlılığı için bu gelirin girdiği bir tam ay yok; içinde bulunulan ay sayılmaz."
    return note


def _currency_income(ds: Dataset, currency: str, rows: list[Transaction], window: _Window) -> CurrencyIncome:
    rate = balance_rate(ds, currency, Decimal(1))  # the income is an asset: the buying side
    items = [
        IncomeRow(
            fingerprint=t.fingerprint,
            day=t.date,
            account=t.account,
            title=t.merchant or t.counterparty or t.description,
            amount=-(t.reason.native or ZERO),
            counted=-t.amount,
            worth=to_tl(-(t.reason.native or ZERO), rate.rate) if rate else None,
        )
        for t in rows
        if window.start <= t.date <= window.end
    ]
    received = sum((r.amount for r in items), ZERO)
    income = CurrencyIncome(
        currency=currency,
        rate=rate,
        rows=items,
        received=received,
        worth=to_tl(received, rate.rate) if rate else None,
        sold=_sold(ds, currency, window.start, window.end),
        sensitivity=_sensitivity(currency, rows, window.months, rate),
        note="",
    )
    return replace(income, note=_currency_note(income, window.start, window.end))


def foreign_income(ds: Dataset, today: date) -> ForeignIncome:
    """The income that comes in a foreign currency (docs/domain/interpretation.md, "Döviz geliri"), by currency: the
    last 12 months' rows at the current rate, the sales of the currency for TL, and the sensitivity of the monthly
    income to the rate, over complete months only."""
    start, end = window_of(today)
    full = complete_months(ds)
    current = month_of(today)  # partial by nature, whatever the documents cover
    window = _Window(start, end, tuple(m for m in timeline(ds).window if m in full and m < current))
    found = [_currency_income(ds, c, rows, window) for c, rows in sorted(_income_rows(ds).items())]
    if not found:
        note = "Döviz cinsinden gelen bir gelir yok: döviz hesaplarında gelir satırı görünmüyor."
    else:
        note = (
            "Döviz hesaplarına gelen gelir, para birimi başına: son 12 ayın satırları bugünkü kurla, dövizin TL'ye "
            "çevrildiği günler ve kurun aylık gelire etkisi. Ortalama yalnızca tam aylardan; içinde bulunulan ay "
            "sayılmaz."
        )
    return ForeignIncome(start, end, found, note)
