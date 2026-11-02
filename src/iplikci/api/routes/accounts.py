"""The accounts (F07) for the Hesaplar screen: the open accounts in their groups with each group's assets and debts
apart, the closed ones apart; an account's page with its rows a page at a time, its daily balance, its months and
fees and what its type adds; the name the user gives an account; and where the money went between the accounts (the
Sankey and its table). Amounts are minor units with their currency; what no document prints is null (architecture
§16). Reading needs a session or the token; naming an account, the service's own pages."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import BaseModel, Field

from ...app import accounts, flows, reach, transactions
from ...app.accounts import AccountGroup, AccountType, Actor, Certainty, DocumentKind, PaidStatus
from ...app.analysis import Analysis, account_labels
from ...app.flows import FlowKind, TransactionKind
from ...app.links import Link, Screen
from ...app.workspace import Busy
from ..context import Context, context_of
from ..guard import Principal
from ..models import AccountRefOut, LinkOut, MoneyOut, RowOut, account_ref, link_out, money, row_out
from ..problems import Problem
from .deps import only
from .feed import NowCardOut, card_out
from .outlook import CalendarItemOut, InstallmentOut, SeriesOut, calendar_item, installment_out, series_out
from .transactions import TotalsOut

router = APIRouter()

READ = [Depends(only(Principal.BROWSER, Principal.CLIENT))]
WRITE = [Depends(only(Principal.BROWSER))]
AccountId = Annotated[str, Path(min_length=1, max_length=100)]


class FreshnessOut(BaseModel):
    """How far an account's documents reach."""

    account: AccountRefOut
    kind: DocumentKind  # what its newest document is
    document: str  # that document's sha256; "" when unknown
    name: str  # its readable name
    last: date  # the newest day its documents reach
    behind: int  # days from that to today
    expected: date | None  # when its next statement is due: a card's next cut, a brokerage statement's month end
    late: bool  # that day passed days ago without it: five days for a card, ten for a brokerage statement
    missing: list[str]  # months inside its statements they cover only partly or not
    note: str
    link: LinkOut


class CoverOut(BaseModel):
    account: AccountRefOut
    closed: bool  # its documents stopped 180 days before the newest
    shares: list[str]  # one per month: the share of its days its statements and lists cover, a decimal ("0.452")
    link: LinkOut


class CoverageOut(BaseModel):
    """How much of each month each account's statements and account lists cover: the MVP report's coverage grid."""

    months: list[str]  # YYYY-MM, from the first month any account's documents cover to the last
    accounts: list[CoverOut]  # the open accounts first, then the closed, each by its name


class MonthFlowOut(BaseModel):
    """The money in and out of an account in the current month so far, counted rows only, in TL."""

    month: str  # YYYY-MM
    money_in: MoneyOut
    money_out: MoneyOut
    rows: int
    provisional: int  # rows only a receipt or a notice shows yet
    note: str  # what the sums leave out; "" when nothing


class AccountOut(BaseModel):
    account: AccountRefOut  # its id and the name the screens show: the user's name for it, else the bank's label
    label: str  # the bank's label
    alias: str  # the name the user gave it; "" for none
    bank: str
    type: AccountType
    group: AccountGroup
    balance: MoneyOut | None  # in its currency (gold as "GR"); below zero: a debt; null: unknown
    value: MoneyOut | None  # in TL; null without a rate (gold), for a closed account, or an unknown balance
    day: date | None  # the newest day the balance knows of
    certainty: Certainty | None  # provisional: moved by receipts and notices since the document that printed it
    note: str  # what the balance rests on, or why there is none
    freshness: FreshnessOut | None
    month: MonthFlowOut
    closed: bool  # its documents stopped 180 days before the newest: listed apart, in no total
    link: LinkOut


class GroupOut(BaseModel):
    group: AccountGroup
    assets: MoneyOut  # the TL values above zero
    debts: MoneyOut  # the TL values below zero, above zero
    total: MoneyOut
    unvalued: int  # its accounts without a TL value, left out of the totals
    accounts: list[AccountOut]  # the largest TL value first


