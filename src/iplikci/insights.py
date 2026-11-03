"""Interpretation: what the numbers mean and what to do next.

* Regular payments (rent, bills, subscriptions, pension) and whether each one
  still runs, ended (the card's statements go on without it) or was cancelled
  (listed under `_biten` in the user's rules); periodic ones too, half a year
  or a year apart (an insurance, a car tax, a yearly subscription).
* Discretionary spending per merchant: a monthly habit, a new habit, an
  occasional purchase, a one-off or a habit that stopped. Only habits get a
  monthly cost; an occasional purchase is spread over the months it was seen
  in, and a one-off is never turned into a yearly figure.
* What changed between the last six complete months and the months before.
* Balances: cash, term deposits, overdraft (KMH), card debt, foreign currency, gold and stocks, with the
  transfers whose receipts came after the newest statement (provisional until the statement shows them).
* Findings and steps, each with its effect in TL per month where it has one.

Only complete months are used: card statements end at their cut dates, so the
newest month is usually partial.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise
from statistics import median

from .analysis import (
    NOT_ON_STATEMENT,
    POSTING_DAYS,
    PROVISIONAL,
    Dataset,
    DatedRate,
    ReceiptLine,
    payments,
    whole,
)
from .categorize import FX_CATEGORY
from .domain.codes import (
    CARD_TYPES,
    DEFAULT_EXPENSE_KINDS,
    AccountType,
    Necessity,
    RateSource,
    SeriesPeriod,
    SeriesStatus,
    TransactionKind,
)
from .domain.labels import MONTHS, RATE_SOURCE, format_amount, format_rate
from .domain.models import TRY, Transaction
from .domain.money import CENT, round_half_up, to_decimal
from .domain.text import fold

# Statements that say whether a month's income is known: bank accounts, not cards or a brokerage account.
NOT_BANK_ACCOUNTS = (*CARD_TYPES, AccountType.BROKERAGE)
FULL = 0.97  # share of a month the statements must cover for the month to be complete
NEEDED, OPTIONAL, AVOIDABLE = Necessity.REQUIRED, Necessity.OPTIONAL, Necessity.UNNECESSARY
INTEREST = ("Kredi Kartı Faizi", "Ek Hesap (KMH) Faizi", "Kredi Faizi")
CARD_FEES = "Kart Aidatı & Ücretleri"
WORK_CATEGORIES = ("Yazılım, Bulut & Dijital Hizmet", "Muhasebe & Şirket Hizmetleri")
ZERO = Decimal(0)
GOLD_DUST = Decimal("0.001")  # grams of gold below this are a rounding remainder, not a holding


# --- months and money ---------------------------------------------------------------


def month_of(d: date) -> str:
    return f"{d:%Y-%m}"


def shift(month: str, n: int) -> str:
    index = int(month[:4]) * 12 + int(month[5:]) - 1 + n
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def span(first: str, last: str) -> list[str]:
    out = []
    while first <= last:
        out.append(first)
        first = shift(first, 1)
    return out


def month_name(month: str) -> str:
    return f"{MONTHS[int(month[5:]) - 1]} {month[:4]}"


# How the last word of a year is spoken decides its case suffix: 2026 (altı) -> 'dan, 2025 (beş) -> 'ten.
_YEAR_SOUND = {"1": "e", "2": "e", "3": "eT", "4": "eT", "5": "eT", "6": "a", "7": "e", "8": "e", "9": "a"}
_TENS_SOUND = {"0": "e", "1": "a", "2": "e", "3": "a", "4": "aT", "5": "e", "6": "aT", "7": "eT", "8": "e", "9": "a"}


def year_suffix(year: str, ablative: bool) -> str:
    """2026 -> "'dan" (ablative) or "'da" (locative); 2025 -> "'ten" / "'te"."""
    sound = _YEAR_SOUND.get(year[-1]) or _TENS_SOUND[year[-2]]
    return "'" + ("t" if sound.endswith("T") else "d") + sound[0] + ("n" if ablative else "")


def since(month: str) -> str:
    """'2026-05' -> 'Mayıs 2026'dan beri'."""
    return f"{month_name(month)}{year_suffix(month[:4], True)} beri"


def months_in(months: list[str]) -> str:
    """['2026-03', '2026-07', '2025-12'] -> 'Mart ve Temmuz 2026'da, Aralık 2025'te'."""
    by_year: dict[str, list[str]] = {}
    for m in months:
        by_year.setdefault(m[:4], []).append(MONTHS[int(m[5:]) - 1])
    parts = []
    for year, names in by_year.items():
        joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " ve " + names[-1]
        parts.append(f"{joined} {year}{year_suffix(year, False)}")
    return ", ".join(parts)


# Possessive suffix after a number, by how it is spoken: %64'ü (dört), %72'si (iki), %29'u (dokuz).
_ONES_POSSESSIVE = {"1": "i", "2": "si", "3": "ü", "4": "ü", "5": "i", "6": "sı", "7": "si", "8": "i", "9": "u"}
_TENS_POSSESSIVE = {
    "0": "ü",
    "1": "u",
    "2": "si",
    "3": "u",
    "4": "ı",
    "5": "si",
    "6": "ı",
    "7": "i",
    "8": "i",
    "9": "ı",
}


def possessive(n: int) -> str:
    """The possessive after a whole number, by its last spoken word: 64 -> "ü" (dört), 100 -> "ü" (yüz),
    1000 -> "i" (bin), 1000000 -> "u" (milyon)."""
    digits = str(abs(n))
    zeros = len(digits) - len(digits.rstrip("0"))
    if digits == "0":
        return "ı"
    if zeros == 0:
        return _ONES_POSSESSIVE[digits[-1]]
    if zeros == 1:
        return _TENS_POSSESSIVE[digits[-2]]
    return "ü" if zeros == 2 else "i" if zeros < 6 else "u" if zeros < 9 else "ı"


def pct(share: Decimal | float) -> str:
    """0.64 -> "%64'ü": a share of something, with the suffix Turkish needs after it. A share that rounds to none or
    to the whole without being so reads "%1'den azı" or "%99'dan fazlası": never nothing or all when it is not."""
    n = round(share * 100)
    if n == 0 and share > 0:
        return f"%1{year_suffix('1', True)} azı"  # the ablative goes by the number's last word, as a year's does
    if n == 100 and share < 1:
        return f"%99{year_suffix('99', True)} fazlası"
    return f"%{n}'{possessive(n)}"


def tl(value: Decimal | float) -> str:
    """1234.5 -> '1.235 TL', -50 -> '−50 TL': whole liras, halves rounded up, written as the interface writes amounts."""
    whole = round_half_up(to_decimal(value), 0)
    return ("−" if whole < 0 else "") + f"{abs(whole):,.0f}".replace(",", ".") + " TL"


def _day(d: date) -> str:
    return f"{d:%d.%m.%Y}"


def _change(a: Decimal, b: Decimal) -> Decimal:
    return abs(abs(a) - abs(b)) / max(abs(a), abs(b), CENT)


# --- timeline -------------------------------------------------------------------------


@dataclass(frozen=True)
class Timeline:
    as_of: date  # newest statement end
    last_complete: str  # newest month every account covers in full
    window: list[str]  # up to twelve complete months, the ones with account movement lists if there are any
    seen_until: dict[str, date]  # account -> newest statement end


def fresh_starts(ds: Dataset) -> set[str]:
    """Accounts whose first statement starts from a zero balance: opened during that month."""
    first: dict[str, object] = {}
    for s in sorted(ds.statements, key=lambda s: s.cut_date):
        if s.currency == ds.accounts[s.account].currency:
            first.setdefault(s.account, s)
    return {a for a, s in first.items() if abs(s.previous or ZERO) < CENT}


def complete_months(ds: Dataset) -> set[str]:
    """Months no account covers only partly. An account that is not open yet (or any
    more) does not count; a gap between two of its statements does."""
    fresh = fresh_starts(ds)
    # A brokerage account only holds securities: a month without its statement still has every payment.
    coverage = {a: c for a, c in ds.coverage.items() if c and ds.accounts[a].type != AccountType.BROKERAGE}
    bounds = {a: (min(c), max(c)) for a, c in coverage.items()}
    out = set()
    for m in {m for c in coverage.values() for m in c}:
        for a, cov in coverage.items():
            share = cov.get(m, 0)
            first, last = bounds[a]
            if share >= FULL or (share == 0 and not first < m < last) or (m == first and a in fresh):
                continue
            break
        else:
            out.add(m)
    return out


def timeline(ds: Dataset) -> Timeline:
    seen: dict[str, date] = {}
    for s in ds.statements:
        seen[s.account] = max(seen.get(s.account, s.cut_date), s.cut_date)
    newest = max((t.date for t in ds.transactions), default=date.today())
    as_of = max(seen.values(), default=newest)
    full = sorted(m for m in complete_months(ds) if m <= month_of(newest))
    last = full[-1] if full else shift(month_of(newest), -1)
    with_accounts = {
        m
        for a, cov in ds.coverage.items()
        if ds.accounts[a].type not in NOT_BANK_ACCOUNTS
        for m, share in cov.items()
        if share >= FULL
    }
    candidates = [m for m in span(shift(last, -11), last) if not full or m in full]
    window = [m for m in candidates if m in with_accounts] or candidates
    return Timeline(as_of, last, window, seen)


# --- regular payments ---------------------------------------------------------------------

STATUS = {
    "devam": "Devam ediyor",
    "bitti": "Bitti",
    "iptal": "İptal edildi",
    "iptal_sonrasi": "İptalden sonra ödeme var",
}
# The V1 codes of the statuses above (docs/domain/interpretation.md): what the API and the newer MCP tools carry.
V1_STATUS = {
    "devam": SeriesStatus.ACTIVE,
    "bitti": SeriesStatus.ENDED,
    "iptal": SeriesStatus.CANCELLED,
    "iptal_sonrasi": SeriesStatus.PAID_AFTER_CANCEL,
}

