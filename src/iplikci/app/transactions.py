"""The Transactions screen (F04): the ledger's rows filtered, sorted and paged, with the totals of what the filters
keep and the months of the filtered days that have not closed, with what they wait for; a CSV of them; one row's
detail with why it is what it is; the user's corrections on one row or many; the filters the user keeps as views.

The list holds the rows the ledger counts and the receipts' and notices' rows a statement covering their days leaves
out (excluded: shown, never in a total). A receipt's row a statement shows is not listed apart: the statement's row
stands for it, and its detail names the receipt. A row the user split is listed as its parts; a part's detail and
corrections are its row's."""

import csv
import io
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, cast

from ..analysis import ReceiptLine
from ..categorize import DEFAULT_RULES, Categorizer, RuleSet
from ..domain.codes import (
    DEFAULT_EXPENSE_KINDS,
    SPLITTABLE_KINDS,
    Actor,
    CategoryReason,
    Certainty,
    DocumentKind,
    EvidenceStatus,
    MonthStatus,
    Necessity,
    NecessityReason,
    RateSource,
    RuleLayer,
    TransactionKind,
    TransferStep,
)
from ..domain.labels import CERTAINTY, KIND, NECESSITY, currency_label
from ..domain.models import Reason, Transaction
from ..domain.text import fold, spreadsheet_text
from ..insights import month_of, shift
from ..month_end import first_day, last_day
from ..storage import annotations, audit, documents, feed_state
from ..storage.annotations import Annotation
from . import annotate, background, closing
from .analysis import Analysis, account_labels
from .links import Link, Screen
from .rows import Direction, Found, Rows, RowView, view
from .workspace import Workspace

__all__ = [
    "Actor",
    "Awaited",
    "CategoryReason",
    "Certainty",
    "Checked",
    "Detail",
    "Direction",
    "DocumentKind",
    "EvidenceStatus",
    "Filter",
    "MonthStatus",
    "Necessity",
    "NecessityReason",
    "OpenMonth",
    "Page",
    "Period",
    "Printed",
    "RateSource",
    "RowView",
    "RuleLayer",
    "Sort",
    "Totals",
    "TransactionKind",
    "TransferStep",
    "open_months",
    "period_days",
    "tag_counts",
]

MAX_PAGE = 500
VIEWS = "transactions.views"  # feed_state: the filters the user keeps, by name
MAX_VIEWS = 30
VIEW_SAVED, VIEW_REMOVED = "transactions.view_saved", "transactions.view_removed"


class Refused(Exception):
    """A correction the program will not make; the message says why, in Turkish."""


class NotFound(Exception):
    """No row has the fingerprint (a reading changed the row, or it never was one)."""


class Sort(StrEnum):
    DAY = "day"
    AMOUNT = "amount"
    TITLE = "title"
    CATEGORY = "category"
    ACCOUNT = "account"


class Period(StrEnum):
    """A period the screen offers by name; its days are reckoned from today, so a view kept with it moves with time."""

    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    LAST_30_DAYS = "last_30_days"  # today and the 29 days before it
    LAST_3_MONTHS = "last_3_months"  # this month and the two before it
    THIS_YEAR = "this_year"
    LAST_YEAR = "last_year"


def period_days(period: Period, today: date) -> tuple[date, date]:
    """The first and the last day of a named period, both in it."""
    month = month_of(today)
    match period:
        case Period.THIS_MONTH:
            return first_day(month), last_day(month)
        case Period.LAST_MONTH:
            before = shift(month, -1)
            return first_day(before), last_day(before)
        case Period.LAST_30_DAYS:
            return today - timedelta(days=29), today
        case Period.LAST_3_MONTHS:
            return first_day(shift(month, -2)), last_day(month)
        case Period.THIS_YEAR:
            return date(today.year, 1, 1), date(today.year, 12, 31)
        case Period.LAST_YEAR:
            return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)


