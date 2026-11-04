"""What an account's page shows besides its rows (F07): the daily balance curve, the money in and out by month, the
interest and fees, and what its type adds: a card's statements and how each was paid with its installments still to
come, an overdraft's use, a deposit's principal, a foreign currency's or gold's value and cost, a brokerage
account's portfolio, a loan's installments.

Nothing is invented: what no document prints (a deposit's rate and maturity, an overdraft's limit, a loan's remaining
principal, the price of gold) stays None, and the note says so.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from itertools import groupby

from ..analysis import NO_STATEMENT, PROVISIONAL, Dataset, ReceiptLine, statement_periods, untold_in
from ..categorize import FEE_CATEGORIES, FX_CATEGORY
from ..domain.codes import (
    DEFAULT_EXPENSE_KINDS,
    AccountType,
    Certainty,
    PaidStatus,
    PaymentKind,
    RateSource,
    TransactionKind,
)
from ..domain.models import TRY, Security, Statement
from ..domain.money import round_half_up
from ..domain.text import fold
from ..forecast import CARD_PAYMENTS, IN_FULL, last_of_day
from ..insights import FULL, complete_months, month_of, payments_after, shift
from ..upcoming import Due, Installment, installment_items, installments_left
from . import now, outlook
from .analysis import Analysis
from .rows import Direction, RowView

MONTHS = 12  # the months the page's money in and out, and its fees' window, look back on
CURVE_DAYS = 365  # the days an overdraft's days below zero are counted in
NEAR_MINIMUM = Decimal("1.05")  # a payment up to this much above the minimum is the minimum paid
ZERO = Decimal(0)
# Accounts whose balance the documents give day by day: TL accounts with a list of movements (a card's statement
# gives a debt, not a balance; a foreign or a gold account's rows are turned into TL by the ledger).
CURVE_TYPES = (AccountType.CURRENT, AccountType.OVERDRAFT, AccountType.DEPOSIT)
OVERDRAFT_INTEREST = FEE_CATEGORIES["overdraft_interest"]


@dataclass(frozen=True, slots=True)
class CurvePoint:
    day: date
    balance: Decimal  # at the day's end; below zero: overdrawn
    certainty: Certainty  # confirmed: a list or a bank's notice printed it; provisional: moved by receipts since


@dataclass(frozen=True, slots=True)
class MonthTotals:
    month: str
    money_in: Decimal  # in TL, counted rows only
    money_out: Decimal
    rows: int
    complete: bool  # an ended month the account's documents cover in full


@dataclass(frozen=True, slots=True)
class Fees:
    """Interest and fees on the account: a card's interest and fee, an overdraft's interest, transfer fees, a brokerage
    account's commissions, a loan's interest and taxes."""

    months: tuple[str, ...]  # the window: up to the last 12 complete months
    total: Decimal
    by_category: list[tuple[str, Decimal]]  # the largest first


@dataclass(frozen=True, slots=True)
class StatementView:
    """A card statement on the card's timeline."""

    cut: date
    start: date
    end: date
    total: Decimal | None  # its balance (dönem borcu); a debit card's: the sum of its purchases
    due: date | None
    minimum: Decimal | None
    limit: Decimal | None
    rows: int
    spent: Decimal  # purchases less refunds, interest and fees
    verified: bool
    document: str  # sha256
    paid: Decimal | None  # a credit card's: paid by the next statement's cut, the newest's by today; None for debit
    status: PaidStatus | None


@dataclass(frozen=True, slots=True)
class ScheduleMonth:
    """The installments still to come that one month's statement bills."""

    month: str
    amount: Decimal
    count: int


@dataclass(frozen=True, slots=True)
class CardPage:
    statement: now.Card | None  # the newest statement and the period the card is in ("Şu an"); None for a closed card
    statements: list[StatementView]  # the timeline, the newest first
    installments: list[Installment]  # the purchases in installments with some still to come
    schedule: list[ScheduleMonth]  # those installments by the month their statement bills them
    left: Decimal  # all of them together


