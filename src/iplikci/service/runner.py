"""The service in the foreground: the API on 127.0.0.1 at the configured port (ADR-0012: never another address)."""

from collections.abc import Callable

import uvicorn

from ..api.app import create_app
from ..api.context import Context
from ..app import access, background, mail
from ..app.workspace import Workspace
from ..ingest.inbox import InboxWatcher
from ..ingest.mail.idle import IdleWatcher
from ..jobs.worker import Worker

HOST = "127.0.0.1"


def _say(text: str) -> None:
    print(text, flush=True)  # at once, also when the output goes to a file


def context(ws: Workspace) -> Context:
    """The service's context: the API token made or found, and the expired sessions forgotten."""
    with ws.db() as db:
        access.purge_sessions(db)
    return Context(ws=ws, token=access.ensure_api_token())


def worker(ws: Workspace) -> Worker:
    return Worker(ws.connect, background.handlers(ws), background.PERIODIC)


def watcher(ws: Workspace, jobs: Worker) -> IdleWatcher:
    def news() -> None:
        mail.request_fetch(ws)
        jobs.wake()

    return IdleWatcher(lambda: mail.watch_target(ws), news, lambda message: mail.refused(ws, message))


def inbox_watcher(ws: Workspace, jobs: Worker) -> InboxWatcher:
    def settled() -> None:
        background.request_inbox(ws)
        jobs.wake()

    return InboxWatcher(ws.inbox, settled)


def run(ws: Workspace, announce: Callable[[str], None] = _say) -> None:
    """Serve until interrupted. The login link printed at start opens the interface once, within two minutes.
    The worker starts first: the jobs a stop interrupted run again, and the analysis is made again in case the
    readers changed since the last run. The IMAP watcher waits for a set-up account and then for its new mail; the
    inbox watcher hands over what is dropped into the inbox folder."""
    ctx = context(ws)
    app = create_app(ctx)
    jobs = worker(ws)
    background.request_refresh(ws)
    jobs.start()
    ear = watcher(ws, jobs)
    ear.start()
    inbox = inbox_watcher(ws, jobs)
    inbox.start()
    announce(f"İplikçi Nedim servisi http://{HOST}:{ws.port} adresinde çalışıyor (durdurmak için Ctrl+C).")
    announce(f"Arayüz için tek kullanımlık giriş bağlantısı: {ctx.login_url(ctx.keys.issue())}")
    # No access log: a login link's key would land in it.
    config = uvicorn.Config(app, host=HOST, port=ws.port, access_log=False, log_level="warning", server_header=False)
    try:
        uvicorn.Server(config).run()
    finally:
        inbox.stop()
        ear.stop()
        jobs.stop()
