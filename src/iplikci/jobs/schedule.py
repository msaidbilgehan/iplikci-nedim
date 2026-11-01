"""Periodic jobs. Each is queued with its kind and its current period as the key, so it runs once per period.
After a sleep or a restart the next tick queues the current period's job once; the missed periods do not pile up.
Periods follow the computer's local time: a day is the user's day."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from ..storage import jobs
from ..storage.db import Database

type Period = Callable[[datetime], str]


def every(minutes: int) -> Period:
    """Periods of `minutes` counted from midnight."""
    if not 0 < minutes <= 24 * 60:
        raise ValueError(f"period of {minutes} minutes")

    def period(at: datetime) -> str:
        slot = (at.hour * 60 + at.minute) // minutes * minutes
        return f"{at:%Y-%m-%d}T{slot // 60:02d}:{slot % 60:02d}"

    return period


def daily(start: time) -> Period:
    """One period a day that begins at `start`: before that time it is still the day before's period."""

    def period(at: datetime) -> str:
        day = at.date() if at.time() >= start else at.date() - timedelta(days=1)
        return day.isoformat()

    return period


def monthly(start: time) -> Period:
    """One period a month that begins on its first day at `start`: before that it is still the month before's."""

    def period(at: datetime) -> str:
        if at.day == 1 and at.time() < start:
            at -= timedelta(days=1)
        return f"{at:%Y-%m}"

    return period


@dataclass(frozen=True)
class Periodic:
    kind: str
    period: Period
    payload: dict[str, Any] = field(default_factory=dict[str, Any])

    def key(self, at: datetime) -> str:
        return f"{self.kind}@{self.period(at)}"


def tick(db: Database, periodic: Iterable[Periodic], at: datetime) -> list[int]:
    """Queue every periodic job whose current period has none yet; the ids queued."""
    added = (jobs.add(db, p.kind, p.payload, key=p.key(at)) for p in periodic)
    return [job_id for job_id in added if job_id is not None]
