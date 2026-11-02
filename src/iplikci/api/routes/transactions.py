"""The Transactions screen (F04): the ledger's rows filtered, sorted and paged with the totals of what the filters
keep, as CSV too; one row with why it is what it is; corrections on one row or many; the views the user keeps.
Reading needs a session or the token; changing, the service's own pages. The filters' names are the screen's
address query: from, to, account, kind, category, group, necessity, certainty, tag, merchant, q."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi import Path as FastPath
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ...app import transactions
from ...app.analysis import Analysis, account_labels
from ...app.transactions import (
    Actor,
    CategoryReason,
    Certainty,
    DocumentKind,
    EvidenceStatus,
    Filter,
    Necessity,
    NecessityReason,
    Order,
    Printed,
    RuleLayer,
    Sort,
    TransactionKind,
    TransferStep,
)
from ...app.workspace import Busy
from ..context import Context, context_of
from ..guard import Principal
from ..models import MoneyOut, RowOut, money, row_out
from ..problems import Problem
from .deps import only

router = APIRouter()

READ = [Depends(only(Principal.BROWSER, Principal.CLIENT))]
WRITE = [Depends(only(Principal.BROWSER))]
Fingerprint = Annotated[str, FastPath(pattern=r"^[0-9a-f]{20}$")]
Many = Query(max_length=200)


class TotalsOut(BaseModel):
    count: int  # rows the filters keep
    counted: int  # of them in the ledger's totals
    spent: MoneyOut  # spending net of refunds: purchases, refunds, interest and fees
    money_out: MoneyOut  # every counted row's money out, whatever its kind
    money_in: MoneyOut
    provisional: int  # counted rows only a receipt or a notice shows yet
    excluded: int  # rows never counted


class TransactionsOut(BaseModel):
    rows: list[RowOut]
    totals: TotalsOut
    offset: int
    next: int | None  # the next page's offset; null on the last


def _analysis(context: Context) -> Analysis:
    try:
        return context.analysis.get()
    except Busy as exc:
        raise Problem(503, "busy", str(exc)) from exc


def filters(
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
    account: Annotated[list[str] | None, Many] = None,
    kind: Annotated[list[TransactionKind] | None, Many] = None,
    category: Annotated[list[str] | None, Many] = None,
    group: Annotated[list[str] | None, Many] = None,
    necessity: Annotated[list[Necessity] | None, Many] = None,
    certainty: Annotated[list[Certainty] | None, Many] = None,
    tag: Annotated[list[str] | None, Many] = None,
    merchant: Annotated[str, Query(max_length=200)] = "",
    q: Annotated[str, Query(max_length=200)] = "",
) -> Filter:
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
        merchant=merchant.strip(),
        text=q.strip(),
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
    """The rows the filters keep, a page at a time, and what they all add up to."""
    a = _analysis(context_of(request))
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
        ),
        offset=found.offset,
        next=found.next,
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
    rate_day: date | None  # the day of the row that printed it (the source: the documents)


class AnnotationOut(BaseModel):
    note: str
    tags: list[str]
    category: str  # "" when the rules decide
    necessity: Necessity | None  # null when the rules decide
    updated_at: str


class TransactionDetailOut(BaseModel):
    row: RowOut
    printed: PrintedOut | None
    why: WhyOut
    told: list[ToldOut]  # the receipts' and notices' rows about it
    bill: BillOut | None
    annotation: AnnotationOut | None
    correctable: bool  # false for an excluded row: it carries no correction


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
        updated_at=found.updated_at,
    )


@router.get("/api/transactions/{fingerprint}", dependencies=READ)
def transaction_detail(request: Request, fingerprint: Fingerprint) -> TransactionDetailOut:
    """A row, where it is printed and why it is what it is: the rule and its file, how a transfer was resolved and
    its pair, the receipts and notices about it, the bill it paid, the rate, the user's corrections."""
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
    )


Tag = Annotated[str, Field(min_length=1, max_length=40, pattern=r"^[^\x00-\x1f\x7f,]+$")]


class CorrectionIn(BaseModel):
    """What changes; a field left out stays. "" gives the category or the necessity back to the rules."""

    note: Annotated[str, Field(max_length=500)] | None = None
    tags: Annotated[list[Tag], Field(max_length=20)] | None = None
    category: Annotated[str, Field(max_length=100)] | None = None
    necessity: Necessity | Literal[""] | None = None


@router.put("/api/transactions/{fingerprint}/annotation", dependencies=WRITE)
def transaction_correct(request: Request, fingerprint: Fingerprint, body: CorrectionIn) -> AnnotationOut | None:
    """Correct this row only: its note, tags, category or necessity. A new reading of the documents keeps it (the
    fingerprint); null when nothing is kept and the rules decide again. A rule for the merchant goes through
    /api/rules/categories."""
    context = context_of(request)
    change = transactions.Correction(
        note=body.note,
        tags=tuple(body.tags) if body.tags is not None else None,
        category=body.category,
        necessity=body.necessity or None,
        clear_necessity=body.necessity == "",
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
    skipped: list[str]  # fingerprints no counted row has


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
