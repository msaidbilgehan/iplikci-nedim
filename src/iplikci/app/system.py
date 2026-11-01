"""The service's health for the System screen and /api/system (architecture §22, F18): what the data folder holds,
how each reader is doing, the job queue, the e-mail intake, the backups and how much disk it all takes. The service
adds its own process details.
"""

import shutil
import sqlite3
from dataclasses import dataclass

from .. import __version__
from ..domain.codes import DocumentStatus
from ..parsers import registry
from ..settings import config
from ..storage import bridges, jobs
from ..storage import mail as mail_store
from ..storage.db import Database
from .backup import Health as BackupHealth
from .backup import health as backup_health
from .mail import BRIDGE
from .reading import FORMAT_ALARM
from .workspace import Workspace


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
class MailHealth:
    connector: str  # imap or browser_bridge (ADR-0016)
    configured: bool  # an account set up, or an extension paired
    last_run: str  # the last fetch or delivery; "" if none yet
    last_error: str
    stopped: bool  # a refused login stopped the IMAP connector until it is set up again


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
    settings = config.load(ws.layout.settings).mail
    state = mail_store.load(db, settings.connector)
    if settings.connector == BRIDGE:
        configured = any(b.active for b in bridges.every(db))
    else:
        configured = bool(settings.address)
    return MailHealth(settings.connector, configured, state.last_run, state.last_error, state.stopped)


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
