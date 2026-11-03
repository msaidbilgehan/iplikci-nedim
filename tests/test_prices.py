"""TÜFE from EVDS with the user's own key (F12's V1+ part): the key tried once and kept in the keychain only when EVDS
takes it, the settings saying so; the index fetched every day with it, a failure recorded and never raised; nothing
asked — and the keychain never read — without it. Every answer is a fake one; the keychain is a dictionary."""

import json
import logging
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import background, kinds, prices
from iplikci.app.workspace import Workspace
from iplikci.domain.codes import Actor
from iplikci.fakes import Move, teb
from iplikci.fx import evds
from iplikci.fx.provider import ProviderError
from iplikci.settings import config, secrets
from iplikci.storage import audit
from iplikci.storage import prices as stored

from conftest import add

KEY = "AbCdEf1234"
TODAY = date(2026, 11, 3)
# Made up, on the 2025=100 base: up to September, the newest month out on TODAY.
TUFE = {"2026-07": Decimal("118.42"), "2026-08": Decimal("120.37"), "2026-09": Decimal("122.95")}
TOKEN = "deneme-belirteci"


class Keychain(dict[str, str]):
    """The keychain as secrets reaches it: a value by its account."""


@pytest.fixture
def keychain(monkeypatch) -> Keychain:
    kept = Keychain()
    monkeypatch.setattr(secrets, "store", lambda secret, value: kept.update({secret.account: value}) or True)
    monkeypatch.setattr(secrets, "load", lambda secret: kept.get(secret.account))
    monkeypatch.setattr(secrets, "delete", lambda secret: kept.pop(secret.account, None))
    return kept


class Evds:
    """evds.fetch as the use case calls it: the months to answer, or the error to raise; every request kept."""

    def __init__(self, months: dict[str, Decimal] | None = None, error: Exception | None = None) -> None:
        self.months = TUFE if months is None else months
        self.error = error
        self.asked: list[tuple[str, date, date]] = []

    def __call__(self, key: str, start: date, end: date, settings: config.Settings) -> dict[str, Decimal]:
        self.asked.append((key, start, end))
        if self.error is not None:
            raise self.error
        return dict(self.months)


@pytest.fixture
def covered(ws) -> Workspace:
    """ws whose data begins on 2 March 2026: a TEB list of that month."""
    moves = [Move(date(2026, 3, 2), "MARKET ALISVERIS", Decimal(-80))]
    add(ws, "liste.xls", teb.account_export(teb.running_rows(moves, Decimal(1000)), period="02/03/2026 - 31/03/2026"))
    return ws


def kept_index(ws: Workspace) -> dict[str, Decimal]:
    with ws.db() as db:
        return stored.every(db, evds.TUFE)


def test_a_key_evds_takes_is_kept_in_the_keychain_with_the_months_that_came(covered, keychain):
    get = Evds()
    found = prices.set_key(covered, f"  {KEY}\n", Actor.USER, get=get, today=TODAY)
    assert keychain == {"evds": KEY}
    # From January of the year before the data's first day: the trend's months and a year before them.
    assert get.asked == [(KEY, date(2025, 1, 1), TODAY)]
    assert (found.has_key, found.months, found.first, found.newest) == (True, 3, "2026-07", "2026-09")
    assert config.load(covered.layout.settings).fx.evds is True
    assert KEY not in covered.layout.settings.read_text(encoding="utf-8")
    with covered.db() as db:
        [entry] = audit.entries(db, prices.KEY_SET)
    assert KEY not in json.dumps(entry.detail) and entry.detail == {"months": 3}


@pytest.mark.parametrize("typed", ["", "kısa", "anahtar boşluklu", "x" * 129, "AbC;rm-1234"])
def test_what_is_no_key_is_refused_before_it_is_tried(ws, keychain, typed):
    get = Evds()
    with pytest.raises(prices.PricesError, match="EVDS anahtarı değil"):
        prices.set_key(ws, typed, Actor.USER, get=get, today=TODAY)
    assert get.asked == [] and keychain == {}


