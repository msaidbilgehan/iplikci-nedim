"""The IMAP connector's ear (ADR-0015): one connection waits in IDLE and asks for a fetch as soon as the server
announces new mail, so a bank message reaches the feed within seconds. Gmail ends an IDLE after about 29 minutes;
it is renewed every 25. A broken connection is opened again after a wait that doubles each time, up to 15 minutes.
A refused login stops the watcher for good: it never tries the same password again. A server without IDLE leaves
the work to the quarter-hourly fetch."""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from .imap import Account, Connect, LoginRefused, MailError, session, wait_for_news

log = logging.getLogger("iplikci.mail")


@dataclass(frozen=True)
class WatchTarget:
    account: Account
    password: str
    connect: Connect


class IdleWatcher:
    def __init__(
        self,
        target: Callable[[], WatchTarget | None],
        on_news: Callable[[], None],
        on_refused: Callable[[str], None],
        *,
        renew: float = 25 * 60,
        first_wait: float = 5.0,
        longest_wait: float = 15 * 60,
        idle_check: float = 60.0,
    ) -> None:
        self._target = target
        self._on_news = on_news
        self._on_refused = on_refused
        self._renew = renew
        self._first_wait = first_wait
        self._longest_wait = longest_wait
        self._idle_check = idle_check  # how often to look again when there is nothing to watch
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="iplikci-imap-idle", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _loop(self) -> None:
        wait = self._first_wait
        while not self._stop.is_set():
            target = self._target()
            if target is None:  # nothing set up, or stopped by a refused login: look again later
                self._stop.wait(self._idle_check)
                continue
            try:
                if not self._watch(target):
                    return
                wait = self._first_wait
            except LoginRefused as exc:
                self._on_refused(str(exc))
                return
            except (MailError, OSError):
                log.warning("the IDLE connection broke off; it opens again in %d seconds", wait)
                self._stop.wait(wait)
                wait = min(wait * 2, self._longest_wait)

    def _watch(self, target: WatchTarget) -> bool:
        """Wait for news on one connection until it breaks or the watcher stops; False when the server has no
        IDLE."""
        with session(target.account, target.password, target.connect) as box:
            if "IDLE" not in box.imap.capabilities:
                log.info("the mail server has no IDLE; the quarter-hourly fetch takes over")
                return False
            self._on_news()  # whatever came while it was away
            while not self._stop.is_set():
                if wait_for_news(box.imap, self._renew, self._stop):
                    self._on_news()
        return True
