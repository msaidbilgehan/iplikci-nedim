"""The Transactions screen (F04): the ledger's rows filtered, sorted and paged with the totals of what the filters
keep, as CSV too; one row with why it is what it is; corrections on one row or many; the views the user keeps; the
tags the rows carry. Reading needs a session or the token; changing, the service's own pages. The filters' names are
the screen's address query: period, from, to, account, kind, category, group, necessity, certainty, tag, saving,
merchant, direction, min, max, q. A named period stands for its days, from and to, reckoned from the service's today.
The search q is read by domain.search: a comma between its parts finds the rows of any one ("market, kira"). saving
keeps the rows that set money aside or took it out of the savings, by where it went: the rows a month's saving adds up
to, their net in the totals' saving."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi import Path as FastPath
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ...app import annotate, transactions
from ...app.analysis import Analysis, account_labels
from ...app.links import Link, Screen
from ...app.transactions import (
    Actor,
    CategoryReason,
    Certainty,
    Direction,
    DocumentKind,
    EvidenceStatus,
    Filter,
    MonthStatus,
    Necessity,
    NecessityReason,
    Order,
    Period,
    Printed,
    RateSource,
    RuleLayer,
    SavingPart,
    Sort,
    TransactionKind,
    TransferStep,
)
from ...app.workspace import Busy
from ..context import Context, context_of
from ..guard import Principal
from ..models import AccountRefOut, LinkOut, MoneyOut, RowOut, account_ref, link_out, money, row_out
from ..problems import Problem
from .deps import only

router = APIRouter()

READ = [Depends(only(Principal.BROWSER, Principal.CLIENT))]
WRITE = [Depends(only(Principal.BROWSER))]
# A row's fingerprint; a part of a split row has its number after it (F04).
Fingerprint = Annotated[str, FastPath(pattern=r"^[0-9a-f]{20}(-[1-9][0-9]?)?$")]
Many = Query(max_length=200)


class TotalsOut(BaseModel):
    count: int  # rows the filters keep
    counted: int  # of them in the ledger's totals
    spent: MoneyOut  # spending net of refunds: purchases, refunds, interest and fees
    money_out: MoneyOut  # every counted row's money out, whatever its kind
    money_in: MoneyOut
    provisional: int  # counted rows only a receipt or a notice shows yet
    excluded: int  # rows never counted
    # What the counted rows set aside, less what they took out of the savings: with the saving filter, the saving
    # they add up to; above zero set aside.
    saving: MoneyOut


class DaysOut(BaseModel):
    start: date
    end: date


class AwaitedOut(BaseModel):
    """An account whose documents for some of the filtered days are not in yet."""

    account: AccountRefOut
    status: MonthStatus  # waiting, missing or check
    days: list[DaysOut]  # the filtered days it leaves open; none for a check, which is the month's
    waiting_for: str  # what closes them, in a few Turkish words: "19–31 Ekim ekstresi, kesim ~18.11"
    late: bool  # the statement's cut passed days ago and it did not come


class OpenMonthOut(BaseModel):
    """A month of the filtered days that has not closed: its rows are listed as far as the documents in go."""

    month: str  # YYYY-MM
    status: MonthStatus  # never closed
    accounts: list[AwaitedOut]  # none for a running month: it runs on
    closes_by: date | None  # the cut of the last card statement it waits for, when one can be promised
    link: LinkOut  # its month-end page


class SearchPartOut(BaseModel):
    """One part of a search of many (q="market, kira"): a row is listed when one of the parts finds it."""

    text: str  # the part as written: "market"
    count: int  # the rows the other filters keep that it finds; 0 says it finds none


class TransactionsOut(BaseModel):
    rows: list[RowOut]
    totals: TotalsOut
    offset: int
    next: int | None  # the next page's offset; null on the last
    open: list[OpenMonthOut]  # the filtered days' months that have not closed, the oldest first
    search_parts: list[SearchPartOut]  # a search of more than one part, each part with its count; else none


def _open_month(found: transactions.OpenMonth, labels: dict[str, str]) -> OpenMonthOut:
    link = link_out(Link(Screen.MONTH, found.month))
    assert link is not None  # link_out gives None only for no link
    return OpenMonthOut(
        month=found.month,
        status=found.status,
        accounts=[
            AwaitedOut(
                account=account_ref(held.account, labels),
                status=held.status,
                days=[DaysOut(start=lo, end=hi) for lo, hi in held.days],
                waiting_for=held.what,
                late=held.late,
            )
            for held in found.accounts
        ],
        closes_by=found.closes_by,
        link=link,
    )


def _analysis(context: Context) -> Analysis:
    try:
        return context.analysis.get()
    except Busy as exc:
        raise Problem(503, "busy", str(exc)) from exc


def filters(
    request: Request,
    period: Period | None = None,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
    account: Annotated[list[str] | None, Many] = None,
    kind: Annotated[list[TransactionKind] | None, Many] = None,
    category: Annotated[list[str] | None, Many] = None,
    group: Annotated[list[str] | None, Many] = None,
    necessity: Annotated[list[Necessity] | None, Many] = None,
    certainty: Annotated[list[Certainty] | None, Many] = None,
    tag: Annotated[list[str] | None, Many] = None,
    saving: Annotated[list[SavingPart] | None, Many] = None,
    merchant: Annotated[str, Query(max_length=200)] = "",
    direction: Direction | None = None,
    least: Annotated[Decimal | None, Query(alias="min", ge=0, max_digits=14, decimal_places=2)] = None,
    most: Annotated[Decimal | None, Query(alias="max", ge=0, max_digits=14, decimal_places=2)] = None,
    q: Annotated[str, Query(max_length=200)] = "",
) -> Filter:
    if period is not None:  # a named period stands for its days
        start, end = transactions.period_days(period, context_of(request).today())
    return Filter(
        start=start,
        end=end,
        accounts=frozenset(account or ()),
        kinds=frozenset(kind or ()),
        categories=frozenset(category or ()),
        groups=frozenset(group or ()),
        necessities=frozenset(necessity or ()),
        certainties=frozenset(certainty or ()),
        tags=frozenset(tag or ()),
        savings=frozenset(saving or ()),
        merchant=merchant.strip(),
        text=q.strip(),
        direction=direction,
        least=least,
        most=most,
    )


def _order(
    sort: Sort = Sort.DAY,
    order: Literal["asc", "desc"] = "desc",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=transactions.MAX_PAGE)] = 50,
) -> Order:
    return Order(sort, order == "desc", offset, limit)


@router.get("/api/transactions", dependencies=READ)
def transaction_list(
    request: Request, f: Annotated[Filter, Depends(filters)], o: Annotated[Order, Depends(_order)]
) -> TransactionsOut:
    """The rows the filters keep, a page at a time, what they all add up to and the months of their days that have not
    closed, with what each waits for."""
    context = context_of(request)
    a = _analysis(context)
    found = transactions.page(a, f, o)
    labels = account_labels(a)
    t = found.totals
    return TransactionsOut(
        rows=[row_out(r, labels) for r in found.rows],
        totals=TotalsOut(
            count=t.count,
            counted=t.counted,
            spent=money(t.spent),
            money_out=money(t.money_out),
            money_in=money(t.money_in),
            provisional=t.provisional,
            excluded=t.excluded,
            saving=money(t.saving),
        ),
        offset=found.offset,
        next=found.next,
        open=[_open_month(m, labels) for m in transactions.open_months(a, f, context.today())],
        search_parts=[SearchPartOut(text=p.text, count=p.count) for p in found.parts],
    )


@router.get("/api/transactions.csv", dependencies=READ, response_class=Response)
def transaction_csv(
    request: Request, f: Annotated[Filter, Depends(filters)], o: Annotated[Order, Depends(_order)]
) -> Response:
    """Every row the filters keep as CSV, in the list's order, for Excel."""
    context = context_of(request)
    text = transactions.csv_text(_analysis(context), f, o)
    name = f"iplikci-islemler-{context.today().isoformat()}.csv"
    return Response(
        text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# --- kept views (before the rows' paths: "views" is no fingerprint) -----------------------------------------------------------------------------------------------


class ViewModel(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=60)]
    query: dict[
        Annotated[str, Field(max_length=20)],
        Annotated[list[Annotated[str, Field(max_length=200)]], Field(max_length=200)],
    ]


