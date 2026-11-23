"""The job queue, the worker and the scheduler (ADR-0014): a key is done once, a failed attempt waits longer each
time, a restart loses nothing and a sleep runs each missed periodic job once."""

import threading
import time as clock
from datetime import UTC, datetime, time, timedelta, timezone

import pytest

from iplikci.jobs import schedule
from iplikci.jobs.worker import MAX_ATTEMPTS, Worker, backoff
from iplikci.storage import jobs

ISTANBUL = timezone(timedelta(hours=3))


class Clock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def __call__(self) -> datetime:
        return self.at


def iso(at: datetime) -> str:
    return at.astimezone(UTC).replace(microsecond=0).isoformat()


def test_a_job_with_a_key_is_queued_once(ws):
    with ws.db() as db:
        assert jobs.add(db, "backup.daily", key="backup.daily@2026-11-01") is not None
        assert jobs.add(db, "backup.daily", key="backup.daily@2026-11-01") is None
        assert jobs.add(db, "backup.daily", key="backup.daily@2026-11-02") is not None


def test_a_waiting_job_is_a_queued_or_running_one(ws):
    with ws.db() as db:
        assert jobs.waiting(db, "update.install") is None
        job_id = jobs.add(db, "update.install")
        assert jobs.waiting(db, "update.install").id == job_id
        jobs.claim(db, iso(datetime.now(ISTANBUL) + timedelta(seconds=1)))
        assert jobs.waiting(db, "update.install").status == jobs.RUNNING
        jobs.finish(db, job_id, iso(datetime.now(ISTANBUL)))
        assert jobs.waiting(db, "update.install") is None


def test_the_same_job_without_a_key_waits_once_but_may_follow_a_running_one(ws):
    with ws.db() as db:
        first = jobs.add(db, "analysis.refresh")
        assert first is not None
        assert jobs.add(db, "analysis.refresh") is None
        assert jobs.add(db, "analysis.refresh", {"why": "başka"}) is not None
        jobs.claim(db, iso(datetime.now(ISTANBUL) + timedelta(seconds=1)))  # the first one starts
        assert jobs.add(db, "analysis.refresh") is not None


def test_due_jobs_start_in_order_of_their_time(ws):
    start = datetime(2026, 11, 1, 10, tzinfo=ISTANBUL)
    with ws.db() as db:
        later = jobs.add(db, "b", run_after=iso(start + timedelta(minutes=5)))
        sooner = jobs.add(db, "a", run_after=iso(start + timedelta(minutes=1)))
        assert jobs.claim(db, iso(start)) is None
        assert jobs.next_due(db) == iso(start + timedelta(minutes=1))
        first = jobs.claim(db, iso(start + timedelta(minutes=10)))
        second = jobs.claim(db, iso(start + timedelta(minutes=10)))
    assert (first.id, first.status, first.attempts) == (sooner, jobs.RUNNING, 1)
    assert second.id == later


def test_a_failing_job_waits_longer_each_time_and_then_fails_with_its_error(ws):
    now = Clock(datetime(2026, 11, 1, 10, tzinfo=ISTANBUL))

    def broken(_payload):
        raise ValueError("bozuk belge")

    worker = Worker(ws.connect, {"x": broken}, now=now)
    waits = []
    with ws.db() as db:
        job_id = jobs.add(db, "x", run_after=iso(now.at))
        for attempt in range(1, MAX_ATTEMPTS + 1):
            assert worker.step(db)
            job = jobs.get(db, job_id)
            if attempt < MAX_ATTEMPTS:
                assert (job.status, job.last_error) == (jobs.QUEUED, "ValueError: bozuk belge")
                waits.append(datetime.fromisoformat(job.run_after) - now.at)
                assert not worker.step(db)  # not due yet
                now.at = datetime.fromisoformat(job.run_after)
        assert (job.status, job.attempts) == (jobs.FAILED, MAX_ATTEMPTS)
        assert jobs.failures(db)[0].last_error == "ValueError: bozuk belge"
    assert waits == [timedelta(seconds=s) for s in (30, 60, 120, 240)]
    assert backoff(20) == timedelta(hours=1)


def test_a_job_of_an_unknown_kind_fails_at_once(ws):
    worker = Worker(ws.connect, {})
    with ws.db() as db:
        job_id = jobs.add(db, "gizemli")
        assert worker.step(db)
        assert jobs.get(db, job_id).status == jobs.FAILED
        assert "bilinmeyen iş türü" in jobs.get(db, job_id).last_error


