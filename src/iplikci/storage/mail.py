"""Where each mail connector stands and how its last run went (ADR-0015, ADR-0016)."""

import json
from dataclasses import dataclass, field

from .db import Database


@dataclass
class MailState:
    connector: str
    folder: str = ""
    uidvalidity: int = 0
    last_uid: int = 0
    last_id: str = ""
    last_date: str = ""
    scan_key: str = ""
    last_run: str = ""
    last_error: str = ""
    stopped: bool = False
    totals: dict[str, int] = field(default_factory=dict[str, int])

    def count(self, outcome: str, n: int = 1) -> None:
        self.totals[outcome] = self.totals.get(outcome, 0) + n


def load(db: Database, connector: str, folder: str = "") -> MailState:
    """The connector's state; a fresh one when it never ran."""
    row = db.one("SELECT * FROM mail_state WHERE connector = ? AND folder = ?", (connector, folder))
    if row is None:
        return MailState(connector, folder)
    return MailState(
        connector,
        folder,
        int(row["uidvalidity"]),
        int(row["last_uid"]),
        str(row["last_id"]),
        str(row["last_date"]),
        str(row["scan_key"]),
        str(row["last_run"]),
        str(row["last_error"]),
        bool(row["stopped"]),
        {str(k): int(v) for k, v in json.loads(row["totals"]).items()},
    )


def save(db: Database, state: MailState) -> None:
    with db.transaction():
        db.execute(
            "INSERT INTO mail_state (connector, folder, uidvalidity, last_uid, last_id, last_date, scan_key, "
            "last_run, last_error, stopped, totals) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (connector, folder) DO UPDATE SET uidvalidity = excluded.uidvalidity, "
            "last_uid = excluded.last_uid, last_id = excluded.last_id, last_date = excluded.last_date, "
            "scan_key = excluded.scan_key, last_run = excluded.last_run, last_error = excluded.last_error, "
            "stopped = excluded.stopped, totals = excluded.totals",
            (
                state.connector,
                state.folder,
                state.uidvalidity,
                state.last_uid,
                state.last_id,
                state.last_date,
                state.scan_key,
                state.last_run,
                state.last_error,
                int(state.stopped),
                json.dumps(state.totals, sort_keys=True),
            ),
        )


def states(db: Database, connector: str | None = None) -> list[MailState]:
    rows = (
        db.rows("SELECT connector, folder FROM mail_state ORDER BY connector, folder")
        if connector is None
        else db.rows("SELECT connector, folder FROM mail_state WHERE connector = ? ORDER BY folder", (connector,))
    )
    return [load(db, str(r["connector"]), str(r["folder"])) for r in rows]


def forget(db: Database, connector: str) -> None:
    """The connector was removed: where it stood goes with it (the mailbox is read from the start next time)."""
    with db.transaction():
        db.execute("DELETE FROM mail_state WHERE connector = ?", (connector,))
