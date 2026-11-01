"""What the feed saw last (ADR-0014): named JSON values, such as the snapshot the next analysis is compared with."""

import json
from typing import Any

from .db import Database, now


def load(db: Database, name: str) -> Any:
    """The value saved under name; None when there is none."""
    value = db.scalar("SELECT value FROM feed_state WHERE name = ?", (name,))
    return None if value is None else json.loads(value)


def save(db: Database, name: str, value: Any) -> None:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    with db.transaction():
        db.execute(
            "INSERT INTO feed_state (name, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT (name) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (name, text, now()),
        )
