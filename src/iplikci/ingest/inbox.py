"""The inbox folder (F02): files dropped there are taken in without a plan once the folder has stayed quiet for 20
seconds, so a file still being copied or saved is never read half-written. The watcher only notices, by looking
every two seconds (the same on every system); taking the files in is a job of the service's worker."""

import logging
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

QUIET_SECONDS = 20.0
LOOK_EVERY = 2.0

log = logging.getLogger("iplikci.inbox")

type Shape = frozenset[tuple[str, int, int]]


def shape(folder: Path) -> Shape:
    """The files waiting in folder, with their sizes and times; hidden files and folders (unfinished uploads,
    .DS_Store) are left out."""
    found: set[tuple[str, int, int]] = set()
    if not folder.is_dir():
        return frozenset()
    for here, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if name.startswith("."):
                continue
            path = Path(here) / name
            try:
                st = path.stat()
            except FileNotFoundError:  # moved away while we looked
                continue
            found.add((str(path.relative_to(folder)), st.st_size, st.st_mtime_ns))
    return frozenset(found)


class InboxWatcher:
    def __init__(
        self,
        folder: Path,
        on_settled: Callable[[], None],
        *,
        quiet: float = QUIET_SECONDS,
        every: float = LOOK_EVERY,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._folder = folder
        self._on_settled = on_settled
        self._quiet = quiet
        self._every = every
        self._clock = clock
        self._seen: Shape = frozenset()
        self._since = clock()
        self._told: Shape | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def look(self) -> bool:
        """One look: whether files wait and have not changed for the quiet time; once per state of the folder."""
        now = shape(self._folder)
        if now != self._seen:
            self._seen, self._since = now, self._clock()
            return False
        if not now or now == self._told or self._clock() - self._since < self._quiet:
            return False
        self._told = now
        return True

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="iplikci-gelen", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _loop(self) -> None:
        while not self._stop.wait(self._every):
            try:
                if self.look():
                    self._on_settled()
            except OSError:  # the folder went away for a moment (a network drive, a rename)
                log.warning("the inbox could not be read")
