"""The archive as the Documents screen shows it (F03): every kept document with what reading it decided, how it
arrived and when, newest first, a page at a time; one document's detail with the statements and rows read from it,
how the viewer shows it, its original, reading it again and moving it to the Trash."""

import base64
import binascii
import json
import os
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote

from ..analysis import Dataset, payments
from ..domain.codes import Actor, DocumentKind, DocumentStatus, EvidenceStatus, SourceKind, TransactionKind
from ..domain.models import SourceRef, Transaction
from ..parsers import registry
from ..settings.paths import FILE_MODE
from ..storage import aliases, audit, documents, readings
from ..storage.db import Database
from ..viewer import process as viewer
from . import background, reading
from .workspace import Workspace

ViewError = viewer.ViewError

# What the API and the other callers name from here: the use cases, and the codes and records their answers carry.
__all__ = [
    "KEPT",
    "MAX_PAGE",
    "Actor",
    "BadCursor",
    "Detail",
    "EvidenceStatus",
    "Listed",
    "NotFound",
    "SourceRef",
    "TransactionKind",
    "View",
    "ViewError",
    "ViewKind",
    "detail",
    "original",
    "page",
    "page_image",
    "page_lines",
    "remove",
    "reparse",
    "sandboxed_html",
    "view",
]

KEPT = (DocumentStatus.PROCESSED, DocumentStatus.UNPROCESSED, DocumentStatus.UNREADABLE)  # removed: in the Trash
MAX_PAGE = 200


@dataclass(frozen=True, slots=True)
class Named:
    """An account a document's reading names: its id, its name as the screens show it, its bank."""

    id: str
    label: str
    bank: str


@dataclass(frozen=True, slots=True)
class Listed:
    sha256: str
    name: str  # the readable name reading gave it, else the file's own
    file: str  # the file's own name
    kind: str  # a DocumentKind code; "" when no reader took it
    parser: str
    reader: str  # what the reader reads, for people
    status: str  # a DocumentStatus code
    reason: str  # why it was not processed
    verified: bool | None  # a statement's totals or balances checked; None for other documents
    period_start: str
    period_end: str
    sources: list[str]  # SourceKind codes: how it arrived, first arrival first
    added_at: str
    size: int
    accounts: list[Named]  # the accounts its reading names


@dataclass(frozen=True, slots=True)
class Page:
    items: list[Listed]
    next: str  # the cursor of the next page; "" on the last one


class BadCursor(ValueError):
    """The cursor is not one this service gave out."""


@dataclass(frozen=True, slots=True)
class DocumentFilter:
    """What the Documents screen's filters keep (F03); an empty one keeps every kept document."""

    statuses: tuple[str, ...] = ()  # DocumentStatus codes: processed, unprocessed, unreadable
    kinds: tuple[str, ...] = ()  # DocumentKind codes, and "none" for a document no reader took
    sources: tuple[str, ...] = ()  # SourceKind codes: how any of its arrivals came
    accounts: tuple[str, ...] = ()  # account ids its reading names
    banks: tuple[str, ...] = ()
    words: str = ""  # a search (domain.search) in its name, its title and the rows read from it


UNREAD_KIND = "none"


def _narrowing(f: DocumentFilter) -> documents.Narrowing:
    return documents.Narrowing(
        kinds=tuple(DocumentKind(k) for k in f.kinds if k != UNREAD_KIND),
        unread=UNREAD_KIND in f.kinds,
        sources=tuple(SourceKind(k) for k in f.sources),
        accounts=f.accounts,
        banks=f.banks,
        words=f.words,
    )