@dataclass(frozen=True, slots=True)
class Filter:
    """What the screen's filters keep; an empty set keeps everything."""

    start: date | None = None
    end: date | None = None  # inclusive
    accounts: frozenset[str] = frozenset()
    kinds: frozenset[TransactionKind] = frozenset()
    categories: frozenset[str] = frozenset()
    groups: frozenset[str] = frozenset()
    necessities: frozenset[Necessity] = frozenset()
    certainties: frozenset[Certainty] = frozenset()
    tags: frozenset[str] = frozenset()
    merchant: str = ""  # one merchant or person, as the rules name it
    text: str = ""  # every word in the row's names, its description, category, note, tags or account
    direction: Direction | None = None  # money in or money out only
    least: Decimal | None = None  # the row's amount at least, whichever way it goes (in TL, as the list shows it)
    most: Decimal | None = None  # and at most

    def keeps(self, row: RowView, label: str) -> bool:
        return (
            (self.start is None or row.day >= self.start)
            and (self.end is None or row.day <= self.end)
            and (not self.accounts or row.account in self.accounts)
            and (not self.kinds or row.kind in self.kinds)
            and (not self.categories or row.category in self.categories)
            and (not self.groups or row.group in self.groups)
            and (not self.necessities or row.necessity in self.necessities)
            and (not self.certainties or row.certainty in self.certainties)
            and (not self.tags or not self.tags.isdisjoint(row.tags))
            and (not self.merchant or fold(row.merchant) == fold(self.merchant))
            and (self.direction is None or row.direction is self.direction)
            and (self.least is None or row.amount >= self.least)
            and (self.most is None or row.amount <= self.most)
            and (not self.text or _has_words(row, label, self.text))
        )

    def query(self) -> tuple[tuple[str, str], ...]:
        """The filters as the Transactions screen's address holds them, in the API's names, each of many values a pair
        of its own and in a steady order: a link with them opens the screen on these rows."""
        pairs: list[tuple[str, str]] = []
        if self.start is not None:
            pairs.append(("from", self.start.isoformat()))
        if self.end is not None:
            pairs.append(("to", self.end.isoformat()))
        many: tuple[tuple[str, frozenset[str]], ...] = (
            ("account", self.accounts),
            ("kind", frozenset(k.value for k in self.kinds)),
            ("category", self.categories),
            ("group", self.groups),
            ("necessity", frozenset(n.value for n in self.necessities)),
            ("certainty", frozenset(c.value for c in self.certainties)),
            ("tag", self.tags),
        )
        for name, values in many:
            pairs += [(name, value) for value in sorted(values)]
        if self.merchant:
            pairs.append(("merchant", self.merchant))
        if self.direction is not None:
            pairs.append(("direction", self.direction.value))
        if self.least is not None:
            pairs.append(("min", str(self.least)))
        if self.most is not None:
            pairs.append(("max", str(self.most)))
        if self.text:
            pairs.append(("q", self.text))
        return tuple(pairs)


def rows_link(f: Filter) -> Link:
    """The Transactions screen narrowed to the rows f keeps."""
    return Link(Screen.TRANSACTIONS, query=f.query())


def _has_words(row: RowView, label: str, text: str) -> bool:
    found = fold(
        " ".join(
            (row.title, row.description, row.merchant, row.counterparty, row.category, row.group, row.note)
            + row.tags
            + (row.original, label)
        )
    )
    return all(word in found for word in fold(text).split())


@dataclass(frozen=True, slots=True)
class Totals:
    """What the rows the filters keep add up to: only the counted ones are in the sums, in TL."""

    count: int
    counted: int
    spent: Decimal  # spending net of refunds: purchases, refunds, interest and fees
    money_out: Decimal  # every counted row's money out, whatever its kind
    money_in: Decimal
    provisional: int  # counted rows only a receipt or a notice shows yet
    excluded: int  # rows never counted


@dataclass(frozen=True, slots=True)
class Page:
    rows: list[RowView]
    totals: Totals
    offset: int
    next: int | None  # the offset of the next page; None on the last


def labels(a: Analysis) -> dict[str, str]:
    """The accounts as the screens name them: the user's own name for one, else the bank's label."""
    return account_labels(a)


def every_row(a: Analysis) -> list[RowView]:
    """The counted rows and the excluded ones, oldest first."""
    rows = Rows(a.dataset)
    found = [view(t, Certainty.PROVISIONAL if t.provisional else Certainty.CONFIRMED) for t in a.dataset.transactions]
    for line in rows.excluded():
        found.append(view(line.txn, Certainty.EXCLUDED, rows.currency(line.txn.account), counted=False))
    return sorted(found, key=lambda r: (r.day, r.account, r.fingerprint))