class AccountsOut(BaseModel):
    today: date
    groups: list[GroupOut]  # in F07's order, only the groups with an open account
    closed: list[AccountOut]  # the newest documents first
    assets: MoneyOut
    debts: MoneyOut
    total: MoneyOut
    note: str


class CurvePointOut(BaseModel):
    day: date
    balance: MoneyOut  # at the day's end; below zero: overdrawn
    certainty: Certainty  # confirmed: a list or a bank's notice printed it; provisional: moved by receipts since


class MonthTotalsOut(BaseModel):
    month: str
    money_in: MoneyOut
    money_out: MoneyOut
    rows: int
    complete: bool  # an ended month the account's documents cover in full


class FeeOut(BaseModel):
    category: str
    amount: MoneyOut  # below zero: refunded more than charged


class FeesOut(BaseModel):
    months: list[str]  # the window: up to the last 12 complete months
    total: MoneyOut
    categories: list[FeeOut]  # the largest first


class StatementOut(BaseModel):
    """A card statement on the card's timeline."""

    cut: date
    start: date
    end: date
    total: MoneyOut | None  # its balance (dönem borcu); a debit card's: the sum of its purchases
    due: date | None
    minimum: MoneyOut | None
    limit: MoneyOut | None
    rows: int
    spent: MoneyOut  # purchases less refunds, interest and fees
    verified: bool
    document: str  # sha256
    paid: MoneyOut | None  # a credit card's: paid by the next statement's cut, the newest's by today
    status: PaidStatus | None  # how it was paid; null for a debit card


class ScheduleMonthOut(BaseModel):
    month: str
    amount: MoneyOut
    count: int


class CardPageOut(BaseModel):
    statement: NowCardOut | None  # the newest statement and the period the card is in; null for a closed card
    statements: list[StatementOut]  # the newest first
    installments: list[InstallmentOut]  # the purchases in installments with some still to come
    schedule: list[ScheduleMonthOut]  # those installments by the month their statement bills them
    left: MoneyOut


class OverdraftOut(BaseModel):
    limit: MoneyOut | None  # no reader reads an overdraft limit yet
    used: MoneyOut  # today's balance below zero; zero when the account is in credit
    days_below: int  # days the balance ended below zero within the window
    window_start: date | None  # the curve's last 365 days
    window_end: date | None
    interest: MoneyOut  # overdraft interest within the fees' window
    note: str


class DepositOut(BaseModel):
    principal: MoneyOut | None
    rate: str | None  # no document read so far prints these three
    maturity: date | None
    interest: MoneyOut | None
    note: str


class HoldingOut(BaseModel):
    """A foreign currency or gold account."""

    amount: MoneyOut | None  # in its currency, gold as "GR"
    value: MoneyOut | None  # in TL at the documents' newest rate; null without one (gold)
    rate: str | None  # TL for one unit, as a decimal number
    rate_day: date | None
    cost: MoneyOut | None  # TL paid for it where the documents tell: gold bought from a TL account of the same bank
    gain: MoneyOut | None  # value less cost, when both are known
    note: str


class SecurityOut(BaseModel):
    code: str
    name: str
    quantity: str  # as a decimal number
    value: MoneyOut  # at the market value the statement prints
    as_of: date


class BrokerageOut(BaseModel):
    as_of: date | None
    securities: list[SecurityOut]
    cash: MoneyOut | None
    worth: MoneyOut | None  # cash and securities
    dividends: MoneyOut  # within the fees' window
    dividend_rows: int
    note: str


class LoanInstallmentOut(BaseModel):
    day: date
    principal: MoneyOut
    cost: MoneyOut  # interest and taxes
    document: str  # the receipt's sha256
    certainty: Certainty