@dataclass(frozen=True, slots=True)
class OverdraftPage:
    limit: Decimal | None  # no reader reads an overdraft limit yet
    used: Decimal  # today's balance below zero, above zero; zero when the account is in credit
    days_below: int  # days the balance ended below zero, within the window
    window: tuple[date, date] | None  # the curve's last 365 days
    interest: Decimal  # overdraft interest within the fees' window
    note: str


@dataclass(frozen=True, slots=True)
class DepositPage:
    principal: Decimal | None  # the balance
    rate: Decimal | None  # no document read so far prints these three
    maturity: date | None
    interest: Decimal | None
    note: str


@dataclass(frozen=True, slots=True)
class HoldingPage:
    """A foreign currency or gold account: what it holds and what that is worth."""

    amount: Decimal | None  # in the account's currency, or grams of gold
    currency: str
    value: Decimal | None  # in TL at the rate "Şu an" values it at (app.now); None without one (gold)
    rate: Decimal | None
    rate_day: date | None
    rate_source: RateSource | None
    cost: Decimal | None  # TL paid for it where the documents tell: gold bought from a TL account of the same bank
    gain: Decimal | None  # value less cost, when both are known
    note: str


@dataclass(frozen=True, slots=True)
class BrokeragePage:
    as_of: date | None  # the newest statement's market values
    securities: list[Security]
    cash: Decimal | None
    worth: Decimal | None  # cash and securities
    dividends: Decimal  # within the fees' window
    dividend_rows: int
    note: str


@dataclass(frozen=True, slots=True)
class LoanInstallment:
    day: date
    principal: Decimal
    cost: Decimal  # interest and taxes
    document: str  # the receipt's sha256
    certainty: Certainty


@dataclass(frozen=True, slots=True)
class LoanPage:
    installments: list[LoanInstallment]  # the newest first
    principal_paid: Decimal
    interest_paid: Decimal
    next: list[Due]  # the calendar's coming installments
    remaining: Decimal | None  # the remaining principal: no receipt prints it
    note: str


def _signed(r: RowView) -> Decimal:
    return r.amount if r.direction is Direction.OUT else -r.amount


# --- the daily balance -----------------------------------------------------------------------------------------------


def _opening(s: Statement) -> Decimal | None:
    """A list's opening balance: as it prints it, else its closing balance before its rows."""
    if s.previous is not None:
        return s.previous
    if s.total is not None:
        return s.total + sum((t.amount for t in s.transactions), ZERO)
    return None


def curve(ds: Dataset, account: str) -> tuple[list[CurvePoint], str]:
    """The account's balance at each day's end as its lists of movements print it, then on the days after the newest
    list that receipts and notices tell of: a notice's printed balance, else moved by their rows (provisional)."""
    found = ds.accounts[account]
    if found.currency != TRY or found.type not in CURVE_TYPES:
        return [], "Günlük bakiye TL vadesiz, vadeli ve ek hesaplar için çizilir."
    points: dict[date, CurvePoint] = {}
    lists = [s for s in ds.statements if s.account == account and s.is_account and s.currency == TRY]
    for s in sorted(lists, key=lambda s: (s.start or s.cut_date, s.cut_date)):
        opening = _opening(s)
        if opening is None or s.start is None:
            continue
        moves: defaultdict[date, Decimal] = defaultdict(Decimal)
        for t in s.transactions:
            moves[t.date] += t.amount
        balance, day = opening, s.start
        while day <= s.cut_date:
            balance -= moves[day]
            points.setdefault(day, CurvePoint(day, balance, Certainty.CONFIRMED))  # an earlier list's day stands
            day += timedelta(days=1)
    last = max(points, default=None)
    balance = points[last].balance if last is not None else None
    later = sorted(
        (
            line
            for line in ds.receipts
            if line.txn.account == account
            and line.status in (PROVISIONAL, NO_STATEMENT)
            and (last is None or line.txn.date > last)
        ),
        key=lambda line: (line.txn.date, line.key),
    )
    untold = False
    for day, group in groupby(later, key=lambda line: line.txn.date):
        lines = list(group)
        printed: list[tuple[ReceiptLine, Decimal]] = [(x, x.txn.balance) for x in lines if x.txn.balance is not None]
        if printed:
            balance, certainty = last_of_day(printed)[1], Certainty.CONFIRMED
        elif balance is not None:
            balance, certainty = balance - sum((x.native for x in lines), ZERO), Certainty.PROVISIONAL
            if came_in := untold_in(ds, account, balance):  # money in came first that no document tells yet
                balance, untold = balance + came_in, True
        else:
            continue  # nothing tells the balance before the first notice that prints one
        points[day] = CurvePoint(day, balance, certainty)
    if not points:
        return [], "Bakiyeyi yazan bir hesap dökümü ya da banka bildirimi yok."
    told = "bildirimin yazdığı bakiye kesin, dekontlarla değişen günler geçici"
    if last is None:
        note = f"Bakiyeler banka bildirimlerinden ve dekontlardan ({told}); hesap dökümü yok."
    elif later:
        note = f"Gün sonu bakiyeleri hesap dökümlerinden; son dökümden sonrası bildirim ve dekontlardan ({told})."
    else:
        note = "Gün sonu bakiyeleri hesap dökümlerinden."
    if untold:
        note += (
            " Ek hesabı olmayan bir hesap eksiye düşmez: dekontların gösterdiği çıkışın bakiyeyi aştığı günlerde "
            "belgelerde olmayan bir giriş var, bakiye 0 sayıldı."
        )
    return [points[d] for d in sorted(points)], note


