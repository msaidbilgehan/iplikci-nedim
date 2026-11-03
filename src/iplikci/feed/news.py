"""What an analysis has to tell beyond its rows, months and bills (architecture §13), for the notification rules to
match. Each finder returns what it finds with what its notification says; the snapshot decides what is news.

- `payment.due_soon`: an item of the calendar the user has to see to (a card's due date, a non-bank bill, a loan's
  installment, a regular or periodic payment made from an account, as rent is) seven, three, one or no days before
  its day. A card's installments are paid within its statement, and what a card is charged on its own (a
  subscription) asks nothing of the user: telling them would be noise every month. Each of these thresholds is told
  once, the tightest one the days left reach: after a stop only that one, not those skipped.
- `balance.forecast_negative`: a bank account's forecast goes below zero within its days (an overdraft account's
  below-zero balance is its credit in use, and an account the user tops up from their own accounts goes as low as the
  transfers the forecast does not project: neither is told), or the accounts' total does.
- `expected_payment.missing`, `income.late`: the documents of the accounts a regular or periodic payment, or a regular
  income, was last seen on went past its expected day and its grace without it.
- `subscription.price_changed`: a running series' new price, while the payment that made it certain is recent (an
  import of last year's statements brings last year's price rises: history, not news);
  `subscription.paid_after_cancel`: a payment after the month the user's rules give a cancelled series as its last.
- `income.received`: a row of a regular income; `transaction.large`: a single purchase outside the series from the
  insights' large purchase threshold on; both dated within NEWS_DAYS before the analysis day, so that the history an
  import or a statement brings tells nothing. A statement row that confirms a receipt's row is that row told again,
  not a second one.
- `evidence.unmatched`: a receipt's or a bank notice's row the statement covering its days does not show.

Amounts are TL with two decimals, as strings, money out above zero as the ledger counts it; days are ISO dates.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from ..analysis import CONFIRMED, NOT_ON_STATEMENT, Dataset, payments, row_rate
from ..domain.codes import CARD_TYPES, PaymentKind, SeriesPeriod, TransactionKind
from ..domain.models import TRY
from ..domain.money import round_half_up
from ..domain.text import fold
from ..forecast import Forecast, counted_from, forecast
from ..insights import Insights, PeriodicSeries, Series, large_purchase_threshold, paid_after_cancel
from ..upcoming import HORIZON, CardDue, Due, expected_amount, income_amount, next_day, series_id, upcoming

DUE_SOON = "payment.due_soon"
NEGATIVE = "balance.forecast_negative"
MISSING = "expected_payment.missing"
LATE = "income.late"
REPRICED = "subscription.price_changed"
PAID_AFTER_CANCEL = "subscription.paid_after_cancel"
INCOME = "income.received"
LARGE = "transaction.large"
UNMATCHED = "evidence.unmatched"
# The kinds told once per occurrence: a snapshot remembers each one an analysis found, told or only noted.
OCCURRENCES = (DUE_SOON, NEGATIVE, MISSING, LATE, REPRICED, PAID_AFTER_CANCEL)

DUE_DAYS = (0, 1, 3, 7)  # a payment is told a week, three days and a day before its day, and on the day
# The items the user has to see to; a regular or periodic one only when it is paid from an account, not a card.
TO_PAY = frozenset(
    {PaymentKind.CARD_DUE, PaymentKind.BILL, PaymentKind.LOAN, PaymentKind.REGULAR, PaymentKind.PERIODIC}
)
_FROM_ACCOUNT = frozenset({PaymentKind.REGULAR, PaymentKind.PERIODIC})
NEWS_DAYS = 7  # a new row dated more than this many days before the analysis day is history, not news
LATE_DAYS = HORIZON  # a payment or income that did not come is news as long after its grace as the calendar looks ahead
# A price change is news while the payment that made it certain is this recent: a card statement shows a payment up
# to a month after it and comes days after its cut.
REPRICED_DAYS = 45
TOTAL = "Hesaplarınızın toplamı"  # what the accounts' summed forecast is called where an account's name would stand
_EXPECTED = ("devam", "bitti")  # running, or ended as its documents went past it; a cancelled series is not expected


@dataclass(frozen=True, slots=True)
class Found:
    """Something an analysis finds worth telling, with what its notification says."""

    kind: str
    target: str  # the occurrence's or the row's stable key: what the notifier tells deliveries apart by
    detail: dict[str, Any]
    threshold: int | None = None  # a payment due soon: the days before its day it is told at
    rows: tuple[str, ...] = ()  # a row: the fingerprints it may have been known by (its own, its receipt rows')

    @property
    def key(self) -> str:
        """What a snapshot remembers an occurrence by: its target, with its threshold for a payment due soon."""
        return self.target if self.threshold is None else f"{self.target}|{self.threshold}"


def money(value: Decimal) -> str:
    """An amount as the events carry it: two decimals, halves rounded up ("1234.56")."""
    return f"{round_half_up(value):.2f}"


def find(ds: Dataset, ins: Insights, today: date, dues: Sequence[CardDue] = ()) -> list[Found]:
    """Everything the analysis has to tell as of today, kind by kind. The calendar and the forecast are made as the
    outlook makes them (app.outlook.calendar and cash_flow), with the cards' dues the caller reads from the
    statements."""
    items = upcoming(ds, ins, today, dues, since=counted_from(ds, today))
    confirmed = _confirmed(ds)
    return [
        *due_soon(items, today, {a.id for a in ds.accounts.values() if a.type in CARD_TYPES}),
        *negatives(forecast(ds, ins, today, items)),
        *missing(ds, ins, today),
        *late(ds, ins, today),
        *repriced(ins, today),
        *paid_after_cancelling(ds, ins),
        *income_received(ins, today, confirmed),
        *large(ds, ins, today, confirmed),
        *unmatched(ds),
    ]


# --- the days ahead ----------------------------------------------------------------------------------------------


def due_soon(items: Iterable[Due], today: date, cards: Iterable[str] = ()) -> list[Found]:
    """The items of the calendar the user has to see to (TO_PAY) a week or less away, each at the tightest of DUE_DAYS
    its days left reach; a regular or periodic payment last made by one of the cards is the card's to pay."""
    by_card = set(cards)
    found: list[Found] = []
    for item in items:
        days = (item.day - today).days
        threshold = next((t for t in DUE_DAYS if 0 <= days <= t), None)
        if threshold is None or item.kind not in TO_PAY or (item.kind in _FROM_ACCOUNT and item.account in by_card):
            continue
        detail: dict[str, Any] = {
            "payment": str(item.kind),
            "title": item.title,
            "account": item.account,
            "due": item.day.isoformat(),
            "days": days,
            "amount": money(item.amount),
        }
        if item.kind == PaymentKind.CARD_DUE and item.minimum is not None:
            detail["minimum"] = money(item.minimum)
        target = f"{item.kind}|{item.account}|{item.title}|{item.day.isoformat()}"
        found.append(Found(DUE_SOON, target, detail, threshold=threshold))
    return found