class LoanOut(BaseModel):
    installments: list[LoanInstallmentOut]  # the newest first
    principal_paid: MoneyOut
    interest_paid: MoneyOut
    next: list[CalendarItemOut]  # the calendar's coming installments
    remaining: MoneyOut | None  # the remaining principal: no receipt prints it
    note: str


class AccountDetailOut(BaseModel):
    """An account's page (F07)."""

    account: AccountOut
    rows: list[RowOut]  # its rows, the newest first, a page at a time
    totals: TotalsOut  # what all its rows add up to
    offset: int
    next: int | None  # the next page's offset; null on the last
    curve: list[CurvePointOut]  # its balance day by day: a TL bank account's
    curve_note: str
    months: list[MonthTotalsOut]  # the last 12 months' money in and out, the oldest first
    fees: FeesOut
    payments: list[SeriesOut]  # the regular and periodic payments last made from it
    income: list[SeriesOut]  # the regular income that last came into it
    card: CardPageOut | None
    overdraft: OverdraftOut | None  # an overdraft account, or one whose balance went below zero
    deposit: DepositOut | None
    holding: HoldingOut | None  # a foreign currency or gold account
    brokerage: BrokerageOut | None
    loan: LoanOut | None


class AliasIn(BaseModel):
    alias: str = Field(max_length=200)  # "" takes the name away; at most 60 characters once its spaces are trimmed


class AliasOut(BaseModel):
    account: AccountRefOut  # the name the screens show now
    alias: str


class FlowNodeOut(BaseModel):
    id: str  # an account's id, else "<kind>" or "<kind>:<name>"
    kind: FlowKind
    name: str  # an income's payer or a spending group; "" for the others
    account: AccountRefOut | None  # an account node's account


class FlowEdgeOut(BaseModel):
    source: str  # a node's id
    target: str
    amount: MoneyOut  # what went this way less what came back
    rows: int
    kinds: list[TransactionKind]
    link: LinkOut  # those rows on the Transactions screen


class FlowsOut(BaseModel):
    start: date
    end: date
    nodes: list[FlowNodeOut]
    edges: list[FlowEdgeOut]  # the largest first
    note: str


def _analysis(context: Context) -> Analysis:
    try:
        return context.analysis.get()
    except Busy as exc:
        raise Problem(503, "busy", str(exc)) from exc


def _link(found: Link) -> LinkOut:
    out = link_out(found)
    assert out is not None  # link_out gives None only for no link
    return out


def freshness_out(f: accounts.Freshness, labels: dict[str, str]) -> FreshnessOut:
    return FreshnessOut(
        account=account_ref(f.account, labels),
        kind=f.kind,
        document=f.document,
        name=f.name,
        last=f.last,
        behind=f.behind,
        expected=f.expected,
        late=f.late,
        missing=list(f.missing),
        note=f.note,
        link=_link(f.link),
    )


def _account(v: accounts.AccountView, labels: dict[str, str]) -> AccountOut:
    m = v.month
    return AccountOut(
        account=account_ref(v.id, labels),
        label=v.label,
        alias=v.alias,
        bank=v.bank,
        type=v.type,
        group=v.group,
        balance=None if v.balance is None else money(v.balance, v.currency),
        value=None if v.value is None else money(v.value),
        day=v.day,
        certainty=v.certainty,
        note=v.note,
        freshness=None if v.freshness is None else freshness_out(v.freshness, labels),
        month=MonthFlowOut(
            month=m.month,
            money_in=money(m.money_in),
            money_out=money(m.money_out),
            rows=m.rows,
            provisional=m.provisional,
            note=m.note,
        ),
        closed=v.closed,
        link=_link(v.link),
    )


@router.get("/api/accounts", dependencies=READ)
def account_list(request: Request) -> AccountsOut:
    """The open accounts in their groups with each group's assets and debts apart, and the closed accounts apart."""
    context = context_of(request)
    a = _analysis(context)
    found = accounts.overview(context.ws, a, context.today())
    labels = account_labels(a)
    return AccountsOut(
        today=found.today,
        groups=[
            GroupOut(
                group=g.group,
                assets=money(g.assets),
                debts=money(g.debts),
                total=money(g.total),
                unvalued=g.unvalued,
                accounts=[_account(v, labels) for v in g.accounts],
            )
            for g in found.groups
        ],
        closed=[_account(v, labels) for v in found.closed],
        assets=money(found.assets),
        debts=money(found.debts),
        total=money(found.total),
        note=found.note,
    )


