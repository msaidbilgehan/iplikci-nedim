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
