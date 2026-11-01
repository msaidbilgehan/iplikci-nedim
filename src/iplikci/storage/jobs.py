"""The job queue (ADR-0014) in SQLite. A queued job waits for its time and one worker runs it; a failed attempt
waits longer each time; a job with a key is added once; the same job without a key is not queued twice while it
waits. Times are ISO 8601 in UTC (`db.now()`), so they compare as text."""

import json
from dataclasses import dataclass
from typing import Any

from .db import Database, now

QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"


@dataclass(frozen=True, slots=True)
class Job:
    id: int
    kind: str
    payload: dict[str, Any]
    key: str
    status: str
    attempts: int
    run_after: str
    created_at: str
    started_at: str
    finished_at: str
    last_error: str


def _job(row: Any) -> Job:
    return Job(
        int(row["id"]),
        str(row["kind"]),
        json.loads(row["payload"]),
        str(row["key"]),
        str(row["status"]),
        int(row["attempts"]),
        str(row["run_after"]),
        str(row["created_at"]),
        str(row["started_at"]),
        str(row["finished_at"]),
        str(row["last_error"]),
    )


def add(
    db: Database, kind: str, payload: dict[str, Any] | None = None, key: str = "", run_after: str | None = None
) -> int | None:
    """Queue a job; its id, or None when its key was used already or the same job waits unstarted."""
    text = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
    at = now()
    with db.transaction():
        if not key and db.scalar(
            "SELECT 1 FROM jobs WHERE kind = ? AND payload = ? AND status = ? AND key = ''", (kind, text, QUEUED)
        ):
            return None
        cursor = db.execute(
            "INSERT OR IGNORE INTO jobs (kind, payload, key, status, run_after, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, text, key, QUEUED, run_after or at, at),
        )
        return cursor.lastrowid if cursor.rowcount else None


def get(db: Database, job_id: int) -> Job | None:
    row = db.one("SELECT * FROM jobs WHERE id = ?", (job_id,))
    return None if row is None else _job(row)


def claim(db: Database, at: str) -> Job | None:
    """The next due job, marked running with one more attempt; None when nothing is due."""
    with db.transaction():
        row = db.one(
            "SELECT * FROM jobs WHERE status = ? AND run_after <= ? ORDER BY run_after, id LIMIT 1", (QUEUED, at)
        )
        if row is None:
            return None
        db.execute(
            "UPDATE jobs SET status = ?, started_at = ?, attempts = attempts + 1 WHERE id = ?", (RUNNING, at, row["id"])
        )
    return get(db, int(row["id"]))


def finish(db: Database, job_id: int, at: str) -> None:
    with db.transaction():
        db.execute("UPDATE jobs SET status = ?, finished_at = ?, last_error = '' WHERE id = ?", (DONE, at, job_id))


def retry(db: Database, job_id: int, error: str, run_after: str) -> None:
    with db.transaction():
        db.execute(
            "UPDATE jobs SET status = ?, run_after = ?, last_error = ? WHERE id = ?", (QUEUED, run_after, error, job_id)
        )


def fail(db: Database, job_id: int, error: str, at: str) -> None:
    with db.transaction():
        db.execute(
            "UPDATE jobs SET status = ?, finished_at = ?, last_error = ? WHERE id = ?", (FAILED, at, error, job_id)
        )


def recover(db: Database) -> int:
    """Jobs a stopped service left running go back to the queue; how many."""
    with db.transaction():
        return db.execute("UPDATE jobs SET status = ? WHERE status = ?", (QUEUED, RUNNING)).rowcount


def next_due(db: Database) -> str | None:
    """When the earliest queued job may start; None when the queue is empty."""
    value = db.scalar("SELECT min(run_after) FROM jobs WHERE status = ?", (QUEUED,))
    return None if value is None else str(value)


def counts(db: Database) -> dict[str, int]:
    return {str(r["status"]): int(r["n"]) for r in db.rows("SELECT status, count(*) AS n FROM jobs GROUP BY status")}


def failures(db: Database, limit: int = 10) -> list[Job]:
    """The latest failed jobs, newest first."""
    rows = db.rows("SELECT * FROM jobs WHERE status = ? ORDER BY finished_at DESC, id DESC LIMIT ?", (FAILED, limit))
    return [_job(r) for r in rows]


def last_done(db: Database, kind: str) -> Job | None:
    row = db.one(
        "SELECT * FROM jobs WHERE kind = ? AND status = ? ORDER BY finished_at DESC, id DESC LIMIT 1", (kind, DONE)
    )
    return None if row is None else _job(row)


def purge(db: Database, before: str) -> int:
    """Forget the done and failed jobs that finished before `before`; how many. Their keys go with them, which is
    safe: the scheduler only ever adds the current period's key, and a period never comes back."""
    with db.transaction():
        return db.execute(
            "DELETE FROM jobs WHERE status IN (?, ?) AND finished_at != '' AND finished_at < ?", (DONE, FAILED, before)
        ).rowcount