def test_a_key_evds_refuses_or_cannot_be_asked_about_is_not_kept(ws, keychain):
    refused = Evds(error=evds.KeyRefused("EVDS anahtarı kabul etmedi: anahtarı yeniden kopyalayın"))
    with pytest.raises(prices.PricesError, match="kabul etmedi") as error:
        prices.set_key(ws, KEY, Actor.USER, get=refused, today=TODAY)
    assert KEY not in str(error.value)
    with pytest.raises(prices.PricesError, match="^Anahtar denenemedi, saklanmadı: EVDS: ulaşılamadı"):
        prices.set_key(ws, KEY, Actor.USER, get=Evds(error=ProviderError("EVDS: ulaşılamadı")), today=TODAY)
    assert keychain == {} and kept_index(ws) == {}
    assert config.load(ws.layout.settings).fx.evds is False


def test_without_a_keychain_the_key_is_not_kept_and_the_way_round_is_said(ws, monkeypatch):
    monkeypatch.setattr(secrets, "store", lambda secret, value: False)
    with pytest.raises(prices.PricesError, match="IPLIKCI_EVDS_KEY"):
        prices.set_key(ws, KEY, Actor.USER, get=Evds(), today=TODAY)
    assert config.load(ws.layout.settings).fx.evds is False


def test_without_a_key_nothing_is_asked_and_the_keychain_is_never_read(ws):
    # The tests' guard (conftest) fails a test that reaches the keychain: the settings alone say there is no key.
    get = Evds()
    assert prices.fetch(ws, get=get, today=TODAY) == 0 and get.asked == []
    found = prices.status(ws)
    assert (found.has_key, found.months, found.newest, found.last_run, found.behind) == (False, 0, None, "", False)


def test_with_a_key_the_index_is_fetched_and_a_revised_month_written_over(covered, keychain):
    prices.set_key(covered, KEY, Actor.USER, get=Evds(), today=TODAY)
    revised = TUFE | {"2026-09": Decimal("123.01"), "2026-10": Decimal("125.60")}
    assert prices.fetch(covered, get=Evds(revised), today=TODAY) == 2  # the revised month and the new one
    assert kept_index(covered) == revised
    assert prices.fetch(covered, get=Evds(revised), today=TODAY) == 0


def test_a_failed_fetch_is_recorded_and_logged_never_raised(covered, keychain, caplog):
    prices.set_key(covered, KEY, Actor.USER, get=Evds(), today=TODAY)
    caplog.set_level(logging.WARNING, logger="iplikci.prices")
    assert prices.fetch(covered, get=Evds(error=ProviderError("EVDS 503 yanıtı verdi")), today=TODAY) == 0
    found = prices.status(covered)
    assert found.last_error == "EVDS 503 yanıtı verdi" and found.months == 3  # what was kept stays
    assert "TÜFE çekilemedi: EVDS 503 yanıtı verdi" in caplog.text and KEY not in caplog.text


def test_a_key_gone_from_the_keychain_is_said_on_the_next_fetch(covered, keychain):
    prices.set_key(covered, KEY, Actor.USER, get=Evds(), today=TODAY)
    keychain.clear()
    get = Evds()
    assert prices.fetch(covered, get=get, today=TODAY) == 0 and get.asked == []
    assert "Ayarlar'dan yeniden girin" in prices.status(covered).last_error


def test_removing_the_key_turns_the_feature_off_and_stops_the_fetches_keeping_the_months(covered, keychain):
    prices.set_key(covered, KEY, Actor.USER, get=Evds(), today=TODAY)
    assert prices.index(covered) == TUFE
    prices.remove_key(covered, Actor.USER)
    assert keychain == {} and config.load(covered.layout.settings).fx.evds is False
    get = Evds()
    assert prices.fetch(covered, get=get, today=TODAY) == 0 and get.asked == []
    # Değerlendirme no longer reads them; they stay kept, and a new key shows them again before its fetch ends.
    assert prices.index(covered) == {} and kept_index(covered) == TUFE
    config.update(covered.layout.settings, "fx", {"evds": True})
    assert prices.index(covered) == TUFE
    with covered.db() as db:
        assert [e.action for e in audit.entries(db) if e.target == "evds"] == [prices.KEY_SET, prices.KEY_REMOVED]


