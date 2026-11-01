"""The service's background work (ADR-0014): what each kind of job does, which ones recur, and how the other use
cases ask for them. The analysis is made again after new documents and once a day, just after midnight (a new day
can end a month); each time the feed compares it with the last one and records the difference as events."""

from datetime import UTC, date, datetime, time, timedelta

from ..feed import snapshot
from ..jobs.schedule import Periodic, daily, every
from ..jobs.worker import Handler
from ..storage import events, feed_state, jobs
from . import access, mail
from .analysis import analyze
from .kinds import PURGE, REFRESH
from .workspace import Workspace

SNAPSHOT = "snapshot"
JOBS_KEPT = timedelta(days=30)

PERIODIC = (
    Periodic(REFRESH, daily(time(0, 5))),
    Periodic(PURGE, daily(time(4, 0))),
    # ADR-0015: the IMAP connector's fallback beside IDLE; it finds nothing to do for the browser extension.
    Periodic(mail.FETCH_JOB, every(15)),
)


def handlers(ws: Workspace) -> dict[str, Handler]:
    """What each kind of job does in ws."""
    return {
        REFRESH: lambda _payload: refresh(ws),
        PURGE: lambda _payload: purge(ws),
        mail.FETCH_JOB: lambda _payload: poll_mail(ws),
    }


def request_refresh(ws: Workspace) -> int | None:
    """Ask the service to make the analysis again; asked twice before it starts, it does it once."""
    with ws.db() as db:
        return jobs.add(db, REFRESH)


def refresh(ws: Workspace, today: date | None = None) -> list[str]:
    """Read what needs reading, make the analysis and its outputs again, and record what changed since the last
    time as events; the kinds recorded. The events and the new snapshot are saved together, so a stop between them
    can neither lose a change nor tell it twice."""
    day = today or date.today()
    a = analyze(ws, write=True, today=day)
    after = snapshot.take(a.dataset, a.months, day)
    with ws.db() as db, db.transaction():
        changes = snapshot.diff(snapshot.Snapshot.load(feed_state.load(db, SNAPSHOT)), after)
        for change in changes:
            events.append(db, change.kind, change.target, **change.detail)
        feed_state.save(db, SNAPSHOT, after.dump())
    return [change.kind for change in changes]


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


def purge(ws: Workspace) -> None:
    """Forget expired sessions and the jobs that finished more than a month ago."""
    with ws.db() as db:
        access.purge_sessions(db)
        jobs.purge(db, (datetime.now(UTC) - JOBS_KEPT).replace(microsecond=0).isoformat())
