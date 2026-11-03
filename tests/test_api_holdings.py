"""The Döviz screen's API (F12): the TL rates, the providers' as stored or else the documents' own; the net worth in TL
and the other units with each holding's value and, where the documents tell, its cost, and how the assets spread over
currencies; the spread the banks' rates cost and the income that comes in a foreign currency. Nothing is fetched from
the network."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app.workspace import Busy, Workspace
from iplikci.domain.codes import RateSource
from iplikci.fakes import Move, garanti, teb
from iplikci.fx.book import Quote
from iplikci.storage import fx_rates

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
    paths = ("/api/fx", "/api/holdings", "/api/fx/spread", "/api/fx/income")
    for path in paths:
        assert client.get(path).status_code == 401

    def busy():
        raise Busy("başka bir işlem belgeleri işliyor; biraz sonra yeniden deneyin")

    monkeypatch.setattr(context.analysis, "get", busy)
    for path in paths:
        refused = client.get(path, headers=bearer())
        assert (refused.status_code, refused.json()["code"]) == (503, "busy")


def store(ws: Workspace, *quotes: Quote) -> None:
    """The providers' answers as the rate job keeps them, a day and a source at a time."""
    with ws.db() as db:
        for day, source in sorted({(q.day, q.source) for q in quotes}):
            fx_rates.put(db, day, source, [q for q in quotes if (q.day, q.source) == (day, source)])


def tcmb(day: date, buying: str, selling: str, currency: str = "EUR") -> Quote:
    return Quote(day, currency, Decimal(buying), Decimal(selling), RateSource.TCMB)


# TCMB's euro rates for the trading account's days: Friday's stands for the Saturday purchase of 10 October.
EURO_RATES = (
    tcmb(date(2026, 10, 9), "36.3000", "36.4000"),
    tcmb(date(2026, 10, 20), "36.8000", "36.9000"),
    tcmb(date(2026, 10, 30), "36.4521", "36.5178"),
)


def test_the_providers_rates_come_first_with_both_sides_and_the_documents_beside_them(trading_ws):
    store(trading_ws, *EURO_RATES)
    found = get(client_for(trading_ws), "/api/fx")
    euro, dollar = found["currencies"]  # the dollar's only rate is still the document's
    assert euro["newest"] == {
        "day": "2026-10-30",
        "rate": "36.4521",
        "source": "tcmb",
        "buying": "36.4521",
        "selling": "36.5178",
    }
    assert [(r["day"], r["source"]) for r in euro["history"]] == [
        ("2026-10-09", "tcmb"),
        ("2026-10-10", "document"),
        ("2026-10-20", "tcmb"),
        ("2026-10-20", "document"),  # on a day with both, the provider's first
        ("2026-10-30", "tcmb"),
    ]
    assert (dollar["newest"]["source"], dollar["newest"]["rate"]) == ("document", "34.10")
    assert found["missing"] == ["GR"] and "TCMB" in found["note"]


def test_the_holdings_and_the_net_worth_name_the_providers_rate_they_are_valued_at(trading_ws):
    store(trading_ws, *EURO_RATES)
    worth = get(client_for(trading_ws), "/api/holdings")["worth"]
    euro, dollar, _ = worth["currencies"]
    # 23.240 TL at the euro's selling rate, what buying euros would cost; the dollar at the document's rate.
    assert (euro["amount"], euro["rate"], euro["rate_day"], euro["rate_source"]) == (
        tl(63640, "EUR"),
        "36.5178",
        "2026-10-30",
        "tcmb",
    )
    assert euro["note"] == "TCMB 30.10.2026 döviz satış kuruyla"
    assert (dollar["rate"], dollar["rate_source"]) == ("34.10", "document")


def test_the_spread_compares_each_trade_with_tcmbs_rate_of_its_day_and_counts_what_has_none(trading_ws):
    store(trading_ws, *EURO_RATES)  # no dollar rate from TCMB: the dollar purchase is left out
    client = client_for(trading_ws)
    found = get(client, "/api/fx/spread")
    assert (found["start"], found["end"], found["left_out"]) == ("2025-11-06", "2026-11-05", 1)
    first, second = found["trades"]
    assert {k: first[k] for k in ("day", "side", "amount", "tl", "rate", "tcmb_rate", "tcmb_day", "cost")} == {
        "day": "2026-10-10",
        "side": "buy",
        "amount": tl(10000, "EUR"),
        "tl": tl(365000),
        "rate": "36.50",
        "tcmb_rate": "36.4000",  # Friday's selling rate for a Saturday purchase
        "tcmb_day": "2026-10-09",
        "cost": tl(1000),  # (36,50 − 36,40) × 100 EUR
    }
    assert (second["tcmb_rate"], second["cost"]) == ("36.9000", tl(1000))
    assert (found["total"], found["trades_total"], found["purchases"]) == (tl(2000), tl(2000), [])
    assert "TCMB kuru bulunmayan 1 işlem toplama girmedi" in found["note"]
    assert client.get(f"/api/transactions/{first['fingerprint']}", headers=bearer()).status_code == 200


