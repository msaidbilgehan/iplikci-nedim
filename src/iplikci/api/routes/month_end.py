"""The month-end closing (F11) for the Ay sonu screen: the months with their statuses, and one month in full. The
months' script-free pages to keep are the exports' (F20). Amounts are minor units with their currency
(architecture §16)."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel

from ...app import closing, transactions
from ...app.analysis import Analysis, account_labels
from ...app.closing import EvidenceStatus, MonthEnd, MonthStatus, StatementCheck
from ...app.exports import ExportKind
from ...app.links import Link, Screen
from ...app.workspace import Busy
from ..context import Context, context_of
from ..guard import Principal
from ..models import (
    AccountRefOut,
    LinkOut,
    MoneyOut,
    RowOut,
    SavingPartOut,
    account_ref,
    link_out,
    money,
    row_out,
    saving_part_out,
)
from ..problems import Problem
from .deps import only

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])

Month = Annotated[str, Path(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


class MonthEndTotalsOut(BaseModel):
    """A month's totals by calendar month (docs/domain/interpretation.md, "Ay sonu kapanışı")."""

    expense: MoneyOut  # purchases, refunds, interest and fees
    income: MoneyOut | None  # null when no bank account's list covers half the month
    people: MoneyOut  # money sent to people
    debt: MoneyOut  # loan principal repaid
    # What was set aside: BES and investments, currency, gold, deposits and investment accounts; below zero what was
    # taken out of the savings (currency sold, a deposit drawn).
    saving: MoneyOut
    saving_parts: list[SavingPartOut]  # the saving's parts, the largest first
    fees: MoneyOut  # interest and fees, part of expense
    left: MoneyOut | None  # income less the rest; null without income


class MonthEndOut(BaseModel):
    month: str  # YYYY-MM
    name: str  # "Ekim 2026"
    status: MonthStatus
    summary: str  # the closing in one Turkish sentence, after the status' label
    totals: MonthEndTotalsOut
    provisional: int  # rows only receipts and notices show yet
    unmatched: int  # receipts' rows the statements covering their days do not show
    income_note: str  # where the income comes from, or why it is as it is
    closes_by: date | None  # a month waiting for card statements: the last one's cut, when one can be promised
    link: LinkOut


class MonthEndListOut(BaseModel):
    today: date
    months: list[MonthEndOut]  # the current month and the twelve before it with documents, the newest first
    export: ExportKind  # their script-free pages to keep: GET /api/exports/{export} downloads them zipped (F20)


class MonthEndRangeOut(BaseModel):
    start: date
    end: date


class MonthEndStatementOut(BaseModel):
    """A statement or a list overlapping the month, with the days of the month it covers."""

    start: date
    end: date
    cut: date  # its cut date, or a list's last day
    card: bool  # a card statement; else an account's list
    check: StatementCheck
    document: str  # sha256


class MonthEndReceiptsOut(BaseModel):
    matched: int  # a statement shows them
    provisional: int  # after the newest statement: counted now, the next one confirms them
    unmatched: int  # the statements covering their days do not show them
    no_statement: int  # no statement covers their days


class MonthEndAccountOut(BaseModel):
    """One account in one month."""

    account: AccountRefOut
    status: MonthStatus
    label: str  # the status as an account's closing reads it ("Bekleniyor", "Kontrol edin")
    blocking: bool  # the month waits for it; a brokerage account never holds a month open
    needed: int  # days of the month its documents should cover (in the current month, up to today)
    covered: int
    open: list[MonthEndRangeOut]  # days not covered: missing before its newest statement, waiting after it
    statements: list[MonthEndStatementOut]
    receipts: MonthEndReceiptsOut
    balance: MoneyOut | None  # the month-end balance a list prints, in the account's currency
    last: date  # the newest day its documents cover
    next_cut: date | None  # a card's: the cut of the next statement the open days wait for
    next_cut_printed: bool  # that day is the one the statement before prints, not one reckoned a month on
    late: bool  # that day passed days ago and the statement did not come
    untracked: bool  # known only from a passbook: its days after it are not awaited
    waiting_for: str  # what closes its month, in a few Turkish words: "19–31 Ekim, 19 Ekim–18 Kasım ekstresinde"
    note: str  # what there is to know about it this month, in one Turkish line


class MonthEndShareOut(BaseModel):
    name: str  # a group, a necessity level, a category or a merchant
    slot: int  # its colour slot (the charts' fixed slots)
    amount: MoneyOut
    count: int | None  # rows: a category's or a merchant's
    code: str  # a level's necessity code, İşlemler's filter (required, optional, unnecessary, unknown); "" otherwise


class MonthEndRegularOut(BaseModel):
    """A regular payment this month: paid, or expected and not seen yet."""

    payee: str
    category: str
    paid: list[RowOut]  # its payments this month
    expected: date | None  # the day it was expected, when not paid yet
    this_month: MoneyOut  # what was paid this month
    monthly: MoneyOut  # what it costs a month


class MonthEndTrendOut(BaseModel):
    month: str
    expense: MoneyOut


class MonthEndDetailOut(BaseModel):
    month: MonthEndOut
    previous: MonthEndTotalsOut | None  # the month before
    typical: MoneyOut | None  # the median expense of up to six complete months before this one
    typical_months: int
    accounts: list[MonthEndAccountOut]  # the accounts holding it open first
    groups: list[MonthEndShareOut]
    levels: list[MonthEndShareOut]
    categories: list[MonthEndShareOut]  # the most spent first
    merchants: list[MonthEndShareOut]
    regular: list[MonthEndRegularOut]
    big: list[RowOut]  # big one-off spending
    provisional: list[RowOut]  # the rows only receipts and notices show yet: counted, provisional
    unmatched: list[RowOut]  # the receipts' rows no statement covering their days shows: excluded
    count: int  # expense rows
    trend: list[MonthEndTrendOut]  # the expense of the twelve months up to this one
    debt_end: MoneyOut | None  # card statement balances and overdraft use at the month's end
    previous_month: str  # YYYY-MM, for the page's navigation
    next_month: str
    export: ExportKind  # its script-free page among the months': GET /api/exports/{export} downloads them zipped