_GAP = (15, 50)  # days between two payments of a monthly series; salary and rent days drift
_SKIPPED = 70  # one missed month is fine when the amount stayed the same
# Relative amount change between two payments of a series.
_SAME, _STRICT, _SIMILAR, _REPRICED = Decimal("0.03"), Decimal("0.10"), Decimal("0.25"), Decimal("0.70")
_ONE_A_MONTH = 1.3  # payments per active month of a payee that bills once a month
_BUSY = 5  # payments per active month above which a payee is a shop, not a subscription
_STALE = 90  # days after the expected payment with no trace of it anywhere: over
_PAUSE = 100  # days without a payment after which a once-a-month payee starts a new series
_RESUME = 200  # days a commitment can go unseen (paid from an account without documents) and still go on


@dataclass
class Series:
    """Payments to one payee about a month apart. A payee can run several series
    (a YouTube subscription and a channel membership)."""

    merchant: str
    payments: list[Transaction] = field(default_factory=list)
    status: str = ""
    expected: date | None = None  # the next payment if the series goes on

    @property
    def last(self) -> Transaction:
        return self.payments[-1]

    @property
    def amount(self) -> Decimal:
        return abs(self.last.amount)

    @property
    def monthly(self) -> Decimal:
        """Amount to expect next: the last one, or the median of the last three when it moves
        from month to month (bills)."""
        recent = [abs(t.amount) for t in self.payments[-3:]]
        if len(recent) >= 2 and _change(recent[-1], recent[-2]) > _STRICT:
            return median(recent)
        return self.amount

    @property
    def gaps(self) -> list[int]:
        return [(b.date - a.date).days for a, b in zip(self.payments, self.payments[1:])]

    @property
    def cadence(self) -> int:
        return round(median(self.gaps)) if self.gaps else 30

    @property
    def day(self) -> int:
        return round(median(t.date.day for t in self.payments[-4:]))

    @property
    def running(self) -> bool:
        return self.status in ("devam", "iptal_sonrasi")

    @property
    def grace(self) -> int:
        """Days past the expected payment the series still waits for it: as late as it has come lately, ten at least."""
        return max(10, max(self.gaps[-6:], default=self.cadence) - self.cadence)

    def price_change(self) -> tuple[Decimal, Decimal, date] | None:
        """(old price, new price, first payment at the new price) when the latest price has held
        for at least two payments and differs from the three payments before it. A payee that bills in a foreign
        currency is compared by what it bills, the amount a card statement prints beside the TL one: its TL amount
        moves with the rate every month (a plan at 4 USD a month is no price rise as the dollar climbs). The prices
        given are TL, as the payments were."""
        billed = _billed_tail(self.payments)
        paid = self.payments[-len(billed) :] if billed else self.payments
        amounts = [abs(t.amount) for t in paid]
        prices = billed or amounts
        i = len(prices) - 1
        while i > 0 and _change(prices[i - 1], prices[-1]) <= Decimal("0.02"):
            i -= 1
        if len(prices) - i < 2 or i == 0:
            return None
        if _change(median(prices[max(0, i - 3) : i]), prices[-1]) <= Decimal("0.05"):
            return None
        return median(amounts[max(0, i - 3) : i]), amounts[-1], paid[i].date


# The foreign amount a card statement prints beside a payment made abroad: "4,00 USD", "1.234,56 EUR".
_FOREIGN = re.compile(r"^(\d{1,3}(?:\.\d{3})*|\d+),(\d{2}) ([A-Z]{3})$")


def billed(t: Transaction) -> tuple[Decimal, str] | None:
    """What a payment billed in a foreign currency cost in it, and the currency; None for a payment in TL."""
    found = _FOREIGN.match(t.original.strip())
    return (Decimal(f"{found[1].replace('.', '')}.{found[2]}"), found[3]) if found else None


def _billed_tail(payments: list[Transaction]) -> list[Decimal]:
    """The foreign amounts of the latest payments that all have one in the last payment's currency, oldest first;
    none when the last payment was in TL."""
    last = billed(payments[-1]) if payments else None
    if last is None:
        return []
    tail: list[Decimal] = []
    for t in reversed(payments):
        found = billed(t)
        if found is None or found[1] != last[1]:
            break
        tail.append(found[0])
    return tail[::-1]


def _day_gap(a: date, b: date) -> int:
    d = abs(a.day - b.day)
    return min(d, 30 - d) if d <= 30 else 0


def _fit(s: Series, t: Transaction, limit: Decimal) -> Decimal | None:
    """How well t continues s, lower is better; None when it does not."""
    gap = (t.date - s.last.date).days
    change = _change(s.last.amount, t.amount)
    if _GAP[0] <= gap <= _GAP[1]:
        if change <= limit:
            return change
        if limit > _STRICT and change <= _REPRICED and _day_gap(s.last.date, t.date) <= 3:
            return 1 + change  # a new price on the usual day of the month
    elif _GAP[1] < gap <= _SKIPPED and change <= _SAME:
        return 2 + change
    return None


def _chain(payee: str, items: list[Transaction], limit: Decimal) -> list[Series]:
    series: list[Series] = []
    for t in items:
        fits = [(score, s) for s in series if (score := _fit(s, t, limit)) is not None]
        if fits:
            min(fits, key=lambda f: f[0])[1].payments.append(t)
        else:
            series.append(Series(payee, [t]))
    return series


def _months(payments: list[Transaction]) -> int:
    return len({month_of(t.date) for t in payments})


def _split(payee: str, items: list[Transaction]) -> list[Series]:
    """One series per run of payments; a pause of over three months starts a new one (an old
    subscription and the one taken out years later are not the same, a bill paid from another
    account after a skipped month is). A last run too short to be a series continues the one before
    it when the pause stayed within _RESUME days: the bill was paid from elsewhere meanwhile."""
    runs = [[items[0]]]
    for a, b in pairwise(items):
        if (b.date - a.date).days > _PAUSE:
            runs.append([])
        runs[-1].append(b)
    if len(runs) > 1 and _months(runs[-1]) < 3 and (runs[-1][0].date - runs[-2][-1].date).days <= _RESUME:
        last = runs.pop()
        runs[-1] += last
    return [Series(payee, run) for run in runs]


def _resume(series: list[Series], items: list[Transaction]) -> None:
    """Payments after the payee's newest series that are too few for a series of their own continue
    it when they come back within _RESUME days at a similar amount (a phone bill paid from an account
    without documents for two months). Otherwise the bill would read as ended while it is still paid."""
    if not series:
        return
    newest = max(series, key=lambda s: s.last.date)
    taken = {id(t) for s in series for t in s.payments}
    for t in items:
        if (
            id(t) not in taken
            and 0 < (t.date - newest.last.date).days <= _RESUME
            and _change(newest.last.amount, t.amount) <= _SIMILAR
        ):
            newest.payments.append(t)


def find_series(txns: list[Transaction], regular: set[str]) -> list[Series]:
    """Monthly series per payee, at least three months long.

    In commitment categories (`regular`: rent, bills, subscriptions) a payee that is paid once a
    month is one series whatever the amounts (a gas bill moves with the season); several
    subscriptions with one payee are told apart by their amounts. Elsewhere only a nearly
    unchanged amount every month makes a series, so a shop visited monthly is not a commitment.
    """
    by_payee: dict[str, list[Transaction]] = defaultdict(list)
    for t in txns:
        by_payee[t.merchant].append(t)
    found = []
    for payee, items in by_payee.items():
        items.sort(key=lambda t: t.date)
        per_month = len(items) / len({month_of(t.date) for t in items})
        if len(items) < 3 or per_month > _BUSY:
            continue
        if items[-1].kind == TransactionKind.INCOME:
            series = _chain(payee, items, _SIMILAR)
        elif items[-1].category in regular or items[-1].kind != TransactionKind.PURCHASE:
            monthly = per_month <= _ONE_A_MONTH and 20 <= Series(payee, items).cadence <= 45
            series = _split(payee, items) if monthly else _chain(payee, items, _SIMILAR)
            series = [s for s in series if _months(s.payments) >= 3]
            _resume(series, items)
        else:
            series = _chain(payee, items, _STRICT)
        found += [s for s in series if _months(s.payments) >= 3]
    return found


def settle(s: Series, seen_until: dict[str, date], ended: dict[str, str], as_of: date) -> None:
    """Status of a series: running, ended (statements go on without it) or cancelled."""
    s.expected = s.last.date + timedelta(days=s.cadence)
    cancelled = ended.get(fold(s.merchant))
    if cancelled:
        s.status = "iptal_sonrasi" if paid_after_cancel(s, ended) else "iptal"
        return
    seen = max(seen_until.get(t.account, t.date) for t in s.payments[-2:])
    over = seen >= s.expected + timedelta(days=s.grace) or as_of > s.expected + timedelta(days=_STALE)
    s.status = "bitti" if over else "devam"


def paid_after_cancel(s: Series, ended: dict[str, str]) -> list[Transaction]:
    """The payments of a series after the month the user's rules (`_biten`) give its payee as the last one; none
    when they give it none."""
    cancelled = ended.get(fold(s.merchant))
    return [t for t in s.payments if month_of(t.date) > cancelled] if cancelled else []


def _outgoing(ds: Dataset) -> list[Transaction]:
    """The payments a series can be made of: purchases, savings and loan principal, an installment's never; a split
    row whole."""
    return [
        t
        for t in payments(ds)
        if t.kind in (TransactionKind.PURCHASE, TransactionKind.INVESTMENT, TransactionKind.LOAN_PRINCIPAL)
        and t.amount > 0
        and not t.installment
    ]


def regular_payments(ds: Dataset, tl_: Timeline) -> tuple[list[Series], list[Series]]:
    """(outgoing series, income series), running ones and larger amounts first."""
    inc = [t for t in payments(ds) if t.kind == TransactionKind.INCOME and t.amount < 0]
    result = []
    for group in (find_series(_outgoing(ds), ds.regular), find_series(inc, set())):
        for s in group:
            settle(s, tl_.seen_until, ds.ended, tl_.as_of)
        result.append(sorted(group, key=lambda s: (not s.running, -s.monthly)))
    return result[0], result[1]


