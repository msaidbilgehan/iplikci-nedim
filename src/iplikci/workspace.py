"""The user's workspace and the operations every entry point shares.

The command line, the web panel, the MCP server and the automatic run all come through here, so a
document is parsed, filed and reported the same way whichever door it came in by: the report runs
sources.collect -> pipeline.parse_all -> analysis.build -> insights.interpret, filing runs the
organizer (duzenle). New documents land in the inbox ("Gelen Belgeler") first; nothing moves until a
plan was shown (panel, MCP) or the user turned on the automatic run.
"""

import hashlib
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import tomllib
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from . import duzenle, month_end
from .analysis import CONFIRMED, NOT_ON_STATEMENT, PROVISIONAL, Dataset
from .insights import FULL, Insights, interpret, month_of, shift
from .parsers.common import set_business_names
from .pipeline import run
from .report import build_payload, write_csv, write_html, write_xlsx
from .sources import DOCUMENT_EXTENSIONS
from .textutil import nfc

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

SETTINGS = "ayarlar.toml"
HOME_ENV = "IPLIKCI_HOME"
DEFAULT_INBOX = "../Gelen Belgeler"
DEFAULT_PORT = 8643
UPLOAD_EXTENSIONS = frozenset(DOCUMENT_EXTENSIONS | {".zip", ".mbox"})
MAX_UPLOAD_BYTES = 1 << 30  # an e-mail archive can be large; a statement is a few hundred KB
PARTIAL_PREFIX = ".yukleniyor-"  # hidden: no reader picks up a file that is still being written
_LOCK_NAME = ".kilit"
_MAX_FOLDERS = 3  # folder levels kept from an uploaded tree
_IMPORT_LIMIT = (2000, 2 << 30)  # files and bytes one import may read into memory


class Busy(Exception):
    """Another process is filing or reading the documents right now."""


class StalePlan(Exception):
    """A file of the plan changed after it was shown: show a fresh plan instead of applying."""


def _try_lock(f) -> bool:
    if fcntl:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True
    f.seek(0)  # Windows locks bytes from the file position: always the first one
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:  # held by another process
        return False
    return True


def _unlock(f) -> None:
    if fcntl:
        fcntl.flock(f, fcntl.LOCK_UN)
    else:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def output_lock(
    output: Path,
    timeout: float = 120.0,
    name: str = _LOCK_NAME,
    busy: str = "başka bir işlem belgeleri işliyor; biraz sonra yeniden deneyin",
):
    """One reader or writer of the documents and the outputs at a time, across the panel, the MCP
    server, the automatic run and the command line (they share the parse cache and the outputs).
    Another name is another lock (the e-mail fetch has its own)."""
    output.mkdir(parents=True, exist_ok=True)
    with open(output / name, "a+") as f:
        deadline = time.monotonic() + timeout
        while not _try_lock(f):
            if time.monotonic() > deadline:
                raise Busy(busy)
            time.sleep(0.2)
        try:
            yield
        finally:
            _unlock(f)


def home() -> Path:
    """The folder of ayarlar.toml: IPLIKCI_HOME, else the working folder (as in the MVP). The platform's
    data folder becomes the default with the settings module (ADR-0002)."""
    value = os.environ.get(HOME_ENV, "").strip()
    return Path(value).expanduser() if value else Path.cwd()


def business_names(settings: dict) -> list[str]:
    """The user's company names (identity.business_names): their documents are out of scope. A wrong
    value is an error rather than an empty list, so company documents never slip into the analysis."""
    identity = settings.get("identity", {})
    names = identity.get("business_names", []) if isinstance(identity, dict) else None
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ValueError(
            f'{SETTINGS}: [identity] business_names bir ad listesi olmalı, ör. business_names = ["ŞİRKET ADI"]'
        )
    return names