def _analysis(context: Context) -> Analysis:
    try:
        return context.analysis.get()
    except Busy as exc:
        raise Problem(503, "busy", str(exc)) from exc


def _optional(value: Decimal | None, currency: str = "TRY") -> MoneyOut | None:
    return None if value is None else money(value, currency)


def _totals(t: closing.Totals, month: str) -> MonthEndTotalsOut:
    return MonthEndTotalsOut(
        expense=money(t.expense),
        income=_optional(t.income),
        people=money(t.people),
        debt=money(t.debt),
        saving=money(t.saving),
        saving_parts=[saving_part_out(p) for p in transactions.saving_shown(month, t.saving_parts)],
        fees=money(t.fees),
        left=_optional(t.left),
    )


def _link(found: Link) -> LinkOut:
    out = link_out(found)
    assert out is not None  # link_out gives None only for no link
    return out


def _month(me: MonthEnd) -> MonthEndOut:
    return MonthEndOut(
        month=me.month,
        name=me.name,
        status=me.status,
        summary=me.summary,
        totals=_totals(me.totals, me.month),
        provisional=len(me.provisional),
        unmatched=len(me.unmatched),
        income_note=me.income_note,
        closes_by=me.closes_by,
        link=_link(Link(Screen.MONTH, me.month)),
    )


@router.get("/api/month-end")
def month_list(request: Request) -> MonthEndListOut:
    """The current month and the twelve before it with documents, the newest first, each with its status."""
    context = context_of(request)
    today = context.today()
    months = [_month(me) for me in closing.months(_analysis(context), today)]
    return MonthEndListOut(today=today, months=months, export=ExportKind.MONTH_END)


def _account(ac: closing.AccountClose, labels: dict[str, str]) -> MonthEndAccountOut:
    return MonthEndAccountOut(
        account=account_ref(ac.account.id, labels),
        status=ac.status,
        label=closing.ACCOUNT_STATUS[ac.status],
        blocking=ac.blocking,
        needed=ac.needed,
        covered=ac.covered,
        open=[MonthEndRangeOut(start=lo, end=hi) for lo, hi in ac.open],
        statements=[
            MonthEndStatementOut(
                start=lo, end=hi, cut=s.cut_date, card=not s.is_account, check=closing.check_of(s), document=s.document
            )
            for s, lo, hi in ac.statements
        ],
        receipts=MonthEndReceiptsOut(
            matched=ac.count(EvidenceStatus.MATCHED),
            provisional=ac.count(EvidenceStatus.PROVISIONAL),
            unmatched=ac.count(EvidenceStatus.UNMATCHED),
            no_statement=ac.count(EvidenceStatus.NO_STATEMENT),
        ),
        balance=_optional(ac.balance, ac.account.currency),
        last=ac.last,
        next_cut=ac.next_cut.day if ac.next_cut else None,
        next_cut_printed=ac.next_cut is not None and ac.next_cut.printed,
        late=ac.late,
        untracked=ac.untracked,
        waiting_for=ac.waiting_for if ac.status is not MonthStatus.CLOSED else "",
        note=ac.note,
    )


@router.get("/api/month-end/{month}")
def month_detail(request: Request, month: Month) -> MonthEndDetailOut:
    """One month in full: each account's closing and what it waits for, the totals against the month before and the
    typical month, where the money went, the regular payments, and the rows receipts and notices show."""
    context = context_of(request)
    a = _analysis(context)
    me = closing.month(a, month, context.today())
    labels = account_labels(a)
    found = closing.rows_of(a, me)
    regular = [
        MonthEndRegularOut(
            payee=r.payee,
            category=r.category,
            paid=[row_out(row, labels) for row in r.paid],
            expected=r.expected,
            this_month=money(r.this_month),
            monthly=money(r.monthly),
        )
        for r in found.regular
    ]
    return MonthEndDetailOut(
        month=_month(me),
        previous=None if me.previous is None else _totals(me.previous, closing.shift(me.month, -1)),
        typical=_optional(me.typical),
        typical_months=me.typical_months,
        accounts=[_account(ac, labels) for ac in me.accounts],
        groups=[MonthEndShareOut(name=g, slot=slot, amount=money(v), count=None, code="") for g, slot, v in me.groups],
        levels=[
            MonthEndShareOut(name=level, slot=slot, amount=money(v), count=None, code=str(code))
            for (level, slot, v), code in zip(me.levels, me.level_codes, strict=True)
        ],
        categories=[
            MonthEndShareOut(name=c, slot=slot, amount=money(v), count=n, code="") for c, slot, v, n in me.categories
        ],
        merchants=[
            MonthEndShareOut(name=m, slot=slot, amount=money(v), count=n, code="") for m, slot, v, n in me.merchants
        ],
        regular=regular,
        big=[row_out(r, labels) for r in found.big],
        provisional=[row_out(r, labels) for r in found.provisional],
        unmatched=[row_out(r, labels) for r in found.unmatched],
        count=me.count,
        trend=[MonthEndTrendOut(month=m, expense=money(v)) for m, v in me.trend],
        debt_end=_optional(me.debt_end),
        previous_month=closing.shift(me.month, -1),
        next_month=closing.shift(me.month, 1),
        export=ExportKind.MONTH_END,
    )