def listed(s: Series, ds: Dataset, window: list[str]) -> bool:
    """Whether a series belongs on the list of regular payments: a running one, or one that ended or was cancelled
    within the window; an ended purchase only when it was a commitment (a bill, not a shop visited monthly)."""
    recent = month_of(s.last.date) >= window[0]
    if s.status == "bitti":
        return recent and (s.last.category in ds.regular or s.last.kind != TransactionKind.PURCHASE)
    return s.running or (s.status == "iptal" and recent)


# --- periodic payments ------------------------------------------------------------------------------------
# The V1 draft rule (docs/domain/interpretation.md, "Dönemsel seriler"): its thresholds are to be tuned with real data.

PERIODS = {SeriesPeriod.HALF_YEAR: (160, 200), SeriesPeriod.YEAR: (330, 400)}  # days between two payments
# Outside commitment categories a periodic payment may move this much: a yearly price rise, not another purchase.
_PERIODIC_CHANGE = Decimal("0.50")


def period_of(gap: int) -> SeriesPeriod | None:
    """The period a gap of so many days between two payments keeps, if any."""
    return next((p for p, (low, high) in PERIODS.items() if low <= gap <= high), None)


@dataclass
class PeriodicSeries(Series):
    """Payments to one payee about half a year or a year apart: an insurance, a car tax, a yearly subscription."""

    period: SeriesPeriod = SeriesPeriod.YEAR

    @property
    def per_period(self) -> Decimal:
        """The amount to expect next: the last one. A periodic price moves once a period, so the last payment
        already carries the latest price (a yearly subscription after its price rise)."""
        return self.amount

    @property
    def grace(self) -> int:
        """A periodic payment may come as late as its period allows (up to 200 days after the last for half a year,
        400 for a year) before the series counts as over."""
        return max(super().grace, PERIODS[self.period][1] - self.cadence)

    def price_change(self) -> tuple[Decimal, Decimal, date] | None:
        """(previous amount, last amount, the last payment's day) when the last payment moved more than 5%: a
        periodic price holds for a whole period, so one payment at it is enough. A foreign price is compared in its
        own currency, as Series.price_change does."""
        if len(self.payments) < 2:
            return None
        old = abs(self.payments[-2].amount)
        billed = _billed_tail(self.payments)
        before, after = (billed[-2], billed[-1]) if len(billed) >= 2 else (old, self.amount)
        return (old, self.amount, self.last.date) if _change(before, after) > Decimal("0.05") else None


def _periodic_chain(payee: str, items: list[Transaction]) -> list[PeriodicSeries]:
    """Series of payments within ±50% of each other a period apart. A payment continues a series only from the
    newest earlier payment at such an amount: a shop paid similar amounts in between is no periodic commitment."""
    series: list[PeriodicSeries] = []
    for i, t in enumerate(items):
        before = next((p for p in reversed(items[:i]) if _change(p.amount, t.amount) <= _PERIODIC_CHANGE), None)
        period = period_of((t.date - before.date).days) if before else None
        owner = next((s for s in series if s.last is before), None) if before else None
        if owner and period and (len(owner.payments) == 1 or owner.period == period):
            owner.period = period
            owner.payments.append(t)
        else:
            series.append(PeriodicSeries(payee, [t]))
    return series


def find_periodic(txns: list[Transaction], regular: set[str]) -> list[PeriodicSeries]:
    """Periodic series per payee: at least two payments about 182 (160–200) or 365 (330–400) days apart.

    In commitment categories (`regular`) a payee paid once a period is one series whatever the amounts (a car tax
    moves with its base), as a once-a-month bill is; elsewhere, and where the payee is paid more often, the amounts
    stay within ±50% of each other (chained as in _periodic_chain). A payee paid more than five times a month is a
    shop, as for the monthly series.
    """
    by_payee: dict[str, list[Transaction]] = defaultdict(list)
    for t in txns:
        by_payee[t.merchant].append(t)
    found: list[PeriodicSeries] = []
    for payee, items in by_payee.items():
        items.sort(key=lambda t: t.date)
        if len(items) < 2 or len(items) / _months(items) > _BUSY:
            continue
        periods = [period_of((b.date - a.date).days) for a, b in pairwise(items)]
        once = periods[0] if all(p == periods[0] for p in periods) else None
        if items[-1].category in regular and once is not None:
            found.append(PeriodicSeries(payee, items, period=once))
            continue
        found += [s for s in _periodic_chain(payee, items) if len(s.payments) >= 2]
    return found


def periodic_payments(ds: Dataset, tl_: Timeline, monthly: list[Series]) -> list[PeriodicSeries]:
    """Periodic series among the payments no monthly series took, settled with the monthly series' rules (the
    expected day a period after the last payment); running ones and larger amounts first."""
    taken = {id(t) for s in monthly for t in s.payments}
    found = find_periodic([t for t in _outgoing(ds) if id(t) not in taken], ds.regular)
    for s in found:
        settle(s, tl_.seen_until, ds.ended, tl_.as_of)
    return sorted(found, key=lambda s: (not s.running, -s.per_period))


# --- habits -----------------------------------------------------------------------------------

HABIT_STATUS = {
    "duzenli": "Her ay",
    "yeni": "Yeni alışkanlık",
    "ara_sira": "Ara sıra",
    "durdu": "Durdu",
    "tek": "Tek seferlik",
}
_STOPPED_DAYS = 60


@dataclass
class Habit:
    """Discretionary spending at one merchant, or avoidable costs of one category."""

    name: str
    category: str
    necessity: Necessity | None
    by_category: bool
    count: int  # purchases in the window
    months: int  # months of the window with a purchase
    span: int  # months in the window
    total: Decimal  # spent in the window
    recent: Decimal  # monthly average of the last three complete months
    first: date  # first purchase in all the data
    last: date
    status: str = ""
    since: str = ""  # month a new habit started
    idle: int = 0  # days from the last purchase to the newest statement of its cards
    low: Decimal = ZERO  # smallest and largest purchase in the window
    high: Decimal = ZERO

    @property
    def monthly(self) -> Decimal:
        """What the habit costs per month from now on, as far as the data tells."""
        if self.status in ("duzenli", "yeni"):
            return self.recent
        if self.status == "ara_sira":
            return self.total / self.span
        return ZERO

    @property
    def pattern(self) -> str:
        what = "işlem" if self.by_category else "alışveriş"
        amounts = (
            f", tutarlar {tl(self.low)}–{tl(self.high)}"
            if not self.by_category and self.count >= 3 and self.high > self.low * Decimal("1.2")
            else ""
        )
        if self.status == "yeni":
            return f"{since(self.since)}, {self.count} {what}{amounts}"
        if self.status == "durdu":
            return f"son {what} {_day(self.last)}"
        if self.status == "tek":
            return f"{self.count} {what}, {_day(self.last)}"
        return f"{self.span} ayın {self.months} ayında, {self.count} {what}{amounts}"


def _classify(h: Habit, window: list[str], silence: int, stopped: bool) -> None:
    """silence: days without a purchase after which this merchant counts as given up."""
    since_first = [m for m in window if m >= month_of(h.first)]
    if stopped or (h.months >= 2 and h.idle > silence):
        h.status = "durdu"
    elif h.count == 1 or (h.months == 1 and h.count <= 2):
        h.status = "tek"
    elif month_of(h.first) > window[0] and h.months >= 3 and h.months >= 0.75 * len(since_first):
        h.status, h.since = "yeni", month_of(h.first)
    elif h.months >= 0.75 * len(window):
        h.status = "duzenli"
    else:
        h.status = "ara_sira"


def _per_payment(items: list[Transaction]) -> list[Transaction]:
    """A habit's purchases: the parts of a split row in it are one purchase of their sum."""
    merged: dict[object, Transaction] = {}
    for t in items:
        key = t.split_of or id(t)
        merged[key] = replace(merged[key], amount=merged[key].amount + t.amount) if key in merged else t
    return list(merged.values())


def habits(ds: Dataset, tl_: Timeline, series: list[Series]) -> list[Habit]:
    """Discretionary merchants and avoidable cost categories seen in the window. Payees with a
    regular payment are left out: their extra charges are add-ons, not a habit."""
    window = set(tl_.window)
    recent = set(tl_.window[-3:])
    payees = {s.merchant for s in series}
    groups: dict[tuple[str, bool], list[Transaction]] = defaultdict(list)
    for t in ds.transactions:
        if (
            t.merchant in payees
            or t.amount <= 0
            or t.kind not in (TransactionKind.PURCHASE, TransactionKind.INTEREST_FEE)
        ):
            continue
        if t.necessity == AVOIDABLE:
            groups[(t.category, True)].append(t)
        elif t.necessity == OPTIONAL:
            groups[(t.merchant, False)].append(t)
    found = []
    for (name, by_category), parts in groups.items():
        items = _per_payment(parts)
        inside = [t for t in items if month_of(t.date) in window]
        if not inside:
            continue
        h = Habit(
            name=name,
            category=items[-1].category,
            necessity=items[-1].necessity,
            by_category=by_category,
            count=len(inside),
            months=len({month_of(t.date) for t in inside}),
            span=len(window),
            total=sum((t.amount for t in inside), ZERO),
            recent=sum((t.amount for t in inside if month_of(t.date) in recent), ZERO) / len(recent),
            first=min(t.date for t in items),
            last=max(t.date for t in items),
            low=min(t.amount for t in inside),
            high=max(t.amount for t in inside),
        )
        h.idle = (max(tl_.seen_until.get(t.account, h.last) for t in items) - h.last).days
        days = sorted({t.date for t in items})
        usual_gap = median((b - a).days for a, b in pairwise(days)) if len(days) > 1 else 0
        _classify(h, tl_.window, max(_STOPPED_DAYS, 2 * usual_gap), not by_category and fold(name) in ds.ended)
        found.append(h)
    return sorted(found, key=lambda h: (-h.monthly, -h.total))


# --- what changed -------------------------------------------------------------------------


@dataclass
class Change:
    category: str
    before: Decimal  # monthly average
    recent: Decimal