def page(ws: Workspace, f: DocumentFilter | None = None, cursor: str = "", limit: int = 50) -> Page:
    """A page of the kept documents the filter keeps, newest first. ValueError for a code no such kind has."""
    f = f or DocumentFilter()
    wanted = [DocumentStatus(s) for s in f.statuses] or list(KEPT)
    if not set(wanted) <= set(KEPT):
        raise ValueError("a removed document is in the Trash, not listed")
    narrowing = _narrowing(f)
    size = max(1, min(limit, MAX_PAGE))
    with ws.db() as db:
        rows = documents.newest_first(db, wanted, _decode(cursor) if cursor else None, size + 1, narrowing)
        shown = rows[:size]
        kinds = documents.source_kinds(db, [d.sha256 for d in shown])
        named = documents.accounts_of(db, [d.sha256 for d in shown])
        given = {key: alias.alias for key, alias in aliases.every(db).items()}
    items = [
        Listed(
            sha256=d.sha256,
            name=d.display_name or d.name,
            file=d.name,
            kind=d.kind.value if d.kind else "",
            parser=d.parser,
            reader=registry.label(d.parser) if d.parser else "",
            status=d.status.value,
            reason=d.reason,
            verified=d.verified,
            period_start=d.period_start.isoformat() if d.period_start else "",
            period_end=d.period_end.isoformat() if d.period_end else "",
            sources=[k.value for k in kinds[d.sha256]],
            added_at=d.added_at,
            size=d.size,
            accounts=[Named(key, given.get(key) or label, bank) for key, label, bank in named[d.sha256]],
        )
        for d in shown
    ]
    more = len(rows) > size
    return Page(items, _encode(shown[-1].added_at, shown[-1].sha256) if more and shown else "")


def _encode(added_at: str, sha256: str) -> str:
    return base64.urlsafe_b64encode(f"{added_at}|{sha256}".encode()).decode().rstrip("=")


def _decode(cursor: str) -> tuple[str, str]:
    try:
        text = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise BadCursor("geçersiz sayfa imleci") from exc
    added_at, _, sha256 = text.partition("|")
    if not added_at or len(sha256) != 64:
        raise BadCursor("geçersiz sayfa imleci")
    return added_at, sha256


# --- one document (F03): what it is and what came of it, how it is shown, its original, reading it again, removing it


class NotFound(LookupError):
    """No kept document has this sha256 (a removed one is in the Trash)."""


class ViewKind(StrEnum):
    PDF = "pdf"  # its pages as images; a row's box drawn over its page, a text row's line beside it
    TABLE = "table"  # a spreadsheet's cells (also an HTML export saved as .xls); a row highlighted in the table
    MAIL = "mail"  # an e-mail's text; its HTML only in a sandbox
    HTML = "html"  # an HTML document's visible text; its markup only in a sandbox
    TEXT = "text"  # a text document as it is (an e-invoice's XML)
    NONE = "none"  # no way to show it here: the original downloads


_VIEWS = {
    ".pdf": ViewKind.PDF,
    ".xls": ViewKind.TABLE,
    ".xlsx": ViewKind.TABLE,
    ".eml": ViewKind.MAIL,
    ".html": ViewKind.HTML,
    ".htm": ViewKind.HTML,
    ".xml": ViewKind.TEXT,
    ".txt": ViewKind.TEXT,
}
ROW_LIMIT = 1000  # rows listed with one document; a statement has a few hundred at most
REMOVED_REASON = "kullanıcı kaldırdı"
GMAIL_SEARCH = "https://mail.google.com/mail/u/0/#search/rfc822msgid%3A"


@dataclass(frozen=True, slots=True)
class Arrival:
    kind: str  # a SourceKind code
    name: str  # the file's name as it arrived
    origin: str  # the folder, archive or mailbox it came from
    sender: str  # an e-mail's From address
    subject: str
    sent_at: str
    received_at: str
    gmail: str  # finds the message in Gmail's web interface (the user's own click); "" for other arrivals


@dataclass(frozen=True, slots=True)
class Row:
    """A row read from the document, and whether the ledger counts it."""

    fingerprint: str
    day: date
    description: str
    amount: Decimal  # in TL, as the ledger counts it (above zero: money leaving the user)
    kind: TransactionKind
    account: str  # the account's label
    category: str
    provisional: bool  # counted until the account's next statement confirms it
    counted: bool  # a receipt's or a notice's row a statement already shows (or leaves out) is not counted again
    evidence: EvidenceStatus | None  # a receipt's or a notice's row: what the statements say of it
    ref: SourceRef | None  # where it is printed in the document


@dataclass(frozen=True, slots=True)
class Check:
    """A statement read from the document, and how it verified (docs/domain/ledger.md)."""

    account: str
    start: date | None  # an account list's first day; None for a card statement
    cut: date
    currency: str
    printed: Decimal | None  # the total (a card) or the closing balance (an account list) the statement prints
    counted: Decimal  # what its rows add up to (with the previous balance on a card statement)
    verified: bool
    balance_checks: tuple[int, int] | None  # an account list's running balances: how many held, of how many
    rows: int


