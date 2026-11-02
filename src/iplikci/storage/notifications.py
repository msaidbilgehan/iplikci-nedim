"""The notifications (ADR-0010): one row per rule, event key and channel, with the text as it was sent and where it
stands. A row is added once (`add` ignores a second one), sent once, and kept as the history."""

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

from .db import Database

PENDING, SENT, HELD, DIGESTED, FAILED = "pending", "sent", "held", "digested", "failed"


@dataclass(frozen=True, slots=True)
class Notification:
    id: int
    created_at: str
    rule: str
    event_id: int
    kind: str
    key: str
    channel: str
    detail: str
    title: str
    body: str
    status: str
    urgent: bool = False  # its rule sends it in the quiet hours too
    attempts: int = 0
    next_at: str = ""
    sent_at: str = ""
    error: str = ""
    read_at: str = ""


def _notification(row: sqlite3.Row) -> Notification:
    return Notification(
        int(row["id"]),
        str(row["created_at"]),
        str(row["rule"]),
        int(row["event_id"]),
        str(row["kind"]),
        str(row["key"]),
        str(row["channel"]),
        str(row["detail"]),
        str(row["title"]),
        str(row["body"]),
        str(row["status"]),
        bool(row["urgent"]),
        int(row["attempts"]),
        str(row["next_at"]),
        str(row["sent_at"]),
        str(row["error"]),
        str(row["read_at"]),
    )


_COLUMNS = (
    "created_at, rule, event_id, kind, key, channel, detail, title, body, status, urgent, attempts, next_at, sent_at, "
    "error, read_at"
)


def _values(n: Notification) -> tuple[object, ...]:
    return (
        n.created_at,
        n.rule,
        n.event_id,
        n.kind,
        n.key,
        n.channel,
        n.detail,
        n.title,
        n.body,
        n.status,
        int(n.urgent),
        n.attempts,
        n.next_at,
        n.sent_at,
        n.error,
        n.read_at,
    )


def add(db: Database, n: Notification) -> int | None:
    """Add a notification (its id is ignored); the new id, or None when its rule, event key and channel have one."""
    with db.transaction():
        cursor = db.execute(
            f"INSERT OR IGNORE INTO notifications ({_COLUMNS}) VALUES ({', '.join('?' * 16)})", _values(n)
        )
    return cursor.lastrowid if cursor.rowcount else None


def restore(db: Database, n: Notification) -> None:
    """A notification as a dump of the primary data holds it."""
    with db.transaction():
        db.execute(f"INSERT INTO notifications ({_COLUMNS}) VALUES ({', '.join('?' * 16)})", _values(n))


def due(db: Database, at: str) -> list[Notification]:
    """The pending notifications whose time has come, oldest first."""
    rows = db.rows("SELECT * FROM notifications WHERE status = ? AND next_at <= ? ORDER BY id", (PENDING, at))
    return [_notification(r) for r in rows]


def held(db: Database, channel: str) -> list[Notification]:
    """What waits for the channel's next digest, oldest first."""
    rows = db.rows("SELECT * FROM notifications WHERE status = ? AND channel = ? ORDER BY id", (HELD, channel))
    return [_notification(r) for r in rows]


def sent(db: Database, ids: Iterable[int], at: str, status: str = SENT) -> None:
    with db.transaction():
        db.executemany(
            "UPDATE notifications SET status = ?, sent_at = ?, error = '' WHERE id = ?", [(status, at, i) for i in ids]
        )


def retry(db: Database, notification_id: int, error: str, next_at: str) -> None:
    """A failed attempt: one more counted, the next not before next_at."""
    with db.transaction():
        db.execute(
            "UPDATE notifications SET attempts = attempts + 1, error = ?, next_at = ? WHERE id = ?",
            (error, next_at, notification_id),
        )


