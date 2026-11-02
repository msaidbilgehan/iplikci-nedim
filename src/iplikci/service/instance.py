"""One service per data folder (architecture §19). The service holds a lock in run/ for as long as it runs and writes
beside it which process it is and where it listens; the command line reads that to tell whether the service runs.
The system frees the lock when the process ends, however it ends, so a crash leaves no stale lock behind."""

import json
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from ..app.workspace import Busy, file_lock
from ..settings.paths import write_private

LOCK_NAME = "servis.kilit"
HOLDER_NAME = "servis.json"
WAIT_SECONDS = 3.0  # a status check holds the lock for a moment; a service starting just then waits it out


@dataclass(frozen=True, slots=True)
class Holder:
    pid: int  # 0 when the service holds the lock but has not said yet who it is
    port: int
    started_at: str
    version: str


UNKNOWN = Holder(0, 0, "", "")


class AlreadyRunning(Exception):
    """Another process serves this data folder; the message says which (Turkish)."""

    def __init__(self, holder: Holder) -> None:
        self.holder = holder
        where = f" (süreç {holder.pid}, http://127.0.0.1:{holder.port})" if holder.pid else ""
        super().__init__(f"bu veri klasörünün servisi zaten çalışıyor{where}")


@contextmanager
def held(run: Path, holder: Holder, wait: float | None = None) -> Generator[None]:
    """Hold the service's lock while the block runs; AlreadyRunning when another process still holds it after
    `wait` seconds (WAIT_SECONDS by default)."""
    with ExitStack() as stack:
        try:
            stack.enter_context(file_lock(run, LOCK_NAME, WAIT_SECONDS if wait is None else wait))
        except Busy:
            raise AlreadyRunning(current(run) or UNKNOWN) from None
        record = run / HOLDER_NAME
        write_private(record, json.dumps(asdict(holder)))
        try:
            yield
        finally:
            record.unlink(missing_ok=True)  # what this process wrote about itself


def say(run: Path, holder: Holder) -> None:
    """Say again who holds the lock, from inside `held`: a backup put back at the start brings its own port."""
    write_private(run / HOLDER_NAME, json.dumps(asdict(holder)))


def wait_stopped(run: Path, seconds: float) -> Holder | None:
    """Wait up to `seconds` for the process serving this data folder to end; the one still serving it, or None. A
    service told to stop finishes its requests first, and a program replaced under it would lose its files."""
    try:
        with file_lock(run, LOCK_NAME, seconds):
            return None
    except Busy:
        return current(run) or UNKNOWN


def current(run: Path) -> Holder | None:
    """The service that holds this data folder's lock, or None when no process does."""
    try:
        with file_lock(run, LOCK_NAME, timeout=0.0):
            return None
    except Busy:
        return _read(run / HOLDER_NAME)


def _read(record: Path) -> Holder:
    try:
        found = json.loads(record.read_text(encoding="utf-8"))
        return Holder(int(found["pid"]), int(found["port"]), str(found["started_at"]), str(found["version"]))
    except (OSError, ValueError, KeyError, TypeError):  # not written yet, or half written
        return UNKNOWN
