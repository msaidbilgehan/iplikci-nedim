"""The feed (F05) for the Akış screen: the event log a page at a time, newest first, narrowed by the events' kinds and
by the accounts and the certainty they concern; and what stands now: each account's balance as far as the documents
tell, each card's statement and the period it is in, the month's pace against the typical month, and the next 14
days. Amounts are minor units with their currency; money in or out is said in words, not by a sign
(architecture §16)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from ...app import feed, now
from ...app.analysis import Analysis, account_labels
from ...app.feed import Certainty, DocumentKind, DocumentStatus, MonthStatus, PaymentKind, SeriesPeriod, SourceKind
from ...app.now import AccountType, BalanceSource
from ...app.outlook import Due
from ...app.workspace import Busy
from ..context import Context, context_of
from ..guard import Principal
from ..models import AccountRefOut, LinkOut, MoneyOut, PaceOut, RowOut, account_ref, link_out, money, pace_out, row_out
from ..problems import Problem
from .deps import only
from .outlook import CalendarItemOut

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])


class FeedDetailOut(BaseModel):
    """What an event's detail says (architecture §13); a field the event does not carry is null or empty."""

    title: str  # the name the user knows: a merchant, a payee or a payer, a seller, an account; "" for none
    amount: MoneyOut | None  # above zero: money out as the ledger counts it, and income too
    minimum: MoneyOut | None  # a card due's minimum payment
    balance: MoneyOut | None  # a forecast's balance on its day; below zero: overdrawn
    old: MoneyOut | None  # a price before it changed
    new: MoneyOut | None  # and after
    day: date | None  # the day it concerns: a row's, a due date, the forecast's, the expected one, a new price's first
    days: int | None  # from the day the analysis was made to that day
    payment: PaymentKind | None  # what falls due
    period: SeriesPeriod | None  # how far apart a missing payment's series pays
    cancelled: str  # the month the user's rules give a cancelled series as its last, YYYY-MM; "" for none
    status: MonthStatus | None  # an ended month's status
    count: int | None  # an event standing for many: how many
    first: date | None  # the days of the first and the last of the new rows it stands for
    last: date | None
    provisional: bool | None  # a new row only a receipt or a notice showed then
    source: SourceKind | None  # how a document arrived
    document_kind: DocumentKind | None  # what a read document turned out to be
    parser: str  # the reader that read a document or gave up on it; "" for none
    reader: str  # that reader, for people
    version: str  # its version, or the browser extension's
    reason: str  # why a document was not read, a login was refused, a statement did not verify
    stage: str  # a failed backup's: "backup" or "rehearsal"
    unverified: list[AccountRefOut]  # the accounts whose statements did not verify (a format alarm)


class FeedDocumentOut(BaseModel):
    """A document an event concerns, as the archive keeps it now."""

    sha256: str
    name: str  # its readable name, else the file's own
    kind: DocumentKind | None  # what reading found it to be; null when no reader took it
    status: DocumentStatus  # removed: it went to the system Trash


class FeedItemOut(BaseModel):
    """An event of the log, with what it concerns now and where it leads."""

    id: int  # its place in the log: the stream's event id, and a page's `before`
    at: str  # when it was recorded, ISO in UTC
    kind: str  # its code (architecture §13); /api/labels' EventKind names it
    label: str  # the kind, in Turkish
    text: str  # what happened, in a Turkish sentence (as a notification in full says it)
    target: str  # what it concerns, as the log keys it; "" for an event standing for many
    account: AccountRefOut | None  # the one account it concerns; null for none or several
    certainty: Certainty | None  # a row event's: how the ledger counts the row now
    detail: FeedDetailOut
    row: RowOut | None  # the row it concerns as the ledger counts it now (a confirmed receipt's: the statement's row)
    document: FeedDocumentOut | None  # the document a document event concerns
    link: LinkOut | None  # where it leads


class FeedOut(BaseModel):
    items: list[FeedItemOut]  # newest first
    # The next page's `before`; null when nothing older is left. A narrow filter may give a page shorter than its
    # limit with more still to read: only null ends the feed.
    next: int | None


