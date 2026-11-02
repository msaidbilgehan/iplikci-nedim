"""The archive for the Documents screen (F03): the list a page at a time, one document's detail, how the viewer shows
it, its original, reading it again and removing it; the codes' labels for the interface."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi import Path as FastPath
from pydantic import BaseModel, RootModel

from ...app import documents, labels
from ...app.documents import Actor, EvidenceStatus, SourceRef, TransactionKind, ViewError, ViewKind
from ...app.invoices import minor
from ...app.workspace import Busy
from ..context import context_of
from ..guard import Principal
from ..models import MoneyOut
from ..problems import Problem
from .deps import only

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])


class NamedAccountOut(BaseModel):
    id: str
    label: str  # as the screens show it: the user's name for it, else the bank's
    bank: str


class DocumentOut(BaseModel):
    sha256: str
    name: str
    file: str
    kind: str
    parser: str
    reader: str
    status: Literal["processed", "unprocessed", "unreadable"]  # a removed document is in the Trash, not listed
    reason: str
    verified: bool | None
    period_start: str
    period_end: str
    sources: list[str]
    added_at: str
    size: int
    accounts: list[NamedAccountOut]  # the accounts its reading names


class DocumentPageOut(BaseModel):
    items: list[DocumentOut]
    next: str


class LabelsOut(RootModel[dict[str, dict[str, str]]]):
    """The Turkish label of every code, by code type (DocumentStatus, JobKind, …)."""


Many = Query(max_length=100)


@router.get("/api/documents")
def document_page(
    request: Request,
    status: Annotated[list[str] | None, Many] = None,
    kind: Annotated[list[str] | None, Many] = None,
    source: Annotated[list[str] | None, Many] = None,
    account: Annotated[list[str] | None, Many] = None,
    bank: Annotated[list[str] | None, Many] = None,
    q: Annotated[str, Query(max_length=200)] = "",
    cursor: Annotated[str, Query(max_length=200)] = "",
    limit: Annotated[int, Query(ge=1, le=documents.MAX_PAGE)] = 50,
) -> DocumentPageOut:
    """The kept documents, newest first. status (processed, unprocessed, unreadable), kind (a DocumentKind, or "none"
    for a document no reader took), source (a SourceKind), account and bank narrow them; q finds every word in a
    document's name, its title or the rows read from it."""
    wanted = documents.DocumentFilter(
        statuses=tuple(status or ()),
        kinds=tuple(kind or ()),
        sources=tuple(source or ()),
        accounts=tuple(account or ()),
        banks=tuple(bank or ()),
        words=q.strip(),
    )
    try:
        found = documents.page(context_of(request).ws, wanted, cursor, limit)
    except documents.BadCursor as exc:
        raise Problem(400, "cursor_invalid", str(exc)) from exc
    except ValueError as exc:  # a code that is no DocumentStatus, DocumentKind or SourceKind
        raise Problem(400, "filter_invalid", "Bilinmeyen belge durumu, türü ya da kaynağı.") from exc
    return DocumentPageOut(
        items=[DocumentOut.model_validate(d, from_attributes=True) for d in found.items], next=found.next
    )


@router.get("/api/labels")
def code_labels() -> LabelsOut:
    return LabelsOut(labels.tables())


# --- one document (F03): its detail, how it is shown, its pages, its original, reading it again, removing it ----

Sha256 = Annotated[str, FastPath(pattern=r"^[0-9a-f]{64}$")]
Page = Annotated[int, FastPath(ge=1, le=10_000)]
# The sender's markup, shown only in a sandbox: no script runs, nothing loads from elsewhere, no form is sent, and
# only the interface's own page may frame it (architecture §18, ADR-0009).
SANDBOX_CSP = (
    "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; "
    "form-action 'none'; base-uri 'none'; frame-ancestors 'self'"
)


class ArrivalOut(BaseModel):
    kind: str  # a SourceKind code
    name: str  # the file's name as it arrived
    origin: str  # the folder, archive or mailbox it came from
    sender: str  # an e-mail's From address
    subject: str
    sent_at: str
    received_at: str
    gmail: str  # opens the message in Gmail's web interface; "" for other arrivals


class SourceRefOut(BaseModel):
    """Where a row is printed: a PDF page with the line's box (points from the page's top left) or its line in the
    page's text, a spreadsheet's sheet and row, or a span of an e-mail's or HTML document's collapsed text."""

    page: int | None
    box: list[float] | None  # x0, top, x1, bottom
    line: int | None
    sheet: str | None
    row: int | None
    span: list[int] | None  # start, end