@dataclass(frozen=True)
class Workspace:
    base: Path  # folder of ayarlar.toml; relative settings are relative to it
    settings: dict
    sources: tuple[Path, ...]  # `kaynaklar`
    documents: Path  # `belge_klasoru`: Bankalar/<Banka>/<Hesap>/
    inbox: Path  # `gelen_klasoru`: where new documents wait to be filed
    output: Path  # `cikti`
    rules: Path  # `kurallar`
    port: int = DEFAULT_PORT  # `panel_portu`

    @classmethod
    def load(cls, base: Path | None = None) -> "Workspace":
        base = (base or home()).resolve()
        path = base / SETTINGS
        settings: dict = {}
        if path.exists():
            with path.open("rb") as f:
                settings = tomllib.load(f)
        if not settings.get("belge_klasoru"):
            raise ValueError(f"{path} içinde 'belge_klasoru' yok: belgelerin toplandığı klasör gerekli")
        set_business_names(business_names(settings))
        at = lambda value: (base / value).resolve()
        documents = at(settings["belge_klasoru"])
        return cls(
            base=base,
            settings=settings,
            sources=tuple(at(p) for p in settings.get("kaynaklar", [])) or (documents,),
            documents=documents,
            inbox=at(settings.get("gelen_klasoru", DEFAULT_INBOX)),
            output=at(settings.get("cikti", "cikti")),
            rules=at(settings.get("kurallar", "kategoriler.yaml")),
            port=int(settings.get("panel_portu", DEFAULT_PORT)),
        )

    def report_sources(self) -> list[Path]:
        """`kaynaklar`, plus the inbox: a document waiting to be filed already counts in the report."""
        if self.inbox.is_dir() and not any(self.inbox.is_relative_to(s) for s in self.sources):
            return [*self.sources, self.inbox]
        return list(self.sources)

    def lock(self, timeout: float = 120.0):
        return output_lock(self.output, timeout)

    def signature(self) -> tuple:
        """Changes whenever a document, the inbox or the rules change, i.e. when an analysis is stale."""
        entries = []
        for root in self.report_sources():
            if root.is_file():
                st = root.stat()
                entries.append((str(root), st.st_size, st.st_mtime_ns))
            for folder, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for name in files:
                    if not name.startswith("."):
                        try:
                            st = os.stat(os.path.join(folder, name))
                        except FileNotFoundError:  # moved away while we looked
                            continue
                        entries.append((os.path.join(folder, name), st.st_size, st.st_mtime_ns))
        rules = self.rules.stat() if self.rules.exists() else None
        return tuple(sorted(entries)), rules and (rules.st_size, rules.st_mtime_ns)


# --- analysis ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Outputs:
    html: Path
    csv: Path
    xlsx: Path
    month_end: Path  # folder of the month-end pages; index.html lists them


def write_outputs(output: Path, ds: Dataset, ins: Insights, payload: dict, months: list[month_end.MonthEnd]) -> Outputs:
    """The report, the CSV and Excel exports and the month-end pages, side by side in output."""
    outputs = Outputs(
        output / "gider_raporu.html", output / "islemler.csv", output / "islemler.xlsx", output / month_end.FOLDER
    )
    write_html(payload, outputs.html)
    write_csv(ds, outputs.csv)
    write_xlsx(ds, outputs.xlsx, ins, months)
    month_end.write_all(months, ds, outputs.month_end)
    return outputs


@dataclass
class Analysis:
    dataset: Dataset
    stats: dict
    insights: Insights
    payload: dict
    signature: tuple
    made: datetime
    outputs: Outputs | None = None
    months: list[month_end.MonthEnd] = field(default_factory=list)  # month-end closing, oldest first


def analyze(
    ws: Workspace, progress=None, write: bool = False, use_cache: bool = True, today: date | None = None
) -> Analysis:
    """Read every document and interpret it; write=True also writes the report, CSV, Excel and the
    month-end pages (today decides which month is the current one)."""
    sig = ws.signature()
    with ws.lock():
        ds, stats = run(ws.report_sources(), ws.rules, ws.output if use_cache else None, progress, ws.settings)
        ins = interpret(ds)
        months = month_end.build(ds, ins, today)
        payload = build_payload(ds, stats, ins, months)
        outputs = write_outputs(ws.output, ds, ins, payload, months) if write else None
    return Analysis(ds, stats, ins, payload, sig, datetime.now(), outputs, months)