@dataclass
class Trend:
    before: list[str]
    recent: list[str]
    before_avg: Decimal
    recent_avg: Decimal
    usual_before: Decimal  # without large single purchases
    usual_recent: Decimal
    changes: list[Change]  # largest movers first
    big: list[Transaction]  # large single purchases in the window, largest first


def _expenses(ds: Dataset, months: set[str]) -> list[Transaction]:
    return [t for t in ds.transactions if t.kind in DEFAULT_EXPENSE_KINDS and month_of(t.date) in months]


LARGE_PURCHASE = Decimal(5000)  # TL: a single purchase this large is large, however much is spent in a month
LARGE_SHARE = Decimal("0.1")  # or this share of the window's average month of spending, when that is more


def large_purchase_threshold(ds: Dataset, window: list[str]) -> Decimal:
    """The amount from which a single purchase counts as large (docs/domain/interpretation.md, "Tahmin"): 5.000 TL,
    or a tenth of the window's average month of spending when that is more."""
    if not window:
        return LARGE_PURCHASE
    average = sum((t.amount for t in _expenses(ds, set(window))), ZERO) / len(window)
    return max(LARGE_PURCHASE, LARGE_SHARE * average)


def trend(ds: Dataset, tl_: Timeline, in_series: set[int]) -> Trend | None:
    n = len(tl_.window)
    k = 6 if n >= 9 else n // 2
    if k < 2:
        return None
    recent, before = tl_.window[-k:], tl_.window[:-k][-6:]
    spent = _expenses(ds, set(tl_.window))
    threshold = large_purchase_threshold(ds, tl_.window)
    # A large purchase is a whole payment: a split one is large as a whole, and all its parts leave the averages.
    wholes = list({id(w): w for w in (whole(ds, t) for t in spent)}.values())
    big = sorted(
        (t for t in wholes if t.kind == TransactionKind.PURCHASE and id(t) not in in_series and t.amount >= threshold),
        key=lambda t: -t.amount,
    )

    def avg(months: list[str], skip: set[int] = frozenset()) -> Decimal:
        inside = set(months)
        return sum((t.amount for t in spent if month_of(t.date) in inside and id(t) not in skip), ZERO) / len(months)

    large = {id(t) for t in big}
    skip = {id(t) for t in spent if id(whole(ds, t)) in large}
    by_cat: dict[str, list[Decimal]] = defaultdict(lambda: [ZERO, ZERO])
    for t in spent:
        if id(t) in skip:
            continue
        m = month_of(t.date)
        if m in before:
            by_cat[t.category][0] += t.amount / len(before)
        elif m in recent:
            by_cat[t.category][1] += t.amount / len(recent)
    changes = sorted((Change(c, b, r) for c, (b, r) in by_cat.items()), key=lambda c: -abs(c.recent - c.before))
    return Trend(before, recent, avg(before), avg(recent), avg(before, skip), avg(recent, skip), changes[:8], big)


# --- money in and out ---------------------------------------------------------------------


@dataclass
class Flow:
    """Monthly averages over the window."""

    months: list[str]
    income: Decimal
    expense: Decimal
    people: Decimal  # money sent to other people
    debt: Decimal  # debt principal repaid
    saving: Decimal  # pension and other investments
    fx: Decimal  # foreign currency and gold bought (+) or sold (-) with TL
    unnamed_people: Decimal  # sent to people the statement does not name (bank name only)
    debt_start: Decimal = ZERO  # card statement balances and overdraft use before the window
    debt_end: Decimal = ZERO  # and at its end
    other_typical: Decimal = ZERO  # median month of money to people and debt repaid, last six months

    @property
    def left(self) -> Decimal:
        return self.income - self.expense - self.people - self.debt - self.saving


def flow(ds: Dataset, tl_: Timeline) -> Flow | None:
    months = set(tl_.window)
    if not any(ds.accounts[a].type not in NOT_BANK_ACCOUNTS for a in ds.coverage):
        return None
    sums: dict[str, Decimal] = defaultdict(Decimal)
    for t in ds.transactions:
        if month_of(t.date) not in months:
            continue
        key = "expense" if t.kind in DEFAULT_EXPENSE_KINDS else t.kind
        sums[key] += t.amount
        if (
            t.kind == TransactionKind.OWN_TRANSFER
            and t.category == FX_CATEGORY
            and ds.accounts[t.account].currency == TRY
        ):
            sums["fx"] += t.amount
        if t.kind == TransactionKind.P2P_TRANSFER and _bank_name(t.merchant):
            sums["unnamed"] += t.amount
    n = len(months)
    base = tl_.window[-6:]
    other = dict.fromkeys(base, ZERO)
    for t in ds.transactions:
        if t.kind in (TransactionKind.P2P_TRANSFER, TransactionKind.LOAN_PRINCIPAL) and month_of(t.date) in other:
            other[month_of(t.date)] += t.amount
    return Flow(
        sorted(months),
        -sums[TransactionKind.INCOME] / n,
        sums["expense"] / n,
        sums[TransactionKind.P2P_TRANSFER] / n,
        sums[TransactionKind.LOAN_PRINCIPAL] / n,
        sums[TransactionKind.INVESTMENT] / n,
        sums["fx"] / n,
        sums["unnamed"] / n,
        debt_at(ds, month_end(shift(tl_.window[0], -1))),
        debt_at(ds, month_end(tl_.window[-1])),
        median(other.values()),
    )


def _bank_name(name: str) -> bool:
    f = fold(name)
    return f.endswith((" A.S.", " A.S", " T.A.O.", " T.A.O")) or " BANK" in f or "SUBE" in f


def salary_timing(income: list[Series], window: list[str]) -> tuple[list[str], list[str]]:
    """Months of the window without the main salary and months with two of them."""
    main = next((s for s in income if s.running), None)
    if not main:
        return [], []
    per_month = defaultdict(int)
    for t in main.payments:
        per_month[month_of(t.date)] += 1
    covered = [m for m in window if month_of(main.payments[0].date) <= m]
    return [m for m in covered if not per_month[m]], [m for m in covered if per_month[m] >= 2]


# --- balances -------------------------------------------------------------------------------

SAVINGS = ("nakit", "vadeli", "doviz", "yatirim")  # holdings valued in TL that count as savings; gold counts at cost


@dataclass
class Holding:
    label: str
    kind: str  # "nakit", "vadeli", "kmh", "kart", "doviz", "altin", "yatirim"
    currency: str
    amount: Decimal  # in the account's currency; debt is negative
    value: Decimal | None  # in TL; None when no rate is known
    as_of: date
    note: str = ""
    cost: Decimal = ZERO  # TL paid for gold; its market price is not in the documents


def balance_rate(ds: Dataset, currency: str, amount: Decimal) -> DatedRate | None:
    """The TL rate a balance of amount in a foreign currency is valued at (docs/domain/interpretation.md, "Varlıklar
    ve borçlar"; architecture §15): the providers' newest, at the forex buying rate for an asset and at the selling
    rate for a debt (an overdraft below zero), as a bank would take or ask; without one, the newest rate the documents
    print, its day written. None without either."""
    quote = ds.book.newest(currency)
    if quote is not None:
        return DatedRate(quote.selling if amount < 0 else quote.buying, quote.day, quote.source)
    found = ds.rates.get(currency)
    if not found:
        return None
    day, rate = max(found)
    return DatedRate(rate, day, RateSource.DOCUMENT)


def provider_rate_said(r: DatedRate, selling: bool = False) -> str:
    """A provider's rate as the notes name it: "TCMB 03.11.2026 döviz alış kuru"; ECB's and Frankfurter's one rate
    a day stands for both sides: "ECB 03.11.2026 referans kuru"."""
    side = ("döviz satış" if selling else "döviz alış") if r.source is RateSource.TCMB else "referans"
    return f"{RATE_SOURCE[r.source]} {_day(r.day)} {side} kuru"


def _rate_note(r: DatedRate, debt: bool) -> str:
    if r.source is RateSource.DOCUMENT:
        return f"kur {r.rate:.2f} ({_day(r.day)} belgesinden)".replace(".", ",", 1)
    return f"kur {format_rate(r.rate)} ({provider_rate_said(r, debt)})"


def payments_after(ds: Dataset, card: str, cut: date) -> list[Transaction]:
    """The card payments after the statement's cut date: from bank accounts' lists, and from payment receipts
    (booked on the card itself) the next statement will show."""
    acc = ds.accounts[card]
    digits = acc.number[-4:]
    found = []
    for t in ds.transactions:
        if t.kind != TransactionKind.CARD_PAYMENT or t.date <= cut or t.amount <= 0:
            continue
        if t.account == card:
            if t.provisional:
                found.append(t)
            continue
        src = ds.accounts.get(t.account)
        if src and src.type not in CARD_TYPES and (digits in t.description or src.bank == acc.bank):
            found.append(t)
    return found


def paid_after(ds: Dataset, card: str, cut: date) -> Decimal:
    """What was paid on the card after the statement's cut date (payments_after)."""
    return sum((t.amount for t in payments_after(ds, card, cut)), ZERO)


def _waiting(ds: Dataset) -> dict[str, list[ReceiptLine]]:
    """Receipt rows no statement shows yet, per account."""
    out: dict[str, list[ReceiptLine]] = defaultdict(list)
    for line in ds.receipts:
        if line.status == PROVISIONAL:
            out[line.txn.account].append(line)
    return out


def _with_receipts(h: "Holding", lines: list[ReceiptLine], rate: Decimal | None) -> None:
    """Move a balance by the receipts that came after its statement (money out lowers it)."""
    if not lines:
        return
    change = -round_half_up(sum((line.native for line in lines), ZERO))
    stated = h.amount
    h.amount = round_half_up(h.amount + change)
    if h.currency == TRY:
        h.value = h.amount
        moved, before = ("+" if change > 0 else "−") + tl(abs(change)), tl(stated)
    else:
        h.value = round_half_up(h.amount * rate) if rate else None
        moved = ("+" if change > 0 else "−") + f"{format_amount(abs(change))} {h.currency}"
        before = f"{format_amount(stated)} {h.currency}"
    h.note = (
        f"{_day(h.as_of)} dökümünde {before}; sonraki {len(lines)} dekontla {moved} (geçici, döküm gelince "
        "kesinleşir)" + (f"; {h.note}" if h.note else "")
    )
    h.as_of = max(h.as_of, max(line.txn.date for line in lines))


