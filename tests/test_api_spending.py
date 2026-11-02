"""The Değerlendirme screen's spending cards (F10, the MVP report's): tiles, months by group and by necessity,
categories, merchants, money in and out by month and the three-month forecast, narrowed by the Transactions screen's
filters; the forecast by every filter but the period. Averages use complete months only."""

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app.workspace import Workspace

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}


@pytest.fixture(scope="module")
def client(tmp_path_factory) -> TestClient:
    ws = Workspace.load(demo.build(tmp_path_factory.mktemp("demo") / "veri"))
    return TestClient(
        create_app(Context(ws=ws, token=TOKEN, today=lambda: demo.AS_OF)), base_url="http://127.0.0.1:8643"
    )


def cards(client: TestClient, **query: str | list[str]) -> dict:
    response = client.get("/api/spending", params=query, headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    return response.json()


@pytest.fixture(scope="module")
def found(client) -> dict:
    return cards(client)


def test_without_a_period_the_last_twelve_months_of_the_data_count(found):
    assert found["period"] == {"start": "2026-01", "end": "2026-10", "first": "2026-01", "last": "2026-10"}
    tiles = found["tiles"]
    assert tiles["total"]["minor"] == sum(c["total"]["minor"] for c in found["categories"])
    assert tiles["count"] == sum(c["count"] for c in found["categories"])


def test_the_monthly_average_leaves_out_a_month_the_documents_cover_only_partly(found):
    tiles = found["tiles"]
    assert (tiles["average_months"], tiles["partial_months"]) == (9, 1)  # July has a gap in the documents
    july = next(m for m in found["by_group"]["months"] if m["month"] == "2026-07")
    assert july["partial"] and not any(m["partial"] for m in found["by_group"]["months"] if m["month"] != "2026-07")
    assert tiles["income_average"]["minor"] > 0 and float(tiles["income_share"]) < 1


def test_the_months_by_group_and_by_necessity_keep_their_fixed_colour_slots(found):
    groups = found["by_group"]
    assert groups["months"][0]["month"] == "2026-01" and len(groups["months"]) == 10
    assert all(len(m["values"]) == len(groups["slices"]) for m in groups["months"])
    assert {s["slot"] for s in groups["slices"]} <= set(range(9))
    levels = {s["key"]: s["slot"] for s in found["by_level"]["slices"]}
    assert levels == {"required": 1, "optional": 4, "unnecessary": 5}


def test_categories_and_merchants_lead_to_their_rows(found):
    first = found["categories"][0]
    assert first["category"] == "Kira" and first["link"]["query"] == {"category": "Kira"}
    shares = sum(float(c["share"]) for c in found["categories"])
    assert 0.99 < shares < 1.01
    totals = [m["total"]["minor"] for m in found["merchants"]]
    assert totals == sorted(totals, reverse=True)
    assert found["merchants"][0]["link"]["query"] == {"merchant": found["merchants"][0]["merchant"]}


def test_money_in_and_out_by_month_says_what_is_left(found):
    for m in found["flow"]:
        others = m["people"]["minor"] + m["debt"]["minor"] + m["saving"]["minor"]
        assert m["net"]["minor"] == m["income"]["minor"] - m["expense"]["minor"]
        assert m["left"]["minor"] == m["net"]["minor"] - others


def test_the_forecast_goes_three_months_ahead_from_the_last_six_complete_ones(found):
    forecast = found["forecast"]
    assert forecast["months"] == ["2026-11", "2026-12", "2027-01"]
    assert forecast["base"] == ["2026-04", "2026-05", "2026-06", "2026-08", "2026-09", "2026-10"]
    rent = forecast["lines"][0]
    assert (rent["part"], rent["necessity"]) == ("regular", "required") and len(set(map(str, rent["amounts"]))) == 1
    assert forecast["totals"][0]["minor"] == sum(line["amounts"][0]["minor"] for line in forecast["lines"])
    left = forecast["income"]["minor"] - forecast["totals"][0]["minor"]
    left -= forecast["saving"]["minor"] + forecast["other"]["minor"]
    assert forecast["left"]["minor"] == left
    assert [m["month"] for m in forecast["actual"]["months"]][-1] == "2026-10"


def test_a_period_narrows_the_cards_but_never_the_forecast(client, found):
    march = cards(client, **{"from": "2026-03-01", "to": "2026-03-31"})
    assert march["period"]["start"] == march["period"]["end"] == "2026-03"
    assert [m["month"] for m in march["by_group"]["months"]] == ["2026-03"]
    assert march["forecast"] == found["forecast"]
    coffee = cards(client, category="Kafe & Kahve")
    assert {c["category"] for c in coffee["categories"]} == {"Kafe & Kahve"}
    assert [line["label"] for line in coffee["forecast"]["lines"] if line["part"] == "regular"] == ["Ornek Kahve"]


def test_other_kinds_than_spending_are_counted_only_when_asked_for(client):
    income = cards(client, kind="income")
    assert income["tiles"]["count"] == 9 and income["categories"][0]["category"] == "Diğer Gelirler"


def test_monthly_averages_go_over_the_whole_months_only_and_months_without_spending_count(client, found):
    rent = next(c for c in found["categories"] if c["category"] == "Kira")
    assert rent["average"]["minor"] == 1500000  # the nine whole months, not July's gap
    july_only = next(c for c in found["categories"] if c["category"] == "Uçak, Tren & Otobüs")
    assert july_only["total"]["minor"] > 0 and july_only["average"]["minor"] == 0  # spent only in the partial month
    once = cards(client, category="Elektronik")["tiles"]  # one purchase in ten months
    assert (once["average_months"], once["average"]["minor"]) == (9, round(once["total"]["minor"] / 9))
    assert found["tiles"]["income_months"] == 9  # July's income is known, but July is not whole
    assert [m["month"] for m in found["flow"] if m["partial"]] == ["2026-07"]


def test_a_period_of_days_counts_those_days_as_the_transactions_screen_does(client):
    days = {"from": "2026-03-15", "to": "2026-03-20"}
    narrowed = cards(client, **days)
    listed = client.get(
        "/api/transactions",
        params={**days, "kind": ["purchase", "refund", "interest_fee"]},
        headers={"Authorization": f"Bearer {TOKEN}"},
    ).json()["totals"]
    assert (narrowed["tiles"]["total"], narrowed["tiles"]["count"]) == (listed["spent"], listed["counted"])
    assert narrowed["by_group"]["months"][0]["partial"] and narrowed["tiles"]["average"] is None  # a cut month


def test_the_forecasts_regular_payments_follow_the_tag_and_certainty_filters_too(client, found):
    assert [line["label"] for line in found["forecast"]["lines"] if line["part"] == "regular"]
    for narrowing in ({"tag": "hicbir-satirda-olmayan"}, {"certainty": "excluded"}):
        assert cards(client, **narrowing)["forecast"] is None  # no row kept: nothing to forecast
    worded = cards(client, q="kahve")["forecast"]
    assert [line["label"] for line in worded["lines"] if line["part"] == "regular"] == ["Ornek Kahve"]


def test_a_split_regular_payment_is_never_counted_again_as_variable_spending(tmp_path):
    ws = Workspace.load(demo.build(tmp_path / "veri"))
    client = TestClient(create_app(Context(ws=ws, token=TOKEN, today=lambda: demo.AS_OF)), base_url=BASE)
    url = client.post("/api/login-links", headers={"Authorization": f"Bearer {TOKEN}"}).json()["url"]
    client.get(url, follow_redirects=False)
    before = cards(client)["forecast"]["lines"]
    rents = client.get("/api/transactions", params={"category": "Kira", "limit": 500}, headers=OWN_PAGE).json()["rows"]
    for rent in rents:  # rent and its dues, every month
        minor = rent["amount"]["minor"]
        parts = [{"minor": minor - 100000, "category": "Kira"}, {"minor": 100000, "category": "Market & Gıda"}]
        put = client.put(f"/api/transactions/{rent['fingerprint']}/annotation", json={"parts": parts}, headers=OWN_PAGE)
        assert put.status_code == 200
    after = cards(client)["forecast"]["lines"]
    assert after == before  # still one regular payment, and no part of it in the variable spending
