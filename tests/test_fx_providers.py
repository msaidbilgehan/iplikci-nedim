"""The exchange rate providers (architecture §15, ADR-0009): TCMB's bulletin, ECB's reference rates as XML and as
the zip of their history, and Frankfurter's JSON, read from fake answers into TL rates for one unit. An answer comes
from the network: one that declares a document type or an entity is refused unread."""

import io
import json
import zipfile
from datetime import date
from decimal import Decimal

import pytest

from iplikci import egress
from iplikci.domain.codes import RateSource
from iplikci.fakes import fx as fake
from iplikci.fakes.fx import TcmbRate
from iplikci.fx import ecb, frankfurter, provider, tcmb
from iplikci.fx.book import Quote
from iplikci.fx.provider import ProviderError
from iplikci.settings import config

SETTINGS = config.Settings()
MONDAY, FRIDAY = date(2026, 11, 2), date(2026, 10, 30)
BULLETIN = [
    TcmbRate("USD", "49.8827", "49.9726"),
    TcmbRate("EUR", "57.4012", "57.5046"),
    TcmbRate("JPY", "32.4837", "32.7012", unit=100),
    TcmbRate("XDR", "67.5513", None),  # TCMB sells no SDR
]


def by_code(quotes) -> dict[str, Quote]:
    return {q.currency: q for q in quotes}


# --- TCMB ----------------------------------------------------------------------------------------------


def test_a_bulletin_gives_each_currencys_forex_rates_for_one_unit():
    found = tcmb.parse(fake.tcmb_xml(MONDAY, BULLETIN))
    quotes = by_code(found.quotes)
    assert found.day == MONDAY
    assert quotes["USD"] == Quote(MONDAY, "USD", Decimal("49.8827"), Decimal("49.9726"), RateSource.TCMB)
    assert (quotes["JPY"].buying, quotes["JPY"].selling) == (Decimal("0.324837"), Decimal("0.327012"))  # for 100


def test_a_currency_without_forex_rates_is_left_out():
    found = tcmb.parse(fake.tcmb_xml(MONDAY, [*BULLETIN, TcmbRate("KWD", None, None)]))
    assert sorted(by_code(found.quotes)) == ["EUR", "JPY", "USD"]


def test_the_bulletins_own_day_counts_not_the_day_asked(providers):
    # Before 15:30, and all weekend, today.xml still holds the last business day's bulletin.
    providers.answers[(egress.TCMB, tcmb.TODAY)] = (200, fake.tcmb_xml(FRIDAY, BULLETIN))
    found = tcmb.fetch_today(SETTINGS)
    assert found.day == FRIDAY and {q.day for q in found.quotes} == {FRIDAY}
    assert providers.asked == [("www.tcmb.gov.tr", "/kurlar/today.xml")]


def test_a_day_without_a_bulletin_answers_404_and_gives_nothing(providers):
    providers.answers[(egress.TCMB, tcmb.day_path(MONDAY))] = (200, fake.tcmb_xml(MONDAY, BULLETIN))
    assert tcmb.fetch_day(date(2026, 10, 29), SETTINGS) is None  # Republic Day: no bulletin
    assert tcmb.fetch_day(MONDAY, SETTINGS) is not None
    assert providers.paths(egress.TCMB) == ["/kurlar/202610/29102026.xml", "/kurlar/202611/02112026.xml"]


def test_another_answer_than_a_bulletin_is_an_error_never_a_day_without_rates(providers):
    providers.answers[(egress.TCMB, tcmb.day_path(MONDAY))] = (503, b"<html>bakim</html>")
    with pytest.raises(ProviderError, match="503"):
        tcmb.fetch_day(MONDAY, SETTINGS)
    with pytest.raises(ProviderError, match="XML değil"):
        tcmb.parse(b"<html><body>Bakim calismasi</body>")
    with pytest.raises(ProviderError, match="kur yok"):
        tcmb.parse(fake.tcmb_xml(MONDAY, [TcmbRate("XDR", "67.5513", None)]))
    with pytest.raises(ProviderError, match="tarihi"):
        tcmb.parse(b'<Tarih_Date Tarih="2026-11-02"></Tarih_Date>')


