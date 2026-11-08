"""Taking documents into the vault (ADR-0003, architecture §7): from the inbox, from paths the user names,
from e-mail.

A plan comes first and touches nothing: every candidate is read in memory and gets a verdict. Applying it
keeps the new documents in the vault with their readings, notes a known document's new arrival as another
source, and never keeps a company document. Files in the inbox leave it once their bytes are safe: a kept or
known document moves into the vault; a company document, a file that is no document and an emptied archive go
to the system Trash. Paths outside the inbox are only read, never moved.
"""

import email
import os
import secrets
import shutil
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from ..domain.codes import Actor, DocumentKind, DocumentStatus, SourceKind
from ..domain.models import ParseResult
from ..domain.text import nfc
from ..ingest import archives
from ..ingest.archives import (
    DOCUMENT_EXTENSIONS,
    HEAD_BYTES,
    UnreadableArchive,
    from_mbox,
    from_zip,
    is_mbox,
    may_be_document,
    sniffed_extension,
)
from ..storage import audit, documents, events, jobs, readings
from ..storage.db import Database
from ..storage.documents import Source
from ..vault import trash
from ..vault.store import sha256_of
from . import kinds, reading
from .uploads import UPLOADS, file_sha256, inbox_files
from .workspace import StalePlan, Workspace

_IMPORT_LIMIT = (2000, 2 << 30)  # files and bytes one plan may read into memory


class Verdict(StrEnum):
    """What applying a plan does with a candidate."""

    STORE = "store"  # a new document: kept with its reading (processed, unprocessed or unreadable)
    KNOWN = "known"  # the vault has these bytes: the arrival is noted as another source
    BUSINESS = "business"  # a company document: never kept
    NOT_DOCUMENT = "not_document"  # a file in the inbox that is no document
    ARCHIVE = "archive"  # a zip or mbox in the inbox: its documents are planned one by one


# Another file of a statement or receipt the vault holds: kept too (K11), one in the ledger.
COPY = "copy"

# What a plan item is called, by its action (a document's status when it is kept, else the verdict).
ACTION_LABELS = {
    DocumentStatus.PROCESSED: "arşive alınacak",
    COPY: "aynı belgenin başka bir dosyası — arşive alınacak, defterde birleşir",
    DocumentStatus.UNREADABLE: "okunamadı — arşive alınacak, elle bakın",
    DocumentStatus.UNPROCESSED: "para hareketi yok — arşive alınacak",
    Verdict.KNOWN: "zaten arşivde",
    Verdict.BUSINESS: "şirket belgesi — alınmayacak",
    Verdict.NOT_DOCUMENT: "belge değil — çöp kutusuna",
    Verdict.ARCHIVE: "arşiv dosyası — içindekiler alınacak, kendisi çöp kutusuna",
}

# What became of a plan item once the plan was applied, by its action: the Telegram bot's answer (ADR-0021).
ACTION_DONE = {
    DocumentStatus.PROCESSED: "arşive alındı",
    COPY: "aynı belgenin başka bir dosyası; arşive alındı, defterde birleşir",
    DocumentStatus.UNREADABLE: "okunamadı; arşive alındı, Belgeler ekranında elle bakın",
    DocumentStatus.UNPROCESSED: "para hareketi yok; arşive alındı",
    Verdict.KNOWN: "zaten arşivde",
    Verdict.BUSINESS: "şirket belgesi; alınmadı",
    Verdict.NOT_DOCUMENT: "belge değil; alınmadı",
    Verdict.ARCHIVE: "arşiv dosyası; içindekiler alındı",
}