# --- money in and out, interest and fees -----------------------------------------------------------------------------


def window(ds: Dataset, today: date) -> tuple[str, ...]:
    """The fees' and the dividends' window: up to the last 12 complete months before today's month."""
    current = month_of(today)
    return tuple(sorted(m for m in complete_months(ds) if m < current)[-MONTHS:])


def months(ds: Dataset, account: str, rows: list[RowView], today: date) -> list[MonthTotals]:
    """The money in and out of the last 12 months, from the account's first month with rows on; the oldest first."""
    current = month_of(today)
    by_month: defaultdict[str, list[RowView]] = defaultdict(list)
    for r in rows:
        if r.counted:
            by_month[month_of(r.day)].append(r)
    first = min(by_month, default=None)
    covered = ds.coverage.get(account, {})
    found: list[MonthTotals] = []
    for month in (shift(current, -k) for k in range(MONTHS - 1, -1, -1)):
        if first is None or month < first:
            continue
        of_month = by_month.get(month, [])
        money_in = sum((r.amount for r in of_month if r.direction is Direction.IN), ZERO)
        money_out = sum((r.amount for r in of_month if r.direction is Direction.OUT), ZERO)
        complete = month < current and covered.get(month, 0) >= FULL
        found.append(MonthTotals(month, money_in, money_out, len(of_month), complete))
    return found


def fees(rows: list[RowView], months_: tuple[str, ...]) -> Fees:
    within = set(months_)
    by_category: defaultdict[str, Decimal] = defaultdict(Decimal)
    for r in rows:
        if r.counted and r.kind is TransactionKind.INTEREST_FEE and month_of(r.day) in within:
            by_category[r.category] += _signed(r)
    ranked = sorted(((c, v) for c, v in by_category.items() if v), key=lambda pair: -pair[1])
    return Fees(months_, sum((v for _, v in ranked), ZERO), ranked)


# --- a card ----------------------------------------------------------------------------------------------------------


def _paid_status(total: Decimal | None, minimum: Decimal | None, paid: Decimal, open_: bool) -> PaidStatus:
    if total is None or total <= 0:
        return PaidStatus.NOTHING_DUE
    if paid >= total * IN_FULL:
        return PaidStatus.FULL
    if open_:
        return PaidStatus.OPEN
    if paid <= 0:
        return PaidStatus.UNPAID
    if minimum is not None and minimum <= paid <= minimum * NEAR_MINIMUM:
        return PaidStatus.MINIMUM
    return PaidStatus.PARTIAL


def _spent(s: Statement) -> Decimal:
    return sum((t.amount for t in s.transactions if t.kind in DEFAULT_EXPENSE_KINDS), ZERO)


