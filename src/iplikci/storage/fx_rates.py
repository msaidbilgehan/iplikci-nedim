"""The exchange rates the providers published (architecture §15), and the days each was asked for. Rates are kept as
exact decimal text; the rebuild carries them in its dump (they came from the network and may not come again)."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..domain.codes import RateSource
from ..fx.book import Quote
from .db import Database, now


@dataclass(frozen=True, slots=True)
class Asked:
    """A day a provider was asked for."""

    day: date
    source: RateSource
    published: bool  # False: it published nothing that day (a weekend, a holiday)
    asked_at: str


def every(db: Database) -> list[Quote]:
    return [
        Quote(
            date.fromisoformat(r["day"]),
            r["currency"],
            Decimal(r["buying"]),
            Decimal(r["selling"]),
            RateSource(r["source"]),
        )
        for r in db.rows("SELECT * FROM fx_rates ORDER BY day, currency, source")
    ]


def put(db: Database, day: date, source: RateSource, quotes: Iterable[Quote]) -> int:
    """A provider's answer for a day: its quotes (none: it published nothing that day). How many quotes were kept."""
    found = [q for q in quotes if q.day == day and q.source == source]
    at = now()
    with db.transaction():
        db.executemany(
            "INSERT INTO fx_rates (day, currency, source, buying, selling, fetched_at) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (day, currency, source) DO UPDATE SET buying = excluded.buying, "
            "selling = excluded.selling, fetched_at = excluded.fetched_at",
            [(q.day.isoformat(), q.currency, q.source, str(q.buying), str(q.selling), at) for q in found],
        )
        db.execute(
            "INSERT INTO fx_days (day, source, published, asked_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (day, source) DO UPDATE SET published = excluded.published, asked_at = excluded.asked_at",
            (day.isoformat(), source, int(bool(found)), at),
        )
    return len(found)


def asked(db: Database, source: RateSource) -> dict[date, Asked]:
    """The days the provider was asked for, by day."""
    return {
        date.fromisoformat(r["day"]): Asked(
            date.fromisoformat(r["day"]), RateSource(r["source"]), bool(r["published"]), r["asked_at"]
        )
        for r in db.rows("SELECT * FROM fx_days WHERE source = ? ORDER BY day", (source,))
    }


def restore(db: Database, quotes: Iterable[Quote], days: Iterable[Asked], fetched_at: str) -> None:
    """The rates and the days asked as a dump recorded them (the rebuild)."""
    with db.transaction():
        db.executemany(
            "INSERT OR REPLACE INTO fx_rates (day, currency, source, buying, selling, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(q.day.isoformat(), q.currency, q.source, str(q.buying), str(q.selling), fetched_at) for q in quotes],
        )
        db.executemany(
            "INSERT OR REPLACE INTO fx_days (day, source, published, asked_at) VALUES (?, ?, ?, ?)",
            [(a.day.isoformat(), a.source, int(a.published), a.asked_at) for a in days],
        )