class NowBalanceOut(BaseModel):
    """An account's balance today as far as the documents tell: the newest balance a document prints, moved by the
    receipt and notice rows after it."""

    account: AccountRefOut
    type: AccountType
    balance: MoneyOut  # in the account's currency (grams of gold as "GR"); below zero: overdrawn
    value: MoneyOut | None  # in TL: a foreign balance at the documents' newest rate; null without one (gold)
    rate: str | None  # that rate, TL for one unit, as a decimal number ("34.5012")
    rate_day: date | None  # the day of the document that printed it
    stated: MoneyOut  # the balance the newest document printed
    on: date  # that document's day
    source: BalanceSource
    moves: int  # the receipt and notice rows after it, counted in balance
    through: date  # the newest day the balance knows of
    certainty: Certainty  # confirmed: printed by a document; provisional: moved since by receipts and notices
    note: str  # what it rests on, in Turkish


class UnknownOut(BaseModel):
    """An account with no balance or statement to show, and why."""

    account: AccountRefOut
    reason: str


class CardPeriodOut(BaseModel):
    """A card's statement period and its spending (purchases, refunds, interest and fees)."""

    start: date
    end: date  # a statement's cut date; for the period the card is in, the next cut expected (a month on)
    spent: MoneyOut
    rows: int  # its rows known so far


class NowCardOut(BaseModel):
    """A card's newest statement, what it still asks, and the period the card is in now."""

    account: AccountRefOut
    type: AccountType  # a credit card has a debt; a debit card's statement only lists what it spent
    cut: date  # the newest statement's cut date
    total: MoneyOut | None  # its balance (dönem borcu); a debit card's: the sum of its purchases
    due: date | None  # its due date, when it prints one
    minimum: MoneyOut | None  # its minimum payment, when it prints one
    limit: MoneyOut | None  # the card's limit, when it prints one
    paid: MoneyOut  # paid on the card since the cut
    debt: MoneyOut | None  # a credit card's: the balance less what was paid since, never below zero
    last: CardPeriodOut  # the newest statement's period
    current: CardPeriodOut  # the period the card is in now: rows after the cut, as far as notices tell
    certainty: Certainty  # provisional when a payment since the cut or a row of the period is
    note: str


class NowOut(BaseModel):
    """What stands now (F05's "Şu an" and "Yaklaşanlar")."""

    today: date
    balances: list[NowBalanceOut]  # cash first, then what moves with a rate or a market
    unknown: list[UnknownOut]  # accounts and cards without a balance or a statement to show
    cards: list[NowCardOut]
    pace: PaceOut
    upcoming: list[CalendarItemOut]  # the calendar's items from today on, by day (an estimate, as the calendar)
    end: date  # the last day upcoming looks at: 14 days, today the first


def _analysis(context: Context) -> Analysis:
    try:
        return context.analysis.get()
    except Busy as exc:
        raise Problem(503, "busy", str(exc)) from exc


def _detail(found: feed.Detail, labels: dict[str, str]) -> FeedDetailOut:
    return FeedDetailOut(
        title=found.title,
        amount=None if found.amount is None else money(found.amount, found.currency),
        minimum=None if found.minimum is None else money(found.minimum),
        balance=None if found.balance is None else money(found.balance),
        old=None if found.old is None else money(found.old),
        new=None if found.new is None else money(found.new),
        day=found.day,
        days=found.days,
        payment=found.payment,
        period=found.period,
        cancelled=found.cancelled,
        status=found.status,
        count=found.count,
        first=found.first,
        last=found.last,
        provisional=found.provisional,
        source=found.source,
        document_kind=found.document_kind,
        parser=found.parser,
        reader=found.reader,
        version=found.version,
        reason=found.reason,
        stage=found.stage,
        unverified=[account_ref(a, labels) for a in found.unverified],
    )


