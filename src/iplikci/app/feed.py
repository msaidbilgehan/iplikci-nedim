"""The feed (F05): the event log newest first, a page at a time, narrowed by the events' kinds and by the accounts and
the certainty they concern; each event with what it concerns now and where it leads.

An event says what was true when it happened (architecture §13), and its text says it as a notification in full
does. What it names is looked up in the analysis the service keeps: a row is shown as the ledger counts it today (a
receipt's row that a statement confirmed since leads to the statement's row), a document as the archive keeps it.
"""

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, cast

from ..domain.codes import (
    Certainty,
    DetailLevel,
    DocumentKind,
    DocumentStatus,
    EventKind,
    MonthStatus,
    PaymentKind,
    SeriesPeriod,
    SourceKind,
)
from ..domain.labels import EVENT_KIND
from ..domain.models import TRY
from ..invoices import InvoiceMatch
from ..notify import content
from ..parsers import registry
from ..storage import documents, events
from ..storage.db import Database
from ..upcoming import series_id
from .analysis import Analysis
from .links import Link, Screen
from .rows import Found, Rows, RowView
from .workspace import Workspace

# What the API names from here: the use case, its records and the codes they carry.
__all__ = [
    "MAX_PAGE",
    "Certainty",
    "Detail",
    "DocumentKind",
    "DocumentRef",
    "DocumentStatus",
    "Filter",
    "Item",
    "MonthStatus",
    "Page",
    "PaymentKind",
    "SeriesPeriod",
    "SourceKind",
    "detail_of",
    "narrowed",
    "page",
    "text_of",
]

MAX_PAGE = 200
# The events one page looks at, at most: a narrow filter over a long log answers with a short page and where to go
# on from (next), rather than reading the whole log on every request.
SCAN = 2000
_BATCH = 250
_KIND = re.compile(r"[a-z][a-z_]*(\.[a-z][a-z_]*)*\.?")

E = EventKind
_ROWS = frozenset({E.TRANSACTION_CREATED, E.TRANSACTION_CONFIRMED, E.TRANSACTION_LARGE, E.INCOME_RECEIVED})
_SERIES = frozenset(
    {E.EXPECTED_PAYMENT_MISSING, E.INCOME_LATE, E.SUBSCRIPTION_PRICE_CHANGED, E.SUBSCRIPTION_PAID_AFTER_CANCEL}
)
# The day an event concerns, by the detail key that carries it.
_DAY_KEYS = ("date", "due", "day", "expected", "since")


@dataclass(frozen=True, slots=True)
class Filter:
    """What a page is narrowed to; an empty field narrows nothing."""

    codes: tuple[str, ...] = ()  # event kinds, as architecture §13 names them ("transaction.created")
    families: tuple[str, ...] = ()  # the first part of a kind, with its dot ("document.")
    accounts: frozenset[str] = frozenset()  # an event concerning one of these accounts
    certainties: frozenset[Certainty] = frozenset()  # an event about a row the ledger now counts with one of these


EVERY = Filter()


def narrowed(kinds: Iterable[str] = (), accounts: Iterable[str] = (), certainties: Iterable[Certainty] = ()) -> Filter:
    """A filter from what a request asks: a kind with a dot inside is an event's code; one without, or ending in a
    dot, is a family of them ("document" and "document." are the same). ValueError for a kind written otherwise."""
    codes: list[str] = []
    families: list[str] = []
    for kind in kinds:
        if not _KIND.fullmatch(kind):
            raise ValueError(f"olay türü değil: {kind!r}")
        if kind.endswith(".") or "." not in kind:
            families.append(kind.rstrip(".") + ".")
        else:
            codes.append(kind)
    return Filter(
        tuple(dict.fromkeys(codes)), tuple(dict.fromkeys(families)), frozenset(accounts), frozenset(certainties)
    )


@dataclass(frozen=True, slots=True)
class Detail:
    """What an event's detail says, typed; a field the event does not carry is empty (architecture §13)."""

    title: str = ""  # the name the user knows: a merchant, a payee or payer, a seller, an account
    amount: Decimal | None = None  # above zero: money out as the ledger counts it, income too
    currency: str = TRY  # of amount: a foreign account's row no rate valued stays in its currency
    minimum: Decimal | None = None  # a card due's minimum payment
    balance: Decimal | None = None  # a forecast's balance on its day; below zero: overdrawn
    old: Decimal | None = None  # a price before it changed
    new: Decimal | None = None  # and after
    day: date | None = None  # the day it concerns: a row's, a due date, the forecast's, the expected one, a price's
    days: int | None = None  # from the day the analysis was made to that day
    payment: PaymentKind | None = None
    period: SeriesPeriod | None = None
    cancelled: str = ""  # the month the user's rules give a cancelled series as its last, YYYY-MM
    status: MonthStatus | None = None  # an ended month's status
    count: int | None = None  # an event standing for many: how many
    first: date | None = None  # and the days of the first and last of them, for new rows
    last: date | None = None
    provisional: bool | None = None  # a new row only a receipt or a notice showed then
    source: SourceKind | None = None  # how a document arrived
    document_kind: DocumentKind | None = None  # what a read document turned out to be
    parser: str = ""  # the reader that read it, or gave up on it
    reader: str = ""  # that reader, for people
    version: str = ""  # its version, or the extension's
    reason: str = ""  # why a document was not read, a login was refused, a statement did not verify
    stage: str = ""  # a failed backup's: "backup" or "rehearsal"
    unverified: tuple[str, ...] = ()  # the accounts whose statements did not verify (a format alarm)


