"""The accounts as the screens see them (F05, F06, F07): the Accounts screen's groups with their totals, each
account's balance and how far its documents reach, its page, and the name the user gives it.

An account whose documents stopped more than 180 days before the newest document is closed or no longer followed:
the screens list it apart and leave it out of every total (F07). Balances are those of "Şu an" (app.now): the
newest balance a document prints, moved by later receipts and notices, a card's statement less what was paid since,
a brokerage account's portfolio; what has no TL value (gold, a currency without a rate) is listed without one and
left out of the totals, never guessed.
"""

from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .. import month_end
from ..analysis import Dataset
from ..domain.codes import (
    CARD_TYPES,
    AccountGroup,
    AccountType,
    Actor,
    Certainty,
    DocumentKind,
    PaidStatus,
    PaymentKind,
)
from ..domain.models import Security
from ..forecast import start_of
from ..insights import FULL, month_of, payments_after, shift
from ..storage import aliases, documents
from ..storage.documents import DocumentRow
from ..upcoming import Installment, add_months
from . import account_pages, now, outlook, transactions
from .account_pages import (
    BrokeragePage,
    CardPage,
    CurvePoint,
    DepositPage,
    Fees,
    HoldingPage,
    LoanInstallment,
    LoanPage,
    MonthTotals,
    OverdraftPage,
    ScheduleMonth,
    StatementView,
)
from .analysis import Analysis, account_labels, document_gaps
from .links import Link, Screen
from .outlook import SeriesView
from .reach import closed, last_seen
from .transactions import Page, Totals
from .workspace import Workspace

# What the API names from here: the use cases, their records and the codes they carry.
__all__ = [
    "AccountGroup",
    "AccountType",
    "AccountView",
    "Actor",
    "BrokeragePage",
    "CardPage",
    "Certainty",
    "CurvePoint",
    "DepositPage",
    "Detail",
    "DocumentKind",
    "Fees",
    "Freshness",
    "Group",
    "HoldingPage",
    "Installment",
    "LoanInstallment",
    "LoanPage",
    "MonthFlow",
    "MonthTotals",
    "NotFound",
    "OverdraftPage",
    "Overview",
    "Page",
    "PaidStatus",
    "PaymentKind",
    "Refused",
    "ScheduleMonth",
    "Security",
    "SeriesView",
    "StatementView",
    "Totals",
    "detail",
    "overview",
    "rename",
]

MAX_ALIAS = 60  # characters of a name the user gives an account
ZERO = Decimal(0)
GROUP_OF: dict[AccountType, AccountGroup] = {
    AccountType.CREDIT_CARD: AccountGroup.CARDS,
    AccountType.DEBIT_CARD: AccountGroup.CARDS,
    AccountType.CURRENT: AccountGroup.CURRENT,
    AccountType.DEPOSIT: AccountGroup.DEPOSIT,
    AccountType.OVERDRAFT: AccountGroup.OVERDRAFT,
    AccountType.FX: AccountGroup.FX,
    AccountType.GOLD: AccountGroup.GOLD,
    AccountType.BROKERAGE: AccountGroup.BROKERAGE,
    AccountType.LOAN: AccountGroup.LOAN,
}
# The accounts that pay and get paid from: their page lists the regular payments and income they carry.
_PAYING = (AccountType.CURRENT, AccountType.OVERDRAFT, AccountType.FX, *CARD_TYPES)


class NotFound(Exception):
    """No account has the id."""


class Refused(Exception):
    """A change the program will not make; the message says why, in Turkish."""


@dataclass(frozen=True, slots=True)
class Freshness:
    """How far an account's documents reach."""

    account: str
    kind: DocumentKind  # what its newest document is
    document: str  # that document's sha256
    name: str  # its readable name
    last: date  # the newest day its documents reach
    behind: int  # days from that to today
    expected: date | None  # when its next statement is due: a card's next cut, a brokerage statement's month end
    late: bool  # that day passed days ago and the statement did not come (five days for a card, ten otherwise)
    missing: tuple[str, ...]  # months inside its statements they cover only partly or not
    note: str
    link: Link