@router.get("/api/accounts/flows", dependencies=READ)
def account_flows(
    request: Request,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
) -> FlowsOut:
    """Where the money went between the accounts from one day to another; without days, over the newest complete
    month."""
    context = context_of(request)
    a = _analysis(context)
    first, last = flows.default_window(a.dataset, context.today())
    start, end = start or first, end or last
    if end < start:
        raise Problem(400, "window_invalid", "Bitiş günü başlangıçtan önce olamaz.")
    found = flows.flows(a, start, end)
    labels = account_labels(a)
    return FlowsOut(
        start=found.start,
        end=found.end,
        nodes=[
            FlowNodeOut(
                id=n.id, kind=n.kind, name=n.name, account=account_ref(n.account, labels) if n.account else None
            )
            for n in found.nodes
        ],
        edges=[
            FlowEdgeOut(
                source=e.source,
                target=e.target,
                amount=money(e.amount),
                rows=e.rows,
                kinds=list(e.kinds),
                link=_link(e.link),
            )
            for e in found.edges
        ],
        note=found.note,
    )


def _optional(value: Decimal | None) -> MoneyOut | None:
    return None if value is None else money(value)


def _card_page(found: accounts.CardPage, labels: dict[str, str]) -> CardPageOut:
    return CardPageOut(
        statement=None if found.statement is None else card_out(found.statement, labels),
        statements=[
            StatementOut(
                cut=s.cut,
                start=s.start,
                end=s.end,
                total=_optional(s.total),
                due=s.due,
                minimum=_optional(s.minimum),
                limit=_optional(s.limit),
                rows=s.rows,
                spent=money(s.spent),
                verified=s.verified,
                document=s.document,
                paid=_optional(s.paid),
                status=s.status,
            )
            for s in found.statements
        ],
        installments=[installment_out(i, labels) for i in found.installments],
        schedule=[ScheduleMonthOut(month=m.month, amount=money(m.amount), count=m.count) for m in found.schedule],
        left=money(found.left),
    )