@pytest.fixture
def earning_ws(ws: Workspace) -> Workspace:
    """A euro account paid by a client every month from July to October, and a TL account that sold 100 EUR in
    October; TCMB's rates for the days of the income."""
    paid = [
        Move(date(2026, 7, 3), "ORNEK MUSTERI LTD GELEN EFT", Decimal(2000)),
        Move(date(2026, 8, 3), "ORNEK MUSTERI LTD GELEN EFT", Decimal(2000)),
        Move(date(2026, 9, 3), "ORNEK MUSTERI LTD GELEN EFT", Decimal(2500)),
        Move(date(2026, 10, 3), "ORNEK MUSTERI LTD GELEN EFT", Decimal(3000)),
    ]
    period = (date(2026, 7, 1), date(2026, 10, 31))
    add(ws, "eur.xls", garanti.account_xls(paid, Decimal(0), "9000001", period=period, currency="EUR"))
    sold = [Move(date(2026, 10, 12), "DÖVİZ SATIŞ EUR: 36,10", Decimal(3610))]
    add(ws, "teb.xls", teb.account_export(teb.running_rows(sold), period=OCTOBER))
    store(
        ws,
        tcmb(date(2026, 7, 3), "35.0000", "35.1000"),
        tcmb(date(2026, 8, 3), "35.5000", "35.6000"),
        tcmb(date(2026, 9, 3), "36.0000", "36.1000"),
        tcmb(date(2026, 10, 2), "36.2000", "36.3000"),
        tcmb(date(2026, 10, 30), "36.4521", "36.5178"),
    )
    return ws


def test_the_foreign_income_is_worth_its_euros_at_the_current_buying_rate(earning_ws):
    found = get(client_for(earning_ws), "/api/fx/income")
    [euro] = found["currencies"]
    assert euro["rate"] == {"day": "2026-10-30", "rate": "36.4521", "source": "tcmb", "buying": None, "selling": None}
    first = euro["rows"][0]
    assert (first["day"], first["amount"], first["counted"], first["worth"]) == (
        "2026-07-03",
        tl(200000, "EUR"),
        tl(7000000),  # at 3 July's rate, as the ledger counts it
        tl(7290420),  # at today's
    )
    assert (euro["received"], euro["worth"]) == (tl(950000, "EUR"), tl(34629495))
    [sale] = euro["sold"]
    assert (sale["day"], sale["amount"], sale["tl"], sale["rate"]) == (
        "2026-10-12",
        tl(10000, "EUR"),
        tl(361000),
        "36.10",
    )


def test_the_incomes_sensitivity_is_over_complete_months_only_and_names_them(earning_ws):
    [euro] = get(client_for(earning_ws), "/api/fx/income")["currencies"]
    sensitivity = euro["sensitivity"]
    assert sensitivity["months"] == ["2026-07", "2026-08", "2026-09", "2026-10"]  # November is the current month
    assert (sensitivity["monthly"], sensitivity["monthly_tl"], sensitivity["change"]) == (
        tl(237500, "EUR"),
        tl(8657374),  # 2.375,00 EUR at 36,4521
        tl(432869),
    )
    assert sensitivity["say"].startswith("Aylık ortalama Temmuz 2026 – Ekim 2026 arasındaki 4 tam ay üzerinden")
    assert "EUR/TRY %5 düşerse aylık gelir 4.328,69 TL azalır" in sensitivity["say"]


def test_without_a_foreign_income_the_income_says_so(trading_ws):
    found = get(client_for(trading_ws), "/api/fx/income")
    assert found["currencies"] == [] and found["note"].startswith("Döviz cinsinden gelen bir gelir yok")


def test_a_foreign_rows_detail_and_balance_name_their_rates_source(earning_ws):
    client = client_for(earning_ws)
    [row] = [r for r in get(client, "/api/fx/income")["currencies"][0]["rows"] if r["day"] == "2026-10-03"]
    why = get(client, f"/api/transactions/{row['fingerprint']}")["why"]
    # A Saturday's income: Friday's bulletin, at the buying rate.
    assert (why["rate"], why["rate_day"], why["rate_source"]) == ("36.2000", "2026-10-02", "tcmb")
    [euro] = [b for b in get(client, "/api/feed/now")["balances"] if b["account"]["id"] == "garanti-9000001"]
    assert (euro["rate"], euro["rate_source"], euro["value"]) == ("36.4521", "tcmb", tl(34629495))
    page = get(client, "/api/accounts/garanti-9000001")
    assert (page["holding"]["rate"], page["holding"]["rate_source"]) == ("36.4521", "tcmb")


def test_the_rates_are_the_documents_own_each_with_its_day(trading_ws):
    found = get(client_for(trading_ws), "/api/fx")
    euro, dollar = found["currencies"]
    assert euro["newest"] == {
        "day": "2026-10-20",
        "rate": "37.00",
        "source": "document",
        "buying": None,
        "selling": None,
    }
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