@dataclass(frozen=True, slots=True)
class MonthFlow:
    """The money in and out of an account in the current month so far."""

    month: str
    money_in: Decimal  # in TL, counted rows only
    money_out: Decimal
    rows: int
    provisional: int  # rows only a receipt or a notice shows yet
    note: str  # what the sums leave out, in Turkish; "" when nothing


@dataclass(frozen=True, slots=True)
class AccountView:
    """An account on the Accounts screen."""

    id: str
    label: str  # the bank's label
    alias: str  # the name the user gave it; "" for none
    bank: str
    type: AccountType
    group: AccountGroup
    currency: str  # TRY, a foreign currency, or GR: grams of gold
    balance: Decimal | None  # in its currency; below zero: a debt (a card's, an overdraft); None: unknown
    value: Decimal | None  # in TL; None without a rate (gold), for a closed account, or an unknown balance
    day: date | None  # the newest day the balance knows of
    certainty: Certainty | None  # provisional: moved by receipts and notices since the document that printed it
    note: str  # what the balance rests on, or why there is none
    freshness: Freshness | None
    month: MonthFlow
    closed: bool  # its documents stopped 180 days before the newest: listed apart, in no total
    link: Link


@dataclass(frozen=True, slots=True)
class Group:
    group: AccountGroup
    assets: Decimal  # the TL values above zero
    debts: Decimal  # the TL values below zero, above zero
    total: Decimal
    unvalued: int  # its accounts without a TL value, left out of the totals
    accounts: list[AccountView]  # the largest TL value first, those without one last


@dataclass(frozen=True, slots=True)
class Overview:
    today: date
    groups: list[Group]  # in F07's order, only the groups with an open account
    closed: list[AccountView]  # the newest documents first
    assets: Decimal
    debts: Decimal
    total: Decimal
    note: str


@dataclass(frozen=True, slots=True)
class Detail:
    """An account's page (F07)."""

    account: AccountView
    page: Page  # its rows, the newest first, with their totals
    curve: list[CurvePoint]  # its balance day by day, for a TL bank account
    curve_note: str
    months: list[MonthTotals]  # the last 12 months' money in and out
    fees: Fees
    payments: list[SeriesView]  # the regular and periodic payments last made from it
    income: list[SeriesView]  # the regular income that last came into it
    card: CardPage | None
    overdraft: OverdraftPage | None  # an overdraft account, or one whose balance went below zero
    deposit: DepositPage | None
    holding: HoldingPage | None  # a foreign currency or gold account
    brokerage: BrokeragePage | None
    loan: LoanPage | None


def _day(d: date) -> str:
    return f"{d:%d.%m.%Y}"


# --- how far the documents reach -------------------------------------------------------------------------------------


def _expected(account: AccountType, cut: date) -> tuple[date, int] | None:
    """When the statement after one cut on a day is due, and how many days later it is late (month_end.LATE_DAYS):
    a card's comes a month after its cut, a brokerage account's after the next month ends. A list is downloaded or
    mailed when it is (K21): nothing is due."""
    if account in CARD_TYPES:
        return add_months(cut, 1), month_end.LATE_DAYS
    if account == AccountType.BROKERAGE:
        return month_end.last_day(shift(month_of(cut), 1)), 2 * month_end.LATE_DAYS
    return None


