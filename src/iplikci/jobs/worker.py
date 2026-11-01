"""The worker (ADR-0014): one thread runs the due jobs one at a time. An attempt that raises is tried again later,
waiting longer each time (30 s, 1, 2 and 4 minutes); the fifth failed attempt fails the job, which keeps its error
in the queue. Every half minute the scheduler queues the periodic jobs. The log gets the job's id and kind only."""

import logging
import sqlite3
import threading
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from datetime import UTC, datetime, timedelta
from typing import Any

from ..storage import jobs
from ..storage.db import Database
from . import schedule

type Handler = Callable[[dict[str, Any]], object]  # what it returns is not used

MAX_ATTEMPTS = 5
TICK = timedelta(seconds=30)
_ERROR_LIMIT = 500

log = logging.getLogger("iplikci.jobs")


def backoff(attempts: int) -> timedelta:
    """How long a job waits after its n-th failed attempt."""
    return timedelta(seconds=min(30 * 2 ** (attempts - 1), 3600))


def _iso(at: datetime) -> str:
    return at.astimezone(UTC).replace(microsecond=0).isoformat()


def _now() -> datetime:
    return datetime.now().astimezone()


class Worker:
    def __init__(
        self,
        connect: Callable[[], Database],
        handlers: Mapping[str, Handler],
        periodic: Sequence[schedule.Periodic] = (),
        *,
        idle: float = 2.0,
        now: Callable[[], datetime] = _now,
    ) -> None:
        self._connect = connect
        self._handlers = handlers
        self._periodic = periodic
        self._idle = idle
        self._now = now
        self._last_tick: datetime | None = None
        self._wake = threading.Event()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Put back the jobs a stopped service left running, then work in a thread of its own."""
        with closing(self._connect()) as db:
            if recovered := jobs.recover(db):
                log.info("%d interrupted jobs queued again", recovered)
        self._thread = threading.Thread(target=self._loop, name="iplikci-isler", daemon=True)
        self._thread.start()

    def wake(self) -> None:
        """Look for due jobs now instead of at the next idle check."""
        self._wake.set()

    def stop(self, timeout: float = 30.0) -> None:
        """Stop after the job at hand; a job that outlives the timeout is queued again at the next start."""
        self._stopping.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def step(self, db: Database) -> bool:
        """Queue the periodic jobs when their tick is due, then run one due job; whether a job ran."""
        at = self._now()
        if self._last_tick is None or at - self._last_tick >= TICK:
            schedule.tick(db, self._periodic, at)
            self._last_tick = at
        job = jobs.claim(db, _iso(at))
        if job is None:
            return False
        self._run(db, job)
        return True

    def _loop(self) -> None:
        with closing(self._connect()) as db:
            while not self._stopping.is_set():
                try:
                    ran = self.step(db)
                except sqlite3.Error:  # the database was busy or failed for a moment: the queue is still there
                    log.exception("the job queue could not be read")
                    ran = False
                if not ran:
                    self._wake.wait(self._idle)
                    self._wake.clear()

    def _run(self, db: Database, job: jobs.Job) -> None:
        handler = self._handlers.get(job.kind)
        if handler is None:
            jobs.fail(db, job.id, f"bilinmeyen iş türü: {job.kind}", _iso(self._now()))
            log.error("job %d has an unknown kind %s", job.id, job.kind)
            return
        try:
            handler(job.payload)
        except Exception as exc:  # noqa: BLE001 - a job's boundary: any error fails this attempt, never the worker
            error = f"{type(exc).__name__}: {exc}"[:_ERROR_LIMIT]
            finished = self._now()
            if job.attempts >= MAX_ATTEMPTS:
                jobs.fail(db, job.id, error, _iso(finished))
                log.error("job %d (%s) failed after %d attempts", job.id, job.kind, job.attempts)
            else:
                jobs.retry(db, job.id, error, _iso(finished + backoff(job.attempts)))
                log.warning("job %d (%s) failed on attempt %d; it runs again later", job.id, job.kind, job.attempts)
            return
        jobs.finish(db, job.id, _iso(self._now()))
