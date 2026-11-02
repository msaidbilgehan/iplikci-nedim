"""The service's health for the System screen and /api/system (architecture §22, F18): what the data folder holds,
how each reader is doing, the job queue, the e-mail intake, the backups and how much disk it all takes. The service
adds its own process details.
"""

import json
import re
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .. import __version__
from ..domain.codes import DocumentStatus
from ..domain.text import fold
from ..parsers import registry
from ..service.logs import LOG_NAME, OUTPUT_NAME
from ..settings import config
from ..storage import bridges, jobs
from ..storage import mail as mail_store
from ..storage.db import Database
from . import bridge
from .backup import Health as BackupHealth
from .backup import health as backup_health
from .inventory import mail_coverage
from .mail import BRIDGE, default_start, refusal_label
from .reading import FORMAT_ALARM
from .workspace import Workspace

_LEFT = 10  # kinds of unknown message the System screen lists


@dataclass(frozen=True, slots=True)
class ReaderHealth:
    parser: str
    name: str
    version: str
    documents: int  # kept documents it recognised
    statements: int  # of those, statements: their totals or balances were checked
    verified: int
    last_read: str  # when it last read a document it processed; "" if never
    alarms: int  # format alarms raised for its documents


@dataclass(frozen=True, slots=True)
class Disk:
    vault: int  # bytes the originals take
    database: int
    free: int  # free bytes on the data folder's disk


@dataclass(frozen=True, slots=True)
class FailedJob:
    id: int
    kind: str
    attempts: int
    finished_at: str
    error: str


@dataclass(frozen=True, slots=True)
class Queue:
    counts: dict[str, int]  # by status: queued, running, done, failed
    next_run: str  # when the earliest queued job may start; "" when none waits
    failures: list[FailedJob]  # the latest, newest first


@dataclass(frozen=True, slots=True)
class RefusedMail:
    taken: str  # unlisted, unverified, business
    reason: str  # what the trust rule saw (ingest.mail.trust.trust_problem)
    domain: str  # the sender's domain; "" for a sender on no list
    count: int
    label: str  # why, in Turkish


@dataclass(frozen=True, slots=True)
class UnknownMail:
    domain: str
    template: str  # the subject with numbers and month names masked (app.inventory.subject_template)
    count: int


@dataclass(frozen=True, slots=True)
class MailCoverage:
    """F01's measure (app.inventory.Coverage): the kept bank messages read or knowingly classified."""

    total: int
    read: int  # a reader read the body
    attached: int  # read through the documents it carries
    no_money: int  # a campaign, an announcement, a security or a card notice
    business: int  # a company's: gone to the Trash
    unknown: int
    share: float  # of the total, what is not unknown; 1.0 when there is nothing yet
    left: list[UnknownMail]  # the unknown ones by kind, most first; at most _LEFT of them


@dataclass(frozen=True, slots=True)
class MailHealth:
    connector: str  # imap or browser_bridge (ADR-0016)
    configured: bool  # an account set up, or an extension paired
    last_run: str  # the last fetch or delivery; "" if none yet
    last_error: str
    stopped: bool  # a refused login stopped the IMAP connector until it is set up again
    start_day: str  # where the history begins
    history_due: bool  # the extension has not scanned Gmail for this start day and these senders (ADR-0016)
    refused: list[RefusedMail]  # messages the extension delivered that were not kept, by why; most first
    coverage: MailCoverage


@dataclass(frozen=True, slots=True)
class SystemStatus:
    version: str
    home: str
    documents: dict[str, int]  # by status code
    readers: list[ReaderHealth]
    disk: Disk
    queue: Queue
    mail: MailHealth
    backup: BackupHealth


def healthy(ws: Workspace) -> bool:
    """Whether the database opens and answers."""
    try:
        with ws.db() as db:
            return db.scalar("SELECT 1") == 1
    except sqlite3.Error:
        return False


def status(ws: Workspace) -> SystemStatus:
    with ws.db() as db:
        rows = db.rows("SELECT status, count(*) AS n FROM documents GROUP BY status")
        documents = {str(row["status"]): int(row["n"]) for row in rows}
        readers = reader_health(db)
        queue = Queue(
            jobs.counts(db),
            jobs.next_due(db) or "",
            [FailedJob(j.id, j.kind, j.attempts, j.finished_at, j.last_error) for j in jobs.failures(db)],
        )
        mail = mail_health(ws, db)
    return SystemStatus(__version__, str(ws.home), documents, readers, disk(ws), queue, mail, backup_health(ws))


def mail_health(ws: Workspace, db: Database) -> MailHealth:
    """How the chosen connector is doing; never the address (ADR-0015). The settings as the file says now: pairing
    an extension or setting up an account changes them while the service runs."""
    settings = config.load(ws.layout.settings)
    connector = settings.mail.connector
    state = mail_store.load(db, connector)
    refused: list[RefusedMail] = []
    if connector == BRIDGE:
        configured = any(b.active for b in bridges.every(db))
        due = configured and bridge.history_due(settings, state)
        refused = [
            RefusedMail(r.taken, r.reason, r.domain, r.count, refusal_label(r.taken, r.reason))
            for r in bridges.refusals(db, bridge.refusal_key(settings))
        ]
    else:
        configured = bool(settings.mail.address)
        due = False  # the service reads the mailbox from the start day by itself
    start = (settings.mail.start_day or default_start()).isoformat()
    covered = coverage(db, settings.mail.bank_senders)
    return MailHealth(
        connector, configured, state.last_run, state.last_error, state.stopped, start, due, refused, covered
    )


