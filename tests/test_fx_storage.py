"""The stored exchange rates (architecture §15): what a provider gave for a day, the days it was asked for, and an
analysis that goes stale when new rates come."""

from datetime import date
from decimal import Decimal

from iplikci.domain.codes import RateSource
from iplikci.fx.book import Quote, RateBook
from iplikci.storage import fx_rates

FRIDAY, SATURDAY = date(2026, 10, 30), date(2026, 10, 31)


def usd(day: date, buying: str, selling: str, source: RateSource = RateSource.TCMB) -> Quote:
    return Quote(day, "USD", Decimal(buying), Decimal(selling), source)


def test_a_days_rates_are_kept_exactly_and_the_day_is_marked_asked(ws):
    with ws.db() as db:
        assert fx_rates.put(db, FRIDAY, RateSource.TCMB, [usd(FRIDAY, "49.8827", "49.9726")]) == 1
        assert fx_rates.put(db, SATURDAY, RateSource.TCMB, []) == 0  # no bulletin on a Saturday
        (found,) = fx_rates.every(db)
        asked = fx_rates.asked(db, RateSource.TCMB)
    assert found == usd(FRIDAY, "49.8827", "49.9726") and isinstance(found.buying, Decimal)
    assert {d: a.published for d, a in asked.items()} == {FRIDAY: True, SATURDAY: False}


def test_a_day_asked_again_keeps_its_newest_answer(ws):
    with ws.db() as db:
        fx_rates.put(db, FRIDAY, RateSource.ECB, [usd(FRIDAY, "49.90", "49.90", RateSource.ECB)])
        fx_rates.put(db, FRIDAY, RateSource.ECB, [usd(FRIDAY, "49.91", "49.91", RateSource.ECB)])
        book = RateBook(fx_rates.every(db))
    found = book.on("USD", FRIDAY)
    assert found is not None and found.buying == Decimal("49.91")


def test_new_rates_leave_an_analysis_stale(ws):
    before = ws.signature()
    with ws.db() as db:
        fx_rates.put(db, FRIDAY, RateSource.TCMB, [usd(FRIDAY, "49.8827", "49.9726")])
    assert ws.signature() != before


def test_a_dump_brings_the_rates_and_the_days_back(ws):
    with ws.db() as db:
        fx_rates.put(db, FRIDAY, RateSource.TCMB, [usd(FRIDAY, "49.8827", "49.9726")])
        fx_rates.put(db, SATURDAY, RateSource.TCMB, [])
        quotes, days = fx_rates.every(db), list(fx_rates.asked(db, RateSource.TCMB).values())
        db.execute("DELETE FROM fx_rates")
        db.execute("DELETE FROM fx_days")
        fx_rates.restore(db, quotes, days, "2026-11-03T00:00:00+00:00")
        assert fx_rates.every(db) == quotes and list(fx_rates.asked(db, RateSource.TCMB).values()) == days