class Current:
    """The latest analysis, redone when a document, the inbox or the rules changed since."""

    def __init__(self, ws: Workspace, write: bool):
        self.ws = ws
        self.write = write
        self._lock = threading.Lock()
        self._analysis: Analysis | None = None

    def get(self, progress=None) -> Analysis:
        with self._lock:
            if self._analysis is None or self._analysis.signature != self.ws.signature():
                self._analysis = analyze(self.ws, progress, write=self.write)
            return self._analysis

    def refresh(self, write: bool = True) -> Analysis:
        with self._lock:
            self._analysis = analyze(self.ws, write=write)
            return self._analysis


def summary(a: Analysis) -> dict:
    """What a run read and how much of it checked out: the numbers the CLI prints."""
    ds = a.dataset
    statuses = [d.status for d in ds.documents]
    cards = [s for s in ds.statements if not s.is_account]
    lists = [s for s in ds.statements if s.is_account]
    unverified = [
        {
            "account": ds.accounts[s.account].label,
            "cut": s.cut_date.isoformat(),
            "file": s.source,
            "detail": f"bakiye {s.checks_ok}/{s.checks_total}" if s.is_account else f"fark {s.difference}",
        }
        for s in ds.statements
        if not s.verified
    ]
    return {
        "documents": a.stats["documents"],
        "duplicates": a.stats["duplicates"],
        "cardStatements": len(cards),
        "cardStatementsVerified": sum(s.verified for s in cards),
        "accountStatements": len(lists),
        "accountStatementsVerified": sum(s.verified for s in lists),
        "receipts": statuses.count("dekont"),
        "business": statuses.count("is"),
        "skipped": statuses.count("atlandi"),
        "errors": statuses.count("hata"),
        "unverified": unverified,
        "unreadable": [{"name": d.name, "detail": d.detail} for d in ds.documents if d.status == "hata"],
        # Receipt rows: waiting for their statement (counted), found on it, or covered by one that does not show them.
        "receiptRows": {
            "provisional": sum(line.status == PROVISIONAL for line in ds.receipts),
            "confirmed": sum(line.status == CONFIRMED for line in ds.receipts),
            "notOnStatement": sum(line.status == NOT_ON_STATEMENT for line in ds.receipts),
        },
        "warnings": ds.warnings,
        "transactions": len(ds.transactions),
        "period": (
            [ds.transactions[0].date.isoformat(), ds.transactions[-1].date.isoformat()] if ds.transactions else None
        ),
    }


# --- what documents are missing ------------------------------------------------------------------


@dataclass(frozen=True)
class Gap:
    """An account whose statements stop early or skip a month: what to download next."""

    account: str
    kind: str  # "ekstre" (card statements) or "hesap" (account movement lists)
    last: date  # newest statement end of the account
    behind: int  # days from that to today
    months: tuple[str, ...]  # months inside the account's statements they cover only partly or not


_CLOSED_DAYS = 180  # statements that stopped this long before the other accounts': probably closed
_BEHIND_DAYS = 35  # a card prints a statement a month


def document_gaps(ds: Dataset, today: date | None = None, horizon: int = 12) -> list[Gap]:
    today = today or date.today()
    seen: dict[str, date] = {}
    kind: dict[str, str] = {}
    for s in ds.statements:
        seen[s.account] = max(seen.get(s.account, s.cut_date), s.cut_date)
        kind[s.account] = "hesap" if s.is_account else "ekstre"
    if not seen:
        return []
    newest = max(seen.values())
    oldest = shift(month_of(newest), -horizon)
    gaps = []
    for account, last in seen.items():
        if (newest - last).days > _CLOSED_DAYS:
            continue
        cov = ds.coverage.get(account, {})
        months = sorted(cov)
        inner = months[1:-1]  # the first and the last month are partial by nature
        holes = tuple(m for m in inner if m >= oldest and cov[m] < FULL)
        behind = (today - last).days
        if holes or behind > _BEHIND_DAYS:
            gaps.append(Gap(ds.accounts[account].label, kind[account], last, behind, holes))
    return sorted(gaps, key=lambda g: (-g.behind, g.account))