_STALE_DAYS = 180  # a balance this much older than the newest statement says nothing about today


def _stocks(label: str, s) -> Holding:
    """A brokerage account: its securities at the market value the statement prints, plus its cash."""
    worth = round_half_up(sum((x.value for x in s.securities), ZERO) + (s.total or ZERO))
    as_of = max((x.as_of for x in s.securities), default=s.cut_date)
    held = ", ".join(f"{x.code} {float(x.quantity):g} adet".replace(".", ",") for x in s.securities)
    note = f"{held}; {_day(as_of)} piyasa değeriyle" if held else "hisse senedi yok"
    return Holding(label, "yatirim", TRY, worth, worth, as_of, note + (f"; nakit {tl(s.total)}" if s.total else ""))


def holdings(ds: Dataset) -> list[Holding]:
    latest: dict[str, object] = {}
    for s in ds.statements:
        a = ds.accounts[s.account]
        if s.total is None or (not s.is_account and (a.type != AccountType.CREDIT_CARD or s.currency != TRY)):
            continue
        if s.account not in latest or s.cut_date > latest[s.account].cut_date:
            latest[s.account] = s
    newest = max((s.cut_date for s in ds.statements), default=None)
    waiting = _waiting(ds)
    out = []
    for account, s in latest.items():
        a = ds.accounts[account]
        if not s.is_account:
            paid = paid_after(ds, account, s.cut_date)
            owed = max(ZERO, s.total - paid)
            note = f"{_day(s.cut_date)} ekstresi {tl(s.total)}" + (f"; sonra {tl(paid)} ödendi" if paid >= 1 else "")
            h = Holding(a.label, "kart", TRY, -owed, -owed, s.cut_date, note)
        elif a.type == AccountType.BROKERAGE:
            h = _stocks(a.label, s)
        elif a.type == AccountType.GOLD:
            paid = sum(
                (
                    t.amount
                    for t in ds.transactions
                    if t.category == FX_CATEGORY
                    and "ALTIN" in fold(t.description)
                    and ds.accounts[t.account].bank == a.bank
                    and ds.accounts[t.account].currency == TRY
                ),
                ZERO,
            )
            note = (
                f"alışta ödenen {tl(paid)}; güncel fiyat belgelerde yok" if paid >= 1 else "güncel fiyat belgelerde yok"
            )
            h = Holding(a.label, "altin", "gr", s.total, None, s.cut_date, note, max(ZERO, paid))
        elif a.currency != TRY:
            lines = waiting.get(account, [])
            # The receipts after the list move the balance (_with_receipts): an asset or a debt is what it comes to.
            after = round_half_up(s.total - round_half_up(sum((line.native for line in lines), ZERO)))
            rate = balance_rate(ds, a.currency, after)
            value = round_half_up(s.total * rate.rate) if rate else None
            note = _rate_note(rate, after < 0) if rate else "kur bulunamadı"
            h = Holding(a.label, "doviz", a.currency, s.total, value, s.cut_date, note)
            _with_receipts(h, lines, rate.rate if rate else None)
        else:
            h = Holding(a.label, "nakit", TRY, s.total, s.total, s.cut_date)
            _with_receipts(h, waiting.get(account, []), None)
            h.kind = "kmh" if h.amount < 0 or a.type == AccountType.OVERDRAFT else "nakit"
            h.kind = "vadeli" if h.kind == "nakit" and a.type == AccountType.DEPOSIT else h.kind
        if newest and (newest - s.cut_date).days > _STALE_DAYS:
            # E.g. a term deposit known only from the passbook sent when it was opened.
            h.value, h.cost = None, ZERO
            h.note = f"son belge {_day(s.cut_date)}; bugünkü bakiyesi belgelerde yok"
        out.append(h)
    order = {"nakit": 0, "vadeli": 1, "doviz": 2, "yatirim": 3, "altin": 4, "kmh": 5, "kart": 6}
    return sorted(out, key=lambda h: (order[h.kind], -(h.value or ZERO)))


def debt_at(ds: Dataset, day: date) -> Decimal:
    """Card statement balances and overdraft use on a day, as far as the statements show. Before
    a card's first statement its opening balance stands in, if that statement is near."""
    cards: dict[str, list] = defaultdict(list)
    balances: dict[str, dict[str, Decimal]] = defaultdict(dict)
    for s in ds.statements:
        a = ds.accounts[s.account]
        if not s.is_account and a.type == AccountType.CREDIT_CARD and s.currency == TRY and s.total is not None:
            cards[s.account].append(s)
        elif s.is_account and a.currency == TRY:
            balances[s.account].update(s.balances)
    total = ZERO
    for stmts in cards.values():
        stmts.sort(key=lambda s: s.cut_date)
        before = [s for s in stmts if s.cut_date <= day]
        if before:
            total += max(ZERO, before[-1].total)
        elif stmts[0].cut_date <= day + timedelta(days=45):
            total += max(ZERO, stmts[0].previous or ZERO)
    month = month_of(day)
    for months in balances.values():
        known = [m for m in months if m <= month]
        if known:
            total += max(ZERO, -months[max(known)])
    return total


def month_end(month: str) -> date:
    return date.fromisoformat(shift(month, 1) + "-01") - timedelta(days=1)


def overdraft_history(ds: Dataset, window: list[str]) -> dict[str, dict[str, Decimal]]:
    """Month-end balances of overdraft (KMH) accounts in the window, by label."""
    out: dict[str, dict[str, Decimal]] = {}
    for s in ds.statements:
        a = ds.accounts[s.account]
        if s.is_account and a.currency == TRY and a.type in (AccountType.OVERDRAFT, AccountType.CURRENT):
            months = {m: v for m, v in s.balances.items() if m in window}
            if any(v < -1 for v in months.values()):
                out.setdefault(a.label, {}).update(months)
    return out


# --- findings and steps -----------------------------------------------------------------------


@dataclass
class Finding:
    tone: str  # "dikkat", "bilgi", "iyi"
    title: str
    text: str
    # What the report shows on click: merchant / category / kind / provisional.
    filter: dict[str, object] = field(default_factory=dict[str, object])


@dataclass
class Step:
    title: str
    text: str
    monthly: Decimal = ZERO  # money freed per month; 0 when it depends on a choice the data cannot price


@dataclass
class BudgetLine:
    label: str
    now: Decimal
    plan: Decimal
    note: str = ""


@dataclass
class Insights:
    timeline: Timeline
    series: list[Series]
    income: list[Series]
    habits: list[Habit]
    trend: Trend | None
    flow: Flow | None
    holdings: list[Holding]
    findings: list[Finding] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    budget: list[BudgetLine] = field(default_factory=list)
    # Half-yearly and yearly payments; kept apart from the monthly series, which the findings and the budget use.
    periodic: list[PeriodicSeries] = field(default_factory=list)


@dataclass
class _Context:
    """Numbers several findings and steps share."""

    ds: Dataset
    ins: Insights
    in_series: set[int]
    expenses: list[Transaction]  # window
    salary: Series | None
    savings: Decimal  # cash, term deposits, foreign currency, stocks at market value and gold at cost
    debts: Decimal  # overdraft and card debt, positive

    @property
    def window(self) -> list[str]:
        return self.ins.timeline.window

    @property
    def base(self) -> list[str]:
        """Months the typical (median) month is taken from."""
        return self.window[-6:]

    def recent_avg(self, pred) -> Decimal:
        last3 = set(self.window[-3:])
        picked = (t.amount for t in self.expenses if month_of(t.date) in last3 and pred(t))
        return sum(picked, ZERO) / min(3, len(self.window))

    def typical(self, pred) -> Decimal:
        """Median month of the expenses pred accepts, over the base months."""
        totals = dict.fromkeys(self.base, ZERO)
        for t in self.expenses:
            m = month_of(t.date)
            if m in totals and pred(t):
                totals[m] += t.amount
        return median(totals.values()) if totals else ZERO

    def level(self, level: Necessity, work: bool = False) -> Decimal:
        """Typical month of one necessity level without regular payments (and without work costs)."""
        return self.typical(
            lambda t: (
                (t.necessity or Necessity.UNKNOWN) == level
                and id(t) not in self.in_series
                and (work or t.category not in WORK_CATEGORIES)
            )
        )


def _window_text(window: list[str]) -> str:
    return f"{month_name(window[0])} – {month_name(window[-1])}"


def _decimal(value: Decimal) -> str:
    return f"{value:.1f}".replace(".", ",")


def interpret(ds: Dataset) -> Insights:
    tl_ = timeline(ds)
    series, income = regular_payments(ds, tl_)
    in_series = {id(t) for s in series for t in s.payments}
    in_series |= {id(t) for t in ds.transactions if t.split_of and id(whole(ds, t)) in in_series}  # their parts
    held = holdings(ds)
    ins = Insights(tl_, series, income, habits(ds, tl_, series), trend(ds, tl_, in_series), flow(ds, tl_), held)
    ins.periodic = periodic_payments(ds, tl_, series)
    savings = sum((h.value or ZERO for h in held if h.kind in SAVINGS), ZERO) + sum((h.cost for h in held), ZERO)
    debts = -sum((h.value or ZERO for h in held if h.kind in ("kmh", "kart") and (h.value or ZERO) < 0), ZERO)
    ctx = _Context(
        ds, ins, in_series, _expenses(ds, set(tl_.window)), next((s for s in income if s.running), None), savings, debts
    )
    # Most telling first: where the month ends, debt and savings, what changed and why.
    for write in (
        _balance,
        _debt_finding,
        _position_finding,
        _receipts_finding,
        _change_finding,
        _habit_finding,
        _fees_finding,
        _overdraft_finding,
        _regular_findings,
        _people_finding,
        _salary,
    ):
        write(ctx)
    _write_steps(ctx)
    _write_budget(ctx)
    return ins