@pytest.mark.parametrize(
    ("newest", "today", "late"),
    [
        ("2026-09", date(2026, 11, 3), False),  # October's comes out today at 10:00
        ("2026-09", date(2026, 11, 30), False),
        ("2026-09", date(2026, 12, 1), True),  # October's came on 3 November
        ("2026-01", date(2026, 11, 3), True),  # the 2003=100 series' last month, an archive since (fx.evds)
        ("2025-11", date(2026, 1, 15), False),  # across the year
        ("2025-10", date(2026, 1, 15), True),
        (None, date(2026, 11, 3), True),
    ],
)
def test_tufe_is_behind_when_the_month_before_last_is_not_kept(newest, today, late):
    assert prices.behind(newest, today) is late


def test_a_series_evds_stopped_giving_is_said_once_a_newer_month_should_have_come(covered, keychain):
    prices.set_key(covered, KEY, Actor.USER, get=Evds(), today=TODAY)
    assert prices.status(covered, today=TODAY).behind is False
    assert prices.fetch(covered, get=Evds(), today=date(2026, 12, 1)) == 0  # nothing newer came
    assert prices.status(covered, today=date(2026, 12, 1)).behind is True


def test_a_key_whose_series_gives_no_month_at_all_is_said_the_same_way(ws, keychain):
    found = prices.set_key(ws, KEY, Actor.USER, get=Evds({}), today=TODAY)
    assert (found.has_key, found.months, found.behind) == (True, 0, True)


def test_the_index_is_fetched_every_day_at_ten_thirty_by_a_job_of_its_own(ws):
    [job] = [p for p in background.PERIODIC if p.kind == kinds.PRICES]
    assert job.key(datetime(2026, 11, 3, 10, 29)) != job.key(datetime(2026, 11, 3, 10, 31))
    assert kinds.PRICES in background.handlers(ws) and kinds.LABELS[kinds.PRICES] == "TÜFE'nin çekilmesi (EVDS)"


# --- the Settings screen's routes -----------------------------------------------------------------------------------


class Today(date):
    """The use case's clock pinned to TODAY: the routes give it no day of their own."""

    @classmethod
    def today(cls) -> "Today":
        return cls(TODAY.year, TODAY.month, TODAY.day)


@pytest.fixture
def client(covered, monkeypatch) -> TestClient:
    monkeypatch.setattr(prices, "date", Today)
    return TestClient(create_app(Context(ws=covered, token=TOKEN)), base_url="http://127.0.0.1:8643")


def browser(client: TestClient) -> dict[str, str]:
    """A browser's session on the service's own page, as the interface has one (the guard): its headers."""
    url = client.post("/api/login-links", headers={"Authorization": f"Bearer {TOKEN}"}).json()["url"]
    assert client.get(url, follow_redirects=False).status_code == 303
    return {"Origin": "http://127.0.0.1:8643", "X-Iplikci": "1"}


def test_the_settings_screen_keeps_a_key_shows_where_tufe_stands_and_never_sends_the_key_back(
    client, keychain, monkeypatch
):
    monkeypatch.setattr(evds, "fetch", Evds())
    headers = browser(client)
    saved = client.put("/api/settings/evds", json={"key": KEY}, headers=headers)
    assert saved.status_code == 200, saved.text
    assert saved.json() == {
        "has_key": True,
        "months": 3,
        "first": "2026-07",
        "newest": "2026-09",
        "last_run": saved.json()["last_run"],
        "last_error": "",
        "behind": False,
    }
    shown = client.get("/api/settings/evds", headers=headers)
    assert shown.status_code == 200 and KEY not in shown.text and shown.json()["has_key"] is True
    assert client.delete("/api/settings/evds", headers=headers).status_code == 204
    assert client.get("/api/settings/evds", headers=headers).json()["has_key"] is False and keychain == {}


def test_a_refused_key_is_said_and_only_a_browser_on_the_services_page_may_give_one(client, keychain, monkeypatch):
    monkeypatch.setattr(evds, "fetch", Evds(error=evds.KeyRefused("EVDS anahtarı kabul etmedi")))
    refused = client.put("/api/settings/evds", json={"key": KEY}, headers=browser(client))
    assert refused.status_code == 400 and refused.json()["code"] == "evds_refused" and keychain == {}
    by_token = client.put("/api/settings/evds", json={"key": KEY}, headers={"Authorization": f"Bearer {TOKEN}"})
    assert by_token.status_code == 403
    read = client.get("/api/settings/evds", headers={"Authorization": f"Bearer {TOKEN}"})
    assert read.status_code == 200 and read.json()["has_key"] is False