def _views(found: list[transactions.View]) -> list[ViewModel]:
    return [ViewModel(name=v.name, query=v.query) for v in found]


@router.get("/api/transactions/views", dependencies=READ)
def transaction_views(request: Request) -> list[ViewModel]:
    return _views(transactions.views(context_of(request).ws))


@router.put("/api/transactions/views", dependencies=WRITE)
def transaction_view_save(request: Request, body: ViewModel) -> list[ViewModel]:
    """Keep the filters under a name; the same name replaces the view kept before."""
    try:
        return _views(transactions.save_view(context_of(request).ws, body.name, body.query, Actor.USER))
    except transactions.Refused as exc:
        raise Problem(400, "view_refused", str(exc)) from exc


@router.delete("/api/transactions/views/{name}", dependencies=WRITE)
def transaction_view_remove(request: Request, name: Annotated[str, FastPath(max_length=60)]) -> list[ViewModel]:
    found = transactions.remove_view(context_of(request).ws, name, Actor.USER)
    if found is None:
        raise Problem(404, "view_not_found", "Bu adla saklanmış bir görünüm yok.")
    return _views(found)


class TagOut(BaseModel):
    tag: str
    count: int  # the rows that carry it


@router.get("/api/tags", dependencies=READ)
def transaction_tags(request: Request) -> list[TagOut]:
    """The tags the user gave rows, the most used first: the tag filter offers them. Not under /api/transactions/,
    whose next part is a row's fingerprint."""
    return [TagOut(tag=tag, count=count) for tag, count in transactions.tag_counts(_analysis(context_of(request)))]