@dataclass
class Candidate:
    name: str
    sha256: str
    source: Source
    data: bytes = b""
    path: Path | None = None  # a file in the inbox, which leaves it once the plan is applied
    container: Path | None = None  # the inbox archive it came out of
    verdict: Verdict = Verdict.STORE
    outcome: reading.Outcome | None = None
    new_source: bool = True  # KNOWN: whether this arrival is not recorded yet
    copy_of: str | None = None  # STORE: the kept document holding the same statement or receipt
    parent: str = ""  # the e-mail it was attached to (its sha256)

    @property
    def status(self) -> DocumentStatus | None:
        return self.outcome.status if self.outcome and self.verdict is Verdict.STORE else None

    @property
    def action(self) -> str:
        """The item's code for the interfaces: the status of a document to keep (COPY for another file of a kept
        statement), else the verdict."""
        if self.copy_of is not None and self.status is DocumentStatus.PROCESSED:
            return COPY
        return str(self.status or self.verdict)

    @property
    def result(self) -> ParseResult | None:
        return self.outcome.result if self.outcome else None

    @property
    def reason(self) -> str:
        return self.outcome.reason if self.outcome else ""

    @property
    def changes_something(self) -> bool:
        return self.verdict is not Verdict.KNOWN or self.new_source or self.path is not None


@dataclass
class Plan:
    id: str
    items: list[Candidate]
    files: dict[Path, str] = field(default_factory=dict[Path, str])  # inbox files it moves, by sha256 when planned
    made: datetime = field(default_factory=datetime.now)

    @property
    def changes(self) -> list[Candidate]:
        return [c for c in self.items if c.changes_something]

    @property
    def documents(self) -> list[Candidate]:
        return [c for c in self.items if c.verdict in (Verdict.STORE, Verdict.KNOWN, Verdict.BUSINESS)]


@dataclass
class Applied:
    counts: Counter[str]  # by action
    items: list[Candidate]
    trash: Path | None  # where the files set aside went (still recoverable)

    @property
    def stored(self) -> list[Candidate]:
        return [c for c in self.items if c.verdict is Verdict.STORE]


@dataclass(frozen=True)
class Incoming:
    """A document held in memory (an e-mail attachment), with where it came from."""

    name: str
    data: bytes
    source: Source


# --- planning ------------------------------------------------------------------------------------------


def _expand(name: str, data: bytes, source: Source, path: Path | None) -> Iterable[Candidate]:
    """The documents in one file: itself, or the members of a zip (nested ones too); an e-mail is a document and so
    is each of its attachments, with the e-mail as their parent. A zip that cannot be opened is itself a document,
    kept as unreadable for a manual look."""
    if name.lower().endswith(".eml"):
        yield from _message(name, data, source, path)
    elif name.lower().endswith(".zip"):
        try:
            members = from_zip(data, source.origin or name)
        except UnreadableArchive:
            yield Candidate(name, sha256_of(data), source, data, path)
            return
        for member, origin, blob in members:
            inner = Source(
                source.kind, member, origin, source.message_id, source.sender, source.subject, source.sent_at
            )
            for c in _expand(member, blob, inner, None):
                c.container = path
                yield c
        if path is not None:
            yield Candidate(name, sha256_of(data), source, b"", path, verdict=Verdict.ARCHIVE)
    elif os.path.splitext(name)[1].lower() in DOCUMENT_EXTENSIONS:
        yield Candidate(name, sha256_of(data), source, data, path)


def _message(name: str, data: bytes, source: Source, path: Path | None) -> Iterable[Candidate]:
    msg = email.message_from_bytes(data)
    if not source.message_id:  # a file the user brought: what the e-mail says of itself
        source = replace(source, **archives.message_fields(msg))
    message = Candidate(name, sha256_of(data), source, data, path)
    yield message
    for attachment, blob in archives.attachments(msg):
        inner = replace(source, original=attachment, origin=f"{source.origin or name} › {attachment}")
        for c in _expand(attachment, blob, inner, None):
            c.parent = c.parent or message.sha256
            c.container = path
            yield c


