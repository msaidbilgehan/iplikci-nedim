"""The Döviz screen's API (F12, its Phase 6 part): the TL rates the documents print, and the net worth in TL and the
other units with each holding's value and, where the documents tell, its cost, and how the assets spread over
currencies. Nothing is fetched from the network."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app.workspace import Busy, Workspace
from iplikci.fakes import Move, teb

from conftest import add

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
TEB = "teb-123456789"
GOLD = "teb-987654321"
OCTOBER = "01/10/2026 - 31/10/2026"


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def tl(minor: int, currency: str = "TRY") -> dict[str, object]:
    return {"minor": minor, "currency": currency}


def client_for(ws: Workspace, today: date = date(2026, 11, 5)) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN, today=lambda: today)), base_url=BASE)


def get(client: TestClient, path: str) -> dict[str, object]:
    response = client.get(path, headers=bearer())
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(scope="module")
def demo_client(tmp_path_factory) -> TestClient:
    """The demo data folder's service, as on the day its baseline is taken."""
    ws = Workspace.load(demo.build(tmp_path_factory.mktemp("demo")))
    context = Context(ws=ws, token=TOKEN, ui=tmp_path_factory.mktemp("arayuz"), today=lambda: demo.AS_OF)
    return TestClient(create_app(context), base_url=BASE)


@pytest.fixture
def trading_ws(ws: Workspace) -> Workspace:
    """A TL account that bought euros twice and dollars once in October, each row with its rate, and gold."""
    moves = [
        Move(date(2026, 10, 1), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(40000)),
        Move(date(2026, 10, 10), "DÖVİZ ALIŞ EUR: 36,50", Decimal(-3650)),
        Move(date(2026, 10, 15), "DÖVİZ ALIŞ USD: 34,10", Decimal(-3410)),
        Move(date(2026, 10, 20), "DÖVİZ ALIŞ EUR: 37,00", Decimal(-3700)),
        Move(date(2026, 10, 25), "ALTIN ALIŞ 2 GR", Decimal(-6000)),
    ]
    add(ws, "teb.xls", teb.account_export(teb.running_rows(moves), period=OCTOBER))
    grams = [Move(date(2026, 10, 25), "ALTIN ALIŞ", Decimal(2))]
    add(
        ws,
        "altin.xls",
        teb.account_export(teb.running_rows(grams), number="987654321", period=OCTOBER, kind="Altın GR"),
    )
    return ws


def test_the_rates_and_the_holdings_need_a_session_or_the_token(ws, monkeypatch):
    context = Context(ws=ws, token=TOKEN)
    client = TestClient(create_app(context), base_url=BASE)
    assert client.get("/api/fx").status_code == 401
    assert client.get("/api/holdings").status_code == 401

    def busy():
        raise Busy("başka bir işlem belgeleri işliyor; biraz sonra yeniden deneyin")

    monkeypatch.setattr(context.analysis, "get", busy)
    for path in ("/api/fx", "/api/holdings"):
        refused = client.get(path, headers=bearer())
        assert (refused.status_code, refused.json()["code"]) == (503, "busy")


def test_the_rates_are_the_documents_own_each_with_its_day(trading_ws):
    found = get(client_for(trading_ws), "/api/fx")
    euro, dollar = found["currencies"]
    assert euro["newest"] == {"day": "2026-10-20", "rate": "37.00", "source": "document"}
    assert [r["rate"] for r in euro["history"]] == ["36.50", "37.00"]  # the oldest first
    assert (dollar["currency"], dollar["newest"]["rate"]) == ("USD", "34.10")
    assert found["missing"] == ["GR"]  # the gold account: no document prints a gold price


def test_the_holdings_add_up_to_the_dashboards_net_worth(demo_client):
    found = get(demo_client, "/api/holdings")
    board = get(demo_client, "/api/dashboard")["net_worth"]
    worth = found["worth"]
    assert (worth["total"], worth["assets"], worth["debts"]) == (board["total"], board["assets"], board["debts"])
    assert worth["currencies"] == board["currencies"] and worth["left_out"] == board["left_out"]
    assert [(h["account"]["id"], h["group"], h["value"]) for h in found["holdings"]] == [
        (TEB, "current", tl(18438010)),
        ("garanti-yatirim-1234567-101", "brokerage", tl(134200)),
    ]
    [lira] = found["spread"]
    assert (lira["currency"], lira["amount"], lira["value"], lira["share"]) == ("TRY", tl(18572210), tl(18572210), 1.0)
    assert {a["id"] for a in lira["accounts"]} == {TEB, "garanti-yatirim-1234567-101"}


def test_gold_shows_its_grams_and_what_was_paid_for_it_never_a_guessed_value(trading_ws):
    found = get(client_for(trading_ws), "/api/holdings")
    gold = next(h for h in found["holdings"] if h["account"]["id"] == GOLD)
    assert (gold["group"], gold["amount"], gold["value"], gold["gain"]) == ("gold", tl(200, "GR"), None, None)
    assert gold["cost"] == tl(600000)  # bought for 6.000 TL from the TL account of the same bank
    assert "alışta ödenen 6.000,00 TL" in gold["note"]
    assert next(h for h in found["holdings"] if h["account"]["id"] == TEB)["value"] == tl(2324000)
    # Gold has no TL value: it is in the spread by its grams, out of the net worth with the reason why.
    spread = {s["currency"]: s for s in found["spread"]}
    assert (spread["GR"]["amount"], spread["GR"]["value"], spread["GR"]["share"]) == (tl(200, "GR"), None, None)
    assert spread["TRY"]["share"] == 1.0
    [left] = found["worth"]["left_out"]
    assert left["account"]["id"] == GOLD and "altın fiyatı belgelerde yok" in left["reason"]
    euro, dollar, grams = found["worth"]["currencies"]
    # 23.240 TL at the newest rates the documents print.
    assert (euro["amount"], euro["rate"], euro["rate_day"]) == (tl(62811, "EUR"), "37.00", "2026-10-20")
    assert (dollar["amount"], dollar["rate"]) == (tl(68152, "USD"), "34.10")
    assert (grams["amount"], grams["note"]) == (None, "gram altının TL fiyatı belgelerde yok")