def _newest_document(ds: Dataset, account: str, docs: dict[str, DocumentRow]) -> tuple[DocumentKind, str, str]:
    """(kind, sha256, name) of the account's newest document: its newest statement, unless a receipt or a notice
    tells of a later day."""
    statements = [(s.cut_date, 1, s) for s in ds.statements if s.account == account]
    evidence = [(line.txn.date, 0, line) for line in ds.receipts if line.txn.account == account]
    newest = max(statements, key=lambda x: (x[0], x[1]), default=None)
    told = max(evidence, key=lambda x: (x[0], x[1]), default=None)
    if newest is not None and (told is None or newest[0] >= told[0]):
        s = newest[2]
        kind = DocumentKind.ACCOUNT_STATEMENT if s.is_account else DocumentKind.CARD_STATEMENT
        sha = s.document
    elif told is not None:
        sha = told[2].txn.document
        row = docs.get(sha)
        kind = row.kind if row is not None and row.kind is not None else DocumentKind.RECEIPT
    else:
        return DocumentKind.RECEIPT, "", ""
    row = docs.get(sha)
    return kind, sha, (row.display_name or row.name) if row is not None else ""


def _freshness(
    ds: Dataset, account: str, last: date, today: date, holes: dict[str, tuple[str, ...]], docs: dict[str, DocumentRow]
) -> Freshness:
    statements = [s for s in ds.statements if s.account == account]
    newest = max(statements, key=lambda s: s.cut_date) if statements else None
    kind, sha, name = _newest_document(ds, account, docs)
    due = _expected(ds.accounts[account].type, newest.cut_date) if newest is not None else None
    late = due is not None and (today - due[0]).days > due[1]
    if newest is None:
        note = "yalnızca dekont ve banka bildirimlerinden biliniyor"
    elif due is None:
        note = f"son döküm {_day(newest.cut_date)}"
    else:
        note = f"son ekstre {_day(newest.cut_date)}; sonraki ~{_day(due[0])}" + (" (gecikti)" if late else "")
    return Freshness(
        account=account,
        kind=kind,
        document=sha,
        name=name,
        last=last,
        behind=(today - last).days,
        expected=due[0] if due else None,
        late=late,
        missing=holes.get(account, ()),
        note=note,
        link=Link(Screen.ACCOUNT, account),
    )


def _documents_by_sha(ws: Workspace) -> dict[str, DocumentRow]:
    with ws.db() as db:
        return {d.sha256: d for d in documents.every(db)}


def freshness(ws: Workspace, a: Analysis, today: date) -> list[Freshness]:
    """How far each open account's documents reach, the most behind first: its newest document, the next statement
    due and whether it is late, and the months its statements skip."""
    ds = a.dataset
    seen = last_seen(ds)
    gone = closed(seen)
    holes = {gap.id: gap.months for gap in document_gaps(ds, today)}
    docs = _documents_by_sha(ws)
    found = [
        _freshness(ds, account, last, today, holes, docs)
        for account, last in seen.items()
        if account not in gone and account in ds.accounts
    ]
    return sorted(found, key=lambda f: (-f.behind, f.account))


# --- the accounts ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Known:
    """What "Şu an" knows of the open accounts' balances and cards."""

    balances: dict[str, now.Balance]
    cards: dict[str, now.Card]
    unknown: dict[str, str]


def _known(a: Analysis) -> _Known:
    found, unknown = now.balances(a)
    cards, without = now.cards(a)
    return _Known(
        {b.account: b for b in found},
        {c.account: c for c in cards},
        {u.account: u.reason for u in [*unknown, *without]},
    )


def _card_day(ds: Dataset, card: now.Card) -> date:
    """The newest day a card's debt knows of: its cut, or the newest payment since."""
    return max([card.cut, *(t.date for t in payments_after(ds, card.account, card.cut))])