def _walk(path: Path, kind: SourceKind, root: Path | None, in_inbox: bool) -> Iterable[Candidate]:
    """The candidates under path (a file or a folder); hidden files and folders are left out."""
    if path.is_dir():
        for child in sorted(path.iterdir()):
            if not child.name.startswith("."):
                yield from _walk(child, kind, root, in_inbox)
        return
    if not path.is_file():
        return
    shown = str(path.relative_to(root)) if root and path.is_relative_to(root) else str(path)
    loose = path if in_inbox else None
    if is_mbox(path):
        for name, origin, data in from_mbox(path):
            for c in _expand(name, data, Source(kind, name, origin), None):
                c.container = loose
                yield c
        if loose is not None:
            yield Candidate(
                nfc(path.name), "", Source(kind, nfc(path.name), shown), b"", loose, verdict=Verdict.ARCHIVE
            )
        return
    name = nfc(path.name)
    readable = _readable_name(path, name)
    if readable is not None:
        yield from _expand(readable, path.read_bytes(), Source(kind, name, nfc(shown)), loose)
    elif loose is not None:
        yield Candidate(
            nfc(path.name), "", Source(kind, nfc(path.name), shown), b"", loose, verdict=Verdict.NOT_DOCUMENT
        )


def _readable_name(path: Path, name: str) -> str | None:
    """The name a file is read by: its own when its extension is a document's; else its own with the extension its
    bytes say (a bank's download without one, or with a wrong one); None for a file that is no document. What the
    document is comes from its content alone, never its name."""
    if path.suffix.lower() in DOCUMENT_EXTENSIONS or path.suffix.lower() in (".zip", ".eml"):
        return name
    with path.open("rb") as f:
        head = f.read(HEAD_BYTES)
    if not may_be_document(head):
        return None
    found = sniffed_extension(path.read_bytes())
    return f"{name}{found}" if found else None


def _decide(db: Database, items: list[Candidate]) -> None:
    """Read every new document and give each candidate its verdict; the same bytes twice in one plan are one
    document with two arrivals (or one company document, twice refused). Another file of a statement or receipt
    kept already, or earlier in the plan, is named as its copy."""
    first: dict[str, Candidate] = {}
    statements: dict[readings.CopyKey, str] = {}
    for c in items:
        if c.verdict in (Verdict.ARCHIVE, Verdict.NOT_DOCUMENT):
            continue
        earlier = first.get(c.sha256)
        if earlier is not None and earlier.verdict is Verdict.BUSINESS:
            c.verdict, c.outcome = Verdict.BUSINESS, earlier.outcome
            continue
        if earlier is not None or documents.get(db, c.sha256) is not None:
            c.verdict = Verdict.KNOWN
            c.new_source = earlier is not None or not documents.has_source(db, c.sha256, c.source)
            continue
        first[c.sha256] = c
        c.outcome = reading.read(c.name, c.data, c.sha256, c.source.origin)
        if c.outcome.business:
            c.verdict = Verdict.BUSINESS
        elif c.outcome.result is not None:
            keys = readings.copy_keys(c.outcome.result)
            c.copy_of = next((statements[k] for k in keys if k in statements), None) or readings.kept_copy(db, keys)
            for k in keys:
                statements.setdefault(k, c.name)


def _check_size(paths: Sequence[Path]) -> None:
    count = size = 0
    for root in paths:
        no_dirs: list[str] = []
        walk = os.walk(root) if root.is_dir() else [(str(root.parent), no_dirs, [root.name])]
        for folder, dirs, files in walk:
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                if not name.startswith("."):
                    count += 1
                    size += os.stat(os.path.join(folder, name)).st_size
    if count > _IMPORT_LIMIT[0] or size > _IMPORT_LIMIT[1]:
        raise ValueError(
            f"{count} dosya, {size >> 20} MB: tek seferde okunamayacak kadar çok; daha dar bir klasör verin"
        )


def _plan(ws: Workspace, items: list[Candidate]) -> Plan:
    with ws.db() as db:
        _decide(db, items)
    files = {c.path: (file_sha256(c.path) if c.sha256 else "") for c in items if c.path is not None}
    return Plan(secrets.token_hex(8), items, files)


def plan_inbox(ws: Workspace) -> Plan:
    """What taking in the inbox would do, touching nothing."""
    files = inbox_files(ws)
    _check_size(files)
    return _plan(ws, [c for f in files for c in _walk(f, SourceKind.INBOX, ws.inbox, in_inbox=True)])