def fail(db: Database, notification_id: int, error: str) -> None:
    """The last attempt failed too: never tried again."""
    with db.transaction():
        db.execute(
            "UPDATE notifications SET status = ?, attempts = attempts + 1, error = ? WHERE id = ?",
            (FAILED, error, notification_id),
        )


def hold(db: Database, notification_id: int) -> None:
    with db.transaction():
        db.execute("UPDATE notifications SET status = ? WHERE id = ?", (HELD, notification_id))


def held_failed(db: Database, ids: Iterable[int], error: str, next_at: str) -> None:
    """A digest that could not be sent: its notifications wait for the next one, not before next_at, with one more
    attempt counted and the reason."""
    with db.transaction():
        db.executemany(
            "UPDATE notifications SET attempts = attempts + 1, error = ?, next_at = ? WHERE id = ?",
            [(error, next_at, i) for i in ids],
        )


def give_up(db: Database, ids: Iterable[int], error: str) -> None:
    """Notifications no channel will carry any more (it was turned off, or stopped by a refused login)."""
    with db.transaction():
        db.executemany("UPDATE notifications SET status = ?, error = ? WHERE id = ?", [(FAILED, error, i) for i in ids])


def sent_since(db: Database, channel: str, since: str) -> int:
    """How many messages went out on the channel since then: each notification sent alone, and each digest once."""
    alone = db.scalar(
        "SELECT COUNT(*) FROM notifications WHERE channel = ? AND status = ? AND sent_at >= ?", (channel, SENT, since)
    )
    digests = db.scalar(
        "SELECT COUNT(DISTINCT sent_at) FROM notifications WHERE channel = ? AND status = ? AND sent_at >= ?",
        (channel, DIGESTED, since),
    )
    return int(alone or 0) + int(digests or 0)


def last_digest(db: Database, channel: str) -> str:
    """When the channel's last digest went out; "" when none did."""
    return str(
        db.scalar("SELECT MAX(sent_at) FROM notifications WHERE channel = ? AND status = ?", (channel, DIGESTED)) or ""
    )


def page(db: Database, before: int = 0, limit: int = 50, channel: str = "") -> list[Notification]:
    """The newest notifications first, those with an id below before when it is given; of one channel, or of all."""
    where: list[str] = ["id < ?"] if before else []
    params: list[object] = [before] if before else []
    if channel:
        where.append("channel = ?")
        params.append(channel)
    clause = f"WHERE {' AND '.join(where)} " if where else ""
    rows = db.rows(f"SELECT * FROM notifications {clause}ORDER BY id DESC LIMIT ?", (*params, limit))
    return [_notification(r) for r in rows]


def unread(db: Database, channel: str) -> int:
    return int(db.scalar("SELECT COUNT(*) FROM notifications WHERE channel = ? AND read_at = ''", (channel,)) or 0)


def mark_read(db: Database, channel: str, at: str, up_to: int | None = None) -> int:
    """The channel's notifications seen, up to the id given or all; how many were unread."""
    with db.transaction():
        cursor = db.execute(
            "UPDATE notifications SET read_at = ? WHERE channel = ? AND read_at = '' AND id <= ?",
            (at, channel, up_to if up_to is not None else 2**62),
        )
    return cursor.rowcount


def every(db: Database) -> list[Notification]:
    return [_notification(r) for r in db.rows("SELECT * FROM notifications ORDER BY id")]


def version(db: Database) -> str:
    """A word that changes whenever a notification is made or settles (sent, digested or given up): the event stream
    tells the interface by it that the box and the history moved."""
    row = db.one(
        "SELECT COALESCE(MAX(id), 0) AS newest, "
        "COALESCE(SUM(status IN ('sent', 'digested', 'failed')), 0) AS settled FROM notifications"
    )
    return f"{row['newest']}:{row['settled']}" if row else "0:0"


def counts(db: Database) -> dict[str, int]:
    """How many notifications have each status."""
    return {
        str(r["status"]): int(r["n"]) for r in db.rows("SELECT status, COUNT(*) AS n FROM notifications GROUP BY 1")
    }