@dataclass(frozen=True, slots=True)
class Detail:
    document: Listed
    parser_version: str
    view: ViewKind
    arrivals: list[Arrival]
    checks: list[Check]
    rows: list[Row]
    more_rows: bool  # rows beyond ROW_LIMIT, not listed
    parent: str  # the sha256 of the message it came attached to; "" for none
    attachments: list[tuple[str, str]]  # (sha256, name) of the kept documents attached to this message


def view_kind(name: str) -> ViewKind:
    dot = name.rfind(".")
    return _VIEWS.get(name[dot:].lower() if dot > 0 else "", ViewKind.NONE)


def _kept(db: Database, sha256: str) -> documents.DocumentRow:
    doc = documents.get(db, sha256)
    if doc is None or doc.status is DocumentStatus.REMOVED:
        raise NotFound(sha256)
    return doc


def _listed(db: Database, d: documents.DocumentRow) -> Listed:
    return Listed(
        sha256=d.sha256,
        name=d.display_name or d.name,
        file=d.name,
        kind=d.kind.value if d.kind else "",
        parser=d.parser,
        reader=registry.label(d.parser) if d.parser else "",
        status=d.status.value,
        reason=d.reason,
        verified=d.verified,
        period_start=d.period_start.isoformat() if d.period_start else "",
        period_end=d.period_end.isoformat() if d.period_end else "",
        sources=[k.value for k in documents.source_kinds(db, [d.sha256])[d.sha256]],
        added_at=d.added_at,
        size=d.size,
        accounts=_named(db, d.sha256),
    )


def _named(db: Database, sha256: str) -> list[Named]:
    given = {key: alias.alias for key, alias in aliases.every(db).items()}
    return [
        Named(key, given.get(key) or label, bank) for key, label, bank in documents.accounts_of(db, [sha256])[sha256]
    ]


def _arrival(s: documents.Source) -> Arrival:
    gmail = GMAIL_SEARCH + quote(s.message_id.strip("<>"), safe="") if s.message_id else ""
    return Arrival(s.kind.value, s.original, s.origin, s.sender, s.subject, s.sent_at, s.received_at, gmail)


def _place(ref: SourceRef | None) -> tuple[int, float]:
    """Where a row is printed, to list a document's rows in its own order: its page, then its line, row or box."""
    if ref is None:
        return (0, 0.0)
    within = ref.line or ref.row or (ref.box[1] if ref.box else 0.0) or (ref.span[0] if ref.span else 0.0)
    return (ref.page or 0, float(within))


def _rows(ds: Dataset, sha256: str) -> list[Row]:
    def row(t: Transaction, counted: bool, evidence: EvidenceStatus | None) -> Row:
        account = ds.accounts.get(t.account)
        label = account.label if account else t.account
        return Row(
            t.fingerprint,
            t.date,
            t.description,
            t.amount,
            t.kind,
            label,
            t.category,
            t.provisional,
            counted,
            evidence,
            t.ref,
        )

    # A receipt's row the ledger counts is the same row (by its fingerprint: a foreign-currency one was turned into TL).
    evidence = {line.txn.fingerprint: line.status for line in ds.receipts}
    counted = [t for t in payments(ds) if t.document == sha256]  # a split row is one printed line
    seen = {t.fingerprint for t in counted}
    rows = [row(t, True, evidence.get(t.fingerprint)) for t in counted]
    rows += [
        row(line.txn, False, line.status)
        for line in ds.receipts
        if line.txn.document == sha256 and line.txn.fingerprint not in seen
    ]
    return sorted(rows, key=lambda r: (_place(r.ref), r.day))


def _checks(ds: Dataset, sha256: str) -> list[Check]:
    found: list[Check] = []
    for s in ds.statements:
        if s.document != sha256:
            continue
        account = ds.accounts.get(s.account)
        found.append(
            Check(
                account=account.label if account else s.account,
                start=s.start,
                cut=s.cut_date,
                currency=s.currency,
                printed=s.total,
                counted=s.computed_total,
                verified=s.verified,
                balance_checks=(s.checks_ok, s.checks_total) if s.is_account else None,
                rows=len(s.transactions),
            )
        )
    return found


