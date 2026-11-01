"""The user's data folder as the program works with it: its layout, its settings, the vault and the database.

Every entry point opens one Workspace; all of them may run at once (the service, the MCP server, the command
line), so writes take the workspace's lock and the database serializes them again.
"""

import os
import sys
import time
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from ..parsers.common import set_business_names
from ..settings import config
from ..settings.paths import Layout
from ..storage import db
from ..vault.store import Vault

_LOCK_NAME = ".kilit"
BUSY = "başka bir işlem belgeleri işliyor; biraz sonra yeniden deneyin"


class Busy(Exception):
    """Another process is taking in or reading the documents right now."""


class StalePlan(Exception):
    """Something the plan covers changed after it was shown: show a fresh plan instead of applying."""


if sys.platform == "win32":
    import msvcrt

    def _try_lock(f: IO[str]) -> bool:
        f.seek(0)  # Windows locks bytes from the file position: always the first one
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:  # held by another process
            return False
        return True

    def _unlock(f: IO[str]) -> None:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _try_lock(f: IO[str]) -> bool:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def _unlock(f: IO[str]) -> None:
        fcntl.flock(f, fcntl.LOCK_UN)


@contextmanager
def file_lock(folder: Path, name: str = _LOCK_NAME, timeout: float = 120.0, busy: str = BUSY) -> Generator[None]:
    """One holder at a time across processes; another name is another lock (the e-mail fetch has its own)."""
    folder.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(folder / name, os.O_RDWR | os.O_CREAT, 0o600), "r+") as f:
        deadline = time.monotonic() + timeout
        while not _try_lock(f):
            if time.monotonic() > deadline:
                raise Busy(busy)
            time.sleep(0.2)
        try:
            yield
        finally:
            _unlock(f)


@dataclass(frozen=True)
class Workspace:
    layout: Layout
    settings: config.Settings
    # A database somewhere else and a vault only read: the rebuild check makes the database again beside the real
    # one and must never change the vault.
    database: Path | None = None
    read_only: bool = False

    @classmethod
    def load(cls, home: Path | None = None) -> "Workspace":
        """The data folder at home, else IPLIKCI_HOME, else the platform's (ADR-0002); created when missing.
        The company names reach the readers here: their documents are out of scope."""
        layout = Layout(home.expanduser().resolve()) if home else Layout.default()
        layout.ensure()
        settings = config.load(layout.settings)
        set_business_names(settings.identity.business_names)
        return cls(layout, settings)

    @property
    def home(self) -> Path:
        return self.layout.home

    @property
    def inbox(self) -> Path:
        return self.layout.inbox

    @property
    def exports(self) -> Path:
        return self.layout.exports

    @property
    def rules(self) -> Path:
        """The user's own category rules; the ones shipped with the app go under them."""
        return self.layout.personal_rules

    @property
    def rules_history(self) -> Path:
        return self.layout.rules_history

    @property
    def run(self) -> Path:
        return self.layout.run

    @property
    def logs(self) -> Path:
        return self.layout.logs

    @property
    def port(self) -> int:
        return self.settings.server.port

    @property
    def vault(self) -> Vault:
        return Vault(self.layout)

    def connect(self) -> db.Database:
        if self.database is not None:
            return db.connect(self.database, self.database.parent)
        return db.connect(self.layout.database, self.layout.backups)

    @contextmanager
    def db(self) -> Generator[db.Database]:
        database = self.connect()
        try:
            yield database
        finally:
            database.close()

    def lock(self, timeout: float = 120.0) -> AbstractContextManager[None]:
        return file_lock(self.run, _LOCK_NAME, timeout)

    def signature(self) -> tuple[object, ...]:
        """Changes whenever the documents, their readings, the annotations, the rules or the settings change:
        when an analysis is stale."""
        with self.db() as database:
            state = database.one(
                "SELECT (SELECT count(*) FROM documents), (SELECT max(added_at) FROM documents), "
                "(SELECT max(read_at) FROM documents), (SELECT count(*) FROM document_sources), "
                "(SELECT count(*) FROM annotations), (SELECT max(updated_at) FROM annotations), "
                "(SELECT count(*) FROM audit_log)"
            )
        files = tuple(_stamp(p) for p in (self.rules, self.layout.settings))
        return (tuple(state) if state else (), files)


def _stamp(path: Path) -> tuple[int, int] | None:
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return None
    return st.st_size, st.st_mtime_ns