def _balance(
    ds: Dataset, account: str, known: _Known, gone: bool
) -> tuple[Decimal | None, Decimal | None, date | None, Certainty | None, str]:
    """(balance, TL value, its day, certainty, note) of an account."""
    found = ds.accounts[account]
    if gone:
        start = start_of(ds, account)
        if start is None:
            return None, None, None, None, "kapanmış ya da artık izlenmeyen hesap; bakiyesi belgelerde yok"
        note = f"son bakiye {_day(start.on)} tarihli; kapanmış ya da artık izlenmeyen hesap, toplamlara girmez"
        return start.balance, None, start.through, None, note
    if (card := known.cards.get(account)) is not None:
        if card.debt is None:
            return None, None, card.cut, card.certainty, f"banka kartı: borç taşımaz; {card.note}"
        return -card.debt, -card.debt, _card_day(ds, card), card.certainty, card.note
    if (b := known.balances.get(account)) is not None:
        return b.balance, b.value, b.through, b.certainty, b.note
    if found.type == AccountType.BROKERAGE:
        return None, None, None, None, "hesabın ekstresi yok"
    return None, None, None, None, known.unknown.get(account, "bakiyesi hiçbir belgede yazmıyor")


def _month_flow(account_type: AccountType, rows: list[transactions.RowView], today: date) -> MonthFlow:
    month = month_of(today)
    of_month = [r for r in rows if month_of(r.day) == month and r.day <= today]
    t = transactions.totals(of_month)
    # The ledger leaves a foreign account's transfers between own accounts out: they have no TL value of their own.
    note = "kendi hesaplarınızla aranızdaki döviz transferleri sayılmaz" if account_type == AccountType.FX else ""
    return MonthFlow(month, t.money_in, t.money_out, t.counted, t.provisional, note)


def _views(ws: Workspace, a: Analysis, today: date, known: _Known, wanted: Collection[str]) -> list[AccountView]:
    """The wanted accounts as the Accounts screen shows them."""
    ds = a.dataset
    seen = last_seen(ds)
    gone = closed(seen)
    holes = {gap.id: gap.months for gap in document_gaps(ds, today)}
    docs = _documents_by_sha(ws)
    by_account: defaultdict[str, list[transactions.RowView]] = defaultdict(list)
    for r in transactions.every_row(a):
        by_account[r.account].append(r)
    found: list[AccountView] = []
    for account in (ds.accounts[key] for key in wanted):
        is_gone = account.id in gone
        balance, value, day, certainty, note = _balance(ds, account.id, known, is_gone)
        last = seen.get(account.id)
        found.append(
            AccountView(
                id=account.id,
                label=account.label,
                alias=a.aliases.get(account.id, ""),
                bank=account.bank,
                type=account.type,
                group=GROUP_OF[account.type],
                currency=account.currency,
                balance=balance,
                value=value,
                day=day,
                certainty=certainty,
                note=note,
                freshness=_freshness(ds, account.id, last, today, holes, docs) if last is not None else None,
                month=_month_flow(account.type, by_account.get(account.id, []), today),
                closed=is_gone,
                link=Link(Screen.ACCOUNT, account.id),
            )
        )
    return found


def _sums(views: list[AccountView]) -> tuple[Decimal, Decimal]:
    assets = sum((v.value for v in views if v.value is not None and v.value > 0), ZERO)
    debts = -sum((v.value for v in views if v.value is not None and v.value < 0), ZERO)
    return assets, debts


def overview(ws: Workspace, a: Analysis, today: date) -> Overview:
    """The open accounts in F07's groups, each group's assets and debts apart, and the closed accounts apart."""
    views = _views(ws, a, today, _known(a), list(a.dataset.accounts))
    names = account_labels(a)
    open_ = [v for v in views if not v.closed]
    groups: list[Group] = []
    for group in AccountGroup:
        members = [v for v in open_ if v.group is group]
        if not members:
            continue
        members.sort(key=lambda v: (v.value is None, -abs(v.value or ZERO), names.get(v.id, v.id)))
        assets, debts = _sums(members)
        unvalued = sum(1 for v in members if v.value is None)
        groups.append(Group(group, assets, debts, assets - debts, unvalued, members))
    gone = sorted(
        (v for v in views if v.closed), key=lambda v: v.freshness.last if v.freshness else date.min, reverse=True
    )
    assets, debts = _sums(open_)
    note = (
        "Bakiyeler hesapların son belgelerinden, sonraki dekont ve bildirimlerle; kart borçları son ekstreden, "
        "kesimden sonraki ödemeler düşülerek. TL değeri bilinmeyenler (altın, kuru olmayan döviz) ve kapanmış "
        "hesaplar toplamlara girmez."
    )
    return Overview(today, groups, gone, assets, debts, assets - debts, note)