def _top_habit(ins: Insights) -> Habit | None:
    return next((h for h in ins.habits if not h.by_category and h.status in ("duzenli", "yeni")), None)


def _by_payee(series: list[Series]) -> list[tuple[str, Decimal, int]]:
    """(payee, monthly total, number of series), largest first: two YouTube payments are one line."""
    totals: dict[str, list] = {}
    for s in series:
        entry = totals.setdefault(s.merchant, [ZERO, 0])
        entry[0] += s.monthly
        entry[1] += 1
    return sorted(((m, v, n) for m, (v, n) in totals.items()), key=lambda x: -x[1])


def _payee_list(series: list[Series], limit: int = 5) -> str:
    return ", ".join(f"{m}{f' ({n} ödeme)' if n > 1 else ''} {tl(v)}" for m, v, n in _by_payee(series)[:limit])


def _balance(c: _Context) -> None:
    fl = c.ins.flow
    if not fl:
        return
    share = fl.expense / fl.income if fl.income else 0
    text = (
        f"{_window_text(c.window)} arasındaki {len(c.window)} tam ayda ortalama gelir {tl(fl.income)}, gider "
        f"{tl(fl.expense)} (gelirin {pct(share)}). Kişilere gönderilen {tl(fl.people)}, borç ödemesi "
        f"{tl(fl.debt)} ve BES/birikim {tl(fl.saving)} de düşülünce ayda {tl(fl.left)} kalıyor."
    )
    tone = "iyi" if fl.left >= Decimal("0.15") * fl.income else "dikkat"
    c.ins.findings.append(Finding(tone, "Gelir ve gider dengesi", text))


def _debt_finding(c: _Context) -> None:
    fl = c.ins.flow
    if not fl or (fl.debt_start < 1 and fl.debt_end < 1):
        return
    months = len(c.window)
    before = month_name(shift(c.window[0], -1))
    change = fl.debt_end - fl.debt_start
    text = (
        f"Kart ekstre borçları ve ek hesap kullanımı {before} sonunda {tl(fl.debt_start)}, "
        f"{month_name(c.window[-1])} sonunda {tl(fl.debt_end)} ({'+' if change > 0 else ''}{tl(change)})."
    )
    bought = fl.fx * months
    if bought >= 1 and fl.debt_end > fl.debt_start:
        text += (
            f" Aynı {months} ayda {tl(bought)} döviz ve altın alındı; yani birikimin önemli bir kısmı borç "
            "büyürken yapıldı. Borcun faizi bu birikimin getirisinden yüksek olduğu için önce borcu kapatmak "
            "daha kârlı."
        )
    text += f" {_day(c.ins.timeline.as_of)} itibarıyla borç {tl(c.debts)}."
    extra = _extra_income(c)
    if extra:
        text += f" {months_in(extra[2])} (henüz eksik ay) maaş dışında {tl(extra[1])} gelir girdi ({extra[0]})."
    salary = c.salary.amount if c.salary else ZERO
    tone = "dikkat" if fl.debt_end > fl.debt_start or c.debts > Decimal("0.5") * salary else "iyi"
    c.ins.findings.append(Finding(tone, "Borç nasıl değişti", text))


def _extra_income(c: _Context) -> tuple[str, Decimal, list[str]] | None:
    """Large income after the last complete month that is not the salary: (payers, total, months)."""
    last = c.ins.timeline.last_complete
    salary = c.salary.merchant if c.salary else None
    found: dict[str, Decimal] = defaultdict(Decimal)
    months = set()
    for t in c.ds.transactions:
        if t.kind == TransactionKind.INCOME and month_of(t.date) > last and t.merchant != salary:
            found[t.merchant] -= t.amount
            months.add(month_of(t.date))
    total = sum(found.values(), ZERO)
    if not c.salary or total < Decimal("0.5") * c.salary.amount:
        return None
    payers = ", ".join(m for m, v in sorted(found.items(), key=lambda kv: -kv[1]) if v >= Decimal("0.1") * total)
    return payers, total, sorted(months)


def _salary(c: _Context) -> None:
    if not c.salary:
        return
    missing, double = salary_timing(c.ins.income, c.window)
    if not (missing or double):
        return
    parts = []
    if missing:
        parts.append(f"{months_in(missing)} hiç")
    if double:
        parts.append(f"{months_in(double)} iki kez")
    text = (
        f"{c.salary.merchant} ödemesi ayın başına ya da sonuna denk geldiği için {', '.join(parts)} görünüyor. "
        f"Aylık gelir tablosundaki iniş çıkışların sebebi bu; tahminde düzenli gelir {tl(c.salary.amount)} sayıldı."
    )
    c.ins.findings.append(
        Finding("bilgi", "Maaş takvimi", text, {"merchant": c.salary.merchant, "kind": TransactionKind.INCOME})
    )


def _change_finding(c: _Context) -> None:
    tr = c.ins.trend
    if not tr or tr.before_avg <= 0:
        return
    delta = tr.recent_avg / tr.before_avg - 1
    points = int(f"{abs(delta) * 100:.0f}")
    # A change that rounds to no point is said as such: "%0 artış" reads as if it were measured to be none.
    moved = "neredeyse aynı" if points == 0 else f"%{points} {'artış' if delta >= 0 else 'düşüş'}"
    text = (
        f"Son {len(tr.recent)} tam ayda aylık gider ortalaması {tl(tr.recent_avg)}, önceki {len(tr.before)} ayda "
        f"{tl(tr.before_avg)} ({moved})."
    )
    big = [t for t in tr.big if month_of(t.date) in tr.recent]
    if big:
        # Both windows' averages without them, each named: an arrow between two figures left the reader to guess.
        text += (
            " Büyük tek seferlik alışverişler ("
            + ", ".join(f"{t.merchant} {tl(t.amount)}" for t in big[:3])
            + f") çıkarılınca önceki {len(tr.before)} ay {tl(tr.usual_before)}, son {len(tr.recent)} ay "
            f"{tl(tr.usual_recent)}."
        )
    ups = [ch for ch in tr.changes if ch.recent - ch.before >= 500][:3]
    if ups:
        text += (
            " En çok artanlar: " + ", ".join(f"{ch.category} (ayda +{tl(ch.recent - ch.before)})" for ch in ups) + "."
        )
    usual = tr.usual_recent / tr.usual_before - 1 if tr.usual_before > 0 else delta
    c.ins.findings.append(Finding("dikkat" if usual > Decimal("0.15") else "bilgi", "Harcamalar nasıl değişti", text))


def _habit_finding(c: _Context) -> None:
    top = _top_habit(c.ins)
    if not top:
        return
    last3 = set(c.window[-3:])
    count = sum(1 for t in c.expenses if t.merchant == top.name and month_of(t.date) in last3)
    same = (t.amount for t in c.expenses if t.category == top.category and month_of(t.date) in last3)
    same_category = sum(same, ZERO) / 3
    text = (
        f"İsteğe bağlı harcamaların en büyüğü {top.name}: son 3 ayda ayda {tl(top.recent)}, "
        f"ayda ortalama {count / 3:.0f} alışveriş, alışveriş başına {tl(top.recent * 3 / max(1, count))}"
    )
    if same_category > top.recent * Decimal("1.05"):
        text += f"; {top.category} harcamasının {pct(top.recent / same_category)}"
    c.ins.findings.append(Finding("dikkat", "En büyük alışkanlık", text + ".", {"merchant": top.name}))


# How each kind of interest and fee is avoided: paying the debt in full avoids interest, not a transfer's fee.
_AVOIDED_BY = {
    "Kredi Kartı Faizi": "kart faizi, ekstre her ay tamamen ödenince önlenir",
    "Ek Hesap (KMH) Faizi": "ek hesap faizi, hesap eksiye düşürülmeyince önlenir",
    "Kredi Faizi": "kredi faizi, kredi erken kapatılınca azalır",
    CARD_FEES: "kart aidatı, aidatsız bir karta geçerek ya da iadesi istenerek önlenir",
    "Transfer & İşlem Ücretleri": "transfer ücretleri, ücretsiz transfer hakkı olan bir hesap ya da kanalla önlenir",
}
# The budget's word for the same, after "öneri:".
_AVOID_NOTE = {
    "Kredi Kartı Faizi": "borcu tam ödeyerek",
    "Ek Hesap (KMH) Faizi": "borcu tam ödeyerek",
    "Kredi Faizi": "krediyi erken kapatarak",
    CARD_FEES: "aidatsız kartla",
    "Transfer & İşlem Ücretleri": "ücretsiz transfer kanalıyla",
}


def _fees_finding(c: _Context) -> None:
    by_category: dict[str, Decimal] = defaultdict(Decimal)
    for t in c.expenses:
        if t.kind == TransactionKind.INTEREST_FEE:
            by_category[t.category] += t.amount
    total = sum(by_category.values(), ZERO)
    if total < 1:
        return
    ranked = [cat for cat, v in sorted(by_category.items(), key=lambda kv: -kv[1]) if v >= 1]
    parts = ", ".join(f"{cat} {tl(by_category[cat])}" for cat in ranked)
    text = (
        f"{_window_text(c.window)} arasındaki {len(c.window)} tam ayda {tl(total)}, ayda "
        f"{tl(total / len(c.window))}: {parts}."
    )
    if ways := [_AVOIDED_BY[cat] for cat in ranked if cat in _AVOIDED_BY]:
        advice = "; ".join(ways)
        text += f" {advice[0].upper()}{advice[1:]}."
    c.ins.findings.append(Finding("dikkat", "Faiz ve banka ücretleri", text, {"kind": TransactionKind.INTEREST_FEE}))


