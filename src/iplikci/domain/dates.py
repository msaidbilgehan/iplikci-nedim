"""Days on the calendar as the banks count them."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date


def add_months(day: date, n: int) -> date:
    """The same day n months later; the month's last day when that month is shorter (31 January and a month: 28 or 29
    February)."""
    year, month = divmod(day.year * 12 + day.month - 1 + n, 12)
    return date(year, month + 1, min(day.day, monthrange(year, month + 1)[1]))


@dataclass(frozen=True, slots=True)
class Cut:
    """A card statement's cut date to come: as the statement before it prints it, or reckoned a month on."""

    day: date
    printed: bool


def cut_after(cut: date, printed_next: date | None, k: int = 1) -> Cut:
    """The cut date of the k-th card statement after one cut on `cut` (k ≥ 1): the next one's as that statement prints
    it (printed_next), else the same day a month on; each later one a month after the one before. A card's cut day
    moves with the bank's calendar, so a printed day is never second-guessed."""
    if printed_next is not None:
        return Cut(add_months(printed_next, k - 1), printed=k == 1)
    return Cut(add_months(cut, k), printed=False)