# --- one row --------------------------------------------------------------------------------------------------


class PrintedOut(BaseModel):
    """Where the row is printed; the viewer opens /belgeler/<document>?satir=<fingerprint> at it."""

    document: str
    name: str
    kind: DocumentKind | None
    page: int | None
    line: int | None
    sheet: str | None
    row: int | None


class ToldOut(BaseModel):
    fingerprint: str
    status: EvidenceStatus
    day: date
    amount: MoneyOut
    printed: PrintedOut | None


class BillOut(BaseModel):
    key: str  # "<sha256>:<position>": /faturalar opens it
    seller: str
    issued: date
    total: MoneyOut


class WhyOut(BaseModel):
    category: CategoryReason
    rule: str  # the pattern as the rule file writes it; "" when no rule named the row
    layer: RuleLayer | None
    necessity: NecessityReason | None  # null: the row is no spending
    necessity_layer: RuleLayer | None
    transfer: TransferStep | None  # how a transfer was resolved; null for a row that was no transfer to resolve
    pair: RowOut | None  # the opposite row in another own account, or the named payment it is like
    rate: str | None  # the TL rate a foreign account's row was valued at, as a decimal ("54.4400")
    rate_day: date | None  # the day it is of: the row that printed it, or the providers' bulletin
    # Where it comes from: the documents (the row's own rate, else the nearest one) or a provider (TCMB, ECB).
    rate_source: RateSource | None = None


class SplitPartOut(BaseModel):
    """A part as the user split the row: the detail's parts are what the ledger counts of them."""

    minor: int  # kuruş, above zero whichever way the row's money goes
    category: str
    necessity: Necessity | None  # null: the one the category's rules give


class AnnotationOut(BaseModel):
    note: str
    tags: list[str]
    category: str  # "" when the rules decide
    necessity: Necessity | None  # null when the rules decide
    parts: list[SplitPartOut]  # the split as the user made it; [] for none
    updated_at: str


class TransactionDetailOut(BaseModel):
    row: RowOut
    printed: PrintedOut | None
    why: WhyOut
    told: list[ToldOut]  # the receipts' and notices' rows about it
    bill: BillOut | None
    annotation: AnnotationOut | None
    correctable: bool  # false for an excluded row: it carries no correction
    parts: list[RowOut]  # a split row's parts in order, each counted under its own category; [] for a whole row
    splittable: bool  # a counted row of a kind that can be split: spending, money sent to people, income
    # The user split it (annotation.parts), but it counts whole again: its kind no longer splits, or its amount moved
    # so far that a part came to nothing. The to-do list tells it too.
    split_dropped: bool


def _printed(p: Printed | None) -> PrintedOut | None:
    if p is None:
        return None
    return PrintedOut(document=p.document, name=p.name, kind=p.kind, page=p.page, line=p.line, sheet=p.sheet, row=p.row)


def _annotation(found: transactions.Annotation | None) -> AnnotationOut | None:
    if found is None:
        return None
    return AnnotationOut(
        note=found.note,
        tags=list(found.tags),
        category=found.category,
        necessity=found.necessity,
        parts=[SplitPartOut(minor=p.amount, category=p.category, necessity=p.necessity) for p in found.parts],
        updated_at=found.updated_at,
    )


