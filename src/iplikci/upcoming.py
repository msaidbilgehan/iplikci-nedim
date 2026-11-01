"""What comes in the next days (F09): the next payments of the regular and periodic series, the salary and other
regular income, the installments left on the cards, the loans' installments and the cards' due dates.

Each item says the account it leaves or enters (where its series was last paid from; the card for its installments
and its due date), its day, its amount, its kind and what it rests on. The series' days and amounts are expected, not
known: a monthly payment falls on its usual day of the month, a periodic one a period after the last. A card's due date
and what it asks come from its statement; the caller reads them (CardDue).
"""

from calendar import monthrange
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from .analysis import NO_STATEMENT, PROVISIONAL, Dataset
from .domain.codes import CARD_TYPES, AccountType, PaymentKind, TransactionKind
from .domain.labels import SERIES_PERIOD, format_amount
from .domain.models import TRY, Statement, Transaction
from .insights import Insights, PeriodicSeries, Series, Timeline, month_name, month_of, settle, shift

HORIZON = 60  # days the calendar and the cash-flow forecast look ahead, today the first of them (F09)
# A monthly payment comes again at least this many days after its last one, the shortest gap of a monthly series: a
# salary paid on the 31st for the 1st does not come again on the 1st.
_AFTER_LAST = 15
_TURN = 15  # the days up to the 15th count from the 1st; later ones count back from the next month's 1st


@dataclass(frozen=True)
class Due:
    """One payment or income expected in the next days."""

    day: date
    kind: PaymentKind
    title: str  # the payee, the payer, the purchase, the loan or the card
    account: str  # the account it leaves or enters: where its series was last paid from; a card for its own items
    amount: Decimal  # in TL; above zero money out, below zero money in, as a Transaction's
    basis: str  # what the day and the amount rest on, in Turkish
    series: str = ""  # the series it continues (series_id): a regular, periodic or income item's
    rows: tuple[str, ...] = ()  # fingerprints of the rows it rests on, newest last
    minimum: Decimal | None = None  # a card due's minimum payment


@dataclass(frozen=True)
class CardDue:
    """A card statement's due date and what it asks, as the statement prints them."""

    account: str  # the card
    due_date: date
    total: Decimal  # the statement's balance (dönem borcu)
    minimum: Decimal | None = None  # the minimum payment (asgari ödeme), when the statement prints it


@dataclass(frozen=True)
class Installment:
    """A card purchase in installments with some still to come (F08): its card's newest statement billed number
    `number` of `count`, and every later statement bills one more."""

    account: str  # the card
    title: str  # the merchant
    number: int
    count: int
    amount: Decimal  # one installment, in TL
    cut: date  # the newest statement's cut date
    row: str  # the fingerprint of its row on that statement

    @property
    def left(self) -> int:
        return self.count - self.number

    @property
    def remaining(self) -> Decimal:
        return self.amount * self.left

    def billed(self, k: int) -> date:
        """The cut date of the k-th statement after the newest: the day the installment number + k is billed."""
        return add_months(self.cut, k)

    @property
    def last(self) -> date:
        return self.billed(self.left)


def horizon_end(today: date, days: int = HORIZON) -> date:
    """The last day of the days that start today."""
    return today + timedelta(days=days - 1)


def add_months(day: date, n: int) -> date:
    """The same day n months later; the month's last day when that month is shorter (a card's next cut)."""
    year, month = divmod(day.year * 12 + day.month - 1 + n, 12)
    return date(year, month + 1, min(day.day, monthrange(year, month + 1)[1]))


def series_id(s: Series) -> str:
    """How the API names a series: its first payment's fingerprint, which a re-read keeps."""
    first = s.payments[0]
    return first.fingerprint or f"{s.merchant}|{first.date.isoformat()}"


def _usual_day(days: Sequence[date]) -> tuple[bool, int]:
    """Where in the month a monthly payment falls, from its latest days: (counted from the month's turn, day). Near
    the turn of the month the 30th of a 30-day month counts as -1, a day before the 1st, so that a salary paid on the
    30th and the 1st does not average to the 15th; otherwise a day is its day of the month. The count that keeps the
    days closer together wins."""
    plain = [d.day for d in days]
    turn = [d.day - 1 if d.day <= _TURN else d.day - monthrange(d.year, d.month)[1] - 1 for d in days]
    by_turn = max(turn) - min(turn) < max(plain) - min(plain)
    return by_turn, round(median(turn if by_turn else plain))


def _day_in(month: str, by_turn: bool, day: int) -> date:
    year, number = int(month[:4]), int(month[5:])
    if by_turn:
        return date(year, number, 1) + timedelta(days=day)
    return date(year, number, min(day, monthrange(year, number)[1]))


def monthly_days(payments: Sequence[Transaction], start: date, end: date) -> list[date]:
    """The days from start to end a monthly payment is expected on: its usual day of the month (of its last four
    payments), from the first one at least _AFTER_LAST days after its last payment."""
    last = payments[-1].date
    by_turn, day = _usual_day([t.date for t in payments[-4:]])
    found: list[date] = []
    month = shift(month_of(last), -1)  # a payment due on the 1st may have come on the last day of the month before
    while (when := _day_in(month, by_turn, day)) <= end:
        if when >= start and (when - last).days >= _AFTER_LAST:
            found.append(when)
        month = shift(month, 1)
    return found