def select(a: Analysis, f: Filter) -> list[RowView]:
    names = labels(a)
    return [r for r in every_row(a) if f.keeps(r, names.get(r.account, r.account))]


def tag_counts(a: Analysis) -> list[tuple[str, int]]:
    """The tags the user gave rows, each with how many rows carry it: the most used first, then by name. The tag
    filter offers them, so a tag is chosen rather than guessed."""
    found = Counter(tag for row in every_row(a) for tag in row.tags)
    return sorted(found.items(), key=lambda item: (-item[1], fold(item[0])))


def _sort_key(r: RowView, sort: Sort, names: Mapping[str, str]) -> Any:
    match sort:
        case Sort.DAY:
            return r.day
        case Sort.AMOUNT:
            return r.amount
        case Sort.TITLE:
            return fold(r.title)
        case Sort.CATEGORY:
            return fold(r.category)
        case Sort.ACCOUNT:
            return fold(names.get(r.account, r.account))


def _place(r: RowView) -> tuple[date, str, int]:
    """Where a row stands among alike ones: a split row's parts stand together, in their order."""
    if r.split_of:
        return r.day, r.split_of, -int(r.fingerprint.rsplit("-", 1)[1])
    return r.day, r.fingerprint, 0


def ordered(rows: Sequence[RowView], sort: Sort, descending: bool, names: Mapping[str, str]) -> list[RowView]:
    """The rows by sort; alike rows newest first, then in the ledger's order."""
    stable = sorted(rows, key=_place, reverse=True)
    return sorted(stable, key=lambda r: _sort_key(r, sort, names), reverse=descending)


def totals(rows: Iterable[RowView]) -> Totals:
    count = counted = provisional = excluded = 0
    spent = money_out = money_in = Decimal(0)
    for r in rows:
        count += 1
        if not r.counted:
            excluded += 1
            continue
        counted += 1
        provisional += r.certainty is Certainty.PROVISIONAL
        signed = r.amount if r.direction is Direction.OUT else -r.amount
        if r.kind in DEFAULT_EXPENSE_KINDS:
            spent += signed
        if r.direction is Direction.OUT:
            money_out += r.amount
        else:
            money_in += r.amount
    return Totals(count, counted, spent, money_out, money_in, provisional, excluded)


@dataclass(frozen=True, slots=True)
class Order:
    sort: Sort = Sort.DAY
    descending: bool = True
    offset: int = 0
    limit: int = 50


def page(a: Analysis, f: Filter, order: Order) -> Page:
    found = select(a, f)
    rows = ordered(found, order.sort, order.descending, labels(a))
    limit = max(1, min(order.limit, MAX_PAGE))
    shown = rows[order.offset : order.offset + limit]
    more = order.offset + limit < len(rows)
    return Page(shown, totals(found), order.offset, order.offset + limit if more else None)


@dataclass(frozen=True, slots=True)
class Awaited:
    """An account whose documents for some of the filtered days are not in yet (month_end.AccountClose)."""

    account: str
    status: MonthStatus  # waiting, missing or check
    days: list[tuple[date, date]]  # the filtered days it leaves open; none for a check, which is the month's
    what: str  # what closes them, in a few Turkish words: "19–31 Ekim ekstresi, kesim ~18.11"
    late: bool  # the statement's cut passed days ago and it did not come


@dataclass(frozen=True, slots=True)
class OpenMonth:
    """A month of the filtered days that has not closed, with what it waits for: the list shows those days' rows as
    far as the documents in go."""

    month: str
    status: MonthStatus  # never closed
    accounts: list[Awaited]  # a running month names none: it runs on
    closes_by: date | None  # the day it should close (MonthEnd.closes_by)


