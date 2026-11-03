"""TCMB's EVDS (F12's V1+ part, ADR-0009): TÜFE read from fake answers by YYYY-MM, a month not out yet left out, an
answer EVDS would not give refused, and the user's key sent in the request's header only — never in the address or
in a message."""

from datetime import date
from decimal import Decimal

import pytest

from iplikci import egress
from iplikci.fakes import fx as fake
from iplikci.fx import evds
from iplikci.fx.provider import ProviderError
from iplikci.settings import config

SETTINGS = config.Settings()
KEY = "AbCdEf1234"


def test_a_request_names_the_series_and_the_span_in_the_path_as_evds_wants_them():
    path = evds.path(evds.TUFE, date(2025, 1, 1), date(2026, 11, 3))
    assert path == "/igmevdsms-dis/series=TP.FG.J0&startDate=01-01-2025&endDate=03-11-2026&type=json"
    assert "?" not in path and KEY not in path


def test_evds_monthly_dates_become_months():
    assert [evds.month(w) for w in ("2025-1", "2025-12", "2025-13", "2025-01-01", "yanlış")] == [
        "2025-01",
        "2025-12",
        None,
        None,
        None,
    ]


def test_an_answer_gives_each_month_its_index_exactly_and_leaves_a_month_not_out_yet():
    found = evds.parse(fake.evds_json({"2025-12": "3112.37", "2026-01": "3215.05", "2026-02": None}))
    assert found == {"2025-12": Decimal("3112.37"), "2026-01": Decimal("3215.05")}


def test_a_number_written_as_a_json_number_is_read_exactly_too():
    found = evds.parse(b'{"totalCount":1,"items":[{"Tarih":"2026-1","TP_FG_J0":3215.05}]}')
    assert found == {"2026-01": Decimal("3215.05")}


@pytest.mark.parametrize(
    "answer",
    [
        b"<html>bakim</html>",  # no JSON
        b'{"totalCount":0}',  # no items
        b'{"items":[{"Tarih":"2026-01-15","TP_FG_J0":"3215.05"}]}',  # a daily date in a monthly series
        b'{"items":[{"Tarih":"2026-1","TP_FG_J0":"3.215,05"}]}',  # a number EVDS does not write
        b'{"items":[{"TP_FG_J0":"3215.05"}]}',  # no date
        b'{"items":["2026-1"]}',
    ],
)
def test_an_answer_evds_would_not_give_is_an_error(answer):
    with pytest.raises(ProviderError):
        evds.parse(answer)


def test_the_key_travels_in_the_header_only(monkeypatch):
    asked: list[tuple[str, str, dict[str, str]]] = []

    def answer(host, path, settings, headers=None, timeout=30.0):
        asked.append((host, path, dict(headers or {})))
        return 200, fake.evds_json({"2026-09": "3402.11"})

    monkeypatch.setattr(egress, "https_get", answer)
    found = evds.fetch(KEY, date(2025, 1, 1), date(2026, 11, 3), SETTINGS)
    assert found == {"2026-09": Decimal("3402.11")}
    (host, path, headers), *_ = asked
    assert host == "evds3.tcmb.gov.tr" and headers == {"key": KEY} and KEY not in path


@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_key_says_so_without_the_key(monkeypatch, status):
    monkeypatch.setattr(egress, "https_get", lambda *_args, **_kw: (status, b"Required request header 'key'"))
    with pytest.raises(evds.KeyRefused) as refused:
        evds.fetch(KEY, date(2025, 1, 1), date(2026, 11, 3), SETTINGS)
    assert "kabul etmedi" in str(refused.value) and KEY not in str(refused.value)


def test_evds_out_of_reach_or_failing_is_an_error_that_names_no_path(monkeypatch):
    def unreachable(*_args, **_kw):
        raise egress.Unreachable("evds3.tcmb.gov.tr adresine ulaşılamadı (URLError)")

    monkeypatch.setattr(egress, "https_get", unreachable)
    with pytest.raises(ProviderError, match="^EVDS: evds3.tcmb.gov.tr adresine ulaşılamadı"):
        evds.fetch(KEY, date(2025, 1, 1), date(2026, 11, 3), SETTINGS)
    monkeypatch.setattr(egress, "https_get", lambda *_args, **_kw: (500, b"hata"))
    with pytest.raises(ProviderError, match="^EVDS 500 yanıtı verdi$"):
        evds.fetch(KEY, date(2025, 1, 1), date(2026, 11, 3), SETTINGS)