# --- the inbox: uploads, plans, filing -------------------------------------------------------------


@dataclass(frozen=True)
class Upload:
    status: str  # "eklendi", "zaten-var" (same bytes already waiting), "reddedildi"
    name: str  # path inside the inbox, or the name that was refused
    reason: str = ""


_UNSAFE = re.compile(r"[\x00-\x1f\x7f:]")
_upload_lock = threading.Lock()
_hashes: dict[tuple, str] = {}  # (path, size, mtime) -> sha256 of inbox files


def safe_upload_path(name: str) -> PurePosixPath | None:
    """An uploaded file's relative path made safe: no "..", no absolute path, no control characters,
    at most a few folders; None for a hidden file or when nothing usable is left."""
    parts = []
    for part in PurePosixPath(nfc(name).replace("\\", "/")).parts:
        part = _UNSAFE.sub("", part).strip()
        if part in ("", "/", ".", ".."):
            continue
        if part.startswith("."):
            return None  # .DS_Store and friends are never documents
        parts.append(part[:150])
    if not parts:
        return None
    return PurePosixPath(*parts[:-1][-_MAX_FOLDERS:], parts[-1])


def inbox_files(ws: Workspace) -> list[Path]:
    """Files waiting in the inbox (hidden files and folders, i.e. unfinished uploads, left out)."""
    if not ws.inbox.is_dir():
        return []
    found = []
    for folder, dirs, files in os.walk(ws.inbox):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        found += [Path(folder) / f for f in sorted(files) if not f.startswith(".")]
    return found


def _sha256(path: Path) -> str:
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime_ns)
    if len(_hashes) > 10_000:
        _hashes.clear()
    if key not in _hashes:
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        _hashes[key] = digest.hexdigest()
    return _hashes[key]


def _place(src: Path, dest: Path) -> None:
    """Make src's bytes appear under dest; FileExistsError if dest exists (nothing is replaced)."""
    try:
        os.link(src, dest)
        return
    except FileExistsError:
        raise
    except OSError:  # a file system without hard links (FAT, exFAT, some network shares): copy
        pass
    with open(dest, "xb") as out:
        try:
            with open(src, "rb") as f:
                shutil.copyfileobj(f, out)
        except BaseException:
            out.close()
            dest.unlink(missing_ok=True)  # our half-written copy, never someone's file
            raise


def _link_free(src: Path, dest: Path) -> Path:
    """Give src the name dest, or "dest (2)" and so on: never replaces an existing file."""
    candidate, n = dest, 2
    while True:
        try:
            _place(src, candidate)
            return candidate
        except FileExistsError:
            candidate = dest.with_name(f"{dest.stem} ({n}){dest.suffix}")
            n += 1