def _item(item: feed.Item, labels: dict[str, str]) -> FeedItemOut:
    doc = item.document
    return FeedItemOut(
        id=item.id,
        at=item.at,
        kind=item.kind,
        label=item.label,
        text=item.text,
        target=item.target,
        account=account_ref(item.account, labels) if item.account else None,
        certainty=item.certainty,
        detail=_detail(item.detail, labels),
        row=row_out(item.row, labels) if item.row else None,
        document=FeedDocumentOut(sha256=doc.sha256, name=doc.name, kind=doc.kind, status=doc.status) if doc else None,
        link=link_out(item.link),
    )


@router.get("/api/feed")
def feed_page(
    request: Request,
    before: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=feed.MAX_PAGE)] = 50,
    kind: Annotated[list[str] | None, Query(max_length=30)] = None,
    account: Annotated[list[str] | None, Query(max_length=100)] = None,
    certainty: Annotated[list[Certainty] | None, Query(max_length=4)] = None,
) -> FeedOut:
    """The event log newest first, before the event with id before (0: from the newest). kind narrows it to codes
    ("transaction.created") or families ("document", "document."); account to the events concerning one of the
    accounts; certainty to the row events whose row the ledger now counts so."""
    try:
        wanted = feed.narrowed(kind or (), account or (), certainty or ())
    except ValueError as exc:
        raise Problem(400, "kind_invalid", "Olay türü anlaşılamadı.") from exc
    context = context_of(request)
    a = _analysis(context)
    found = feed.page(context.ws, a, before, limit, wanted)
    labels = account_labels(a)
    return FeedOut(items=[_item(item, labels) for item in found.items], next=found.next)


def calendar_item(item: Due, labels: dict[str, str]) -> CalendarItemOut:
    return CalendarItemOut(
        day=item.day,
        kind=item.kind,
        title=item.title,
        account=account_ref(item.account, labels),
        direction="in" if item.amount < 0 else "out",
        amount=money(abs(item.amount)),
        minimum=None if item.minimum is None else money(item.minimum),
        basis=item.basis,
        series=item.series,
        fingerprints=list(item.rows),
    )


def _balance(b: now.Balance, labels: dict[str, str]) -> NowBalanceOut:
    return NowBalanceOut(
        account=account_ref(b.account, labels),
        type=b.type,
        balance=money(b.balance, b.currency),
        value=None if b.value is None else money(b.value),
        rate=None if b.rate is None else str(b.rate),
        rate_day=b.rate_day,
        stated=money(b.stated, b.currency),
        on=b.on,
        source=b.source,
        moves=b.moves,
        through=b.through,
        certainty=b.certainty,
        note=b.note,
    )


def _period(p: now.Period) -> CardPeriodOut:
    return CardPeriodOut(start=p.start, end=p.end, spent=money(p.spent), rows=p.rows)


def _card(c: now.Card, labels: dict[str, str]) -> NowCardOut:
    return NowCardOut(
        account=account_ref(c.account, labels),
        type=c.type,
        cut=c.cut,
        total=None if c.total is None else money(c.total),
        due=c.due,
        minimum=None if c.minimum is None else money(c.minimum),
        limit=None if c.limit is None else money(c.limit),
        paid=money(c.paid),
        debt=None if c.debt is None else money(c.debt),
        last=_period(c.last),
        current=_period(c.current),
        certainty=c.certainty,
        note=c.note,
    )


@router.get("/api/feed/now")
def feed_now(request: Request) -> NowOut:
    """What stands now: the balances as far as the documents tell, the cards' statements and periods, the month's
    pace against the typical month, and the next 14 days."""
    context = context_of(request)
    a = _analysis(context)
    found = now.now(a, context.today())
    labels = account_labels(a)
    return NowOut(
        today=found.today,
        balances=[_balance(b, labels) for b in found.balances],
        unknown=[UnknownOut(account=account_ref(u.account, labels), reason=u.reason) for u in found.unknown],
        cards=[_card(c, labels) for c in found.cards],
        pace=pace_out(found.pace),
        upcoming=[calendar_item(item, labels) for item in found.upcoming],
        end=found.end,
    )