def plan_paths(ws: Workspace, paths: Sequence[str | Path]) -> Plan:
    """What taking in the documents under paths would do; the files themselves are never moved."""
    resolved: list[Path] = []
    for p in paths:
        path = Path(p).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"bulunamadı: {path}")
        if path.is_relative_to(ws.home.resolve()):
            raise ValueError(f"{path} veri klasörünün içinde; gelen klasöründekiler için planı gelen kutusundan alın")
        resolved.append(path)
    _check_size(resolved)
    return _plan(ws, [c for path in resolved for c in _walk(path, SourceKind.IMPORT, None, in_inbox=False)])


def plan_upload(ws: Workspace, folder: Path, kind: SourceKind = SourceKind.UPLOAD) -> Plan:
    """What taking in a batch of uploads would do; its files, copies in the staging area, leave it once the plan is
    applied (ADR-0007). kind: how they came, through the interface or to the Telegram bot (ADR-0021)."""
    files = [
        p
        for p in sorted(folder.rglob("*"))
        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(folder).parts)
    ]
    _check_size(files)
    return _plan(ws, [c for f in files for c in _walk(f, kind, folder, in_inbox=True)])


def plan_documents(ws: Workspace, incoming: Iterable[Incoming]) -> Plan:
    """What taking in documents held in memory would do (e-mail attachments; their zips are opened)."""
    return _plan(ws, [c for doc in incoming for c in _expand(nfc(doc.name), doc.data, doc.source, None)])


# --- applying ------------------------------------------------------------------------------------------


def apply(ws: Workspace, plan: Plan, actor: Actor = Actor.USER) -> Applied:
    """Carry out exactly the plan that was shown; refuse if one of its inbox files changed since."""
    if ws.read_only:
        raise PermissionError("bu çalışma alanı yalnızca okunur: belge alınamaz")
    for path, sha in plan.files.items():
        if not path.exists() or (sha and file_sha256(path) != sha):
            raise StalePlan(f"{path.name} plan hazırlandıktan sonra değişti; planı yeniden alın")
    counts: Counter[str] = Counter()
    leaving: list[Path] = []
    set_aside: list[Path] = []
    with ws.lock(), ws.db() as db:
        for c in plan.items:
            counts[c.action] += 1
            if c.verdict is Verdict.STORE:
                _store(ws, db, c, actor)
            elif c.verdict is Verdict.KNOWN:
                documents.add_source(db, c.sha256, c.source)
            elif c.verdict is Verdict.BUSINESS:
                audit.record(db, actor, "document.business", c.sha256, stage="ingest")
            if c.path is None:
                continue
            if c.verdict in (Verdict.STORE, Verdict.KNOWN) and ws.vault.has(c.sha256):
                leaving.append(c.path)
            elif c.verdict in (Verdict.BUSINESS, Verdict.NOT_DOCUMENT, Verdict.ARCHIVE):
                set_aside.append(c.path)
        for path in leaving:  # its bytes are in the vault now: the move is complete
            path.unlink(missing_ok=True)
        folder = _set_aside(ws, set_aside)
        if folder is not None:
            audit.record(db, actor, "inbox.set_aside", "", files=len(set_aside), trash=folder.name)
        if any(c.verdict is Verdict.STORE for c in plan.items):
            jobs.add(db, kinds.REFRESH)  # the service makes the analysis again and tells what changed
    _remove_empty_folders(ws.inbox)
    _remove_empty_folders(ws.layout.staging / UPLOADS, keep_root=False)
    return Applied(counts, plan.items, folder)


def _store(ws: Workspace, db: Database, c: Candidate, actor: Actor) -> None:
    assert c.outcome is not None
    if documents.get(db, c.sha256) is not None:  # another process kept it after the plan was made
        documents.add_source(db, c.sha256, c.source)
        return
    ws.vault.put(c.data)
    with db.transaction():
        documents.add(db, c.sha256, c.name, len(c.data), parent=c.parent)
        documents.add_source(db, c.sha256, c.source)
        events.record(db, "document.received", c.sha256, source=str(c.source.kind))
        reading.record(db, c.sha256, c.name, c.outcome)
        audit.record(db, actor, "document.stored", c.sha256, status=str(c.outcome.status))