def card_page(a: Analysis, account: str, today: date) -> CardPage:
    """A card's newest statement and its period, every TL statement with how it was paid (as the next statement shows
    the payments; the newest, as far as the payments since its cut tell), and the installments still to come."""
    ds = a.dataset
    credit = ds.accounts[account].type == AccountType.CREDIT_CARD
    statements = sorted(
        (s for s in ds.statements if s.account == account and not s.is_account and s.currency == TRY),
        key=lambda s: s.cut_date,
    )
    periods = {id(s): (start, end) for s, start, end in statement_periods(statements)}
    views: list[StatementView] = []
    nexts: list[Statement | None] = [*statements[1:], None]
    for s, after in zip(statements, nexts, strict=True):
        paid: Decimal | None = None
        status: PaidStatus | None = None
        if credit:
            if after is not None:
                paid = -sum((t.amount for t in after.transactions if t.kind in CARD_PAYMENTS and t.amount < 0), ZERO)
            else:
                paid = sum((t.amount for t in payments_after(ds, account, s.cut_date)), ZERO)
            open_ = after is None and (s.due_date is None or today <= s.due_date)
            status = _paid_status(s.total, s.minimum_payment, paid, open_)
        start, end = periods.get(id(s), (s.cut_date, s.cut_date))
        views.append(
            StatementView(
                cut=s.cut_date,
                start=start,
                end=end,
                total=s.total,
                due=s.due_date,
                minimum=s.minimum_payment,
                limit=s.credit_limit,
                rows=len(s.transactions),
                spent=_spent(s),
                verified=s.verified,
                document=s.document,
                paid=paid,
                status=status,
            )
        )
    found, _ = now.cards(a)
    statement = next((c for c in found if c.account == account), None)
    installments = [i for i in installments_left(ds) if i.account == account]
    last = max((i.last for i in installments), default=today)
    by_month: defaultdict[str, list[Due]] = defaultdict(list)
    # Every installment after the newest statement, a statement still to come past its cut day included.
    for item in installment_items(ds, date.min, last):
        if item.account == account:
            by_month[month_of(item.day)].append(item)
    schedule = [
        ScheduleMonth(m, sum((i.amount for i in items), ZERO), len(items)) for m, items in sorted(by_month.items())
    ]
    left = sum((i.remaining for i in installments), ZERO)
    return CardPage(statement, views[::-1], installments, schedule, left)


# --- an overdraft, a deposit, a foreign currency or gold, a brokerage account, a loan ---------------------------------


def overdraft_page(points: list[CurvePoint], balance: Decimal | None, fees_: Fees) -> OverdraftPage:
    used = max(ZERO, -balance) if balance is not None else ZERO
    end = points[-1].day if points else None
    start = end - timedelta(days=CURVE_DAYS - 1) if end is not None else None
    below = sum(1 for p in points if start is not None and p.day >= start and p.balance < 0)
    interest = sum((v for c, v in fees_.by_category if c == OVERDRAFT_INTEREST), ZERO)
    note = (
        "Ek hesap limiti ve faiz oranı belgelerde yazmıyor; eksi günler gün sonu bakiyelerinden, faiz son tam "
        "aylardaki ek hesap faizi satırlarından. Çıkış planı için oran gerekiyor."
    )
    return OverdraftPage(None, used, below, (start, end) if start and end else None, interest, note)


def deposit_page(balance: Decimal | None) -> DepositPage:
    note = "Faiz oranı, vade sonu ve faiz getirisi okunan belgelerde yazmıyor; anapara hesabın bakiyesidir."
    return DepositPage(balance, None, None, None, note)


def gold_cost(ds: Dataset, account: str) -> Decimal | None:
    """TL paid for gold (the MVP's rule, docs/domain/interpretation.md "Varlıklar ve borçlar"): the trades in gold of
    the TL accounts of the same bank, net of what selling brought back."""
    bank = ds.accounts[account].bank
    paid = sum(
        (
            t.amount
            for t in ds.transactions
            if t.category == FX_CATEGORY
            and "ALTIN" in fold(t.description)
            and (source := ds.accounts.get(t.account)) is not None
            and source.bank == bank
            and source.currency == TRY
        ),
        ZERO,
    )
    return round_half_up(paid) if paid >= 1 else None


