"""The service in the foreground: the API on 127.0.0.1 at the configured port (ADR-0012: never another address). One
service runs per data folder; the service manager starts the same command in the background (`manager`)."""

import logging
import os
import re
import signal
import sys
import threading
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

import uvicorn

from .. import __version__
from ..api.app import create_app
from ..api.context import Context
from ..app import access, background, calls, extension, fx, lifecycle, mail, telegram, update
from ..app.workspace import Workspace
from ..ingest.inbox import InboxWatcher
from ..ingest.mail.idle import IdleWatcher
from ..ingest.telegram import BotWatcher, Heard
from ..jobs.worker import Worker
from . import instance, logs

HOST = "127.0.0.1"
GRACE_SECONDS = 5  # how long a stop waits for open requests: the event streams would hold it for minutes

log = logging.getLogger("iplikci.service")


def _say(text: str) -> None:
    print(text, flush=True)  # at once, also when the output goes to a file


_VERSION = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)
PACKAGE = Path(__file__).resolve().parent.parent  # the program's files, as the running process imported them
PROGRAM_CHECK_SECONDS = 60.0


def version_on_disk(package: Path = PACKAGE) -> str | None:
    """The version the program's files on disk hold now; None while they cannot be read (being replaced)."""
    try:
        found = _VERSION.search((package / "__init__.py").read_text(encoding="utf-8"))
    except OSError:
        return None
    return found[1] if found else None


class ProgramWatch:
    """Ends the service to start again with the program on disk once that is another version: an update dragged
    over the app (macOS) replaces the files under the running process, whose new reading processes and pages would no
    longer match it. The new version must be seen twice in a row, so that a copy still being made is not started."""

    def __init__(
        self, life: "Life", found: Callable[[], str | None] = version_on_disk, every: float = PROGRAM_CHECK_SECONDS
    ) -> None:
        self.life = life
        self.found = found
        self.every = every
        self._stop = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._run, name="program-watch", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        seen: str | None = None
        while not self._stop.wait(self.every):
            now = self.found()
            if now is None or now == __version__:
                seen = None
                continue
            if now == seen:
                log.info("the program on disk is version %s; the service starts again with it", now)
                self.life.end(lifecycle.RESTART)
                return
            seen = now


class Life:
    """The running service's own end (app.lifecycle): the server stops after the responses being written, and the
    process exits with the code asked for."""

    def __init__(self) -> None:
        self.server: uvicorn.Server | None = None
        self.code = lifecycle.STOP

    def end(self, code: int) -> None:
        self.code = code
        if self.server is not None:
            self.server.should_exit = True

    def ending(self) -> bool:
        return self.server is not None and self.server.should_exit  # uvicorn sets it on the system's stop too


def context(ws: Workspace, life: Life | None = None) -> Context:
    """The service's context: the API token made or found, and the expired sessions forgotten."""
    with ws.db() as db:
        access.purge_sessions(db)
    return Context(ws=ws, token=access.ensure_api_token(), lifecycle=life)


def worker(ws: Workspace, life: "Life | None" = None) -> Worker:
    """The job worker; an update it installs ends the service through life, to start again with the new version."""
    restart = (lambda: life.end(lifecycle.RESTART)) if life is not None else (lambda: None)
    return Worker(ws.connect, background.handlers(ws, restart), background.PERIODIC)


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


def bot_watcher(ws: Workspace, jobs: Worker) -> BotWatcher:
    def listen() -> Heard:
        heard = telegram.listen(ws)
        if heard is Heard.READ:
            jobs.wake()  # a document sent to the bot may wait in the queue now
        return heard

    return BotWatcher(listen)


