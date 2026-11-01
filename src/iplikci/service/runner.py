"""The service in the foreground: the API on 127.0.0.1 at the configured port (ADR-0012: never another address). One
service runs per data folder; the service manager starts the same command in the background (`manager`)."""

import logging
import os
import signal
import sys
from collections.abc import Callable
from datetime import UTC, datetime

import uvicorn

from .. import __version__
from ..api.app import create_app
from ..api.context import Context
from ..app import access, background, mail
from ..app.workspace import Workspace
from ..ingest.inbox import InboxWatcher
from ..ingest.mail.idle import IdleWatcher
from ..jobs.worker import Worker
from . import instance, logs

HOST = "127.0.0.1"

log = logging.getLogger("iplikci.service")


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
    """Serve until interrupted (KeyboardInterrupt); instance.AlreadyRunning when another process serves this data
    folder. A stop the system asks for (SIGTERM, as launchd and systemd send) ends the service as Ctrl+C does: the
    worker finishes its job first. Uvicorn would otherwise raise the signal again after its own shutdown and end the
    process before that. What the service creates is the user's alone, and its log goes to logs/ (architecture
    §22)."""
    _console_to_file(ws)
    holder = instance.Holder(os.getpid(), ws.port, datetime.now(UTC).isoformat(timespec="seconds"), __version__)
    umask = os.umask(0o077)
    on_term = signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        with instance.held(ws.run, holder), logs.kept(ws.logs):
            log.info("service %s starting on port %d", __version__, ws.port)
            try:
                _serve(ws, announce)
            except Exception:
                log.exception("the service stopped on an error")
                raise
            except KeyboardInterrupt:
                log.info("service stopped")
                raise
            log.info("service stopped")
    finally:
        signal.signal(signal.SIGTERM, on_term)
        os.umask(umask)


def _serve(ws: Workspace, announce: Callable[[str], None]) -> None:
    """The login link printed at start opens the interface once, within two minutes; it is printed only to a
    terminal, never into a file. The worker starts first: the jobs a stop interrupted run again, and the analysis is
    made again in case the readers changed since the last run. The IMAP watcher waits for a set-up account and then
    for its new mail; the inbox watcher hands over what is dropped into the inbox folder."""
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
    if sys.stdout is not None and sys.stdout.isatty():
        announce(f"Arayüz için tek kullanımlık giriş bağlantısı: {ctx.login_url(ctx.keys.issue())}")
    # No access log: a login link's key would land in it. No logging set-up of uvicorn's own: its records join the
    # service's log.
    config = uvicorn.Config(
        app, host=HOST, port=ws.port, access_log=False, log_level="warning", log_config=None, server_header=False
    )
    try:
        uvicorn.Server(config).run()
    finally:
        inbox.stop()
        ear.stop()
        jobs.stop()


def _console_to_file(ws: Workspace) -> None:
    """pythonw, which the Windows task runs, has no console: what the service prints goes to the file where launchd
    and systemd send it on the other systems. The file stays open for the life of the process."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    ws.logs.mkdir(parents=True, exist_ok=True)
    output = open(ws.logs / logs.OUTPUT_NAME, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = sys.stdout or output
    sys.stderr = sys.stderr or output
