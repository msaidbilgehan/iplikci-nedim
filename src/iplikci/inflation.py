"""Spending in real terms (F12, its V1+ part): the Değerlendirme screen's spending trend at one month's prices, with
TÜFE, the consumer price index TCMB's EVDS publishes as TP.FG.J0 (2003=100; fx.evds), for a user who gave an EVDS
key.

The trend compares the average month of its recent complete months with the months before them (insights.trend).
Here each of those months' spending is carried to the prices of the newest of them that has an index:

    real = spent × index(base) ÷ index(month)

so spending that rose only as fast as prices shows no rise. Only complete months are used, as everywhere. A month
of the trend without an index (TÜFE comes out early in the next month) is left out of both sides and named.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from .analysis import Dataset
from .domain.codes import DEFAULT_EXPENSE_KINDS
from .domain.money import round_half_up
from .insights import month_of

ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class RealTrend:
    """The trend's two sides in TL of their own time and at the base month's prices."""

    base: str  # YYYY-MM: the month whose prices the real amounts are in
    before: tuple[str, ...]  # the months compared that have an index, oldest first
    recent: tuple[str, ...]
    before_nominal: Decimal  # the average month, in TL of its own time
    recent_nominal: Decimal
    before_real: Decimal  # the same, at the base month's prices
    recent_real: Decimal
    nominal_change: Decimal | None  # recent ÷ before − 1; None when before is zero
    real_change: Decimal | None
    prices: Decimal  # how much prices rose from the before months to the recent ones: their average indexes
    missing: tuple[str, ...]  # the trend's months without an index


def monthly_spending(ds: Dataset, months: Iterable[str]) -> dict[str, Decimal]:
    """What was spent in each of the months: the expense kinds alone, as the trend counts them."""
    wanted = set(months)
    spent = dict.fromkeys(sorted(wanted), ZERO)
    for t in ds.transactions:
        month = month_of(t.date)
        if month in wanted and t.kind in DEFAULT_EXPENSE_KINDS:
            spent[month] += t.amount
    return spent


def _average(values: Sequence[Decimal]) -> Decimal:
    return sum(values, ZERO) / len(values)


def _change(new: Decimal, old: Decimal) -> Decimal | None:
    return round_half_up(new / old - 1, 4) if old else None


def real_trend(
    before: Sequence[str], recent: Sequence[str], spent: Mapping[str, Decimal], index: Mapping[str, Decimal]
) -> RealTrend | None:
    """The trend of before and recent (complete months, as insights.trend chose them) at the newest indexed month's
    prices; None when either side has no month with an index."""
    missing = tuple(m for m in (*before, *recent) if m not in index)
    old = tuple(m for m in before if m in index)
    new = tuple(m for m in recent if m in index)
    if not old or not new:
        return None
    base = max((*old, *new))

    def real(month: str) -> Decimal:
        return spent.get(month, ZERO) * index[base] / index[month]

    before_nominal = _average([spent.get(m, ZERO) for m in old])
    recent_nominal = _average([spent.get(m, ZERO) for m in new])
    before_real = _average([real(m) for m in old])
    recent_real = _average([real(m) for m in new])
    prices = _average([index[m] for m in new]) / _average([index[m] for m in old]) - 1
    return RealTrend(
        base=base,
        before=old,
        recent=new,
        before_nominal=round_half_up(before_nominal),
        recent_nominal=round_half_up(recent_nominal),
        before_real=round_half_up(before_real),
        recent_real=round_half_up(recent_real),
        nominal_change=_change(recent_nominal, before_nominal),
        real_change=_change(recent_real, before_real),
        prices=round_half_up(prices, 4),
        missing=missing,
    )