@router.get("/api/transactions/{fingerprint}", dependencies=READ)
def transaction_detail(request: Request, fingerprint: Fingerprint) -> TransactionDetailOut:
    """A row, where it is printed and why it is what it is: the rule and its file, how a transfer was resolved and
    its pair, the receipts and notices about it, the bill it paid, the rate, the user's corrections. A part of a split
    row gives its row, with every part."""
    context = context_of(request)
    a = _analysis(context)
    try:
        found = transactions.detail(context.ws, a, fingerprint)
    except transactions.NotFound as exc:
        raise Problem(404, "transaction_not_found", "Bu parmak iziyle bir işlem yok.") from exc
    labels = account_labels(a)
    why = found.why
    bill = found.bill
    return TransactionDetailOut(
        row=row_out(found.row, labels),
        printed=_printed(found.printed),
        why=WhyOut(
            category=why.category,
            rule=why.rule,
            layer=why.layer,
            necessity=why.necessity,
            necessity_layer=why.necessity_layer,
            transfer=why.transfer,
            pair=row_out(why.pair, labels) if why.pair is not None else None,
            rate=str(why.rate) if why.rate is not None else None,
            rate_day=why.rate_day,
            rate_source=why.rate_source,
        ),
        told=[
            ToldOut(
                fingerprint=t.fingerprint,
                status=t.status,
                day=t.day,
                amount=money(t.amount),
                printed=_printed(t.printed),
            )
            for t in found.told
        ],
        bill=BillOut(key=bill.key, seller=bill.seller, issued=bill.issued, total=money(bill.total, bill.currency))
        if bill is not None
        else None,
        annotation=_annotation(found.annotation),
        correctable=found.correctable,
        parts=[row_out(part, labels) for part in found.parts],
        splittable=found.splittable,
        split_dropped=found.split_dropped,
    )


Tag = Annotated[str, Field(min_length=1, max_length=40, pattern=r"^[^\x00-\x1f\x7f,]+$")]


class PartIn(BaseModel):
    """A part of a split row: what of it counts under which category."""

    minor: Annotated[int, Field(gt=0, le=10**15)]  # kuruş, above zero whichever way the row's money goes
    category: Annotated[str, Field(min_length=1, max_length=100)]
    necessity: Necessity | None = None  # null: the one the category's rules give


class CorrectionIn(BaseModel):
    """What changes; a field left out stays. "" gives the category or the necessity back to the rules; [] joins a
    split row again."""

    note: Annotated[str, Field(max_length=500)] | None = None
    tags: Annotated[list[Tag], Field(max_length=20)] | None = None
    category: Annotated[str, Field(max_length=100)] | None = None
    necessity: Necessity | Literal[""] | None = None
    parts: Annotated[list[PartIn], Field(max_length=annotate.MAX_PARTS)] | None = None


@router.put("/api/transactions/{fingerprint}/annotation", dependencies=WRITE)
def transaction_correct(request: Request, fingerprint: Fingerprint, body: CorrectionIn) -> AnnotationOut | None:
    """Correct this row only: its note, tags, category or necessity, or split it into parts that add up to it, each
    under its own category (a part's fingerprint means its row). A new reading of the documents keeps it (the
    fingerprint); null when nothing is kept and the rules decide again. A rule for the merchant goes through
    /api/rules/categories."""
    context = context_of(request)
    change = transactions.Correction(
        note=body.note,
        tags=tuple(body.tags) if body.tags is not None else None,
        category=body.category,
        necessity=body.necessity or None,
        clear_necessity=body.necessity == "",
        parts=tuple(annotate.Share(Decimal(p.minor) / 100, p.category, p.necessity) for p in body.parts)
        if body.parts is not None
        else None,
    )
    try:
        kept = transactions.correct(context.ws, _analysis(context), fingerprint, change, Actor.USER)
    except transactions.NotFound as exc:
        raise Problem(404, "transaction_not_found", "Bu parmak iziyle bir işlem yok.") from exc
    except transactions.Refused as exc:
        raise Problem(400, "correction_refused", str(exc)) from exc
    return _annotation(kept)


class BulkIn(BaseModel):
    fingerprints: Annotated[list[str], Field(min_length=1, max_length=1000)]
    category: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    tags: Annotated[list[Tag], Field(max_length=20)] = []


class BulkOut(BaseModel):
    changed: int
    skipped: list[str]  # fingerprints no counted row has; for a category, a split row's: its parts keep theirs


@router.post("/api/transactions/bulk", dependencies=WRITE)
def transaction_bulk(request: Request, body: BulkIn) -> BulkOut:
    """Give the selected rows one category, or add tags to theirs."""
    context = context_of(request)
    try:
        found = transactions.correct_many(
            context.ws, _analysis(context), body.fingerprints, body.category, body.tags, Actor.USER
        )
    except transactions.Refused as exc:
        raise Problem(400, "correction_refused", str(exc)) from exc
    return BulkOut(changed=found.changed, skipped=found.skipped)