def run(ws: Workspace, announce: Callable[[str], None] = _say) -> int:
    """Serve until interrupted (KeyboardInterrupt) or ended from the interface; the exit code (app.lifecycle).
    instance.AlreadyRunning when another process serves this data folder. A stop the system asks for (SIGTERM, as
    launchd and systemd send) ends the service as Ctrl+C does: the worker finishes its job first. Uvicorn would
    otherwise raise the signal again after its own shutdown and end the process before that. What the service
    creates is the user's alone, and its log goes to logs/ (architecture §22). A backup a restore asked for is put
    back first, before anything opens the database, and the service goes on with the backup's settings; the browser
    extension's folder, once made, is brought up to date with the program, and an update that ended the last run is
    told and its leftovers removed. A removal that asked for it moves the data
    folder to the Trash last, once the lock, the log and the output file have let go of it."""
    output = _console_to_file(ws)
    holder = instance.Holder(os.getpid(), ws.port, datetime.now(UTC).isoformat(timespec="seconds"), __version__)
    umask = os.umask(0o077)
    on_term = signal.signal(signal.SIGTERM, signal.default_int_handler)
    to_trash = False
    try:
        with instance.held(ws.run, holder), logs.kept(ws.logs):
            log.info("service %s starting on port %d", __version__, ws.port)
            lifecycle.drop_stale_removal(ws)
            if lifecycle.apply_pending_restore(ws) is not None:
                ws = Workspace.load(ws.home)  # the backup's settings: its port, its e-mail way, its names
                holder = replace(holder, port=ws.port)
                instance.say(ws.run, holder)
            extension.refresh(ws)
            update.finish(ws)  # how the update that ended the last run went; the old version's files go
            try:
                code = _serve(ws, announce)
            except Exception:
                log.exception("the service stopped on an error")
                raise
            except KeyboardInterrupt:
                log.info("service stopped")
                raise
            log.info("service stopped%s", " to start again" if code == lifecycle.RESTART else "")
            to_trash = lifecycle.removal_asked(ws, code)
            if to_trash:
                log.info("the data folder goes to the Trash as the service ends")
    finally:
        signal.signal(signal.SIGTERM, on_term)
        os.umask(umask)
    if to_trash:
        _close(output)
        moved = lifecycle.move_data_to_trash(ws)
        announce(f"Veri klasörü çöp kutusuna taşındı: {moved}" if moved else f"Veri klasörü taşınamadı: {ws.home}")
    return code


def _serve(ws: Workspace, announce: Callable[[str], None]) -> int:
    """The login link printed at start opens the interface once, within two minutes; it is printed only to a
    terminal, never into a file. The worker starts first: the jobs a stop interrupted run again, the analysis is made
    again in case the readers changed since the last run, and the exchange rates' history is fetched where days are
    missing. The IMAP watcher waits for a set-up account and then for its new mail; the inbox watcher hands over what
    is dropped into the inbox folder, and the Telegram bot's ear what its paired chat sends it."""
    life = Life()
    ctx = context(ws, life)
    calls.take_waiting(ws)  # the MCP calls answered while the service was down, into the audit log
    app = create_app(ctx)
    jobs = worker(ws, life)
    background.request_refresh(ws)
    fx.request_missing(ws)
    jobs.start()
    ear = watcher(ws, jobs)
    ear.start()
    inbox = inbox_watcher(ws, jobs)
    inbox.start()
    bot = bot_watcher(ws, jobs)
    bot.start()
    program = ProgramWatch(life)
    program.start()
    announce(f"İplikçi Nedim servisi http://{HOST}:{ws.port} adresinde çalışıyor (durdurmak için Ctrl+C).")
    if sys.stdout is not None and sys.stdout.isatty():
        announce(f"Arayüz için tek kullanımlık giriş bağlantısı: {ctx.login_url(ctx.keys.issue())}")
    # No access log: a login link's key would land in it. No logging set-up of uvicorn's own: its records join the
    # service's log.
    config = uvicorn.Config(
        app,
        host=HOST,
        port=ws.port,
        access_log=False,
        log_level="warning",
        log_config=None,
        server_header=False,
        timeout_graceful_shutdown=GRACE_SECONDS,
    )
    life.server = uvicorn.Server(config)
    try:
        life.server.run()
    finally:
        program.stop()
        bot.stop()
        inbox.stop()
        ear.stop()
        jobs.stop()
    return life.code


def _console_to_file(ws: Workspace) -> TextIO | None:
    """pythonw, which the Windows task runs, has no console: what the service prints goes to the file where launchd
    and systemd send it on the other systems. The file stays open for the life of the process, unless the data
    folder goes to the Trash; the file opened here, or None."""
    if sys.stdout is not None and sys.stderr is not None:
        return None
    ws.logs.mkdir(parents=True, exist_ok=True)
    output = open(ws.logs / logs.OUTPUT_NAME, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = sys.stdout or output
    sys.stderr = sys.stderr or output
    return output


def _close(output: TextIO | None) -> None:
    """Close the output file of a process without a console, so that Windows can move the folder it is in."""
    if output is None:
        return
    if sys.stdout is output:
        sys.stdout = None  # pythonw's own value: no console
    if sys.stderr is output:
        sys.stderr = None
    output.close()