def open_months(a: Analysis, f: Filter, today: date) -> list[OpenMonth]:
    """The months of the filter's days that have not closed, of the current month and the twelve before it (the
    closing's months), the oldest first, each with the accounts the filter keeps whose documents for those days are
    not in yet. A month whose open days lie outside the filter's, or whose open accounts the filter leaves out, waits
    for nothing the list could show."""
    found: list[OpenMonth] = []
    for me in reversed(closing.months(a, today)):
        start = max(first_day(me.month), f.start or date.min)
        end = min(last_day(me.month), f.end or date.max)
        if me.status is MonthStatus.CLOSED or start > end:
            continue
        if me.status is MonthStatus.RUNNING:
            found.append(OpenMonth(me.month, me.status, [], None))
            continue
        held = [
            Awaited(ac.account.id, ac.status, days, ac.waiting_for, ac.late)
            for ac in me.open
            if not f.accounts or ac.account.id in f.accounts
            if (days := [(max(lo, start), min(hi, end)) for lo, hi in ac.open if lo <= end and hi >= start])
            or ac.status is MonthStatus.CHECK
        ]
        if held:
            found.append(OpenMonth(me.month, me.status, held, me.closes_by))
    return found


_CSV_COLUMNS = (
    "Tarih",
    "Ay",
    "Banka",
    "Hesap",
    "İşlem türü",
    "Ana grup",
    "Kategori",
    "Gereklilik",
    "İşyeri / kişi",
    "Açıklama",
    "Tutar",
    "Para birimi",
    "Taksit",
    "Döviz tutarı",
    "Gider sayılır",
    "Kesinlik",
    "Not",
    "Etiketler",
    "Parmak izi",
)


def csv_text(a: Analysis, f: Filter, order: Order) -> str:
    """The rows the filters keep as the MVP's CSV wrote them: semicolons, comma decimals, money out above zero; a
    byte-order mark, so Turkish Excel opens it cleanly."""
    banks = {key: acc.bank for key, acc in a.dataset.accounts.items()}
    names = labels(a)
    out = io.StringIO()
    w = csv.writer(out, delimiter=";", lineterminator="\r\n")
    w.writerow(_CSV_COLUMNS)
    for r in ordered(select(a, f), order.sort, order.descending, names):
        signed = r.amount if r.direction is Direction.OUT else -r.amount
        text = spreadsheet_text  # what the documents, the rules and the user wrote: never run as a formula
        w.writerow(
            (
                f"{r.day:%d.%m.%Y}",
                f"{r.day:%Y-%m}",
                text(banks.get(r.account, "")),
                text(names.get(r.account, r.account)),
                KIND[r.kind],
                text(r.group),
                text(r.category),
                NECESSITY[r.necessity] if r.necessity else "",
                text(r.title),
                text(r.description),
                f"{signed:.2f}".replace(".", ","),
                currency_label(r.currency),
                text(r.installment),
                text(r.original),
                "Evet" if r.expense else "Hayır",
                CERTAINTY[r.certainty],
                text(r.note),
                text(", ".join(r.tags)),
                r.fingerprint,
            )
        )
    return "﻿" + out.getvalue()


# --- one row --------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Printed:
    """Where a row is printed: the document, and the place in it the viewer opens at."""

    document: str  # sha256
    name: str  # the document's readable name
    kind: DocumentKind | None
    page: int | None
    line: int | None
    sheet: str | None
    row: int | None


@dataclass(frozen=True, slots=True)
class Told:
    """A receipt's or a bank notice's row about this row, and what the statements say of it."""

    fingerprint: str
    status: EvidenceStatus
    day: date
    amount: Decimal  # in TL, above zero
    printed: Printed | None


@dataclass(frozen=True, slots=True)
class Bill:
    """The non-bank bill or receipt the row paid (F14)."""

    key: str  # "<sha256>:<position>"
    seller: str
    issued: date
    total: Decimal
    currency: str


@dataclass(frozen=True, slots=True)
class Why:
    category: CategoryReason
    rule: str  # the pattern, as its rule file writes it
    layer: RuleLayer | None
    necessity: NecessityReason | None  # None: the row is no spending
    necessity_layer: RuleLayer | None
    transfer: TransferStep | None
    pair: RowView | None  # the opposite row in another own account, or the named payment it is like
    rate: Decimal | None  # a foreign account's row: the TL rate it was valued at (docs/domain/ledger.md)
    rate_day: date | None  # the day that rate is of: the row that printed it, or the providers' bulletin
    rate_source: RateSource | None  # the documents (the row's own rate, else the nearest), or a provider


