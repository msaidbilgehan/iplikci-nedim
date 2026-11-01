"""The audit log (architecture §21): who changed what, when. Entries are only ever added. Details hold
identifiers and counts, never amounts, names or addresses."""

import json
from dataclasses import dataclass
from typing import Any

from ..domain.codes import Actor
from .db import Database, now


@dataclass(frozen=True, slots=True)
class Entry:
    at: str
    actor: Actor
    action: str
    target: str
    detail: dict[str, Any]


def record(db: Database, actor: Actor, action: str, target: str = "", **detail: Any) -> None:
    with db.transaction():
        db.execute(
            "INSERT INTO audit_log (at, actor, action, target, detail) VALUES (?, ?, ?, ?, ?)",
            (now(), actor, action, target, json.dumps(detail, ensure_ascii=False, sort_keys=True)),
        )


def entries(db: Database, action: str | None = None) -> list[Entry]:
    rows = (
        db.rows("SELECT * FROM audit_log ORDER BY id")
        if action is None
        else db.rows("SELECT * FROM audit_log WHERE action = ? ORDER BY id", (action,))
    )
    return [Entry(r["at"], Actor(r["actor"]), r["action"], r["target"], json.loads(r["detail"])) for r in rows]


def targets(db: Database, action: str) -> set[str]:
    """Every target an action was ever taken on."""
    return {r[0] for r in db.rows("SELECT DISTINCT target FROM audit_log WHERE action = ?", (action,))}
