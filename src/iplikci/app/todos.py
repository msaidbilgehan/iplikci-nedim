"""The to-do list (F19): what keeps the data from being complete and right, each item with the steps that settle it
— a rule, a document from the computer, reading it again, a request for Claude — or taken off the list by the user.

An item's key names what it stands for, so one the user took off stays off until that changes: a new statement makes
an account's gap a new item, a merchant's rows stay one item however many come. What the user took off is kept with
the feed's state; rebuilding the database from the primary data forgets it, and the items come back once."""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast

from ..analysis import NOT_ON_STATEMENT, Dataset
from ..categorize import UNCATEGORIZED
from ..domain.codes import SPLITTABLE_KINDS, Actor, DocumentStatus, InvoiceStatus, TodoAction, TodoKind
from ..domain.labels import KIND, format_amount
from ..domain.models import Transaction
from ..domain.search import exactly
from ..domain.text import fold
from ..insights import month_name
from ..parsers import registry
from ..parsers.common import BUSINESS_REASON
from ..parsers.messages import ATTACHED, NO_MONEY
from ..storage import audit, documents, feed_state
from ..storage.annotations import Annotation
from ..storage.db import Database
from .analysis import Analysis, account_labels, document_gaps
from .annotate import Unsplit
from .bridge import INCOMPLETE_REASON
from .links import Link, Screen
from .reading import FORMAT_ALARM
from .workspace import Workspace

__all__ = ["Actor", "Todo", "TodoAction", "TodoKind", "counts", "ignore", "items"]

IGNORED = "todos.ignored"  # feed_state: an item's key -> when the user took it off the list
TODO_IGNORED = "todo.ignored"  # the audit log's action
# What an unprocessed document's reason says it knowingly is: no to-do for it.
_SETTLED = frozenset({ATTACHED, BUSINESS_REASON, INCOMPLETE_REASON, *NO_MONEY})
_KIND_ORDER = list(TodoKind)


@dataclass(frozen=True, slots=True)
class Todo:
    key: str  # what it stands for; the same thing keeps its key from one analysis to the next
    kind: TodoKind
    title: str
    detail: str  # what it is, with its numbers and window
    count: int  # the rows or documents it stands for
    amount: Decimal | None  # their total in TL, where it applies
    target: str  # a merchant, a row's fingerprint, a document's sha256, an account or a reader
    link: Link | None  # where the interface shows it
    actions: tuple[TodoAction, ...]
    prompt: str  # a request to paste into Claude with the MCP server connected; "" when it offers none
    ignored: bool = False


def _tl(value: Decimal) -> str:
    return f"{format_amount(abs(value))} TL"