def _overdraft_finding(c: _Context) -> None:
    history = overdraft_history(c.ds, c.window)
    if not history:
        return
    parts = []
    for label, months in history.items():
        minus = [v for v in months.values() if v < -1]
        parts.append(
            f"{label} {len(c.window)} ayın {len(minus)} ayını eksi bakiyeyle kapattı "
            f"(ay sonu ortalaması {tl(sum(minus, ZERO) / len(minus))})"
        )
    text = "; ".join(parts) + "."
    rate = overdraft_rate(c.ds, c.window, history)
    if rate:
        text += f" Ödenen faize göre ek hesabın maliyeti ayda yaklaşık %{_decimal(rate * 100)}."
    c.ins.findings.append(Finding("dikkat", "Ek hesap (KMH) kullanımı", text, {"category": "Ek Hesap (KMH) Faizi"}))


def overdraft_rate(ds: Dataset, window: list[str], history: dict[str, dict[str, Decimal]]) -> Decimal | None:
    """Overdraft interest paid in the window over the month-end overdraft balances."""
    used = sum((-v for months in history.values() for v in months.values() if v < 0), ZERO)
    paid = sum((t.amount for t in _expenses(ds, set(window)) if t.category == "Ek Hesap (KMH) Faizi"), ZERO)
    return paid / used if used > 0 and paid > 0 else None


def _regular_findings(c: _Context) -> None:
    ins, window = c.ins, c.window
    running = [s for s in ins.series if s.running and s.last.kind == TransactionKind.PURCHASE]
    if running:
        optional = [s for s in running if s.last.necessity == OPTIONAL]
        text = f"{len(running)} düzenli ödeme ayda {tl(sum((s.monthly for s in running), ZERO))} tutuyor"
        if optional:
            chosen = sum((s.monthly for s in optional), ZERO)
            text += f"; bunun {tl(chosen)} kadarı isteğe bağlı ({_payee_list(optional, 4)})"
        text += "."
        changes = [(s, ch) for s in running if (ch := s.price_change()) and month_of(ch[2]) >= window[0]]
        if changes:
            text += (
                " Fiyatı artanlar: "
                + ", ".join(
                    f"{s.merchant} {tl(old)} → {tl(new)} ({month_name(month_of(when))})"
                    for s, (old, new, when) in changes[:4]
                    if new > old
                )
                + "."
            )
        ins.findings.append(
            Finding("bilgi", "Düzenli ödemeler ve abonelikler", text.replace(" Fiyatı artanlar: .", ""))
        )
    ended = [s for s in ins.series if s.status in ("bitti", "iptal") and month_of(s.last.date) >= window[0]]
    stopped = [s for s in ended if s.last.necessity != NEEDED]
    if stopped:
        text = (
            "Bitenler ve iptal ettikleriniz: "
            + ", ".join(f"{s.merchant} {tl(s.monthly)} (son ödeme {_day(s.last.date)})" for s in stopped[:6])
            + f". Ayda {tl(sum((s.monthly for s in stopped), ZERO))} tasarruf; tahmine girmiyorlar."
        )
        ins.findings.append(Finding("iyi", "Biten abonelikler", text))
    missing = [s for s in ended if s.last.necessity == NEEDED and s.status == "bitti"]
    if missing:
        text = (
            "Bir süredir hiçbir belgede görünmeyen düzenli ödemeler: "
            + ", ".join(f"{s.merchant} (son {_day(s.last.date)}, {tl(s.monthly)})" for s in missing)
            + ". Başka bir hesaptan ödeniyorsa o hesabın dökümünü de ekleyin; bittiyse Düzenli ödemeler ekranında "
            "“İptal ettim…” ile işaretleyin."
        )
        ins.findings.append(Finding("bilgi", "Görünmeyen faturalar", text))
    for s in (s for s in ins.series if s.status == "iptal_sonrasi"):
        cancelled = c.ds.ended[fold(s.merchant)]
        late = paid_after_cancel(s, c.ds.ended)
        ins.findings.append(
            Finding(
                "dikkat",
                f"{s.merchant}: iptalden sonra ödeme",
                f"Kişisel kurallarınızda son ödemenin {month_name(cancelled)} olduğu yazıyor ama sonrasında {len(late)} ödeme "
                f"daha alınmış (son {_day(late[-1].date)}, {tl(late[-1].amount)}). Aboneliği kontrol edin.",
                {"merchant": s.merchant},
            )
        )


def _people_finding(c: _Context) -> None:
    fl = c.ins.flow
    if not fl or fl.people < 1:
        return
    text = f"Kişilere ayda ortalama {tl(fl.people)} gönderildi"
    if fl.unnamed_people >= 1:
        text += (
            f"; bunun {tl(fl.unnamed_people)} kadarında belgede alıcının adı yok, yalnızca bankası yazıyor. "
            "Kime gittiğini kişisel kurallarınıza eklerseniz kira, aile ya da borç olarak ayrılır"
        )
    c.ins.findings.append(
        Finding("bilgi", "Kişilere gönderilen para", text + ".", {"kind": TransactionKind.P2P_TRANSFER})
    )


def _position_finding(c: _Context) -> None:
    held = c.ins.holdings
    if not held:
        return
    cash = sum((h.value or ZERO for h in held if h.kind in ("nakit", "vadeli", "doviz")), ZERO)
    parts = [f"nakit ve döviz {tl(cash)}"]
    for h in held:
        if h.kind == "altin" and h.amount > GOLD_DUST:
            grams = f"{h.amount:.2f}".replace(".", ",")
            parts.append(f"altın {grams} gr" + (f" (alışta {tl(h.cost)} ödendi)" if h.cost else ""))
        elif h.kind == "yatirim" and h.value:
            parts.append(f"hisse senedi {tl(h.value)} ({_day(h.as_of)} piyasa değeri)")
    text = (
        f"{_day(c.ins.timeline.as_of)} itibarıyla " + ", ".join(parts) + f"; ek hesap ve kart borcu {tl(c.debts)}. "
        "Hesap hesap ayrıntılar Döviz ekranındaki Varlıklar ve borçlar tablosunda."
    )
    c.ins.findings.append(Finding("iyi" if c.savings > c.debts else "dikkat", "Birikim ve borç durumu", text))


# How the rows a receipt brought before its statement read in a sentence, by kind.
_RECEIPT_KINDS = (
    ((TransactionKind.INCOME,), "gelen para"),
    ((TransactionKind.P2P_TRANSFER,), "kişilere giden"),
    (DEFAULT_EXPENSE_KINDS, "harcama ve ücret"),
    ((TransactionKind.LOAN_PRINCIPAL,), "kredi ödemesi"),
    ((TransactionKind.CARD_PAYMENT, TransactionKind.CARD_PAYMENT_NO_STATEMENT), "kart borcu ödemesi"),
    ((TransactionKind.INVESTMENT,), "birikim ve yatırım"),
    ((TransactionKind.CASH_ADVANCE,), "nakit çekim"),
    ((TransactionKind.OWN_TRANSFER,), "kendi hesaplarınız arasında"),
)


def receipt_amount(ds: Dataset, line: ReceiptLine) -> str:
    """A receipt row's amount as the receipt prints it: in TL, or in the account's currency."""
    currency = ds.accounts[line.txn.account].currency if line.txn.account in ds.accounts else TRY
    if currency == TRY:
        return tl(abs(line.native))
    return f"{format_amount(abs(line.native))} {currency}"


def _transfers_once(rows: list[Transaction]) -> list[Transaction]:
    """Provisional transfers between one's own accounts, each once. When both ends of a transfer wait for their
    lists, the money shows going out of one account and the same money coming into another, a few days apart at
    most; the ledger names both as one's own without pairing them, and their signed sum is nothing."""
    outs = [t for t in rows if t.amount > 0]
    once, left = list(outs), list(outs)
    for t in (t for t in rows if t.amount < 0):
        twin = next(
            (
                o
                for o in left
                if o.account != t.account
                and abs(o.amount + t.amount) <= CENT
                and abs((o.date - t.date).days) <= POSTING_DAYS[1]
            ),
            None,
        )
        if twin is None:
            once.append(t)
        else:
            left = [o for o in left if o is not twin]
    return once


def _receipts_finding(c: _Context) -> None:
    rows = [t for t in c.ds.transactions if t.provisional]
    if rows:
        own = [t for t in rows if t.kind == TransactionKind.OWN_TRANSFER]
        made_of = [t for t in rows if t.kind != TransactionKind.OWN_TRANSFER] + _transfers_once(own)
        parts = []
        for kinds, label in _RECEIPT_KINDS:
            found = [t for t in made_of if t.kind in kinds]
            if kinds == (TransactionKind.OWN_TRANSFER,):
                total = sum((abs(t.amount) for t in found), ZERO)  # how much moved, not where to
            else:
                total = sum((t.amount for t in found), ZERO)
            if abs(total) >= 1:
                parts.append(f"{label} {tl(abs(total))}")
        first, last = min(t.date for t in rows), max(t.date for t in rows)
        when = _day(first) if first == last else f"{_day(first)}–{_day(last)}"
        made = len({t.split_of or id(t) for t in made_of})  # payments: a split row's parts are one, a transfer's ends
        listed = f": {', '.join(parts)}" if parts else ""
        text = (
            f"Son ekstre ve hesap dökümlerinden sonra gelen dekontlardan {made} işlem şimdiden işlendi "
            f"({when}){listed}. Bakiyeler ve kart borcu bunlarla güncellendi; ekstre ya da döküm gelince "
            "satırlarıyla eşleşip kesinleşecekler."
        )
        c.ins.findings.append(Finding("bilgi", "Ekstre gelmeden işlenen dekontlar", text, {"provisional": True}))
    missing = [line for line in c.ds.receipts if line.status == NOT_ON_STATEMENT]
    if missing:
        shown = ", ".join(
            f"{_day(line.txn.date)} {c.ds.accounts[line.txn.account].label} {receipt_amount(c.ds, line)}"
            for line in sorted(missing, key=lambda line: line.txn.date, reverse=True)[:4]
        )
        text = (
            f"{len(missing)} dekont satırı, aynı günleri kapsayan ekstrede ya da hesap dökümünde yok ({shown}). "
            "İşlem iptal edilmiş, başka bir hesaptan yapılmış ya da dekont başka bir hesaba yazılmış olabilir; "
            "toplamlara ekstredeki satırlar katıldı. Ay sonu raporunun kapanış bölümünde ayrıntısı var."
        )
        c.ins.findings.append(Finding("dikkat", "Ekstrede görünmeyen dekontlar", text))


