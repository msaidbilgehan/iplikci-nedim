"""The accounts the user says they closed (F07), with the day. Primary data: a new reading of the documents never
touches them, the rebuild carries them in the dump and the sync folder shares them (ADR-0025). The audit log records
each change by the account's id."""

from dataclasses import dataclass
from datetime import date

from ..domain.codes import Actor
from . import audit
from .db import Database, now

CLOSED, REOPENED = "account.closed", "account.reopened"  # the audit log's actions


@dataclass(frozen=True, slots=True)
class Closure:
    account: str  # the account's id
    closed_on: str  # YYYY-MM-DD
    updated_at: str
    actor: Actor

    @property
    def day(self) -> date:
        return date.fromisoformat(self.closed_on)


def every(db: Database) -> dict[str, Closure]:
    return {
        r["account"]: Closure(r["account"], r["closed_on"], r["updated_at"], Actor(r["actor"]))
        for r in db.rows("SELECT * FROM account_closures ORDER BY account")
    }


def close(db: Database, account: str, day: date, actor: Actor) -> Closure:
    """Mark the account closed on day; nothing is recorded when it already was, on that day."""
    with db.transaction():
        old = db.one("SELECT closed_on FROM account_closures WHERE account = ?", (account,))
        if old is not None and old["closed_on"] == day.isoformat():
            return every(db)[account]
        found = Closure(account, day.isoformat(), now(), actor)
        _write(db, found)
        audit.record(db, actor, CLOSED, account, closed_on=found.closed_on)
    return found


def reopen(db: Database, account: str, actor: Actor) -> bool:
    """Take the mark away; False when the account had none."""
    with db.transaction():
        if db.one("SELECT 1 FROM account_closures WHERE account = ?", (account,)) is None:
            return False
        db.execute("DELETE FROM account_closures WHERE account = ?", (account,))
        audit.record(db, actor, REOPENED, account)
    return True


def restore(db: Database, closure: Closure) -> None:
    """A mark as a dump of the primary data recorded it, with its own time."""
    with db.transaction():
        db.execute(
            "INSERT INTO account_closures (account, closed_on, updated_at, actor) VALUES (?, ?, ?, ?)",
            (closure.account, closure.closed_on, closure.updated_at, closure.actor),
        )


def put(db: Database, closure: Closure) -> None:
    """A mark as another computer has it (ADR-0025), with its own time and author; the one here replaced."""
    with db.transaction():
        _write(db, closure)


def drop(db: Database, account: str) -> None:
    """A mark another computer took away (ADR-0025)."""
    with db.transaction():
        db.execute("DELETE FROM account_closures WHERE account = ?", (account,))


def _write(db: Database, closure: Closure) -> None:
    db.execute(
        "INSERT INTO account_closures (account, closed_on, updated_at, actor) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (account) DO UPDATE SET closed_on = excluded.closed_on, updated_at = excluded.updated_at, "
        "actor = excluded.actor",
        (closure.account, closure.closed_on, closure.updated_at, closure.actor),
    )
