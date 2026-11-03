"""The rate book (architecture §15): a day's rate is its own bulletin or the latest one before it within a week,
TCMB's before the reference rate, and every conversion is rounded in one place."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from iplikci.domain.codes import RateSource
from iplikci.fx.book import EMPTY, LOOKBACK, Quote, RateBook, from_tl, to_tl

FRIDAY = date(2026, 10, 30)


def quote(day: date, buying: str, selling: str | None = None, source: RateSource = RateSource.TCMB, currency="USD"):
    return Quote(day, currency, Decimal(buying), Decimal(selling or buying), source)


def test_a_weekend_takes_fridays_bulletin_and_an_old_one_says_nothing():
    book = RateBook([quote(FRIDAY, "49.88", "49.97")])
    assert book.on("USD", FRIDAY + timedelta(days=2)) == book.on("USD", FRIDAY)  # Sunday
    assert book.on("USD", FRIDAY + LOOKBACK) is not None
    assert book.on("USD", FRIDAY + LOOKBACK + timedelta(days=1)) is None
    assert book.on("USD", FRIDAY - timedelta(days=1)) is None  # nothing before the first bulletin
    assert book.on("EUR", FRIDAY) is None and not EMPTY and book


def test_on_a_day_with_more_than_one_rate_tcmbs_comes_first():
    reference = quote(FRIDAY, "49.90", source=RateSource.ECB)
    central = quote(FRIDAY, "49.88", "49.97")
    for quotes in ([reference, central], [central, reference]):
        found = RateBook(quotes).on("USD", FRIDAY)
        assert found is not None and found.source == RateSource.TCMB and found.middle == Decimal("49.925")
    alone = RateBook([quote(FRIDAY, "49.90", source=RateSource.FRANKFURTER), reference]).on("USD", FRIDAY)
    assert alone is not None and alone.source == RateSource.ECB


def test_the_newest_and_the_history_follow_the_days():
    days = [FRIDAY - timedelta(days=n) for n in (3, 0, 7)]
    book = RateBook([quote(d, str(40 + i)) for i, d in enumerate(days)] + [quote(FRIDAY, "50", currency="EUR")])
    assert [q.day for q in book.history("USD")] == sorted(days)
    newest = book.newest("USD")
    assert newest is not None and newest.day == FRIDAY and book.currencies() == ["EUR", "USD"]


def test_a_documents_rate_is_no_providers():
    with pytest.raises(ValueError):
        RateBook([quote(FRIDAY, "49.88", source=RateSource.DOCUMENT)])


def test_conversions_round_to_the_kurus_halves_away_from_zero():
    assert to_tl(Decimal("10.005"), Decimal(1)) == Decimal("10.01")
    assert to_tl(Decimal("-3.5"), Decimal("49.881")) == Decimal("-174.58")
    assert from_tl(Decimal(1000), Decimal("49.88")) == Decimal("20.05")


@given(
    st.decimals(min_value=Decimal(-1000000), max_value=Decimal(1000000), places=2),
    st.decimals(min_value=Decimal("0.0001"), max_value=Decimal(1000), places=4),
)
def test_a_conversion_is_never_more_than_half_a_kurus_off(amount, rate):
    assert abs(to_tl(amount, rate) - amount * rate) <= Decimal("0.005")
