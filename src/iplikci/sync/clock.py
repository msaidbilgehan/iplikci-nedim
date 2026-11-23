"""When a piece of the shared data changed: a hybrid logical clock (ADR-0025).

Wall clocks of two computers drift apart, a minute or, on a computer whose clock was set by hand, much more. A stamp is
the wall clock's milliseconds, a counter for changes within one millisecond and the computer's id; the clock never
gives a stamp below one it has seen, its own or another computer's. So a change made after another computer's change
was merged always comes after it, whatever the two wall clocks say, and two stamps are never equal: the id decides
between two changes made in the same millisecond on two computers.
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass

_TEXT = re.compile(r"(\d{13})\.(\d{5})\.([0-9a-z]{1,32})")
_COUNTER_MAX = 99_999  # five digits in the text; a busier millisecond moves on to the next one
# 2200-01-01: a stamp beyond it is no computer's clock but a damaged or forged file. Taken in, it would carry every
# later stamp past the thirteen digits the text holds.
MAX_MS = 7_258_118_400_000


class StampError(ValueError):
    """A stamp in a file that is not one (another program's file, or a damaged one)."""


@dataclass(frozen=True, order=True, slots=True)
class Stamp:
    ms: int  # the wall clock's milliseconds since 1970, as the computer that made the change saw them (or later)
    counter: int  # changes within that millisecond
    device: str  # the computer's id: the last word between two stamps

    @property
    def text(self) -> str:
        """As the database and the folder keep it; text order is stamp order for ids of one length."""
        return f"{self.ms:013d}.{self.counter:05d}.{self.device}"

    @classmethod
    def parse(cls, text: str) -> "Stamp":
        found = _TEXT.fullmatch(text)
        if found is None or int(found[1]) > MAX_MS:
            raise StampError(f"geçersiz zaman damgası: {text[:40]!r}")
        return cls(int(found[1]), int(found[2]), found[3])

    @classmethod
    def zero(cls, device: str) -> "Stamp":
        """Older than every change: what a computer joining a set of data stamps its own data with, so that what the
        others decided wins wherever both have a value, and its own stays where they have none."""
        return cls(0, 0, device)


def wall_ms() -> int:
    return time.time_ns() // 1_000_000


class Clock:
    """One computer's clock. Not shared between threads: a sync round makes its stamps alone."""

    def __init__(self, device: str, last: Stamp | None = None, wall: Callable[[], int] = wall_ms) -> None:
        self.device = device
        self._wall = wall
        self._ms = last.ms if last else 0
        self._counter = last.counter if last else 0

    @property
    def last(self) -> Stamp:
        return Stamp(self._ms, self._counter, self.device)

    def now(self) -> Stamp:
        """A stamp after every stamp this clock gave or saw."""
        wall = self._wall()
        if wall > self._ms:
            self._ms, self._counter = wall, 0
        elif self._counter < _COUNTER_MAX:
            self._counter += 1
        else:
            self._ms, self._counter = self._ms + 1, 0
        return self.last

    def observe(self, seen: Stamp) -> None:
        """Another computer's stamp, merged: every stamp this clock gives from now on comes after it."""
        self._ms, self._counter = max((self._ms, self._counter), (seen.ms, seen.counter))