def save_upload(ws: Workspace, name: str, stream: BinaryIO, length: int) -> Upload:
    """Store one uploaded file in the inbox. It is written under a hidden name first and gets its
    real name only when complete, so a plan or the automatic run never sees half a file."""
    rel = safe_upload_path(name)
    if rel is None or rel.suffix.lower() not in UPLOAD_EXTENSIONS:
        kinds = ", ".join(sorted(e.lstrip(".").upper() for e in UPLOAD_EXTENSIONS))
        return Upload("reddedildi", name, f"desteklenmeyen dosya türü (kabul edilenler: {kinds})")
    if length > MAX_UPLOAD_BYTES:
        return Upload(
            "reddedildi",
            name,
            f"dosya {MAX_UPLOAD_BYTES >> 20} MB sınırından büyük; "
            f"büyük arşivleri doğrudan {ws.inbox.name} klasörüne kopyalayın",
        )
    ws.inbox.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=PARTIAL_PREFIX, dir=ws.inbox)
    tmp = Path(tmp_name)
    try:
        digest = hashlib.sha256()
        with os.fdopen(fd, "wb") as f:
            left = length
            while left > 0:
                chunk = stream.read(min(left, 1 << 20))
                if not chunk:
                    raise ConnectionError("yükleme yarıda kesildi")
                f.write(chunk)
                digest.update(chunk)
                left -= len(chunk)
        sha = digest.hexdigest()
        with _upload_lock:
            twin = next((p for p in inbox_files(ws) if _sha256(p) == sha), None)
            if twin:
                return Upload("zaten-var", str(twin.relative_to(ws.inbox)), "aynı dosya gelen kutusunda zaten var")
            dest = ws.inbox / rel
            existing = dest.parent
            while not existing.exists():
                existing = existing.parent
            if not existing.resolve().is_relative_to(ws.inbox.resolve()):  # a symlinked folder
                return Upload("reddedildi", name, "gelen kutusunun dışına yazılamaz")
            dest.parent.mkdir(parents=True, exist_ok=True)
            final = _link_free(tmp, dest)
        return Upload("eklendi", str(final.relative_to(ws.inbox)))
    finally:
        tmp.unlink(missing_ok=True)  # our own partial file, never a document


@dataclass
class Plan:
    id: str
    items: list[duzenle.Item]  # the organizer's whole plan
    made: datetime = field(default_factory=datetime.now)

    @property
    def changes(self) -> list[duzenle.Item]:
        return duzenle.changes(self.items)


def plan_inbox(ws: Workspace, progress=None) -> Plan:
    """What filing the inbox would do, touching nothing. The documents already filed take part, so a
    second copy of a statement is recognised as one."""
    with ws.lock():
        items = duzenle.plan([ws.documents, ws.inbox], ws.documents, ws.output, progress, inbox=ws.inbox)
    # A plan is kept until it is applied; only archive members it extracts still need their bytes.
    moving = {id(it) for it in duzenle.changes(items)}
    for it in items:
        if id(it) not in moving:
            it.data = b""
    return Plan(secrets.token_hex(8), items)


@dataclass
class Applied:
    counts: dict[str, int]
    items: list[duzenle.Item]
    trash: Path | None  # where the set-aside files went (still recoverable)
    log: Path | None


def apply(ws: Workspace, plan: Plan, trash: Path | None = None) -> Applied:
    """Carry out exactly the plan that was shown; refuse if one of its files changed since."""
    todo = plan.changes
    if not todo:
        return Applied({}, [], None, None)
    for it in todo:
        if it.path is not None and (not it.path.exists() or (it.sha256 and _sha256(it.path) != it.sha256)):
            raise StalePlan(f"{it.path.name} plan hazırlandıktan sonra değişti; planı yeniden alın")
    stamp = datetime.now().strftime("%Y-%m-%d %H.%M.%S")
    with ws.lock():
        folder = trash or duzenle.default_trash(ws.documents)
        log = ws.documents.parent / f"belge-duzenleme-kaydi {stamp}.csv"
        counts = duzenle.apply(todo, ws.documents, folder, log, keep=(ws.inbox, *ws.sources))
        if trash is None:
            folder = duzenle.move_to_system_trash(folder)
    ws.inbox.mkdir(parents=True, exist_ok=True)
    return Applied(counts, todo, folder if folder.exists() else None, log)