def periodic_days(s: PeriodicSeries, start: date, end: date) -> list[date]:
    """The days from start to end a periodic payment is expected on: a period (its median gap) after the last."""
    found: list[date] = []
    when = s.last.date + timedelta(days=s.cadence)
    while when <= end:
        if when >= start:
            found.append(when)
        when += timedelta(days=s.cadence)
    return found


def next_day(s: Series) -> date:
    """The day a series' next payment is expected, whether that is past or to come."""
    if isinstance(s, PeriodicSeries):
        return s.last.date + timedelta(days=s.cadence)
    # The usual day comes again between _AFTER_LAST and _AFTER_LAST + 31 days (and a turn) after the last payment.
    return monthly_days(s.payments, s.last.date, s.last.date + timedelta(days=_AFTER_LAST + 62))[0]


def expected_amount(s: Series) -> Decimal:
    """What a series' next payment is expected to be: a periodic one's last amount; a monthly one's last amount, or
    the median of the last three when the amounts move (docs/domain/interpretation.md, "Tahmin")."""
    return s.per_period if isinstance(s, PeriodicSeries) else s.monthly


# --- the items -------------------------------------------------------------------------------------------------


def _tl(value: Decimal) -> str:
    return f"{format_amount(value)} TL"


def _day(d: date) -> str:
    return f"{d:%d.%m.%Y}"


def _months(rows: Sequence[Transaction]) -> str:
    """The months rows fall in, as a window: "Ağustos 2026 – Ekim 2026", or one month."""
    first, last = month_of(rows[0].date), month_of(rows[-1].date)
    return month_name(first) if first == last else f"{month_name(first)} – {month_name(last)}"


def _rows(s: Series) -> tuple[str, ...]:
    return tuple(t.fingerprint for t in s.payments[-3:] if t.fingerprint)


def _amount_basis(s: Series) -> str:
    if s.monthly == s.amount:
        return f"son ödeme {_day(s.last.date)}: {_tl(s.amount)}"
    return f"son üç ödemenin medyanı ({_months(s.payments[-3:])})"


def series_items(ds: Dataset, series: Iterable[Series], start: date, end: date) -> list[Due]:
    """The running monthly series' next payments, from the account each was last paid from. A loan's series is left
    to loan_items, which knows its whole installment."""
    found: list[Due] = []
    for s in series:
        account = ds.accounts.get(s.last.account)
        if not s.running or (account is not None and account.type == AccountType.LOAN):
            continue
        basis = _amount_basis(s) + ("; iptal edildi ama ödeme sürüyor" if s.status == "iptal_sonrasi" else "")
        for day in monthly_days(s.payments, start, end):
            found.append(
                Due(day, PaymentKind.REGULAR, s.merchant, s.last.account, s.monthly, basis, series_id(s), _rows(s))
            )
    return found


def periodic_items(series: Iterable[PeriodicSeries], start: date, end: date) -> list[Due]:
    found: list[Due] = []
    for s in series:
        if not s.running:
            continue
        basis = f"{SERIES_PERIOD[s.period].lower()}; son ödeme {_day(s.last.date)}: {_tl(s.per_period)}"
        for day in periodic_days(s, start, end):
            found.append(
                Due(day, PaymentKind.PERIODIC, s.merchant, s.last.account, s.per_period, basis, series_id(s), _rows(s))
            )
    return found


def income_amount(s: Series) -> Decimal:
    """What a regular income is expected to bring: the median of its last three amounts."""
    return median(abs(t.amount) for t in s.payments[-3:])


def income_items(series: Iterable[Series], start: date, end: date) -> list[Due]:
    """The salary and the other running income series, on the series' day, into the account they last came to."""
    found: list[Due] = []
    for s in series:
        if not s.running:
            continue
        basis = f"son üç tutarın medyanı ({_months(s.payments[-3:])})"
        for day in monthly_days(s.payments, start, end):
            found.append(
                Due(
                    day,
                    PaymentKind.INCOME,
                    s.merchant,
                    s.last.account,
                    -income_amount(s),
                    basis,
                    series_id(s),
                    _rows(s),
                )
            )
    return found


def _installment(label: str) -> tuple[int, int]:
    """'8/12' -> (8, 12); (0, 0) for anything else."""
    number, _, count = label.partition("/")
    return (int(number), int(count)) if number.isdigit() and count.isdigit() else (0, 0)