@dataclass(frozen=True, slots=True)
class Detail:
    row: RowView
    account: str  # the account's label
    printed: Printed | None
    why: Why
    told: list[Told]  # the receipts' and notices' rows about it
    bill: Bill | None
    annotation: Annotation | None  # the user's note, tags and corrections on it
    correctable: bool  # a counted row: an excluded one carries no correction
    parts: list[RowView] = field(default_factory=list[RowView])  # a split row's parts, in order
    splittable: bool = False  # a counted row of a kind that can be split (spending, money to people, income)
    # The user split it, but it counts whole again: its kind no longer splits, or its amount moved so far that a part
    # came to nothing (the annotation keeps the parts).
    split_dropped: bool = False


def _layer(name: str) -> RuleLayer | None:
    if not name:
        return None
    return RuleLayer.SHIPPED if name == DEFAULT_RULES.name else RuleLayer.OWN


def _necessity_reason(
    t: Transaction, rules: Categorizer, note: Annotation | None
) -> tuple[NecessityReason | None, str]:
    """Where the row's necessity comes from, and the rule file that gives it."""
    if t.necessity is None:
        return None, ""
    if note is not None and note.necessity:
        return NecessityReason.USER, ""
    if t.kind is TransactionKind.INTEREST_FEE:  # a fee is unnecessary unless its category's level says otherwise
        return _from_layers(rules, lambda layer: t.category in layer.necessity, NecessityReason.CATEGORY)
    merchant = fold(t.merchant)
    if merchant in rules.merchant_necessity:
        return _from_layers(rules, lambda layer: merchant in layer.merchant_necessity, NecessityReason.MERCHANT)
    return _from_layers(rules, lambda layer: t.category in layer.necessity, NecessityReason.CATEGORY)


def _from_layers(
    rules: Categorizer, has: Callable[[RuleSet], bool], found: NecessityReason
) -> tuple[NecessityReason, str]:
    for layer in rules.layers:  # the user's file first: its word stands
        if has(layer):
            return found, layer.name
    return NecessityReason.DEFAULT, ""


def _printed(t: Transaction, docs: Mapping[str, documents.DocumentRow]) -> Printed | None:
    doc = docs.get(t.document)
    if not t.document or doc is None:
        return None
    ref = t.ref
    return Printed(
        t.document,
        doc.display_name or doc.name,
        doc.kind,
        ref.page if ref else None,
        ref.line if ref else None,
        ref.sheet if ref else None,
        ref.row if ref else None,
    )


def _told(lines: Iterable[ReceiptLine], docs: Mapping[str, documents.DocumentRow]) -> list[Told]:
    return [
        Told(line.txn.fingerprint, line.status, line.txn.date, abs(line.txn.amount), _printed(line.txn, docs))
        for line in lines
    ]


def detail(ws: Workspace, a: Analysis, fingerprint: str) -> Detail:
    """A row and why it is what it is; a part of a split row gives its row's. NotFound when no row has the
    fingerprint."""
    rows = Rows(a.dataset)
    found = rows.find_whole(fingerprint)
    if found is None:
        raise NotFound(fingerprint)
    t = found.row
    with ws.db() as db:
        docs = {d.sha256: d for d in documents.every(db)}
        note = annotations.get(db, t.fingerprint) if found.counted else None
    rules = Categorizer.layered(ws.rules)
    level, level_file = _necessity_reason(t, rules, note)
    # The receipts and notices about the row: the ones a statement's row stands for, the receipt's own row that counts
    # while no statement shows it, or the excluded row's own.
    if found.told is None:
        about = [line for line in a.dataset.receipts if line.match is t or line.txn is t]
    else:
        about = [found.told]
    return Detail(
        row=found.view,
        account=labels(a).get(t.account, t.account),
        printed=_printed(t, docs),
        why=_why(t.reason, level, level_file, Rows(a.dataset)),
        told=_told(about, docs),
        bill=_bill(a, t.invoice),
        annotation=note,
        correctable=found.counted,
        parts=[
            view(part, Certainty.PROVISIONAL if part.provisional else Certainty.CONFIRMED)
            for part in rows.parts(t.fingerprint)
        ],
        splittable=found.counted and t.kind in SPLITTABLE_KINDS,
        split_dropped=note is not None and bool(note.parts) and t.fingerprint not in a.dataset.split,
    )