def detail(ws: Workspace, ds: Dataset, sha256: str) -> Detail:
    """A kept document: what it is, how it arrived, the statements and rows read from it as the ledger (ds) has
    them, and the documents it came with. NotFound for no kept document."""
    with ws.db() as db:
        doc = _kept(db, sha256)
        listed = _listed(db, doc)
        arrivals = [_arrival(s) for s in documents.sources(db, sha256)]
        attached = [(d.sha256, d.display_name or d.name) for d in documents.every(db, KEPT) if d.parent == sha256]
    rows = _rows(ds, sha256)
    return Detail(
        document=listed,
        parser_version=doc.parser_version if doc.parser else "",
        view=view_kind(doc.name),
        arrivals=arrivals,
        checks=_checks(ds, sha256),
        rows=rows[:ROW_LIMIT],
        more_rows=len(rows) > ROW_LIMIT,
        parent=doc.parent,
        attachments=attached,
    )


# How a document is shown is made once in the viewing process (iplikci.viewer) and kept beside it in the vault's
# derived folder: the original never changes, so neither does what is made from it. A new VIEW_VERSION makes it again.
VIEW_VERSION = 1
PAGE_WIDTHS = (400, 800, 1200, 1600, 2000)  # the widths a page is drawn at: a request takes the next one up
_MEDIA = {
    ".pdf": "application/pdf",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".eml": "message/rfc822",
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".xml": "application/xml",
    ".txt": "text/plain; charset=utf-8",
}


@dataclass(frozen=True, slots=True)
class View:
    kind: ViewKind
    pages: list[tuple[float, float]]  # a PDF's pages: width and height in points, as the rows' boxes measure them
    table: viewer.Table | None  # a spreadsheet's first sheet
    mail: viewer.MailView | None  # an e-mail; its HTML is served apart, only into a sandbox
    text: str  # an HTML document's visible text, or a text document as it is
    has_html: bool  # an e-mail with an HTML part, or an HTML document: its own markup shows in a sandbox


@dataclass(frozen=True, slots=True)
class Original:
    name: str  # the readable name it downloads under
    media_type: str
    content: bytes


def _write_bytes(path: Path, data: bytes) -> None:
    """Keep a made file only the user can read; written beside and renamed, so a reader never sees half of it."""
    part = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}")
    fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE)
    with os.fdopen(fd, "wb") as out:
        out.write(data)
    os.replace(part, path)


def _made[T](ws: Workspace, sha256: str, name: str, make: Callable[[], T], dump: Callable[[T], bytes]) -> bytes:
    """What is made from a document, from its derived folder or made now and kept there."""
    path = ws.vault.derived(sha256) / name
    if path.is_file():
        return path.read_bytes()
    data = dump(make())
    _write_bytes(path, data)
    return data


def _original_bytes(ws: Workspace, sha256: str) -> tuple[documents.DocumentRow, bytes]:
    with ws.db() as db:
        doc = _kept(db, sha256)
    return doc, ws.vault.read(sha256)


def view(ws: Workspace, sha256: str) -> View:
    """How a kept document is shown. NotFound for no kept document; viewer.ViewError when it cannot be shown."""
    with ws.db() as db:
        doc = _kept(db, sha256)
    kind = view_kind(doc.name)
    if kind is ViewKind.NONE:
        return View(kind, [], None, None, "", False)

    def make() -> dict[str, object]:
        data = ws.vault.read(sha256)
        if kind is ViewKind.PDF:
            return {"pages": viewer.page_sizes(data)}
        if kind is ViewKind.TABLE:
            return {"table": asdict(viewer.table(data))}
        if kind is ViewKind.MAIL:
            found = viewer.message(data)
            return {"mail": asdict(found) | {"html": ""}, "has_html": bool(found.html)}
        if kind is ViewKind.HTML:
            return {"text": viewer.html_text(data), "has_html": True}
        return {"text": viewer.text(data)}

    stored = json.loads(_made(ws, sha256, f"gorunum-{VIEW_VERSION}.json", make, _json))
    table = stored.get("table")
    mail = stored.get("mail")
    return View(
        kind,
        [(float(w), float(h)) for w, h in stored.get("pages", [])],
        viewer.Table(table["name"], table["rows"], table["more"]) if table else None,
        viewer.MailView(**mail) if mail else None,
        str(stored.get("text", "")),
        bool(stored.get("has_html", False)),
    )


