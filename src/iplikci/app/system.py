"""The service's health for the System screen and /api/system (architecture §22, F18): what the data folder holds,
how each reader is doing and how much disk it all takes. The service adds its own process details; the e-mail
fetch, the job queue and the backups join as they land.
"""

import shutil
import sqlite3
from dataclasses import dataclass

from .. import __version__
from ..domain.codes import DocumentStatus
from ..parsers import registry
from ..storage.db import Database
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
class SystemStatus:
    version: str
    home: str
    documents: dict[str, int]  # by status code
    readers: list[ReaderHealth]
    disk: Disk


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
    return SystemStatus(__version__, str(ws.home), documents, readers, disk(ws))


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