def holding_page(ds: Dataset, account: str, balance: now.Balance | None) -> HoldingPage:
    found = ds.accounts[account]
    gold = found.type == AccountType.GOLD
    cost = gold_cost(ds, account) if gold else None
    value = balance.value if balance is not None else None
    gain = value - cost if value is not None and cost is not None else None
    if gold:
        note = "Altının güncel fiyatı belgelerde yok: TL değeri ve kazancı bilinmiyor."
        if cost is not None:
            note += " Maliyet, aynı bankanın TL hesaplarından altın alımına ödenenler (satışlar düşülerek)."
    else:
        source = balance.rate_source if balance is not None else None
        valued = (
            "TL değeri belgelerdeki en yeni kurla."
            if source in (None, RateSource.DOCUMENT)
            else "TL değeri TCMB'nin (ulaşılamayan günlerde ECB'nin) en yeni kuruyla: varlık döviz alış, borç döviz "
            "satış kuruyla."
        )
        note = f"{valued} Maliyet ve kur farkı için dövizin hangi kurdan alındığı belgelerden bütünüyle çıkmıyor."
    return HoldingPage(
        amount=balance.balance if balance is not None else None,
        currency=found.currency,
        value=value,
        rate=balance.rate if balance is not None else None,
        rate_day=balance.rate_day if balance is not None else None,
        rate_source=balance.rate_source if balance is not None else None,
        cost=cost,
        gain=gain,
        note=note,
    )


def brokerage_page(ds: Dataset, account: str, rows: list[RowView], months_: tuple[str, ...]) -> BrokeragePage:
    lists = [s for s in ds.statements if s.account == account and s.total is not None]
    newest = max(lists, key=lambda s: s.cut_date, default=None)
    within = set(months_)
    dividends = [r for r in rows if r.counted and r.kind is TransactionKind.INCOME and month_of(r.day) in within]
    if newest is None:
        return BrokeragePage(None, [], None, None, ZERO, 0, "Hesabın ekstresi yok.")
    held = round_half_up(sum((x.value for x in newest.securities), ZERO))
    cash = newest.total
    as_of = max((x.as_of for x in newest.securities), default=newest.cut_date)
    note = "Portföy en yeni ekstrenin piyasa değeriyle; temettüler son tam aylardan, komisyonlar faiz ve ücretlerde."
    return BrokeragePage(
        as_of=as_of,
        securities=list(newest.securities),
        cash=cash,
        worth=round_half_up(held + (cash or ZERO)),
        dividends=sum((r.amount for r in dividends), ZERO),
        dividend_rows=len(dividends),
        note=note,
    )


def loan_page(a: Analysis, account: str, rows: list[RowView], today: date) -> LoanPage:
    """A loan's installments as its receipts tell them, principal and cost apart, and the calendar's next ones."""
    by_installment: defaultdict[tuple[date, str], list[RowView]] = defaultdict(list)
    for r in rows:
        if r.counted:
            by_installment[(r.day, r.document)].append(r)
    installments = [
        LoanInstallment(
            day=day,
            principal=sum((r.amount for r in group if r.kind is TransactionKind.LOAN_PRINCIPAL), ZERO),
            cost=sum((r.amount for r in group if r.kind is TransactionKind.INTEREST_FEE), ZERO),
            document=document,
            certainty=Certainty.PROVISIONAL
            if any(r.certainty is Certainty.PROVISIONAL for r in group)
            else Certainty.CONFIRMED,
        )
        for (day, document), group in sorted(by_installment.items(), reverse=True)
    ]
    coming = [i for i in outlook.calendar(a, today).items if i.kind is PaymentKind.LOAN and i.account == account]
    note = "Taksitler kredi dekontlarından; kalan anapara ve kalan taksit sayısı dekontlarda yazmıyor."
    return LoanPage(
        installments=installments,
        principal_paid=sum((i.principal for i in installments), ZERO),
        interest_paid=sum((i.cost for i in installments), ZERO),
        next=coming,
        remaining=None,
        note=note,
    )