def _optional_cut(c: _Context) -> tuple[Decimal, Decimal]:
    """(typical discretionary month without subscriptions and work costs, suggested cut)."""
    typical = c.level(OPTIONAL)
    top = _top_habit(c.ins)
    cut = max(Decimal("0.2") * typical, top.recent / 2 if top else ZERO)
    return typical, min(cut, typical)


def _write_steps(c: _Context) -> None:
    ins, window, steps = c.ins, c.window, c.ins.steps
    interest = c.recent_avg(lambda t: t.category in INTEREST)
    if interest >= 1:
        overdraft = -sum((h.amount for h in ins.holdings if h.kind == "kmh" and h.amount < 0), ZERO)
        text = (
            f"Son 3 ayda faize ayda {tl(interest)} gitti. Kart ekstresinin her ay tamamını ödeyin, ek hesabı "
            "sıfırlayıp eksiye düşürmeyin."
        )
        if overdraft >= 1 and c.savings >= overdraft:
            text += (
                f" Ek hesaplarda şu an {tl(overdraft)} borç var; birikiminizin bir kısmıyla kapatmak, o paranın "
                "getirisinden daha yüksek bir faizi keser."
            )
        steps.append(Step("Faiz ödemeyi bırakın", text, interest))

    fee_cards = {t.account for t in c.expenses if t.category == CARD_FEES}
    fees = sum((t.amount for t in c.expenses if t.category == CARD_FEES), ZERO)
    if len(fee_cards) >= 2 and fees >= 1:
        steps.append(
            Step(
                "Kart sayısını azaltın",
                f"{len(fee_cards)} kartınız {len(window)} ayda {tl(fees)} aidat ve kart ücreti kesti. Aidatsız "
                "bir karta geçin ya da az kullandıklarınızı kapatın.",
                fees / len(window),
            )
        )

    typical, cut = _optional_cut(c)
    if typical >= 1:
        top = _top_habit(ins)
        text = (
            f"Abonelikler dışındaki isteğe bağlı harcamalar son {len(c.base)} ayda tipik olarak ayda {tl(typical)}. "
            f"Ayda {tl(typical - cut)} sınırı koymak {tl(cut)} bırakır."
        )
        if top:
            text += (
                f" En kolay yer {top.name}: ayda {tl(top.recent)}; haftalık planlı alışverişle yarıya inmesi tek "
                f"başına {tl(top.recent / 2)} eder."
            )
        steps.append(Step("İsteğe bağlı harcamaya aylık sınır koyun", text, cut))

    subs = [
        s
        for s in ins.series
        if s.running
        and s.last.kind == TransactionKind.PURCHASE
        and s.last.necessity == OPTIONAL
        and s.last.category not in WORK_CATEGORIES
    ]
    if subs:
        steps.append(
            Step(
                "Abonelikleri gözden geçirin",
                f"İsteğe bağlı abonelikler ayda {tl(sum((s.monthly for s in subs), ZERO))}: {_payee_list(subs)}. "
                "İptal ettiklerinizi Düzenli ödemeler ekranında “İptal ettim…” ile işaretleyin; tahmin ona göre "
                "düşer.",
            )
        )

    work = c.recent_avg(lambda t: t.category in WORK_CATEGORIES)
    if work >= 500:
        last3 = set(window[-3:])
        names = sorted({t.merchant for t in c.expenses if t.category in WORK_CATEGORIES and month_of(t.date) in last3})
        steps.append(
            Step(
                "İşle ilgili ödemeleri ayırın",
                f"{', '.join(names[:5])} gibi yazılım, bulut ve muhasebe ödemeleri son 3 ayda ayda {tl(work)}. "
                "İşiniz içinse şirket hesabından ödenmesi kişisel bütçeyi o kadar rahatlatır.",
                work,
            )
        )

    if ins.flow and ins.flow.income > 0 and (ins.flow.people + ins.flow.debt) >= Decimal("0.1") * ins.flow.income:
        other = ins.flow.people + ins.flow.debt
        text = (
            f"Kişilere gönderilen para ve borç geri ödemeleri ayda ortalama {tl(other)}, gelirin "
            f"{pct(other / ins.flow.income)}. Hangisi kalıcı (aile desteği), hangisi geçici (borç iadesi) "
            "belirleyip bütçeye ayrı kalem olarak yazın; geçici olanlar bitince aynı tutarı birikime yönlendirin."
        )
        if ins.flow.debt >= 1:
            text += f" Borç iadesi ayda ortalama {tl(ins.flow.debt)}."
        steps.append(Step("Kişilere ve borca giden parayı planlayın", text))

    big = [t for t in (ins.trend.big if ins.trend else []) if t.necessity != NEEDED]
    if big:
        total = sum((t.amount for t in big), ZERO)
        on_card = sum(1 for t in big if c.ds.accounts[t.account].type == AccountType.CREDIT_CARD)
        # Only a credit card turns a large purchase into card debt: one paid from an account takes the month's money.
        if on_card == len(big):
            paid, spared = "tek seferde karttan ödendi", "kart borcunu ve faizi önler"
        elif on_card:
            paid, spared = f"tek seferde ödendi ({on_card} tanesi karttan)", "kart borcunu ve faizi önler"
        else:
            paid, spared = "tek seferde hesaptan ödendi", "o ayın bütçesinin bir anda açık vermesini önler"
        steps.append(
            Step(
                "Büyük alışverişler için önceden biriktirin",
                f"{len(window)} ayda {len(big)} büyük alışveriş ({tl(total)}) {paid}. "
                f"Bunlar için her ay {tl(total / len(window))} ayırmak {spared}.",
            )
        )

    needed = c.typical(lambda t: t.necessity == NEEDED)
    if needed >= 1:
        target = 3 * needed
        have = max(ZERO, c.savings - c.debts)
        text = (
            f"Zorunlu giderler ayda yaklaşık {tl(needed)}; 3 aylık tampon {tl(target)} eder. Borçlar düşülünce "
            f"birikiminiz {tl(have)}, yani yaklaşık {_decimal(have / needed)} aylık."
        )
        text += (
            f" Eksik {tl(target - have)}; maaş yatınca otomatik talimatla ayırın."
            if have < target
            else " Tampon yeterli; fazlası için uzun vadeli birikim planlayabilirsiniz."
        )
        steps.append(Step("Acil durum fonu", text))


def _write_budget(c: _Context) -> None:
    """The month now and after the priced steps; the difference is what the steps free."""
    ins = c.ins
    income = c.salary.amount if c.salary else (ins.flow.income if ins.flow else ZERO)
    fixed = [s for s in ins.series if s.running and s.last.kind == TransactionKind.PURCHASE]
    needed = c.level(NEEDED)
    unsure = c.level(Necessity.UNKNOWN, work=True)

    # The unnecessary level as the other levels' lines count theirs: a regular payment the user counts as unnecessary
    # is among the fixed payments while it runs and nowhere once it ended, a work cost on its own line; the fees' own
    # series (an account's monthly fee) stay here, as no other line has them.
    def avoidable(t: Transaction) -> bool:
        return (
            t.necessity == AVOIDABLE
            and (id(t) not in c.in_series or t.kind == TransactionKind.INTEREST_FEE)
            and t.category not in WORK_CATEGORIES
        )

    fees = c.typical(avoidable)
    base = set(c.base)
    ways = {_AVOID_NOTE.get(t.category, "") for t in c.expenses if avoidable(t) and month_of(t.date) in base}
    avoid = ", ".join(sorted(w for w in ways if w))
    work = c.typical(lambda t: t.category in WORK_CATEGORIES and id(t) not in c.in_series)
    optional, cut = _optional_cut(c)
    saving = sum((s.monthly for s in ins.series if s.running and s.last.kind == TransactionKind.INVESTMENT), ZERO)
    lines = [
        BudgetLine(
            "Düzenli gelir", income, income, f"son maaş ({c.salary.merchant})" if c.salary else "ortalama gelir"
        ),
        BudgetLine(
            "Sabit ödemeler (kira, aidat, faturalar, abonelikler)",
            sum((s.monthly for s in fixed), ZERO),
            sum((s.monthly for s in fixed), ZERO),
            f"{len(fixed)} düzenli ödeme, son tutarlarıyla",
        ),
        BudgetLine(
            "Değişken zorunlu giderler (market, ulaşım, sağlık…)", needed, needed, f"son {len(c.base)} ayın medyanı"
        ),
        BudgetLine("İsteğe bağlı harcamalar", optional, optional - cut, "öneri: aylık sınır"),
        BudgetLine("Yazılım, bulut ve muhasebe (abonelik dışı)", work, work, "işinizse şirkete taşınabilir"),
        BudgetLine("Sınıflanmamış harcamalar", unsure, unsure, "kişisel kurallarla netleşir"),
        BudgetLine(
            "Gereksiz harcamalar (faiz, banka ücretleri…)",
            fees,
            ZERO,
            f"öneri: {avoid} sıfırlayın" if avoid else "öneri: sıfırlayın",
        ),
        BudgetLine("BES ve düzenli birikim", saving, saving, "düzenli ödemelerden"),
    ]
    if ins.flow:
        other = ins.flow.other_typical
        lines.append(
            BudgetLine(
                "Kişilere ve borç ödemelerine giden",
                other,
                other,
                f"düzensiz; son {len(c.base)} ayın medyanı ({len(c.window)} aylık ortalama "
                f"{tl(ins.flow.people + ins.flow.debt)})",
            )
        )
    spent_now = sum((line.now for line in lines[1:]), ZERO)
    spent_plan = sum((line.plan for line in lines[1:]), ZERO)
    lines.append(
        BudgetLine("Ay sonunda kalan", income - spent_now, income - spent_plan, "birikime ve acil durum fonuna")
    )
    ins.budget.extend(lines)