def _why(reason: Reason, level: NecessityReason | None, level_file: str, rows: Rows) -> Why:
    pair = rows.find(reason.pair) if reason.pair else None
    return Why(
        category=reason.category,
        rule=reason.rule,
        layer=_layer(reason.layer),
        necessity=level,
        necessity_layer=_layer(level_file),
        transfer=reason.transfer,
        pair=pair.view if pair is not None else None,
        rate=reason.rate,
        rate_day=reason.rate_day,
        rate_source=reason.rate_source,
    )


def _bill(a: Analysis, key: str) -> Bill | None:
    if not key:
        return None
    for found in a.dataset.invoices:
        if found.key == key:
            i = found.invoice
            return Bill(key, i.seller, i.issued, i.total, i.currency)
    return None


# --- corrections ----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Correction:
    """What changes on a row; a field left out stays as it is. "" (or None for the necessity) gives it back to the
    rules."""

    note: str | None = None
    tags: tuple[str, ...] | None = None
    category: str | None = None
    necessity: Necessity | None = None
    clear_necessity: bool = False
    parts: tuple[annotate.Share, ...] | None = None  # the row split; () joins it again


def _counted(a: Analysis, fingerprint: str) -> Found:
    """The row a correction goes on: a part of a split row stands for its row."""
    found = Rows(a.dataset).find_whole(fingerprint)
    if found is None:
        raise NotFound(fingerprint)
    if not found.counted:
        raise Refused("Toplama girmeyen bir satır düzeltilmez; ekstrede görünmeyen kanıttır.")
    return found


def _changes(ws: Workspace, change: Correction, t: Transaction | None = None) -> dict[str, Any]:
    """The annotation's fields a correction sets, checked; t is the row, which a split must add up to."""
    values: dict[str, Any] = {}
    if change.note is not None:
        values["note"] = change.note.strip()
    if change.tags is not None:
        values["tags"] = annotations.clean_tags(change.tags)
    if change.category is not None:
        try:
            values["category"] = (
                annotate.category(Categorizer.layered(ws.rules), change.category) if change.category else ""
            )
        except ValueError as exc:
            raise Refused(str(exc)) from exc
    if change.clear_necessity:
        values["necessity"] = None
    elif change.necessity is not None:
        values["necessity"] = change.necessity
    if change.parts is not None and t is not None:
        try:
            values["parts"] = annotate.split(Categorizer.layered(ws.rules), t, change.parts)
        except ValueError as exc:
            raise Refused(str(exc)) from exc
    if not values:
        raise Refused("Neyin değişeceğini seçin: not, etiket, kategori, gereklilik ya da bölme.")
    return values


def _labelled(change: Correction) -> bool:
    """Whether a correction gives the row a category or a necessity of its own, rather than back to the rules."""
    return bool(change.category) or (change.necessity is not None and not change.clear_necessity)


@dataclass(frozen=True, slots=True)
class Checked:
    """A correction as correct makes it: the row it goes on (a part's is its row) and the annotation's fields it
    sets, checked (a category written as the rules write it)."""

    row: Transaction
    values: dict[str, Any]  # note, tags, category ("" back to the rules), necessity (None back to them), parts
    # The kind the row takes with the category it is given, when that is not its kind now: a transfer the ledger
    # worked out counts as its new category says (annotate.kind_in). None when it stays.
    kind: TransactionKind | None = None


def check(ws: Workspace, a: Analysis, fingerprint: str, change: Correction) -> Checked:
    """What correct would do, nothing written: the MCP server shows it before the user approves it. NotFound and
    Refused as correct raises them. A split row's category and necessity are its parts': one given to the row itself
    would not show, so it is refused unless the same change joins the row."""
    t = _counted(a, fingerprint).row
    split_stays = (t.fingerprint in a.dataset.split and change.parts != ()) or bool(change.parts)
    if split_stays and _labelled(change):
        raise Refused(
            "Bölünmüş satırın kategorisi ve gerekliliği her parçada ayrı seçilir: parçaları düzenleyin ya da önce "
            "bölmeyi kaldırın."
        )
    values = _changes(ws, change, t)
    kind = annotate.kind_in(t, values["category"], Categorizer.layered(ws.rules)) if values.get("category") else None
    return Checked(t, values, kind if kind != t.kind else None)