def _set_aside(ws: Workspace, paths: list[Path]) -> Path | None:
    """Move inbox files to one dated folder in the system Trash, keeping their place in the inbox."""
    moving = [p for p in paths if p.exists()]
    if not moving:
        return None
    folder = trash.default_folder(ws.home)
    for path in moving:
        dest = folder / _within(ws, path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(path, _free(dest))
    return trash.move_to_system_trash(folder)


def _within(ws: Workspace, path: Path) -> Path:
    """A file's place in the inbox or in the upload area, kept when it is set aside."""
    for root in (ws.inbox, ws.layout.staging / UPLOADS):
        if path.is_relative_to(root):
            return path.relative_to(root)
    return Path(path.name)


def _free(path: Path) -> Path:
    """path, or 'name (2).ext' and so on: never overwrite."""
    candidate, n = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    return candidate


def _remove_empty_folders(inbox: Path, keep_root: bool = True) -> None:
    """Folders the move emptied, below the inbox (the inbox itself stays) or the upload area."""
    if not inbox.is_dir():
        return
    for folder, dirs, files in os.walk(inbox, topdown=False):
        here = Path(folder)
        if here == inbox and keep_root:
            continue
        leftovers = [f for f in files if f != ".DS_Store"]
        if not leftovers and not any((here / d).exists() for d in dirs):
            for f in files:
                (here / f).unlink()  # only .DS_Store: Finder's own file, not a document
            here.rmdir()


# --- for the interfaces ----------------------------------------------------------------------------------


def describe(c: Candidate, ws: Workspace) -> dict[str, object]:
    """A plan item for the interface and the MCP client: what it is and what happens to it."""
    where = c.source.origin or c.name
    source = f"{where} › {c.name}" if c.container is not None or c.source.kind is SourceKind.EMAIL else where
    out: dict[str, object] = {
        "action": c.action,
        "label": ACTION_LABELS.get(c.action, c.action),
        "name": c.name,
        "source": source,
        "reason": c.reason,
        "copyOf": c.copy_of,
        "target": c.outcome.reading(c.name).display_name if c.outcome and c.outcome.result else None,
        "fromInbox": c.path is not None or c.container is not None,
    }
    result = c.result
    if result and result.statements:
        s = result.statements[0]
        account = next((a for a in result.accounts if a.id == s.account), None)
        out["document"] = {
            "kind": "hesap" if s.is_account else "ekstre",
            "account": account.label if account else s.account,
            "start": s.start.isoformat() if s.start else None,
            "end": s.cut_date.isoformat(),
            "rows": sum(len(x.transactions) for x in result.statements),
            "verified": s.verified,
            "check": (
                "bakiyeyi denetleyecek kadar satır yok"
                if s.is_account and not s.checks_total
                else f"bakiye {s.checks_ok}/{s.checks_total} satır tutarlı"
                if s.is_account
                else "bankanın toplamıyla tutarlı"
                if s.verified
                else f"fark {s.difference}"
            ),
        }
    elif result and result.invoices and not result.transactions:
        invoice = result.invoices[0]
        out["document"] = {
            "kind": "fatura",
            "account": invoice.seller,
            "start": None,
            "end": invoice.issued.isoformat(),
            "rows": len(result.invoices),
            "verified": None,
            "check": result.title or "",
        }
    elif result and result.transactions:
        t = result.transactions[0]
        account = next((a for a in result.accounts if a.id == t.account), None)
        out["document"] = {
            "kind": "bildirim" if c.outcome and c.outcome.kind is DocumentKind.NOTICE else "dekont",
            "account": account.label if account else t.account,
            "start": None,
            "end": t.date.isoformat(),
            "rows": len(result.transactions),
            "verified": None,
            "check": result.title or "",
        }
    return out


def kind_counts(items: Iterable[Candidate]) -> Counter[DocumentKind]:
    """How many kept documents of each kind."""
    return Counter(k for c in items if c.verdict is Verdict.STORE and c.outcome and (k := c.outcome.kind))