def test_an_unreachable_provider_is_a_provider_error_naming_its_host(providers):
    providers.down.add(egress.TCMB)
    with pytest.raises(ProviderError, match="www.tcmb.gov.tr"):
        tcmb.fetch_today(SETTINGS)


# --- answers are untrusted -----------------------------------------------------------------------------

BILLION_LAUGHS = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]>
<Tarih_Date Tarih="02.11.2026"><Currency CurrencyCode="USD"><Unit>1</Unit><ForexBuying>&lol2;</ForexBuying>
</Currency></Tarih_Date>"""


def test_a_document_declaring_a_doctype_or_an_entity_is_refused_unread():
    with pytest.raises(ProviderError, match="DOCTYPE ya da ENTITY"):
        tcmb.parse(BILLION_LAUGHS)
    with pytest.raises(ProviderError, match="DOCTYPE ya da ENTITY"):
        ecb.parse_xml(b'<?xml version="1.0"?><!doctype x SYSTEM "file:///etc/passwd"><Cube/>')
    with pytest.raises(ProviderError, match="DOCTYPE ya da ENTITY"):
        provider.xml(b"<a><!ENTITY x 'y'></a>", "ECB")


def test_a_document_that_is_not_utf8_is_refused_unread():
    with pytest.raises(ProviderError, match="UTF-8"):
        tcmb.parse(BILLION_LAUGHS.decode().encode("utf-16"))  # its declarations would hide from the check


# --- ECB -----------------------------------------------------------------------------------------------


def test_reference_rates_become_tl_rates_one_rate_for_both_sides():
    [day] = ecb.parse_xml(fake.ecb_xml({MONDAY: {"USD": "1.1216", "JPY": "172.53", "TRY": "56.0442"}}))
    quotes = by_code(day.quotes)
    assert day.day == MONDAY and set(quotes) == {"EUR", "USD", "JPY"}
    assert quotes["EUR"] == Quote(MONDAY, "EUR", Decimal("56.0442"), Decimal("56.0442"), RateSource.ECB)
    assert quotes["USD"].buying == quotes["USD"].selling == Decimal("49.968081")  # 56.0442 / 1.1216, 6 decimals
    assert quotes["JPY"].buying == Decimal("0.324837")


def test_a_day_without_the_liras_rate_gives_no_tl_rates():
    days = ecb.parse_xml(fake.ecb_xml({MONDAY: {"USD": "1.1216"}, FRIDAY: {"USD": "1.12", "TRY": "56.01"}}))
    assert [(d.day, len(d.quotes)) for d in days] == [(FRIDAY, 2), (MONDAY, 0)]  # the oldest first


def test_a_reference_answer_without_any_lira_rate_is_an_error_not_days_without_rates():
    with pytest.raises(ProviderError, match="TL kuru yok"):
        ecb.parse_xml(fake.ecb_xml({MONDAY: {"USD": "1.1216"}}))
    with pytest.raises(ProviderError, match="TL kuru yok"):
        ecb.parse_zip(fake.ecb_zip({MONDAY: {"USD": "1.1216"}}), MONDAY, MONDAY)
    with pytest.raises(ProviderError, match="TL kuru yok"):
        frankfurter.parse(fake.frankfurter_json({MONDAY: {"USD": "1.1216"}}))


def test_the_history_zip_gives_the_days_asked_and_the_span_it_covers():
    history = {
        date(2004, 12, 31): {"USD": "1.3621"},  # no lira yet: ECB has TRY from 2005 on
        date(2026, 10, 29): {"USD": "1.1190", "TRY": "55.90", "CYP": "N/A"},
        FRIDAY: {"USD": "1.1200", "TRY": "56.01"},
        MONDAY: {"USD": "1.1216", "TRY": "56.0442"},
    }
    data = fake.ecb_zip(history)
    span = ecb.parse_zip(data, date(2026, 10, 30), date(2026, 11, 5))
    assert span is not None and (span.first, span.last) == (FRIDAY, MONDAY)  # nothing is known after Monday
    assert [d.day for d in span.days] == [FRIDAY, MONDAY]
    assert by_code(span.days[1].quotes)["USD"].buying == Decimal("49.968081")
    old = ecb.parse_zip(data, date(2004, 12, 1), date(2004, 12, 31))
    assert old is not None and [len(d.quotes) for d in old.days] == [0]
    assert ecb.parse_zip(data, date(2026, 12, 1), date(2026, 12, 31)) is None  # after its newest day


def test_a_zip_that_unpacks_to_more_than_the_limit_is_refused(monkeypatch):
    monkeypatch.setattr(ecb, "CSV_LIMIT", 1024)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("eurofxref-hist.csv", "Date,USD,\n" + "2026-11-02,1.1216,\n" * 200)
    with pytest.raises(ProviderError, match="büyük"):
        ecb.parse_zip(out.getvalue(), MONDAY, MONDAY)
    with pytest.raises(ProviderError, match="açılamadı"):
        ecb.parse_zip(b"PK\x03\x04 bozuk", MONDAY, MONDAY)


def test_a_recent_span_comes_from_the_90_day_file_an_older_one_from_the_history(providers):
    rates = {FRIDAY: {"USD": "1.12", "TRY": "56.01"}, MONDAY: {"USD": "1.1216", "TRY": "56.0442"}}
    providers.answers[(egress.ECB, ecb.RECENT)] = (200, fake.ecb_xml(rates))
    providers.answers[(egress.ECB, ecb.HISTORY)] = (200, fake.ecb_zip(rates))
    today = date(2026, 11, 3)
    recent = ecb.fetch(FRIDAY, today, today, SETTINGS)
    older = ecb.fetch(date(2026, 1, 2), today, today, SETTINGS)
    assert recent is not None and older is not None and recent.days == older.days
    assert providers.paths(egress.ECB) == [ecb.RECENT, ecb.HISTORY]


# --- Frankfurter ---------------------------------------------------------------------------------------


def test_frankfurters_json_gives_the_same_tl_rates_exactly():
    data = fake.frankfurter_json({MONDAY: {"TRY": "56.0442", "USD": "1.1216"}, FRIDAY: {"TRY": "56.01"}})
    days = frankfurter.parse(data)
    assert [d.day for d in days] == [FRIDAY, MONDAY]
    usd = by_code(days[1].quotes)["USD"]
    assert usd == Quote(MONDAY, "USD", Decimal("49.968081"), Decimal("49.968081"), RateSource.FRANKFURTER)
    assert json.loads(data)["rates"][MONDAY.isoformat()]["TRY"] == 56.0442  # numbers in JSON, read as decimals


def test_a_span_is_asked_from_a_week_before_a_year_at_a_time(providers):
    rates = {date(2024, 12, 31): {"TRY": "36.7372"}, date(2025, 1, 2): {"TRY": "36.70"}}
    path = frankfurter.path(date(2024, 12, 25), date(2025, 1, 3))
    providers.answers[(egress.FRANKFURTER, path)] = (200, fake.frankfurter_json(rates))
    found = frankfurter.fetch(date(2025, 1, 1), date(2025, 1, 3), SETTINGS)
    # New Year's Day is covered: the answer holds a day before it. Nothing is known of the 3rd yet.
    assert found is not None and (found.first, found.last) == (date(2025, 1, 1), date(2025, 1, 2))
    assert [d.day for d in found.days] == [date(2025, 1, 2)]
    assert providers.paths(egress.FRANKFURTER) == ["/v1/2024-12-25..2025-01-03?base=EUR"]
    assert frankfurter.spans(date(2023, 6, 1), date(2025, 1, 3)) == [
        (date(2023, 6, 1), date(2024, 5, 31)),
        (date(2024, 6, 1), date(2025, 1, 3)),
    ]


def test_an_answer_frankfurter_would_not_give_is_an_error():
    with pytest.raises(ProviderError, match="JSON değil"):
        frankfurter.parse(b"<html>hata</html>")
    with pytest.raises(ProviderError, match="JSON değil"):
        frankfurter.parse(b"[" * 100_000)
    with pytest.raises(ProviderError, match="avronun"):
        frankfurter.parse(b'{"amount":1.0,"base":"USD","rates":{}}')
    with pytest.raises(ProviderError, match="biçimde"):
        frankfurter.parse(b'{"amount":1.0,"base":"EUR","rates":[]}')