def correct(ws: Workspace, a: Analysis, fingerprint: str, change: Correction, actor: Actor) -> Annotation | None:
    """Correct one row: its note, tags, category or necessity, bound to its fingerprint so a new reading keeps it.
    Returns what is kept; None when nothing is (the rules decide again). Refused as check says."""
    checked = check(ws, a, fingerprint, change)
    t = checked.row
    label = a.dataset.accounts[t.account].label if t.account in a.dataset.accounts else t.account
    with ws.db() as db:
        kept = annotations.change(db, t.fingerprint, annotate.subject(t, label), actor, **checked.values)
    background.request_refresh(ws)
    return kept


@dataclass(frozen=True, slots=True)
class Bulk:
    changed: int
    # Fingerprints no counted row has, and, for a category, the split rows': their parts keep theirs.
    skipped: list[str] = field(default_factory=list[str])


def correct_many(
    ws: Workspace, a: Analysis, fingerprints: Sequence[str], category: str | None, tags: Sequence[str], actor: Actor
) -> Bulk:
    """Give the rows one category, or add tags to theirs (F04's bulk action), all in one transaction. A part of a
    split row stands for its row."""
    if category is None and not tags:
        raise Refused("Seçili işlemlere verilecek kategoriyi ya da etiketi seçin.")
    values: dict[str, Any] = {}
    if category is not None:
        values = _changes(ws, Correction(category=category))
    rows = Rows(a.dataset)
    changed, skipped, done = 0, list[str](), set[str]()
    with ws.db() as db, db.transaction():
        for fp in dict.fromkeys(fingerprints):
            found = rows.find_whole(fp)
            if (
                found is None
                or not found.counted
                or (category is not None and found.row.fingerprint in a.dataset.split)
            ):
                skipped.append(fp)
                continue
            if found.row.fingerprint in done:  # two parts of one row
                continue
            done.add(found.row.fingerprint)
            t = found.row
            label = a.dataset.accounts[t.account].label if t.account in a.dataset.accounts else t.account
            extra: dict[str, Any] = {"tags": annotations.clean_tags((*t.tags, *tags))} if tags else {}
            annotations.change(db, t.fingerprint, annotate.subject(t, label), actor, **values, **extra)
            changed += 1
    background.request_refresh(ws)
    return Bulk(changed, skipped)


# --- kept views -----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class View:
    name: str
    query: dict[str, list[str]]  # the screen's filters as its address's query


def views(ws: Workspace) -> list[View]:
    with ws.db() as db:
        return _views(db)


def _views(db: Any) -> list[View]:
    found = feed_state.load(db, VIEWS)
    if not isinstance(found, list):
        return []
    out: list[View] = []
    for item in cast(list[Any], found):
        if isinstance(item, dict):
            entry = cast(dict[str, Any], item)
            query = cast(dict[str, Any], entry.get("query") or {})
            out.append(View(str(entry.get("name", "")), {str(k): [str(v) for v in vs] for k, vs in query.items()}))
    return out


def save_view(ws: Workspace, name: str, query: Mapping[str, Sequence[str]], actor: Actor) -> list[View]:
    """Keep the filters under a name; the same name replaces the one kept before."""
    name = " ".join(name.split())
    if not name:
        raise Refused("Görünüme bir ad verin.")
    with ws.db() as db, db.transaction():
        kept = [v for v in _views(db) if fold(v.name) != fold(name)]
        if len(kept) >= MAX_VIEWS:
            raise Refused(f"En çok {MAX_VIEWS} görünüm saklanır; önce birini silin.")
        kept.append(View(name, {k: list(vs) for k, vs in query.items() if vs}))
        feed_state.save(db, VIEWS, [{"name": v.name, "query": v.query} for v in kept])
        audit.record(db, actor, VIEW_SAVED, "transactions")
        return kept


def remove_view(ws: Workspace, name: str, actor: Actor) -> list[View] | None:
    """Forget a kept view; None when there is none by that name."""
    with ws.db() as db, db.transaction():
        found = _views(db)
        kept = [v for v in found if fold(v.name) != fold(name)]
        if len(kept) == len(found):
            return None
        feed_state.save(db, VIEWS, [{"name": v.name, "query": v.query} for v in kept])
        audit.record(db, actor, VIEW_REMOVED, "transactions")
        return kept
