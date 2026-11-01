"""The archive check (`iplikci dogrula --arsiv`, ADR-0003): every object hashed again, and the database checked
against the vault and against itself."""

import sqlite3
from dataclasses import dataclass, field

from ..domain.codes import DocumentStatus
from ..storage import documents
from ..storage.db import Database
from ..vault.store import Integrity
from . import reading
from .workspace import Workspace


@dataclass
class ArchiveReport:
    integrity: Integrity
    documents: int = 0  # rows in the database
    missing: list[str] = field(default_factory=list[str])  # kept documents whose object is not in the vault
    unknown: list[str] = field(default_factory=list[str])  # objects no document names (a run stopped halfway)
    lingering: list[str] = field(default_factory=list[str])  # removed documents whose object is still there
    database: list[str] = field(default_factory=list[str])  # what the database's own checks found
    stale: int = 0  # documents waiting to be read again (new readers, other company names)

    @property
    def ok(self) -> bool:
        """Whether nothing is lost or damaged; the other findings are worth a look but harm nothing."""
        return self.integrity.ok and not self.missing and not self.database


def _database_problems(db: Database) -> list[str]:
    found = [str(r[0]) for r in db.rows("PRAGMA integrity_check") if str(r[0]) != "ok"]
    found += [f"yabancı anahtar: {r[0]} satır {r[1]} → {r[2]}" for r in db.rows("PRAGMA foreign_key_check")]
    try:
        db.execute("INSERT INTO search (search) VALUES ('integrity-check')")
    except sqlite3.DatabaseError as exc:
        found.append(f"arama dizini: {exc}")
    # Only a processed document has rows: a reading that went away must have taken them along.
    for table in ("statements", "evidence"):  # fixed names, never input
        n = db.scalar(
            f"SELECT count(*) FROM {table} t JOIN documents d ON d.sha256 = t.sha256 WHERE d.status != 'processed'"
        )
        if n:
            found.append(f"{table}: işlenmemiş belgelere ait {n} satır")
    return found


def archive(ws: Workspace) -> ArchiveReport:
    vault = ws.vault
    report = ArchiveReport(vault.verify())
    objects = set(vault.objects())
    with ws.db() as db:
        rows = documents.every(db)
        report.documents = len(rows)
        report.database = _database_problems(db)
    named = {d.sha256 for d in rows}
    for d in rows:
        if d.status is DocumentStatus.REMOVED:
            if d.sha256 in objects:
                report.lingering.append(d.sha256)
        elif d.sha256 not in objects:
            report.missing.append(d.sha256)
        elif reading.stale(d):
            report.stale += 1
    report.unknown = sorted(objects - named)
    return report