@dataclass(frozen=True, slots=True)
class DocumentRef:
    """A document an event concerns, as the archive keeps it now."""

    sha256: str
    name: str  # its readable name, else the file's own
    kind: DocumentKind | None
    status: DocumentStatus


@dataclass(frozen=True, slots=True)
class Item:
    id: int
    at: str  # when it was recorded, ISO in UTC
    kind: str  # its code (architecture §13); a kind this version does not know passes as it is
    label: str  # the kind, in Turkish, as its notification is titled (notify.content.title)
    text: str  # what happened, in a Turkish sentence
    target: str  # what it concerns, as the log keys it; "" for an event standing for many
    account: str  # the one account it concerns; "" for none or several
    certainty: Certainty | None  # a row's, as the ledger counts it now
    detail: Detail
    row: RowView | None  # the row it concerns, as the ledger counts it now
    document: DocumentRef | None  # the document it concerns
    link: Link | None  # where it leads


@dataclass(frozen=True, slots=True)
class Page:
    items: list[Item]  # newest first
    next: int | None  # the next page's `before`; None when nothing older is left


@dataclass(frozen=True, slots=True)
class _Concern:
    accounts: tuple[str, ...] = ()
    found: Found | None = None
    document: str = ""
    link: Link | None = None


@dataclass
class _Lookups:
    """What an analysis tells about the things events name."""

    rows: Rows
    documents: dict[str, set[str]] = field(default_factory=dict[str, set[str]])  # sha256 -> its accounts
    series: dict[str, str] = field(default_factory=dict[str, str])  # a series' id -> the account last seen on
    invoices: dict[str, InvoiceMatch] = field(default_factory=dict[str, InvoiceMatch])


def _lookups(a: Analysis) -> _Lookups:
    ds, ins = a.dataset, a.insights
    by_document: defaultdict[str, set[str]] = defaultdict(set)
    for t in ds.transactions:
        by_document[t.document].add(t.account)
    for line in ds.receipts:
        by_document[line.txn.document].add(line.txn.account)
    for s in ds.statements:
        by_document[s.document].add(s.account)
    by_document.pop("", None)
    series = {series_id(s): s.last.account for s in [*ins.series, *ins.periodic, *ins.income]}
    return _Lookups(Rows(ds), dict(by_document), series, {found.key: found for found in ds.invoices})


def _text_of(value: object) -> str:
    return value if isinstance(value, str) else ""