def negatives(fc: Forecast) -> list[Found]:
    """The bank accounts whose forecast goes below zero within its days and warns of it (AccountForecast.warning), at
    the first such day; and the accounts' total, when it goes below zero after today."""
    labels = {account.account: account.label for account in fc.accounts}
    found: list[Found] = []
    for account, (day, balance) in fc.warnings:
        title = labels[account] if account else TOTAL
        detail: dict[str, Any] = {
            "account": account,
            "title": title,
            "day": day.isoformat(),
            "days": (day - fc.today).days,
            "balance": money(balance),
        }
        found.append(Found(NEGATIVE, f"{account or 'toplam'}|{day.isoformat()}", detail))
    return found


# --- the series --------------------------------------------------------------------------------------------------


def _newest_evidence(ds: Dataset) -> dict[str, date]:
    """Each account's newest receipt or bank notice row, counted or not."""
    newest: dict[str, date] = {}
    for line in ds.receipts:
        newest[line.txn.account] = max(newest.get(line.txn.account, line.txn.date), line.txn.date)
    return newest


def _overdue(ds: Dataset, ins: Insights, series: Iterable[Series], today: date) -> list[tuple[Series, date]]:
    """The series whose next payment or income did not come, with the day it was expected on (upcoming.next_day: the
    day the calendar and the Subscriptions screen give it). It did not come when the documents of the accounts its
    last two payments were seen on went past that day and the series' grace without it (insights.settle): a statement
    that ends on the grace's last day or later, or a receipt or a bank notice of a later day. Until they do, a
    payment by card or from an account with monthly lists may well have come: its statement is still to arrive. A
    cancelled series is not expected, and a grace that ended more than LATE_DAYS ago is history."""
    seen, newest = ins.timeline.seen_until, _newest_evidence(ds)
    found: list[tuple[Series, date]] = []
    for s in series:
        if s.status not in _EXPECTED:
            continue
        expected = next_day(s)
        end = expected + timedelta(days=s.grace)
        if not today - timedelta(days=LATE_DAYS) <= end < today:
            continue
        accounts = {t.account for t in s.payments[-2:]}
        if any(seen.get(a, date.min) >= end or newest.get(a, date.min) > end for a in accounts):
            found.append((s, expected))
    return found