# --- an account's page -----------------------------------------------------------------------------------------------


def detail(ws: Workspace, a: Analysis, account: str, today: date, order: transactions.Order) -> Detail:
    """An account's page: its card on the Accounts screen, its rows a page at a time, and what its type adds."""
    ds = a.dataset
    if account not in ds.accounts:
        raise NotFound(account)
    known = _known(a)
    [view] = _views(ws, a, today, known, [account])
    wanted = transactions.Filter(accounts=frozenset({account}))
    rows = transactions.select(a, wanted)
    page = transactions.page(a, wanted, order)
    points, curve_note = account_pages.curve(ds, account)
    window = account_pages.window(ds, today)
    fees = account_pages.fees(rows, window)
    kind = ds.accounts[account].type
    paying = kind in _PAYING
    subscriptions = outlook.subscriptions(a) if paying else None
    payments = [s for s in subscriptions.series if s.account == account and s.listed] if subscriptions else []
    income = [s for s in subscriptions.income if s.account == account and s.listed] if subscriptions else []
    below = any(p.balance < 0 for p in points) or (view.balance is not None and view.balance < 0)
    overdraft = kind == AccountType.OVERDRAFT or (kind == AccountType.CURRENT and below)
    return Detail(
        account=view,
        page=page,
        curve=points,
        curve_note=curve_note,
        months=account_pages.months(ds, account, rows, today),
        fees=fees,
        payments=payments,
        income=income,
        card=account_pages.card_page(a, account, today) if kind in CARD_TYPES else None,
        overdraft=account_pages.overdraft_page(points, view.balance, fees) if overdraft else None,
        deposit=account_pages.deposit_page(view.balance) if kind == AccountType.DEPOSIT else None,
        holding=(
            account_pages.holding_page(ds, account, known.balances.get(account))
            if kind in (AccountType.FX, AccountType.GOLD)
            else None
        ),
        brokerage=(account_pages.brokerage_page(ds, account, rows, window) if kind == AccountType.BROKERAGE else None),
        loan=account_pages.loan_page(a, account, rows, today) if kind == AccountType.LOAN else None,
    )


# --- the name the user gives an account ------------------------------------------------------------------------------


def rename(ws: Workspace, a: Analysis, account: str, alias: str, actor: Actor) -> str:
    """Give the account a name of the user's own; an empty one takes it away. The bank's label stays the account's
    own: the baseline, the report and the exports keep it. Returns the name kept."""
    if account not in a.dataset.accounts:
        raise NotFound(account)
    alias = " ".join(alias.split())
    if len(alias) > MAX_ALIAS:
        raise Refused(f"Hesabın adı en çok {MAX_ALIAS} karakter olabilir.")
    with ws.db() as db:
        kept = aliases.change(db, account, alias, actor)
    return kept.alias if kept is not None else ""


# --- what the MCP server's accounts tool reports ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Statements:
    """What an account's statements and lists cover."""

    count: int
    verified: int
    first: date | None  # the first day the oldest covers
    last: date | None  # the newest one's last day
    full_months: int  # months they cover in full (insights.FULL)
    partial_months: list[str]  # months they cover only partly


def statements_of(ds: Dataset, account: str) -> Statements:
    found = [s for s in ds.statements if s.account == account]
    covered = ds.coverage.get(account, {})
    return Statements(
        count=len(found),
        verified=sum(s.verified for s in found),
        first=min((s.start or s.cut_date for s in found), default=None),
        last=max((s.cut_date for s in found), default=None),
        full_months=sum(share >= FULL for share in covered.values()),
        partial_months=sorted(m for m, share in covered.items() if share < FULL),
    )
