"""Spending in real terms (F12, V1+): the trend's two sides carried to one month's prices with TÜFE, complete months
only, a month without an index named and left out."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from iplikci.inflation import real_trend

BEFORE = ["2026-01", "2026-02", "2026-03"]
RECENT = ["2026-04", "2026-05", "2026-06"]
SPENT = {m: Decimal(10000) for m in BEFORE} | {m: Decimal(11000) for m in RECENT}


def test_spending_that_rose_with_prices_did_not_rise_in_real_terms():
    index = {m: Decimal(100) for m in BEFORE} | {m: Decimal(110) for m in RECENT}
    found = real_trend(BEFORE, RECENT, SPENT, index)
    assert found is not None and found.base == "2026-06"
    assert (found.nominal_change, found.prices, found.real_change) == (Decimal("0.1"), Decimal("0.1"), Decimal(0))
    assert found.before_real == found.recent_real == Decimal("11000.00") and found.missing == ()


def test_a_month_without_an_index_is_named_and_left_out_of_both_sides():
    index = {m: Decimal(100) for m in BEFORE} | {"2026-04": Decimal(105), "2026-05": Decimal(105)}
    found = real_trend(BEFORE, RECENT, SPENT, index)
    assert found is not None and found.missing == ("2026-06",) and found.recent == ("2026-04", "2026-05")
    assert found.base == "2026-05" and found.recent_nominal == Decimal("11000.00")
    assert real_trend(BEFORE, RECENT, SPENT, {"2026-01": Decimal(100)}) is None  # nothing recent to compare


@given(st.decimals(min_value=Decimal(1), max_value=Decimal(1000), places=2))
def test_prices_alone_never_change_spending_that_kept_up_with_them(rise):
    index = {m: Decimal(100) for m in BEFORE} | {m: Decimal(100) + rise for m in RECENT}
    spent = {m: Decimal(10000) for m in BEFORE} | {m: Decimal(100) * (Decimal(100) + rise) for m in RECENT}
    found = real_trend(BEFORE, RECENT, spent, index)
    assert found is not None and found.real_change == Decimal(0)