def _detail(found: accounts.Detail, labels: dict[str, str]) -> AccountDetailOut:
    page, t = found.page, found.page.totals
    o, d, h, b, loan = found.overdraft, found.deposit, found.holding, found.brokerage, found.loan
    currency = found.account.currency
    return AccountDetailOut(
        account=_account(found.account, labels),
        rows=[row_out(r, labels) for r in page.rows],
        totals=TotalsOut(
            count=t.count,
            counted=t.counted,
            spent=money(t.spent),
            money_out=money(t.money_out),
            money_in=money(t.money_in),
            provisional=t.provisional,
            excluded=t.excluded,
        ),
        offset=page.offset,
        next=page.next,
        curve=[CurvePointOut(day=p.day, balance=money(p.balance), certainty=p.certainty) for p in found.curve],
        curve_note=found.curve_note,
        months=[
            MonthTotalsOut(
                month=m.month,
                money_in=money(m.money_in),
                money_out=money(m.money_out),
                rows=m.rows,
                complete=m.complete,
            )
            for m in found.months
        ],
        fees=FeesOut(
            months=list(found.fees.months),
            total=money(found.fees.total),
            categories=[FeeOut(category=c, amount=money(v)) for c, v in found.fees.by_category],
        ),
        payments=[series_out(s, labels) for s in found.payments],
        income=[series_out(s, labels) for s in found.income],
        card=None if found.card is None else _card_page(found.card, labels),
        overdraft=None
        if o is None
        else OverdraftOut(
            limit=None if o.limit is None else money(o.limit),
            used=money(o.used),
            days_below=o.days_below,
            window_start=o.window[0] if o.window else None,
            window_end=o.window[1] if o.window else None,
            interest=money(o.interest),
            note=o.note,
        ),
        deposit=None
        if d is None
        else DepositOut(
            principal=None if d.principal is None else money(d.principal),
            rate=None if d.rate is None else str(d.rate),
            maturity=d.maturity,
            interest=None if d.interest is None else money(d.interest),
            note=d.note,
        ),
        holding=None
        if h is None
        else HoldingOut(
            amount=None if h.amount is None else money(h.amount, h.currency),
            value=None if h.value is None else money(h.value),
            rate=None if h.rate is None else str(h.rate),
            rate_day=h.rate_day,
            cost=None if h.cost is None else money(h.cost),
            gain=None if h.gain is None else money(h.gain),
            note=h.note,
        ),
        brokerage=None
        if b is None
        else BrokerageOut(
            as_of=b.as_of,
            securities=[
                SecurityOut(code=x.code, name=x.name, quantity=str(x.quantity), value=money(x.value), as_of=x.as_of)
                for x in b.securities
            ],
            cash=None if b.cash is None else money(b.cash, currency),
            worth=None if b.worth is None else money(b.worth),
            dividends=money(b.dividends),
            dividend_rows=b.dividend_rows,
            note=b.note,
        ),
        loan=None
        if loan is None
        else LoanOut(
            installments=[
                LoanInstallmentOut(
                    day=i.day,
                    principal=money(i.principal),
                    cost=money(i.cost),
                    document=i.document,
                    certainty=i.certainty,
                )
                for i in loan.installments
            ],
            principal_paid=money(loan.principal_paid),
            interest_paid=money(loan.interest_paid),
            next=[calendar_item(item, labels) for item in loan.next],
            remaining=None if loan.remaining is None else money(loan.remaining),
            note=loan.note,
        ),
    )


def _share(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


@router.get("/api/accounts/coverage", dependencies=READ)
def account_coverage(request: Request) -> CoverageOut:
    """Each account's months as its statements and account lists cover them; receipts and notices cover none."""
    a = _analysis(context_of(request))
    labels = account_labels(a)
    found = reach.coverage(a.dataset, labels)
    return CoverageOut(
        months=list(found.months),
        accounts=[
            CoverOut(
                account=account_ref(c.account, labels),
                closed=c.closed,
                shares=[_share(share) for share in c.shares],
                link=_link(Link(Screen.ACCOUNT, c.account)),
            )
            for c in found.accounts
        ],
    )


@router.get("/api/accounts/{account}", dependencies=READ)
def account_page(
    request: Request,
    account: AccountId,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=transactions.MAX_PAGE)] = 50,
) -> AccountDetailOut:
    """An account's page: its card, its rows a page at a time (the newest first) and what its type adds."""
    context = context_of(request)
    a = _analysis(context)
    try:
        found = accounts.detail(context.ws, a, account, context.today(), transactions.Order(offset=offset, limit=limit))
    except accounts.NotFound as exc:
        raise Problem(404, "account_not_found", "Böyle bir hesap yok.") from exc
    return _detail(found, account_labels(a))


@router.put("/api/accounts/{account}/alias", dependencies=WRITE)
def account_alias(request: Request, account: AccountId, body: AliasIn) -> AliasOut:
    """Give the account a name of the user's own, or take it away with an empty one. The bank's label stays the
    account's own: the report, the exports and the MCP tools keep it."""
    context = context_of(request)
    a = _analysis(context)
    try:
        kept = accounts.rename(context.ws, a, account, body.alias, Actor.USER)
    except accounts.NotFound as exc:
        raise Problem(404, "account_not_found", "Böyle bir hesap yok.") from exc
    except accounts.Refused as exc:
        raise Problem(400, "alias_refused", str(exc)) from exc
    label = kept or a.dataset.accounts[account].label
    return AliasOut(account=AccountRefOut(id=account, label=label), alias=kept)