def missing(ds: Dataset, ins: Insights, today: date) -> list[Found]:
    """The regular and periodic payments that did not come (_overdue)."""
    found: list[Found] = []
    for s, expected in _overdue(ds, ins, [*ins.series, *ins.periodic], today):
        period = s.period if isinstance(s, PeriodicSeries) else SeriesPeriod.MONTH
        detail: dict[str, Any] = {
            "title": s.merchant,
            "expected": expected.isoformat(),
            "amount": money(expected_amount(s)),
            "period": str(period),
        }
        found.append(Found(MISSING, f"{series_id(s)}|{expected.isoformat()}", detail))
    return found


def late(ds: Dataset, ins: Insights, today: date) -> list[Found]:
    """The salary and the other regular income that did not come (_overdue), at the amount the calendar expects."""
    found: list[Found] = []
    for s, expected in _overdue(ds, ins, ins.income, today):
        detail: dict[str, Any] = {
            "title": s.merchant,
            "expected": expected.isoformat(),
            "amount": money(income_amount(s)),
        }
        found.append(Found(LATE, f"{series_id(s)}|{expected.isoformat()}", detail))
    return found


def repriced(ins: Insights, today: date) -> list[Found]:
    """The running regular and periodic payments with a new price (Series.price_change), from the first payment at
    it, while the payment that made the price certain is within REPRICED_DAYS before today."""
    found: list[Found] = []
    for s in [*ins.series, *ins.periodic]:
        change = s.price_change() if s.running else None
        if change is None or _certain_on(s, change[2]) < today - timedelta(days=REPRICED_DAYS):
            continue
        old, new, since = change
        detail: dict[str, Any] = {"title": s.merchant, "old": money(old), "new": money(new), "since": since.isoformat()}
        found.append(Found(REPRICED, f"{series_id(s)}|{since.isoformat()}", detail))
    return found


def _certain_on(s: Series, since: date) -> date:
    """The day a new price became certain: the second payment at it (Series.price_change wants two); a periodic
    payment's one."""
    if isinstance(s, PeriodicSeries):
        return since
    return next((t.date for t in s.payments if t.date > since), since)


def paid_after_cancelling(ds: Dataset, ins: Insights) -> list[Found]:
    """The cancelled series paid after the month the user's rules give as the last, at the latest such payment."""
    found: list[Found] = []
    for s in [*ins.series, *ins.periodic]:
        late_ = paid_after_cancel(s, ds.ended) if s.status == "iptal_sonrasi" else []
        if not late_:
            continue
        last = late_[-1]
        detail: dict[str, Any] = {
            "title": s.merchant,
            "amount": money(abs(last.amount)),
            "date": last.date.isoformat(),
            "cancelled": ds.ended[fold(s.merchant)],
        }
        found.append(Found(PAID_AFTER_CANCEL, f"{series_id(s)}|{last.date.isoformat()}", detail))
    return found


