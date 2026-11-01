"""The user's notes and corrections, bound to transaction fingerprints (architecture §8). Primary data: a new
reading of the documents never touches them. Each one remembers the row it was made on, so one whose fingerprint
no row has any more can still be shown for what it was."""

import json
import sqlite3
from dataclasses import asdict, dataclass, replace
from typing import Any

from ..domain.codes import Actor, Necessity
from . import audit
from .db import Database, now


@dataclass(frozen=True, slots=True)
class Subject:
    """The row an annotation was made on, as it looked then."""

    account: str  # the account's id
    label: str  # the account as the user saw it
    date: str  # ISO day
    amount: int  # in the currency's smallest unit; positive is money out
    currency: str
    description: str


@dataclass(frozen=True, slots=True)
class Annotation:
    fingerprint: str
    subject: Subject
    note: str = ""
    tags: tuple[str, ...] = ()
    category: str = ""  # replaces the rules' category
    necessity: Necessity | None = None  # replaces the necessity the category's rules give
    created_at: str = ""
    updated_at: str = ""
    actor: Actor = Actor.USER

    @property
    def empty(self) -> bool:
        return not (self.note or self.tags or self.category or self.necessity)


class _Keep:
    """A field left as it is."""


KEEP: Any = _Keep()


def _subject(text: str) -> Subject:
    value: dict[str, Any] = json.loads(text)
    return Subject(
        str(value.get("account", "")),
        str(value.get("label", "")),
        str(value.get("date", "")),
        int(value.get("amount", 0)),
        str(value.get("currency", "")),
        str(value.get("description", "")),
    )


def _row(r: sqlite3.Row) -> Annotation:
    tags: list[str] = json.loads(r["tags"])
    return Annotation(
        fingerprint=r["fingerprint"],
        subject=_subject(r["subject"]),
        note=r["note"],
        tags=tuple(tags),
        category=r["category"],
        necessity=Necessity(r["necessity"]) if r["necessity"] else None,
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        actor=Actor(r["actor"]),
    )


def get(db: Database, fingerprint: str) -> Annotation | None:
    row = db.one("SELECT * FROM annotations WHERE fingerprint = ?", (fingerprint,))
    return None if row is None else _row(row)


def every(db: Database) -> dict[str, Annotation]:
    return {a.fingerprint: a for a in map(_row, db.rows("SELECT * FROM annotations ORDER BY created_at, rowid"))}


def clean_tags(tags: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Tags as kept: trimmed, without empty or repeated ones, in the order given."""
    return tuple(dict.fromkeys(t.strip() for t in tags if t.strip()))


def change(
    db: Database,
    fingerprint: str,
    subject: Subject,
    actor: Actor,
    *,
    note: str = KEEP,
    tags: tuple[str, ...] = KEEP,
    category: str = KEEP,
    necessity: Necessity | None = KEEP,
) -> Annotation | None:
    """Set the given fields of the row's annotation and leave the others; an annotation left with nothing in it is
    removed (None). The subject is updated to the row as it is now."""
    with db.transaction():
        old = get(db, fingerprint)
        base = old or Annotation(fingerprint, subject, actor=actor)
        new = replace(
            base,
            subject=subject,
            note=base.note if note is KEEP else note.strip(),
            tags=base.tags if tags is KEEP else clean_tags(tags),
            category=base.category if category is KEEP else category.strip(),
            necessity=base.necessity if necessity is KEEP else necessity,
            actor=actor,
        )
        if new.empty:
            if old is not None:
                db.execute("DELETE FROM annotations WHERE fingerprint = ?", (fingerprint,))
                audit.record(db, actor, "annotation.removed", fingerprint)
            return None
        stamp = now()
        db.execute(
            "INSERT INTO annotations (fingerprint, note, tags, category, necessity, subject, created_at, updated_at, "
            "actor) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (fingerprint) DO UPDATE SET note = excluded.note, "
            "tags = excluded.tags, category = excluded.category, necessity = excluded.necessity, "
            "subject = excluded.subject, updated_at = excluded.updated_at, actor = excluded.actor",
            (
                fingerprint,
                new.note,
                json.dumps(list(new.tags), ensure_ascii=False),
                new.category,
                new.necessity or "",
                json.dumps(asdict(new.subject), ensure_ascii=False, sort_keys=True),
                old.created_at if old else stamp,
                stamp,
                actor,
            ),
        )
        # The log names the fields that changed, never their contents.
        fields = [f for f in ("note", "tags", "category", "necessity") if getattr(new, f) != getattr(base, f)]
        audit.record(db, actor, "annotation.set", fingerprint, fields=fields)
    return get(db, fingerprint)


def remove(db: Database, fingerprint: str, actor: Actor) -> bool:
    """Forget an annotation altogether (an orphan the user let go); False if there was none."""
    with db.transaction():
        cursor = db.execute("DELETE FROM annotations WHERE fingerprint = ?", (fingerprint,))
        if cursor.rowcount:
            audit.record(db, actor, "annotation.removed", fingerprint)
    return bool(cursor.rowcount)