def test_jobs_a_stop_left_running_are_queued_again_at_start(ws):
    with ws.db() as db:
        job_id = jobs.add(db, "x")
        jobs.claim(db, iso(datetime.now(ISTANBUL) + timedelta(seconds=1)))
        assert jobs.get(db, job_id).status == jobs.RUNNING
    done = threading.Event()
    worker = Worker(ws.connect, {"x": lambda _payload: done.set()}, idle=0.05)
    worker.start()
    try:
        assert done.wait(5), "the interrupted job did not run again"
    finally:
        worker.stop()
    with ws.db() as db:
        assert jobs.get(db, job_id).status == jobs.DONE


def test_the_worker_runs_what_is_queued_while_it_waits(ws):
    seen = []
    worker = Worker(ws.connect, {"x": lambda payload: seen.append(payload)}, idle=5.0)
    worker.start()
    try:
        with ws.db() as db:
            jobs.add(db, "x", {"n": 1})
        worker.wake()
        deadline = clock.monotonic() + 5
        while not seen and clock.monotonic() < deadline:
            clock.sleep(0.01)
    finally:
        worker.stop()
    assert seen == [{"n": 1}]


def test_a_job_that_starts_the_service_again_leaves_the_rest_of_the_queue(ws):
    seen: list[str] = []

    def install(_payload) -> None:
        seen.append("install")
        worker.finish_soon()  # what an installed update does before the service starts again

    worker = Worker(ws.connect, {"install": install, "x": lambda _p: seen.append("x")}, idle=0.05)
    with ws.db() as db:
        first = jobs.add(db, "install")
        second = jobs.add(db, "x")
    worker.start()
    try:
        deadline = clock.monotonic() + 5
        while clock.monotonic() < deadline:
            with ws.db() as db:
                if jobs.get(db, first).status == jobs.DONE:
                    break
            clock.sleep(0.01)
        clock.sleep(0.3)  # six idle checks: a worker that went on would have run the next job by now
    finally:
        worker.stop()
    assert seen == ["install"]
    with ws.db() as db:
        assert jobs.get(db, second).status == jobs.QUEUED  # the next version's


def test_periodic_jobs_run_once_a_period_and_once_after_a_sleep(ws):
    now = Clock(datetime(2026, 11, 1, 5, 0, tzinfo=ISTANBUL))
    periodic = [
        schedule.Periodic("backup.daily", schedule.daily(time(3, 0))),
        schedule.Periodic("poll", schedule.every(15)),
    ]
    worker = Worker(ws.connect, {"backup.daily": lambda _p: None, "poll": lambda _p: None}, periodic, now=now)

    def keys(db) -> list[str]:
        return [r["key"] for r in db.rows("SELECT key FROM jobs ORDER BY id")]

    with ws.db() as db:
        worker.step(db)
        assert keys(db) == ["backup.daily@2026-11-01", "poll@2026-11-01T05:00"]
        now.at += timedelta(minutes=10)
        while worker.step(db):
            pass
        assert len(keys(db)) == 2
        now.at += timedelta(minutes=5)  # 05:15: the next quarter
        worker.step(db)
        assert keys(db)[-1] == "poll@2026-11-01T05:15"
        now.at = datetime(2026, 11, 3, 9, 7, tzinfo=ISTANBUL)  # two days asleep
        worker.step(db)
        assert keys(db)[-2:] == ["backup.daily@2026-11-03", "poll@2026-11-03T09:00"]


def test_a_daily_period_begins_at_its_hour():
    period = schedule.daily(time(4, 0))
    assert period(datetime(2026, 11, 1, 3, 59)) == "2026-10-31"
    assert period(datetime(2026, 11, 1, 4, 0)) == "2026-11-01"
    assert schedule.every(60)(datetime(2026, 11, 1, 23, 59)) == "2026-11-01T23:00"
    with pytest.raises(ValueError):
        schedule.every(0)


def test_finished_jobs_are_forgotten_after_a_while(ws):
    with ws.db() as db:
        old = jobs.add(db, "x")
        jobs.claim(db, iso(datetime.now(ISTANBUL) + timedelta(seconds=1)))
        jobs.finish(db, old, "2026-09-01T00:00:00+00:00")
        fresh = jobs.add(db, "y")
        assert jobs.purge(db, "2026-10-01T00:00:00+00:00") == 1
        assert jobs.get(db, old) is None and jobs.get(db, fresh) is not None