class DocumentRowOut(BaseModel):
    fingerprint: str
    day: date
    description: str
    amount: MoneyOut  # in TL as the ledger counts it; above zero money leaves the user
    kind: TransactionKind
    account: str
    category: str
    provisional: bool  # counted until the account's next statement confirms it
    counted: bool  # false: a receipt's or notice's row a statement already shows, or leaves out
    evidence: EvidenceStatus | None  # a receipt's or notice's row: what the statements say of it
    ref: SourceRefOut | None


class StatementCheckOut(BaseModel):
    account: str
    start: date | None  # an account list's first day
    cut: date
    printed: MoneyOut | None  # the total (a card) or closing balance (an account list) the statement prints
    counted: MoneyOut  # what its rows add up to (with the previous balance on a card statement)
    verified: bool
    balance_checks: list[int] | None  # an account list's running balances: [held, of]
    rows: int


class AttachmentOut(BaseModel):
    sha256: str
    name: str


class DocumentDetailOut(BaseModel):
    document: DocumentOut
    parser_version: str
    view: ViewKind  # how the viewer shows it
    arrivals: list[ArrivalOut]  # first arrival first
    checks: list[StatementCheckOut]
    rows: list[DocumentRowOut]  # in the document's own order
    more_rows: bool
    parent: str  # the message it came attached to; "" for none
    attachments: list[AttachmentOut]  # the kept documents attached to this message


class PageSizeOut(BaseModel):
    width: float  # points
    height: float


class TableOut(BaseModel):
    name: str  # the sheet's name; "" for an HTML export's table
    rows: list[list[str]]  # row 1 is the first; a row's SourceRef.row counts from it
    more: bool


class DocumentMailOut(BaseModel):
    subject: str
    sender: str  # the domain of the From address
    sent: str  # ISO time; "" when the message has no date
    lines: list[str]  # the body's text as a browser breaks it
    text: str  # the same text collapsed: a notice row's span counts in it


class DocumentViewOut(BaseModel):
    kind: ViewKind
    pages: list[PageSizeOut]  # a PDF's pages
    table: TableOut | None
    mail: DocumentMailOut | None
    text: str  # an HTML document's visible text, or a text document as it is
    has_html: bool  # the sandboxed original view (mail.html) exists


class PageLinesOut(BaseModel):
    lines: list[str]


class ReparsedOut(BaseModel):
    status: str  # the DocumentStatus code it has now


class RemovedOut(BaseModel):
    trash: str  # the folder in the system Trash it went to


def _ref(ref: SourceRef | None) -> SourceRefOut | None:
    if ref is None:
        return None
    return SourceRefOut(
        page=ref.page,
        box=list(ref.box) if ref.box else None,
        line=ref.line,
        sheet=ref.sheet,
        row=ref.row,
        span=list(ref.span) if ref.span else None,
    )


def _money(value: Decimal, currency: str = "TRY") -> MoneyOut:
    return MoneyOut(minor=minor(value, currency), currency=currency)


def _missing(exc: Exception) -> Problem:
    return Problem(404, "document_missing", "Böyle bir belge yok ya da kaldırıldı.")


def _unshown(exc: ViewError) -> Problem:
    return Problem(422, "document_unshown", f"Belge gösterilemiyor: {exc}")


@router.get("/api/documents/{sha256}")
def document_detail(request: Request, sha256: Sha256) -> DocumentDetailOut:
    """A kept document: what it is, how it arrived, the statements and rows read from it, what it came with."""
    context = context_of(request)
    try:
        found = documents.detail(context.ws, context.analysis.get().dataset, sha256)
    except documents.NotFound as exc:
        raise _missing(exc) from exc
    return DocumentDetailOut(
        document=DocumentOut.model_validate(found.document, from_attributes=True),
        parser_version=found.parser_version,
        view=found.view,
        arrivals=[ArrivalOut.model_validate(a, from_attributes=True) for a in found.arrivals],
        checks=[
            StatementCheckOut(
                account=c.account,
                start=c.start,
                cut=c.cut,
                printed=_money(c.printed, c.currency) if c.printed is not None else None,
                counted=_money(c.counted, c.currency),
                verified=c.verified,
                balance_checks=list(c.balance_checks) if c.balance_checks else None,
                rows=c.rows,
            )
            for c in found.checks
        ],
        rows=[
            DocumentRowOut(
                fingerprint=r.fingerprint,
                day=r.day,
                description=r.description,
                amount=_money(r.amount),
                kind=r.kind,
                account=r.account,
                category=r.category,
                provisional=r.provisional,
                counted=r.counted,
                evidence=r.evidence,
                ref=_ref(r.ref),
            )
            for r in found.rows
        ],
        more_rows=found.more_rows,
        parent=found.parent,
        attachments=[AttachmentOut(sha256=sha, name=name) for sha, name in found.attachments],
    )


