"""TÜFE as EVDS publishes it (inflation.py): a value a month and series, kept as exact decimal text. A month EVDS
revises is written over."""

from collections.abc import Mapping
from decimal import Decimal

from .db import Database, now


def every(db: Database, series: str) -> dict[str, Decimal]:
    """The series' months and values, by YYYY-MM, the oldest first."""
    return {
        r["month"]: Decimal(r["value"])
        for r in db.rows("SELECT month, value FROM price_index WHERE series = ? ORDER BY month", (series,))
    }


def put(db: Database, series: str, values: Mapping[str, Decimal]) -> int:
    """Keep the months of an answer; how many were new or changed."""
    kept = every(db, series)
    changed = {month: value for month, value in values.items() if kept.get(month) != value}
    at = now()
    with db.transaction():
        db.executemany(
            "INSERT INTO price_index (series, month, value, fetched_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (series, month) DO UPDATE SET value = excluded.value, fetched_at = excluded.fetched_at",
            [(series, month, str(value), at) for month, value in sorted(changed.items())],
        )
    return len(changed)