def _json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode()


def page_image(ws: Workspace, sha256: str, page: int, width: int) -> bytes:
    """A PDF's page as a PNG image at the next drawing width up from width."""
    with ws.db() as db:
        doc = _kept(db, sha256)
    if view_kind(doc.name) is not ViewKind.PDF:
        raise viewer.ViewError("bu belgenin sayfa resmi yok")
    drawn = next((w for w in PAGE_WIDTHS if w >= width), PAGE_WIDTHS[-1])
    return _made(
        ws,
        sha256,
        f"sayfa-{VIEW_VERSION}-{page}-{drawn}.png",
        lambda: viewer.render_page(ws.vault.read(sha256), page, drawn).png,
        lambda png: png,
    )


def page_lines(ws: Workspace, sha256: str, page: int) -> list[str]:
    """A PDF's page's text line by line, as the readers that read text count its lines (SourceRef.line)."""
    with ws.db() as db:
        doc = _kept(db, sha256)
    if view_kind(doc.name) is not ViewKind.PDF:
        raise viewer.ViewError("bu belgenin sayfası yok")
    made = _made(
        ws,
        sha256,
        f"satirlar-{VIEW_VERSION}-{page}.json",
        lambda: viewer.page_lines(ws.vault.read(sha256), page),
        _json,
    )
    return [str(line) for line in json.loads(made)]


def sandboxed_html(ws: Workspace, sha256: str) -> str:
    """An e-mail's HTML part or an HTML document's markup as it is: the sender's, to be shown only in a sandbox."""
    with ws.db() as db:
        doc = _kept(db, sha256)
    kind = view_kind(doc.name)
    if kind not in (ViewKind.MAIL, ViewKind.HTML):
        raise viewer.ViewError("bu belgenin HTML görünümü yok")

    def make() -> str:
        data = ws.vault.read(sha256)
        return viewer.message(data).html if kind is ViewKind.MAIL else viewer.text(data)

    return _made(ws, sha256, f"ozgun-{VIEW_VERSION}.html", make, str.encode).decode()


def original(ws: Workspace, sha256: str) -> Original:
    """The document's bytes as they arrived, under its readable name."""
    doc, data = _original_bytes(ws, sha256)
    name = doc.display_name or doc.name
    dot = doc.name.rfind(".")
    media = _MEDIA.get(doc.name[dot:].lower() if dot > 0 else "", "application/octet-stream")
    return Original(name, media, data)


def reparse(ws: Workspace, sha256: str) -> str:
    """Read a kept document again now (a reading that failed for a passing reason, a reader that changed); the status
    it has now. A document that turns out to be a company's goes to the Trash (ADR-0003). The analysis follows."""
    with ws.lock(), ws.db() as db:
        doc = _kept(db, sha256)
        first = next(iter(documents.sources(db, sha256)), None)
        outcome = reading.read(doc.name, ws.vault.read(sha256), sha256, first.origin if first else "")
        if outcome.business:
            reading.remove_company(ws, db, doc, outcome.reason)
            status = DocumentStatus.REMOVED
        else:
            reading.record(db, sha256, doc.name, outcome)
            status = outcome.status
    background.request_refresh(ws)
    return status.value


def remove(ws: Workspace, sha256: str, actor: Actor) -> str:
    """A kept document to the system Trash (never deleted, ADR-0003): its rows go, the audit log says who and where;
    the same bytes arriving again stay out. The name of the Trash folder it went to."""
    with ws.lock(), ws.db() as db:
        _kept(db, sha256)
        where = ws.vault.remove(sha256)
        with db.transaction():
            readings.clear(db, sha256)
            documents.set_status(db, sha256, DocumentStatus.REMOVED, REMOVED_REASON)
            audit.record(db, actor, "document.removed", sha256, trash=where.parent.name)
    ws.vault.drop_derived(sha256)
    background.request_refresh(ws)
    return where.parent.name