def _day(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _uncategorized(ds: Dataset) -> list[Todo]:
    groups: defaultdict[str, list[Transaction]] = defaultdict(list)
    for t in ds.transactions:
        if t.category == UNCATEGORIZED:
            groups[fold(t.merchant or t.description)].append(t)
    found: list[Todo] = []
    for key, rows in groups.items():
        name = rows[-1].merchant or rows[-1].description
        total = sum((t.amount for t in rows), Decimal(0))
        last = max(t.date for t in rows)
        found.append(
            Todo(
                key=f"uncategorized:{key}",
                kind=TodoKind.UNCATEGORIZED,
                title=name,
                detail=f"{len(rows)} işlem, toplam {_tl(total)}; sonuncusu {_day(last)}. Hiçbir kural adlandırmıyor.",
                count=len(rows),
                amount=total,
                target=name,
                # The name searched whole: a comma in it would part the search (domain.search).
                link=Link(Screen.TRANSACTIONS, query=(("category", UNCATEGORIZED), ("q", exactly(name)))),
                actions=(TodoAction.ADD_RULE, TodoAction.ASK_CLAUDE, TodoAction.IGNORE),
                prompt=(
                    f"İplikçi Nedim'de '{name}' adlı işyerinin {len(rows)} işlemi kategorisiz. transactions aracıyla "
                    "işlemlere bak, uygun kategoriyi öner; onaylarsam add_rule ile kural ekle."
                ),
            )
        )
    # The most frequent merchants first: one rule settles the most rows (F19).
    return sorted(found, key=lambda t: (-t.count, -abs(t.amount or 0), t.title))


def _evidence(ds: Dataset, names: Mapping[str, str]) -> list[Todo]:
    found: list[Todo] = []
    for line in ds.receipts:
        if line.status is not NOT_ON_STATEMENT:
            continue
        t = line.txn
        found.append(
            Todo(
                key=f"evidence:{t.fingerprint}",
                kind=TodoKind.UNMATCHED_EVIDENCE,
                title=t.description,
                detail=(
                    f"{_day(t.date)} günlü {_tl(t.amount)}; {names.get(t.account, t.account)} ekstresi o "
                    "günleri kapsıyor ama bu hareketi göstermiyor. Toplamlara girmez."
                ),
                count=1,
                amount=t.amount,
                target=t.fingerprint,
                link=Link(Screen.DOCUMENT, t.document, (("satir", t.fingerprint),)) if t.document else None,
                actions=(TodoAction.OPEN, TodoAction.ASK_CLAUDE, TodoAction.IGNORE),
                prompt=(
                    f"İplikçi Nedim'de {_day(t.date)} günlü {_tl(t.amount)} tutarlı '{t.description}' hareketi bir "
                    "dekontta var ama ekstrede görünmüyor. Nedenini bulmama yardım et."
                ),
            )
        )
    return found


def _invoices(ds: Dataset) -> list[Todo]:
    return [
        Todo(
            key=f"invoice:{found.key}",
            kind=TodoKind.UNMATCHED_INVOICE,
            title=found.invoice.seller,
            detail=f"{_day(found.invoice.issued)} tarihli {found.invoice.total} {found.invoice.currency}; "
            + (found.reasons[0] if found.reasons else "ödeyen banka satırı bulunamadı."),
            count=1,
            amount=None,
            target=found.key,
            link=Link(Screen.INVOICE, found.key),
            actions=(TodoAction.OPEN, TodoAction.IGNORE),
            prompt="",
        )
        for found in ds.invoices
        if found.status is InvoiceStatus.UNMATCHED
    ]


def _statements(ds: Dataset, names: Mapping[str, str]) -> list[Todo]:
    found: list[Todo] = []
    for s in ds.statements:
        if s.verified:
            continue
        label = names.get(s.account, s.account)
        if s.is_account:
            why = f"bakiye denetimlerinin {s.checks_ok}/{s.checks_total} tanesi tutuyor"
        else:
            why = f"satırları yazdığı toplamdan {s.difference} farklı" if s.difference is not None else "toplamı yok"
        found.append(
            Todo(
                key=f"statement:{s.document or s.source}:{s.cut_date.isoformat()}",
                kind=TodoKind.UNVERIFIED_STATEMENT,
                title=f"{label}, {_day(s.cut_date)}",
                detail=f"Ekstre doğrulanmadı: {why}.",
                count=len(s.transactions),
                amount=None,
                target=s.document,
                link=Link(Screen.DOCUMENT, s.document) if s.document else None,
                actions=(TodoAction.OPEN, TodoAction.REPARSE, TodoAction.ASK_CLAUDE),
                prompt=(
                    f"İplikçi Nedim'de {label} hesabının {_day(s.cut_date)} kesimli ekstresi doğrulanmadı ({why}). "
                    "Belgeye bakıp okuyucunun neyi kaçırdığını bulmama yardım et."
                ),
            )
        )
    return found


def _gaps(ds: Dataset, today: date, names: Mapping[str, str]) -> list[Todo]:
    found: list[Todo] = []
    for gap in document_gaps(ds, today):
        what = "ekstresi" if gap.kind == "ekstre" else "hesap hareketleri"
        months = f"; eksik aylar: {', '.join(month_name(m) for m in gap.months)}" if gap.months else ""
        found.append(
            Todo(
                key=f"gap:{gap.account}:{gap.last.isoformat()}:{','.join(gap.months)}",  # the bank's label: it lasts
                kind=TodoKind.MISSING_DOCUMENTS,
                title=names.get(gap.id, gap.account),
                detail=f"Son {what} {_day(gap.last)} tarihli, {gap.behind} gün önce{months}.",
                count=len(gap.months) or 1,
                amount=None,
                target=gap.account,
                link=Link(Screen.DOCUMENTS),
                actions=(TodoAction.UPLOAD, TodoAction.IGNORE),
                prompt="",
            )
        )
    return found


def _documents(db: Database) -> list[Todo]:
    found: list[Todo] = []
    for d in documents.every(db, [DocumentStatus.UNPROCESSED, DocumentStatus.UNREADABLE]):
        if d.status is DocumentStatus.UNPROCESSED and d.reason in _SETTLED:
            continue
        name = d.display_name or d.name
        word = "okunamadı" if d.status is DocumentStatus.UNREADABLE else "işlenmedi"
        found.append(
            Todo(
                key=f"document:{d.sha256}",
                kind=TodoKind.UNPROCESSED_DOCUMENT,
                title=name,
                detail=f"Belge {word}" + (f": {d.reason}." if d.reason else "."),
                count=1,
                amount=None,
                target=d.sha256,
                link=Link(Screen.DOCUMENT, d.sha256),
                actions=(TodoAction.OPEN, TodoAction.REPARSE, TodoAction.ASK_CLAUDE, TodoAction.IGNORE),
                prompt=(
                    f"İplikçi Nedim'de '{name}' belgesi {word}" + (f" ({d.reason})" if d.reason else "") + ". "
                    "Belgeye bakıp hangi okuyucunun onu okuyabileceğini ya da neden okunamadığını bulmama yardım et."
                ),
            )
        )
    return found


def _orphans(orphans: list[Annotation]) -> list[Todo]:
    found: list[Todo] = []
    for a in orphans:
        what = [part for part in (a.note, ", ".join(a.tags), a.category) if part]
        found.append(
            Todo(
                key=f"annotation:{a.fingerprint}",
                kind=TodoKind.ORPHAN_ANNOTATION,
                title=what[0] if what else a.fingerprint[:8],
                detail="Bu düzeltmenin bağlı olduğu satır artık hiçbir belgede yok; belge kaldırılmış ya da başka "
                "türlü okunmuş olabilir.",
                count=1,
                amount=None,
                target=a.fingerprint,
                link=None,
                actions=(TodoAction.ASK_CLAUDE, TodoAction.IGNORE),
                prompt=(
                    "İplikçi Nedim'de eşi bulunamayan bir düzeltme var ("
                    + "; ".join(what or [a.fingerprint[:8]])
                    + "). Hangi işleme ait olabileceğini bulmama yardım et."
                ),
            )
        )
    return found


def _unsplit(unsplit: list[Unsplit]) -> list[Todo]:
    found: list[Todo] = []
    for u in unsplit:
        t = u.row
        if t.kind in SPLITTABLE_KINDS:
            why = "tutarı değiştiği için bir parçası sıfıra indi"
        else:
            why = f"türü artık “{KIND[t.kind]}” ve bu tür bölünmüyor"
        name = t.merchant or t.counterparty or t.description
        found.append(
            Todo(
                key=f"split:{t.fingerprint}",
                kind=TodoKind.SPLIT_DROPPED,
                title=name,
                detail=f"{_day(t.date)} günlü {_tl(t.amount)} tutarındaki satırı {u.parts} parçaya bölmüştünüz; {why}. "
                "Satır bütün olarak sayılıyor. Satırı açıp yeniden bölün ya da bölmeyi kaldırın.",
                count=1,
                amount=t.amount,
                target=t.fingerprint,
                link=Link(Screen.TRANSACTION, t.fingerprint),
                actions=(TodoAction.OPEN, TodoAction.IGNORE),
                prompt="",
            )
        )
    return found


def _alarms(db: Database) -> list[Todo]:
    """Format alarms of the readers as they are now: an alarm an older version raised was answered by the new one."""
    raised: defaultdict[str, set[str]] = defaultdict(set)
    for row in db.rows(
        "SELECT target, json_extract(detail, '$.parser') AS parser, json_extract(detail, '$.version') AS version "
        "FROM events WHERE kind = ?",
        (FORMAT_ALARM,),
    ):
        reader = registry.find(str(row["parser"] or ""))
        if reader is not None and str(row["version"]) == registry.version_of(reader):
            raised[reader.id].add(str(row["target"]))
    found: list[Todo] = []
    for parser, shas in raised.items():
        reader = registry.find(parser)
        name = reader.name if reader else parser
        found.append(
            Todo(
                key=f"alarm:{parser}:{registry.version_of(reader) if reader else ''}",
                kind=TodoKind.FORMAT_ALARM,
                title=name,
                detail=f"{len(shas)} belgede okuyucu bankanın biçimini tanımadı ya da okuduğu ekstre doğrulanmadı; "
                "banka biçimini değiştirmiş olabilir.",
                count=len(shas),
                amount=None,
                target=parser,
                link=Link(Screen.SYSTEM),
                actions=(TodoAction.OPEN, TodoAction.ASK_CLAUDE, TodoAction.IGNORE),
                prompt=(
                    f"İplikçi Nedim'de '{name}' okuyucusu {len(shas)} belgede biçim alarmı verdi. Belgelere bakıp "
                    "bankanın biçiminde neyin değiştiğini bulmama yardım et."
                ),
            )
        )
    return found


def _ignored(db: Database) -> dict[str, str]:
    found = feed_state.load(db, IGNORED)
    return {str(k): str(v) for k, v in cast(dict[str, Any], found).items()} if isinstance(found, dict) else {}


def items(ws: Workspace, analysis: Analysis, today: date, with_ignored: bool = False) -> list[Todo]:
    """The to-do list, by kind in F19's order; what the user took off is left out unless with_ignored."""
    ds = analysis.dataset
    names = account_labels(analysis)  # as the screens name the accounts: the user's names first
    with ws.db() as db:
        stored = _documents(db) + _alarms(db)
        ignored = _ignored(db)
    found = (
        _uncategorized(ds)
        + _evidence(ds, names)
        + _invoices(ds)
        + _statements(ds, names)
        + _gaps(ds, today, names)
        + stored
        + _orphans(analysis.orphans)
        + _unsplit(analysis.unsplit)
    )
    found.sort(key=lambda t: _KIND_ORDER.index(t.kind))  # stable: each kind keeps its own order
    return [replace(t, ignored=True) if t.key in ignored else t for t in found if with_ignored or t.key not in ignored]


def counts(ws: Workspace, analysis: Analysis, today: date) -> dict[TodoKind, int]:
    """How many items of each kind are on the list (the dashboard's number, F06)."""
    found: dict[TodoKind, int] = dict.fromkeys(TodoKind, 0)
    for t in items(ws, analysis, today):
        found[t.kind] += 1
    return found


def ignore(ws: Workspace, key: str, on: bool, actor: Actor) -> None:
    """Take an item off the list (on), or put it back."""
    with ws.db() as db, db.transaction():
        ignored = _ignored(db)
        if on:
            ignored[key] = datetime.now(UTC).isoformat(timespec="seconds")
        else:
            ignored.pop(key, None)
        feed_state.save(db, IGNORED, ignored)
        audit.record(db, actor, TODO_IGNORED if on else "todo.restored", key)