# --- rows --------------------------------------------------------------------------------------------------------


def _confirmed(ds: Dataset) -> dict[str, tuple[str, ...]]:
    """A statement row's fingerprint -> the receipt and notice rows it confirms: the same money, told before it."""
    found: defaultdict[str, list[str]] = defaultdict(list)
    for line in ds.receipts:
        if line.status == CONFIRMED and line.match is not None and line.match.fingerprint and line.txn.fingerprint:
            found[line.match.fingerprint].append(line.txn.fingerprint)
    return {fp: tuple(rows) for fp, rows in found.items()}


def income_received(ins: Insights, today: date, confirmed: Mapping[str, tuple[str, ...]]) -> list[Found]:
    """The rows of a regular income dated within NEWS_DAYS before today, as received: the snapshot tells the new
    ones."""
    since = today - timedelta(days=NEWS_DAYS)
    found: list[Found] = []
    for s in ins.income:
        for t in s.payments:
            if not t.fingerprint or not since <= t.date <= today:
                continue
            detail: dict[str, Any] = {
                "title": s.merchant,
                "amount": money(abs(t.amount)),
                "account": t.account,
                "date": t.date.isoformat(),
            }
            found.append(Found(INCOME, t.fingerprint, detail, rows=(t.fingerprint, *confirmed.get(t.fingerprint, ()))))
    return sorted(found, key=lambda f: (f.detail["date"], f.target))


def large(ds: Dataset, ins: Insights, today: date, confirmed: Mapping[str, tuple[str, ...]]) -> list[Found]:
    """The single purchases outside the regular and periodic payments from the large purchase threshold on
    (insights.large_purchase_threshold), dated within NEWS_DAYS before today: an older one a statement or an import
    brings is history."""
    threshold = large_purchase_threshold(ds, ins.timeline.window)
    in_series = {id(t) for s in [*ins.series, *ins.periodic] for t in s.payments}
    since = today - timedelta(days=NEWS_DAYS)
    found: list[Found] = []
    for t in payments(ds):  # a split purchase is large or not as a whole
        if t.kind != TransactionKind.PURCHASE or t.amount < threshold or id(t) in in_series or not t.fingerprint:
            continue
        if since <= t.date <= today:
            detail: dict[str, Any] = {
                "title": t.merchant or t.description,
                "amount": money(t.amount),
                "account": t.account,
                "date": t.date.isoformat(),
            }
            found.append(Found(LARGE, t.fingerprint, detail, rows=(t.fingerprint, *confirmed.get(t.fingerprint, ()))))
    return found


def unmatched(ds: Dataset) -> list[Found]:
    """The receipt and notice rows the statements covering their days do not show (docs/domain/ledger.md,
    "Kanıtlar"). Such a row counts nowhere, so the ledger never valued it in TL: a foreign-currency account's row is
    valued as the ledger values that account's rows (analysis.row_rate: its own rate, else the providers' of its day,
    else the documents' nearest); without a rate, its amount stays in the account's currency, which `currency`
    names."""
    found: list[Found] = []
    for line in sorted(ds.receipts, key=lambda line: (line.txn.date, line.txn.fingerprint)):
        t = line.txn
        if line.status != NOT_ON_STATEMENT or not t.fingerprint:
            continue
        detail: dict[str, Any] = {
            "title": t.merchant or t.counterparty or t.description,
            "amount": money(line.native),
            "account": t.account,
            "date": t.date.isoformat(),
        }
        account = ds.accounts.get(t.account)
        currency = account.currency if account is not None else TRY
        if currency != TRY:
            rate = row_rate(ds.rates, ds.book, currency, t)
            if rate is None:
                detail["currency"] = currency
            else:
                detail["amount"] = money(line.native * rate.rate)
        found.append(Found(UNMATCHED, t.fingerprint, detail))
    return found