def _check_import_size(paths: list[Path]) -> None:
    count = size = 0
    wanted = UPLOAD_EXTENSIONS
    for root in paths:
        walk = os.walk(root) if root.is_dir() else [(str(root.parent), [], [root.name])]
        for folder, dirs, files in walk:
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for name in files:
                if name.startswith(".") or os.path.splitext(name)[1].lower() not in wanted:
                    continue
                count += 1
                size += os.stat(os.path.join(folder, name)).st_size
    if count > _IMPORT_LIMIT[0] or size > _IMPORT_LIMIT[1]:
        raise ValueError(
            f"{count} dosya, {size >> 20} MB: tek seferde okunamayacak kadar çok; daha dar bir klasör verin"
        )


def import_paths(ws: Workspace, paths: list[str]) -> tuple[list[duzenle.Item], list[Path]]:
    """Copy the bank documents under paths into the inbox, leaving the originals alone: the ones the
    organizer would file and the unreadable ones (for a manual look). Copies of documents already
    filed, company documents and files that are not statements are only reported.
    Returns the documents found with the organizer's verdict and the copies made."""
    resolved = []
    for p in paths:
        path = Path(p).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"bulunamadı: {path}")
        if path.is_relative_to(ws.documents) or path.is_relative_to(ws.inbox):
            raise ValueError(f"{path} zaten {ws.documents.name} ya da {ws.inbox.name} içinde")
        resolved.append(path)
    _check_import_size(resolved)
    with ws.lock():
        items = duzenle.plan([ws.documents, *resolved], ws.documents, ws.output)
    found = [it for it in items if it.sha256 and any(duzenle._inside(it.path or it.archive, p) for p in resolved)]
    return found, [path for _, path in _copy_new(ws, found)]


def import_documents(ws: Workspace, docs: list[duzenle.Item]) -> list[tuple[duzenle.Item, Path]]:
    """import_paths for documents held in memory (e-mail attachments): organizer items with their
    bytes and, as archive, a label saying where they came from. Each gets the organizer's verdict;
    returns the ones copied into the inbox, with their copy."""
    with ws.lock():
        duzenle.plan([ws.documents], ws.documents, ws.output, extra=docs)
    return _copy_new(ws, docs)


def _copy_new(ws: Workspace, found: list[duzenle.Item]) -> list[tuple[duzenle.Item, Path]]:
    """Copy into the inbox what the organizer would file, and the unreadable documents (for a
    manual look); a document already waiting there is not copied again."""
    copies = []
    with _upload_lock:
        waiting = {_sha256(p) for p in inbox_files(ws)}
        for it in found:
            if it.action not in (duzenle.KEEP, duzenle.FAILED) or it.sha256 in waiting:
                continue
            ws.inbox.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=PARTIAL_PREFIX, dir=ws.inbox)
            tmp = Path(tmp_name)
            safe = safe_upload_path(it.name)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(it.data)
                name = safe.name if safe else f"belge{Path(it.name).suffix}"
                copies.append((it, _link_free(tmp, ws.inbox / name)))
            finally:
                tmp.unlink(missing_ok=True)
            waiting.add(it.sha256)
    return copies


def describe(it: duzenle.Item, ws: Workspace) -> dict:
    """A plan item for the panel and the MCP client: what it is and what happens to it."""
    where = it.path or it.archive
    if where is not None:
        for root in (ws.inbox, ws.documents):
            if duzenle._inside(where, root):
                where = Path(root.name) / where.resolve().relative_to(root.resolve())
                break
    source = f"{where} › {it.name}" if it.archive else str(where)
    out = {
        "action": it.action,
        "name": it.name,
        "source": source,
        "reason": it.reason,
        "target": str(it.target.relative_to(ws.documents))
        if it.target and it.target.is_relative_to(ws.documents)
        else None,
        "fromInbox": duzenle._inside(it.path or it.archive, ws.inbox),
    }
    result = it.result
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
    elif result and result.transactions:
        t = result.transactions[0]
        account = next((a for a in result.accounts if a.id == t.account), None)
        out["document"] = {
            "kind": "dekont",
            "account": account.label if account else t.account,
            "start": None,
            "end": t.date.isoformat(),
            "rows": len(result.transactions),
            "verified": None,
            "check": result.title or "",
        }
    return out