def coverage(db: Database, bank_senders: tuple[str, ...]) -> MailCoverage:
    found = mail_coverage(db, bank_senders)
    left = [UnknownMail(domain, template, n) for (domain, template), n in found.left.most_common(_LEFT)]
    return MailCoverage(
        found.total, found.read, found.attached, found.no_money, found.business, found.unknown, found.share, left
    )


def reader_health(db: Database) -> list[ReaderHealth]:
    """Every reader, with what it did among the kept documents (the removed ones left the vault)."""
    counts = {
        str(row["parser"]): row
        for row in db.rows(
            "SELECT parser, count(*) AS documents, count(verified) AS statements, "
            "coalesce(sum(verified), 0) AS verified, "
            "coalesce(max(CASE WHEN status = ? THEN read_at END), '') AS last_read "
            "FROM documents WHERE status != ? AND parser != '' GROUP BY parser",
            (DocumentStatus.PROCESSED.value, DocumentStatus.REMOVED.value),
        )
    }
    alarms = {
        str(row["parser"]): int(row["n"])
        for row in db.rows(
            "SELECT json_extract(detail, '$.parser') AS parser, count(*) AS n FROM events WHERE kind = ? GROUP BY 1",
            (FORMAT_ALARM,),
        )
    }
    health: list[ReaderHealth] = []
    for reader in registry.readers():
        row = counts.get(reader.id)
        health.append(
            ReaderHealth(
                parser=reader.id,
                name=reader.name,
                version=registry.version_of(reader),
                documents=int(row["documents"]) if row else 0,
                statements=int(row["statements"]) if row else 0,
                verified=int(row["verified"]) if row else 0,
                last_read=str(row["last_read"]) if row else "",
                alarms=alarms.get(reader.id, 0),
            )
        )
    return health


def disk(ws: Workspace) -> Disk:
    vault = sum(path.stat().st_size for path in ws.layout.objects.rglob("*") if path.is_file())
    database = sum(
        path.stat().st_size
        for path in (ws.layout.database, ws.layout.database.with_name(ws.layout.database.name + "-wal"))
        if path.exists()
    )
    return Disk(vault=vault, database=database, free=shutil.disk_usage(ws.home).free)


# --- the log the user may send on (F18) -----------------------------------------------------------------------

LOG_TAIL = 1024 * 1024  # bytes kept of each file: the newest part
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Any country's IBAN, in groups or not; the country code in capitals, so a hexadecimal id is never taken for one.
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b")
_LONG_NUMBER = re.compile(r"\d{8,}")  # an account's or a card's number; times and counts are shorter
# A home folder's account name in any path, a JSON line's doubled backslashes too: /Users/<name>, /home/<name>,
# C:\Users\<name>. A Windows account name may have spaces: it runs to the next separator.
_HOME_FOLDER = re.compile(r"(/Users/|/home/|[A-Za-z]:(?:\\\\|\\)Users(?:\\\\|\\))([^\\/\"'\n]+)")
_NAME_WORD = 4  # letters from which a word of a name is taken out on its own; shorter ones are common words


def _written(path: str) -> list[str]:
    """A path as the log may write it: as it is, and in a JSON line (backslashes doubled, other letters escaped)."""
    return list(dict.fromkeys((path, json.dumps(path)[1:-1], json.dumps(path, ensure_ascii=False)[1:-1])))


def _names(ws: Workspace) -> re.Pattern[str] | None:
    """The user's own and company names as settings.toml gives them, written as typed or folded as banks print
    them, whole and word by word; None when there are none or the file cannot be read."""
    try:
        identity = config.load(ws.layout.settings).identity
    except config.SettingsError:
        return None
    found: set[str] = set()
    for name in (*identity.names, *identity.business_names):
        for words in (name.split(), fold(name).split()):
            found.add(" ".join(words))
            found |= {w for w in words if len(w) >= _NAME_WORD}
    found = {n for n in found if len(n) >= _NAME_WORD}
    if not found:
        return None
    alternatives = "|".join(re.escape(n) for n in sorted(found, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


def _scrubbed(text: str, ws: Workspace) -> str:
    """The text with what could be personal taken out: the data folder's and the home folder's paths and any home
    folder's account name, the user's own and company names, e-mail addresses, IBANs and long numbers. The log
    writes ids and counts only; a traceback or a library's message may still carry such a value."""
    for path, mark in ((str(ws.home), "<veri klasörü>"), (str(Path.home()), "~")):
        for written in _written(path):
            text = text.replace(written, mark)
    text = _HOME_FOLDER.sub(r"\1<kullanıcı>", text)
    names = _names(ws)
    if names is not None:
        text = names.sub("<ad>", text)
    text = _EMAIL.sub("<e-posta>", text)
    text = _IBAN.sub("<IBAN>", text)
    return _LONG_NUMBER.sub("<sayı>", text)


def _tail(path: Path) -> str:
    try:
        with path.open("rb") as f:
            size = f.seek(0, 2)
            f.seek(max(0, size - LOG_TAIL))
            data = f.read()
    except FileNotFoundError:
        return ""
    text = data.decode("utf-8", errors="replace")
    return text if len(data) < LOG_TAIL else text.partition("\n")[2]  # a cut first line is dropped


def log_text(ws: Workspace) -> str:
    """The service's log to download and send on: its previous and current file, oldest first, then what the process
    printed itself (its start line, a crash before its log opened), each scrubbed of what could be personal."""
    parts: list[str] = []
    for name in (f"{LOG_NAME}.1", LOG_NAME, OUTPUT_NAME):
        text = _tail(ws.logs / name)
        if text:
            parts.append(f"# {name}\n{_scrubbed(text, ws)}")
    return "\n".join(parts) if parts else "# Günlük boş.\n"
