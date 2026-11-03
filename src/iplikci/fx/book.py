"""The exchange rates the providers publish, as the analysis reads them: by currency and day (architecture §15).

TCMB publishes its forex buying and selling rates on business days; ECB, and Frankfurter, which copies ECB, publish
one reference rate a day, and it stands for both sides. On a day with more than one, TCMB's comes first. A day
without a bulletin (a weekend, a holiday) takes the latest one before it, at most a week back: an older one says
nothing of that day.

Every conversion between a currency and TL is rounded here and nowhere else: to the kuruş, halves away from zero, as
banks round (domain.money).
"""

from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from ..domain.codes import RateSource
from ..domain.money import round_half_up

LOOKBACK = timedelta(days=7)  # how far back a day without a bulletin looks for one
# On a day with more than one rate, the first of these is taken: the Central Bank's own over the reference rate.
PREFERENCE = (RateSource.TCMB, RateSource.ECB, RateSource.FRANKFURTER)


@dataclass(frozen=True, slots=True)
class Quote:
    """One currency's rates on one day, in TL for one unit."""

    day: date  # the bulletin's own day
    currency: str  # its ISO code: USD, EUR, GBP, …
    buying: Decimal  # what a bank pays for one unit: assets are valued at it
    selling: Decimal  # what a bank asks for one unit: debts are valued at it
    source: RateSource

    @property
    def middle(self) -> Decimal:
        return (self.buying + self.selling) / 2


class RateBook:
    """The rates the providers published, one quote a currency and day."""

    def __init__(self, quotes: Iterable[Quote] = ()) -> None:
        chosen: dict[tuple[str, date], Quote] = {}
        for q in quotes:
            if q.source not in PREFERENCE:
                raise ValueError(f"{q.source} is no provider's rate")
            key = (q.currency, q.day)
            known = chosen.get(key)
            if known is None or PREFERENCE.index(q.source) < PREFERENCE.index(known.source):
                chosen[key] = q
        self._days: dict[str, list[date]] = {}
        self._quotes: dict[tuple[str, date], Quote] = chosen
        for currency, day in sorted(chosen):
            self._days.setdefault(currency, []).append(day)

    def __bool__(self) -> bool:
        return bool(self._quotes)

    def currencies(self) -> list[str]:
        return sorted(self._days)

    def on(self, currency: str, day: date) -> Quote | None:
        """The rate of that day: its own bulletin, else the latest one before it within LOOKBACK; None without."""
        days = self._days.get(currency)
        if not days:
            return None
        i = bisect_right(days, day)
        if i == 0 or day - days[i - 1] > LOOKBACK:
            return None
        return self._quotes[(currency, days[i - 1])]

    def newest(self, currency: str) -> Quote | None:
        days = self._days.get(currency)
        return self._quotes[(currency, days[-1])] if days else None

    def history(self, currency: str) -> list[Quote]:
        """Every quote of the currency, the oldest first."""
        return [self._quotes[(currency, d)] for d in self._days.get(currency, [])]


EMPTY = RateBook()


def to_tl(amount: Decimal, rate: Decimal) -> Decimal:
    """amount in a currency, in TL at rate (TL for one unit)."""
    return round_half_up(amount * rate)


def from_tl(amount: Decimal, rate: Decimal) -> Decimal:
    """amount in TL, in the currency of rate (TL for one unit)."""
    return round_half_up(amount / rate)