def installments_left(ds: Dataset) -> list[Installment]:
    """The purchases in installments with some still to come, from each card's newest statement in TL. A purchase
    whose rows stopped before it (paid off early, or a statement missing) is not counted on."""
    newest: dict[str, Statement] = {}
    for s in ds.statements:
        account = ds.accounts.get(s.account)
        if s.is_account or s.currency != TRY or account is None or account.type not in CARD_TYPES:
            continue
        if s.account not in newest or s.cut_date > newest[s.account].cut_date:
            newest[s.account] = s
    found: list[Installment] = []
    for card, s in newest.items():
        for t in s.transactions:
            number, count = _installment(t.installment)
            if 0 < number < count and t.amount > 0:
                found.append(
                    Installment(card, t.merchant or t.description, number, count, t.amount, s.cut_date, t.fingerprint)
                )
    return sorted(found, key=lambda i: (i.last, i.title))


def installment_items(ds: Dataset, start: date, end: date) -> list[Due]:
    """The installments still to come, each on the cut date of the statement that bills it."""
    found: list[Due] = []
    for i in installments_left(ds):
        basis = f"{i.number}/{i.count}. taksit {_day(i.cut)} ekstresinde; her kesimde bir taksit daha"
        for k in range(1, i.left + 1):
            day = i.billed(k)
            if start <= day <= end:
                title = f"{i.title} ({i.number + k}/{i.count})"
                found.append(Due(day, PaymentKind.INSTALLMENT, title, i.account, i.amount, basis, rows=(i.row,)))
    return found


def _loan_receipts(ds: Dataset) -> dict[str, list[list[Transaction]]]:
    """Each loan's receipts that count (an installment each: principal, interest and taxes), oldest first."""
    by_loan: dict[str, dict[str, list[Transaction]]] = defaultdict(dict)
    for line in ds.receipts:
        account = ds.accounts.get(line.txn.account)
        if account is not None and account.type == AccountType.LOAN and line.status in (PROVISIONAL, NO_STATEMENT):
            by_loan[account.id].setdefault(line.key, []).append(line.txn)
    return {
        loan: sorted(receipts.values(), key=lambda rows: min(t.date for t in rows))
        for loan, receipts in by_loan.items()
    }


def loan_items(ds: Dataset, tl_: Timeline, series: Iterable[Series], start: date, end: date) -> list[Due]:
    """A loan's next installments from its receipts, monthly on its usual day at the last installment's whole amount,
    while the receipts keep coming (the status rules of a series; `_biten` ends it too). How many are left the
    receipts do not say. A loan of a bank whose account list books the installments as a running series is that
    series, not a second item."""
    listed = {
        account.bank
        for s in series
        if s.running
        and s.last.kind == TransactionKind.LOAN_PRINCIPAL
        and (account := ds.accounts.get(s.last.account)) is not None
        and account.type != AccountType.LOAN
    }
    found: list[Due] = []
    for loan, receipts in _loan_receipts(ds).items():
        account = ds.accounts[loan]
        if account.bank in listed:
            continue
        # Each installment stands as its principal's row in a series, for the status rules and the usual day.
        rows = [next((t for t in r if t.kind == TransactionKind.LOAN_PRINCIPAL), r[0]) for r in receipts]
        s = Series(rows[-1].merchant or account.label, rows)
        settle(s, tl_.seen_until, ds.ended, tl_.as_of)
        if not s.running:
            continue
        last = receipts[-1]
        amount = sum((t.amount for t in last), Decimal(0))
        principal = sum((t.amount for t in last if t.kind == TransactionKind.LOAN_PRINCIPAL), Decimal(0))
        basis = (
            f"son taksit {_day(s.last.date)}: {_tl(amount)} (anapara {_tl(principal)}, faiz ve vergiler "
            f"{_tl(amount - principal)}); kalan taksit sayısı belgelerde yok"
        )
        prints = tuple(t.fingerprint for t in last if t.fingerprint)
        for day in monthly_days(rows, start, end):
            found.append(Due(day, PaymentKind.LOAN, account.label, loan, amount, basis, rows=prints))
    return found


def card_due_items(ds: Dataset, dues: Iterable[CardDue], start: date, end: date) -> list[Due]:
    """The cards' due dates from start to end, with what their statements ask."""
    found: list[Due] = []
    for d in dues:
        if not start <= d.due_date <= end or d.total <= 0:
            continue
        account = ds.accounts.get(d.account)
        basis = f"ekstrenin dönem borcu {_tl(d.total)}" + (
            f", asgari ödeme {_tl(d.minimum)}" if d.minimum is not None else ""
        )
        title = account.label if account is not None else d.account
        found.append(Due(d.due_date, PaymentKind.CARD_DUE, title, d.account, d.total, basis, minimum=d.minimum))
    return found


def upcoming(ds: Dataset, ins: Insights, today: date, dues: Iterable[CardDue] = (), days: int = HORIZON) -> list[Due]:
    """Every item expected from today on, for days days, by day."""
    end = horizon_end(today, days)
    items = [
        *series_items(ds, ins.series, today, end),
        *periodic_items(ins.periodic, today, end),
        *income_items(ins.income, today, end),
        *installment_items(ds, today, end),
        *loan_items(ds, ins.timeline, ins.series, today, end),
        *card_due_items(ds, dues, today, end),
    ]
    return sorted(items, key=lambda d: (d.day, d.kind, d.title))