def _number(value: object) -> Decimal | None:
    """An amount as the events carry it ("1234.56")."""
    if not isinstance(value, str):
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _date(value: object) -> date | None:
    """An ISO day, or the day of an ISO time."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _code[T: StrEnum](kind: type[T], value: object) -> T | None:
    if not isinstance(value, str):
        return None
    try:
        return kind(value)
    except ValueError:
        return None


def _strings(value: object) -> tuple[str, ...]:
    """A list of texts the detail carries; anything else in it is left out."""
    if not isinstance(value, list):
        return ()
    return tuple(item for item in cast(list[object], value) if isinstance(item, str))


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def detail_of(d: Mapping[str, Any]) -> Detail:
    """An event's detail, typed; what it does not carry, or carries in a shape this version does not know, is
    left empty."""
    parser = _text_of(d.get("parser"))
    reader = registry.find(parser) if parser else None
    day = next((found for key in _DAY_KEYS if (found := _date(d.get(key))) is not None), None)
    return Detail(
        title=_text_of(d.get("title")),
        amount=_number(d.get("amount")),
        currency=_text_of(d.get("currency")) or TRY,
        minimum=_number(d.get("minimum")),
        balance=_number(d.get("balance")),
        old=_number(d.get("old")),
        new=_number(d.get("new")),
        day=day,
        days=_int(d.get("days")),
        payment=_code(PaymentKind, d.get("payment")),
        period=_code(SeriesPeriod, d.get("period")),
        cancelled=_text_of(d.get("cancelled")),
        status=_code(MonthStatus, d.get("status")),
        count=_int(d.get("count")),
        first=_date(d.get("from")),
        last=_date(d.get("to")),
        provisional=d["provisional"] if isinstance(d.get("provisional"), bool) else None,
        source=_code(SourceKind, d.get("source")),
        document_kind=_code(DocumentKind, d.get("kind")),
        parser=parser,
        reader=reader.name if reader is not None else "",
        version=_text_of(d.get("version")),
        reason=_text_of(d.get("reason")),
        stage=_text_of(d.get("stage")),
        unverified=_strings(d.get("unverified")),
    )


def _label(kind: str) -> str:
    code = _code(EventKind, kind)
    return EVENT_KIND[code] if code is not None else kind


def _day(value: date | None) -> str:
    return f"{value:%d.%m.%Y}" if value else ""


def text_of(kind: str, target: str, d: Mapping[str, Any]) -> str:
    """What happened, in a Turkish sentence: as a notification in full says it (notify.content), and for an event
    standing for many, how many."""
    count = _int(d.get("count"))
    if not target and count is not None:
        first, last = _date(d.get("from")), _date(d.get("to"))
        if kind == E.TRANSACTION_CREATED and first and last:
            return f"{_day(first)} – {_day(last)} arasında {count} yeni işlem."
        return f"{_label(kind)}: {count} kayıt."
    return content.render(kind, target, d, DetailLevel.FULL).body


def _concern(kind: str, target: str, d: Mapping[str, Any], found: _Lookups) -> _Concern:
    """The accounts, the row or the document an event concerns, and where it leads."""
    account = _text_of(d.get("account"))
    own = (account,) if account else ()
    if kind.startswith("document.") or kind == E.PARSER_FORMAT_ALARM:
        accounts = tuple(sorted(found.documents.get(target, set()) | set(_strings(d.get("unverified")))))
        return _Concern(accounts, document=target, link=Link(Screen.DOCUMENT, target) if target else None)
    if kind in _ROWS or kind == E.EVIDENCE_UNMATCHED:
        if not target:  # many new rows at once: the list of their days
            first, last = _text_of(d.get("from")), _text_of(d.get("to"))
            return _Concern(link=Link(Screen.TRANSACTIONS, query=(("from", first), ("to", last)) if first else ()))
        row = found.rows.find(target)
        accounts = own if row is None or row.row.account in own else (*own, row.row.account)
        return _Concern(accounts, row, link=Link(Screen.TRANSACTION, row.row.fingerprint if row else target))
    if kind.startswith("invoice."):
        match = found.invoices.get(target)
        paid = match.row.account if match is not None and match.row is not None else ""
        return _Concern((paid,) if paid else (), link=Link(Screen.INVOICE, target) if target else Link(Screen.INVOICES))
    if kind.startswith("month."):
        return _Concern(link=Link(Screen.MONTH, target))
    if kind == E.PAYMENT_DUE_SOON:
        return _Concern(own, link=Link(Screen.CALENDAR, _text_of(d.get("due"))))
    if kind == E.BALANCE_FORECAST_NEGATIVE:
        return _Concern(own, link=Link(Screen.FORECAST, account))
    if kind in _SERIES:
        series = target.partition("|")[0]
        last = found.series.get(series, "")
        return _Concern((last,) if last else (), link=Link(Screen.SUBSCRIPTION, series))
    if kind.startswith(("mail.", "backup.", "bridge.")):
        return _Concern(link=Link(Screen.SYSTEM))
    return _Concern(own)


def _document(db: Database, sha256: str) -> DocumentRef | None:
    found = documents.get(db, sha256) if sha256 else None
    if found is None:
        return None
    return DocumentRef(found.sha256, found.display_name or found.name, found.kind, found.status)


def _item(db: Database, event_id: int, event: events.Event, concern: _Concern, detail: Detail) -> Item:
    row = concern.found
    return Item(
        id=event_id,
        at=event.at,
        kind=event.kind,
        label=content.title(event.kind, event.detail),  # as its notification is titled: a new price rose or fell
        text=text_of(event.kind, event.target, event.detail),
        target=event.target,
        account=concern.accounts[0] if len(concern.accounts) == 1 else "",
        certainty=row.certainty if row else None,
        detail=detail,
        row=row.view if row else None,
        document=_document(db, concern.document),
        link=concern.link,
    )


def _wanted(concern: _Concern, wanted: Filter) -> bool:
    if wanted.accounts and not wanted.accounts & set(concern.accounts):
        return False
    return not wanted.certainties or (concern.found is not None and concern.found.certainty in wanted.certainties)


def page(ws: Workspace, a: Analysis, before: int = 0, limit: int = 50, wanted: Filter = EVERY) -> Page:
    """A page of the event log, newest first, from before the event with id before (0: from the newest), narrowed
    by wanted. A narrow filter may give fewer events than limit with a next page still to read: next is None only
    when the log holds nothing older."""
    size = max(1, min(limit, MAX_PAGE))
    found = _lookups(a)
    shown: list[Item] = []
    cursor, scanned, more = before, 0, True
    with ws.db() as db:
        while more and scanned < SCAN and len(shown) <= size:
            asked = min(_BATCH, SCAN - scanned)
            batch = events.newest_first(db, cursor, asked, wanted.codes, wanted.families)
            more = len(batch) == asked
            for event_id, event in batch:
                scanned, cursor = scanned + 1, event_id
                concern = _concern(event.kind, event.target, event.detail, found)
                if _wanted(concern, wanted):
                    shown.append(_item(db, event_id, event, concern, detail_of(event.detail)))
                    if len(shown) > size:
                        break
    if len(shown) > size:
        return Page(shown[:size], shown[size - 1].id)
    return Page(shown, cursor if more else None)
