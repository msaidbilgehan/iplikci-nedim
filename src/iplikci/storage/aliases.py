"""The names the user gives accounts (F07). Primary data: a new reading of the documents never touches them, and the
rebuild carries them in the dump. The audit log records each change by the account's id, never the name."""

from dataclasses import dataclass

from ..domain.codes import Actor
from . import audit
from .db import Database, now

SET, REMOVED = "account.alias", "account.alias_removed"  # the audit log's actions


@dataclass(frozen=True, slots=True)
class Alias:
    account: str  # the account's id
    alias: str
    updated_at: str
    actor: Actor


def every(db: Database) -> dict[str, Alias]:
    return {
        r["account"]: Alias(r["account"], r["alias"], r["updated_at"], Actor(r["actor"]))
        for r in db.rows("SELECT * FROM account_aliases ORDER BY account")
    }


def change(db: Database, account: str, alias: str, actor: Actor) -> Alias | None:
    """Give the account the name alias; an empty one takes the name away (None). Nothing is recorded when the name
    stays as it was."""
    alias = alias.strip()
    with db.transaction():
        old = db.one("SELECT alias FROM account_aliases WHERE account = ?", (account,))
        if not alias:
            if old is not None:
                db.execute("DELETE FROM account_aliases WHERE account = ?", (account,))
                audit.record(db, actor, REMOVED, account)
            return None
        found = Alias(account, alias, now(), actor)
        if old is not None and old["alias"] == alias:
            return every(db)[account]
        db.execute(
            "INSERT INTO account_aliases (account, alias, updated_at, actor) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (account) DO UPDATE SET alias = excluded.alias, updated_at = excluded.updated_at, "
            "actor = excluded.actor",
            (found.account, found.alias, found.updated_at, found.actor),
        )
        audit.record(db, actor, SET, account)
    return found


def restore(db: Database, alias: Alias) -> None:
    """A name as a dump of the primary data recorded it, with its own time."""
    with db.transaction():
        db.execute(
            "INSERT INTO account_aliases (account, alias, updated_at, actor) VALUES (?, ?, ?, ?)",
            (alias.account, alias.alias, alias.updated_at, alias.actor),
        )
