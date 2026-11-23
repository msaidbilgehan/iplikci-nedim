"""The service's background work (ADR-0014): what each kind of job does, which ones recur, and how the other use
cases ask for them. The analysis is made again after new documents and once a day, just after midnight (a new day
can end a month); each time the feed compares it with the last one and records the difference as events, and the
notifications follow at once (they also run every five minutes). A backup is made every night and its restore
rehearsed every month. The exchange rates are fetched every day from 16:30, the history's missing days with them,
and TÜFE every day at 10:30 when the user gave an EVDS key. A document sent to the Telegram bot is fetched and taken in
as its own job, queued by the service's ear for the bot (ADR-0021). Every three hours the service checks whether a newer
version is released and, as the settings say, installs it (ADR-0022)."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta

from ..domain.codes import Actor, BackupReason
from ..feed import snapshot
from ..jobs.schedule import Periodic, daily, every, monthly
from ..jobs.worker import Handler
from ..storage import audit, events, feed_state, jobs
from ..vault import trash
from . import access, backup, bridge, fx, intake, mail, notify, outlook, prices, telegram, update, uploads
from .analysis import analyze
from .kinds import (
    BACKUP_DAILY,
    BACKUP_NOW,
    BACKUP_REHEARSAL,
    BRIDGE_CHECK,
    INBOX_TAKE,
    NOTIFY,
    PURGE,
    REFRESH,
    TELEGRAM_DOCUMENT,
)
from .workspace import Busy, Workspace

SNAPSHOT = "snapshot"
JOBS_KEPT = timedelta(days=30)
UPLOADS_KEPT = timedelta(days=1)  # an upload batch nobody applied goes to the Trash after this

PERIODIC = (
    Periodic(REFRESH, daily(time(0, 5))),
    Periodic(PURGE, daily(time(4, 0))),
    # ADR-0015: the IMAP connector's fallback beside IDLE; it finds nothing to do for the browser extension.
    Periodic(mail.FETCH_JOB, every(15)),
    Periodic(BACKUP_DAILY, daily(backup.DAILY_AT)),
    Periodic(BACKUP_REHEARSAL, monthly(time(4, 30))),
    Periodic(BRIDGE_CHECK, every(60)),
    # The events the other jobs record, a failed attempt's next try and the digest after the quiet hours; a
    # refresh asks for the notifications at once (ADR-0010).
    Periodic(NOTIFY, every(5)),
    # The day's bulletin, and the history where days are missing (architecture §15).
    Periodic(fx.FETCH_JOB, daily(fx.DAILY_AT), {"history": True}),
    # The month's TÜFE, with the user's EVDS key only; without one the job asks nothing.
    Periodic(prices.FETCH_JOB, daily(prices.DAILY_AT)),
    # Whether a newer version is released (ADR-0022); with [updates] mode = "off" the job asks nothing.
    Periodic(update.CHECK_JOB, every(update.CHECK_EVERY)),
)


def _no_restart() -> None:
    """Outside the service there is nothing to start again: the next start runs the new version."""


def handlers(ws: Workspace, restart: Callable[[], None] = _no_restart) -> dict[str, Handler]:
    """What each kind of job does in ws; restart ends the service to start again, as an installed update needs."""
    return {
        REFRESH: lambda _payload: (refresh(ws), request_notify(ws)),
        NOTIFY: lambda _payload: notify.run(ws),
        PURGE: lambda _payload: purge(ws),
        mail.FETCH_JOB: lambda _payload: poll_mail(ws),
        INBOX_TAKE: lambda _payload: take_inbox(ws),
        BACKUP_DAILY: lambda _payload: back_up(ws, BackupReason.DAILY),
        BACKUP_NOW: lambda _payload: back_up(ws, BackupReason.MANUAL),
        BACKUP_REHEARSAL: lambda _payload: rehearse(ws),
        BRIDGE_CHECK: lambda _payload: bridge.check_silence(ws),
        fx.FETCH_JOB: lambda payload: fetch_rates(ws, history=bool(payload.get("history", True))),
        prices.FETCH_JOB: lambda _payload: prices.fetch(ws),
        TELEGRAM_DOCUMENT: lambda payload: telegram.take_document(ws, payload),
        update.CHECK_JOB: lambda payload: update.check(ws, forced=bool(payload.get("forced", False))),
        update.INSTALL_JOB: lambda payload: update.install_update(ws, restart, asked=bool(payload.get("asked", False))),
    }


def request_refresh(ws: Workspace) -> int | None:
    """Ask the service to make the analysis again; asked twice before it starts, it does it once."""
    with ws.db() as db:
        return jobs.add(db, REFRESH)


def refresh(ws: Workspace, today: date | None = None) -> list[str]:
    """Read what needs reading, make the analysis and its outputs again, and record as events what changed since the
    last time and what the days ahead hold that was not told yet; the kinds recorded. The events and the new
    snapshot are saved together, so a stop between them can neither lose a change nor tell it twice."""
    day = today or date.today()
    a = analyze(ws, write=True, today=day)
    after = snapshot.take(a.dataset, a.insights, a.months, day, outlook.card_dues(a.dataset))
    with ws.db() as db, db.transaction():
        before = snapshot.Snapshot.load(feed_state.load(db, SNAPSHOT))
        changes = snapshot.diff(before, after)
        for change in changes:
            events.append(db, change.kind, change.target, **change.detail)
        feed_state.save(db, SNAPSHOT, after.keeping(before).dump())
    return [change.kind for change in changes]


def request_notify(ws: Workspace) -> None:
    """Ask the service to turn the new events into notifications and send them; asked twice before it starts, it
    does it once."""
    with ws.db() as db:
        jobs.add(db, NOTIFY)


def poll_mail(ws: Workspace) -> None:
    """Fetch the new messages over IMAP; with more waiting, the next fetch follows at once. Without an account, or
    with the connector stopped by a refused login, there is nothing to do: the mail state holds the error and the
    user was told once."""
    try:
        fetched = mail.fetch(ws, wait=5)
    except mail.MailError:
        return
    if fetched.more:
        mail.request_fetch(ws)


def fetch_rates(ws: Workspace, history: bool) -> int:
    """Fetch the exchange rates (app.fx); how many days' rates came. A run that stopped at its limit queues the next
    behind the jobs waiting already; the run that ends the history, or brings new rates, makes the analysis again — once,
    not after every piece of a long history. A provider's failure is recorded for the System screen, never raised: the
    job is done, and a later run tries again."""
    done = fx.fetch(ws, history)
    if done.more:
        fx.request(ws, history=True)
    elif done.stored or history:
        request_refresh(ws)
    return done.stored


def take_inbox(ws: Workspace) -> int:
    """Take in what waits in the inbox, without showing a plan: putting files there is the user's consent (F02).
    A file that changes between the plan and its use fails the attempt, which runs again later. How many documents
    were kept."""
    applied = intake.apply(ws, intake.plan_inbox(ws), Actor.SYSTEM)
    return len(applied.stored)


def request_inbox(ws: Workspace) -> None:
    with ws.db() as db:
        jobs.add(db, INBOX_TAKE)


def purge(ws: Workspace) -> None:
    """Forget expired sessions and the jobs that finished more than a month ago; upload batches nobody applied go to
    the system Trash, with an audit entry (ADR-0003: nothing is deleted for good)."""
    with ws.db() as db:
        access.purge_sessions(db)
        jobs.purge(db, (datetime.now(UTC) - JOBS_KEPT).replace(microsecond=0).isoformat())
        for batch in uploads.abandoned_batches(ws, UPLOADS_KEPT.total_seconds()):
            where = trash.move_to_system_trash(batch)
            audit.record(db, Actor.SYSTEM, "upload.abandoned", "", batch=batch.name, trash=where.name)


def back_up(ws: Workspace, reason: BackupReason) -> str:
    """Make a backup and delete the expired ones; the backup's name. A backup that cannot be made is told once a
    day (backup.failed) and tried again later."""
    try:
        made = backup.take(ws, reason)
        backup.prune(ws)
    except (OSError, sqlite3.Error, backup.BackupError, Busy) as exc:
        with ws.db() as db:
            events.record(db, backup.FAILED, date.today().isoformat(), stage="backup", error=type(exc).__name__)
        raise
    return made.name


def request_backup(ws: Workspace) -> None:
    """Ask the service for a backup now; asked twice before it starts, it makes one."""
    with ws.db() as db:
        jobs.add(db, BACKUP_NOW)


def rehearse(ws: Workspace) -> bool:
    """Rehearse restoring the newest backup; a rehearsal that fails is told once that month (backup.failed). With no
    backup yet the attempt fails and is retried a few times; the scheduler queues the day's backup before it, so a new
    service rehearses the backup it has just made. Whether it passed."""
    result = backup.rehearse(ws)
    if not result.ok:
        with ws.db() as db:
            events.record(
                db,
                backup.FAILED,
                result.at[:7],
                stage="rehearsal",
                problems=len(result.problems),
                differences=len(result.differences),
            )
    return result.ok