@router.get("/api/documents/{sha256}/view")
def document_view(request: Request, sha256: Sha256) -> DocumentViewOut:
    """How the viewer shows the document: a PDF's page sizes, a sheet's cells, an e-mail's text, a text."""
    try:
        found = documents.view(context_of(request).ws, sha256)
    except documents.NotFound as exc:
        raise _missing(exc) from exc
    except ViewError as exc:
        raise _unshown(exc) from exc
    mail = found.mail
    return DocumentViewOut(
        kind=found.kind,
        pages=[PageSizeOut(width=w, height=h) for w, h in found.pages],
        table=TableOut(name=found.table.name, rows=found.table.rows, more=found.table.more) if found.table else None,
        mail=DocumentMailOut(subject=mail.subject, sender=mail.sender, sent=mail.sent, lines=mail.lines, text=mail.text)
        if mail
        else None,
        text=found.text,
        has_html=found.has_html,
    )


@router.get("/api/documents/{sha256}/pages/{page}.png", response_class=Response)
def document_page_image(
    request: Request, sha256: Sha256, page: Page, width: Annotated[int, Query(ge=100, le=4000)] = 1200
) -> Response:
    """A PDF's page drawn as an image; the rows' boxes scale onto it by the page's size in points."""
    try:
        png = documents.page_image(context_of(request).ws, sha256, page, width)
    except documents.NotFound as exc:
        raise _missing(exc) from exc
    except ViewError as exc:
        raise _unshown(exc) from exc
    return Response(png, media_type="image/png")  # no-store like every answer: the service keeps it, not the browser


@router.get("/api/documents/{sha256}/pages/{page}/lines")
def document_page_lines(request: Request, sha256: Sha256, page: Page) -> PageLinesOut:
    """A PDF's page's text line by line, for a row placed by its line (SourceRef.line)."""
    try:
        return PageLinesOut(lines=documents.page_lines(context_of(request).ws, sha256, page))
    except documents.NotFound as exc:
        raise _missing(exc) from exc
    except ViewError as exc:
        raise _unshown(exc) from exc


@router.get("/api/documents/{sha256}/original.html", response_class=Response)
def document_sandboxed_html(request: Request, sha256: Sha256) -> Response:
    """An e-mail's or HTML document's own markup, for the viewer's sandboxed frame only (the "Özgün görünüm")."""
    try:
        html = documents.sandboxed_html(context_of(request).ws, sha256)
    except documents.NotFound as exc:
        raise _missing(exc) from exc
    except ViewError as exc:
        raise _unshown(exc) from exc
    return Response(
        html,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Security-Policy": SANDBOX_CSP,
            "X-Frame-Options": "SAMEORIGIN",
            "Cross-Origin-Resource-Policy": "same-origin",
        },
    )


@router.get("/api/documents/{sha256}/download", response_class=Response)
def document_download(request: Request, sha256: Sha256) -> Response:
    """The document as it arrived, saved under its readable name; never opened in the interface's origin."""
    try:
        found = documents.original(context_of(request).ws, sha256)
    except documents.NotFound as exc:
        raise _missing(exc) from exc
    return Response(
        found.content,
        media_type=found.media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(found.name, safe='')}"},
    )


@router.post("/api/documents/{sha256}/reparse")
def document_reparse(request: Request, sha256: Sha256) -> ReparsedOut:
    """Read the document again now; the analysis follows in the background."""
    try:
        return ReparsedOut(status=documents.reparse(context_of(request).ws, sha256))
    except documents.NotFound as exc:
        raise _missing(exc) from exc
    except Busy as exc:
        raise Problem(409, "documents_busy", "Belgeler şu an okunuyor; birazdan yeniden deneyin.") from exc


@router.post("/api/documents/{sha256}/remove", dependencies=[Depends(only(Principal.BROWSER))])
def document_remove(request: Request, sha256: Sha256) -> RemovedOut:
    """Move the document to the system Trash, after the user confirmed it in the interface (ADR-0003)."""
    try:
        return RemovedOut(trash=documents.remove(context_of(request).ws, sha256, Actor.USER))
    except documents.NotFound as exc:
        raise _missing(exc) from exc
    except Busy as exc:
        raise Problem(409, "documents_busy", "Belgeler şu an okunuyor; birazdan yeniden deneyin.") from exc
