"""The service's sync rounds (ADR-0025): one thread runs a round every minute, at once when something asks for it (the
sync just turned on, a change the user made), and again after a short pause while originals wait to be copied, so a
first copy of a whole archive goes on without holding up anything else. What a round does is the use case's
(app.sync); a round that fails waits for the next minute."""

import logging
import threading
from collections.abc import Callable

log = logging.getLogger("iplikci.sync")

EVERY = 60.0  # seconds between rounds
PAUSE = 2.0  # seconds between rounds while originals wait to be copied


class SyncWatcher:
    def __init__(self, run_round: Callable[[], bool], every: float = EVERY, pause: float = PAUSE) -> None:
        self._run_round = run_round  # one round; whether more waits to be done at once
        self._every = every
        self._pause = pause
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="iplikci-sync", daemon=True)
        self._thread.start()

    def wake(self) -> None:
        """Run a round now rather than at the next minute."""
        self._wake.set()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop after the round running now; a copy waiting on the sync service is left to end with the process."""
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.clear()
            try:
                more = self._run_round()
            except Exception:  # the thread's boundary: a failed round waits for the next one, never ends the thread
                log.exception("a sync round failed")
                more = False
            if self._stop.is_set():
                return
            self._wake.wait(self._pause if more else self._every)
