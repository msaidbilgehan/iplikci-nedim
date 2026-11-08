"""The Telegram bot's ear (ADR-0021): one thread reads the bot's messages as they come, so a document sent to the bot
is taken in within seconds. Each read waits up to half a minute for a message (long polling): the service only calls
out to Telegram, never opens a port, and Telegram answers the waiting read when a message comes.

What a read does is the use case's (app.telegram); the ear only keeps reading and waits between reads. With nothing to
read for (no paired bot, documents turned off, a token Telegram refused) it looks again every ten seconds without
asking Telegram. A read another one cut short (a pairing being checked at once) is made again after a few seconds;
a failed one after a wait that doubles each time, up to 15 minutes, as the IMAP connector's ear waits."""

import logging
import threading
from collections.abc import Callable
from enum import StrEnum

log = logging.getLogger("iplikci.telegram")


class Heard(StrEnum):
    """How one read of the bot's messages went."""

    NOTHING = "nothing"  # nothing to read for: look again later, Telegram unasked
    READ = "read"  # the messages were read and handled, or the wait ended without one: read again
    TAKEN = "taken"  # another read took the bot's messages (Telegram's conflict): again after a few seconds
    FAILED = "failed"  # Telegram could not be reached, or answered with an error: again after a longer wait


class BotWatcher:
    def __init__(
        self,
        listen: Callable[[], Heard],
        *,
        idle_check: float = 10.0,
        taken_wait: float = 5.0,
        first_wait: float = 5.0,
        longest_wait: float = 15 * 60,
        pause: float = 0.5,
    ) -> None:
        self._listen = listen
        self._idle_check = idle_check  # how often to look again when there is nothing to read for
        self._taken_wait = taken_wait
        self._first_wait = first_wait
        self._longest_wait = longest_wait
        self._pause = pause  # between two reads: a read that keeps answering at once never spins
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="iplikci-telegram", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stop reading; a read waiting for Telegram's answer is left to end with the process."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _loop(self) -> None:
        wait = self._first_wait
        while not self._stop.is_set():
            try:
                heard = self._listen()
            except Exception:  # the thread's boundary: an error waits as a failed read, never ends the ear
                log.exception("the bot's messages could not be handled")
                heard = Heard.FAILED
            if heard is Heard.READ:
                wait = self._first_wait
                self._stop.wait(self._pause)
            elif heard is Heard.NOTHING:
                wait = self._first_wait
                self._stop.wait(self._idle_check)
            elif heard is Heard.TAKEN:
                self._stop.wait(self._taken_wait)
            else:
                log.warning("the bot's messages could not be read; trying again in %d seconds", wait)
                self._stop.wait(wait)
                wait = min(wait * 2, self._longest_wait)
