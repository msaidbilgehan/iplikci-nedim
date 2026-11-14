"""The Ay sonu screen's API (F11): the months with their statuses, and one month in full: each account's closing and
what it waits for, the totals, where the money went, the regular payments, the provisional rows and the receipts'
rows no statement shows."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import background
from iplikci.app.workspace import Busy, Workspace
from iplikci.fakes import garanti

from conftest import add

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
TEB = "teb-123456789"
CURRENT = "garanti-1234567"
CARD = "garanti-1234"


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
def garanti_ws(ws: Workspace) -> Workspace:
    """The Garanti current account's October list and the Bonus card's statement cut on 5 October."""
    add(ws, "ekim.xls", garanti.account_xls())
    add(ws, "ekstre.pdf", garanti.bonus_statement())
    background.refresh(ws, date(2026, 11, 5))
    return ws


def receipt(day: date, amount: str, note: str, reference: str) -> bytes:
    body = garanti.fast_body(note, "VELİ ÖRNEKSOY")
    return garanti.receipt("HESAPTAN FAST", "106/1234567", garanti.HOLDER, body, amount, day, reference)


def test_the_months_need_a_session_or_the_token(ws, monkeypatch):
    context = Context(ws=ws, token=TOKEN)
    client = TestClient(create_app(context), base_url=BASE)
    assert client.get("/api/month-end").status_code == 401
    assert client.get("/api/month-end/2026-10").status_code == 401

    def busy():
        raise Busy("başka bir işlem belgeleri işliyor; biraz sonra yeniden deneyin")

    monkeypatch.setattr(context.analysis, "get", busy)
    refused = client.get("/api/month-end", headers=bearer())
    assert (refused.status_code, refused.json()["code"]) == (503, "busy")


def test_the_months_come_newest_first_with_their_status(demo_client):
    found = get(demo_client, "/api/month-end")
    months = {m["month"]: m for m in found["months"]}
    assert [m["month"] for m in found["months"]][:2] == ["2026-11", "2026-10"]
    assert (months["2026-11"]["status"], months["2026-10"]["status"], months["2026-07"]["status"]) == (
        "running",
        "closed",
        "missing",
    )
    july = months["2026-07"]
    assert (
        july["summary"]
        == "Kapanması için eksik belge var: TEB Vadesiz TL 123456789 (1–4 Temmuz için hesap dökümü eksik)."
    )
    assert (july["name"], july["link"]) == ("Temmuz 2026", {"screen": "month", "id": "2026-07", "query": {}})
    assert found["export"] == "month_end"  # the pages to keep, as the exports zip them


def test_a_months_page_tells_each_accounts_closing_and_what_it_waits_for(demo_client):
    found = get(demo_client, "/api/month-end/2026-07")
    teb, garanti_card, qnb_card, teb_card, brokerage = found["accounts"]
    assert (teb["account"]["id"], teb["status"], teb["label"], teb["covered"], teb["needed"]) == (
        TEB,
        "missing",
        "Belge eksik",
        27,
        31,
    )
    assert teb["open"] == [{"start": "2026-07-01", "end": "2026-07-04"}]
    assert teb["waiting_for"] == "1–4 Temmuz için hesap dökümü eksik"
    [statement] = teb["statements"]
    assert (statement["start"], statement["end"], statement["card"], statement["check"]) == (
        "2026-07-05",
        "2026-10-31",
        False,
        "verified",
    )
    # Each card's statements cover its days of July; the QNB card, opened on 13 July, needs only those.
    assert [
        (c["account"]["id"], c["status"], c["covered"], c["needed"]) for c in (garanti_card, qnb_card, teb_card)
    ] == [
        ("garanti-2468", "closed", 31, 31),
        ("qnb-1357", "closed", 19, 19),
        ("teb-4321", "closed", 31, 31),
    ]
    assert [(s["start"], s["end"], s["card"]) for s in teb_card["statements"]] == [
        ("2026-06-06", "2026-07-05", True),
        ("2026-07-06", "2026-08-05", True),
    ]
    # A brokerage account never holds a month open.
    assert (brokerage["blocking"], brokerage["status"], brokerage["waiting_for"]) == (False, "closed", "")
    assert (found["typical"], found["typical_months"]) == (tl(2156474), 6)
    assert (found["previous_month"], found["next_month"]) == ("2026-06", "2026-08")
    assert {r["payee"] for r in found["regular"]} >= {"Spotify", "Turkcell"}
    # A level names its code, the filter of İşlemler; the other shares have none.
    assert {(s["name"], s["code"]) for s in found["levels"]} <= {
        ("Gerekli", "required"),
        ("İsteğe bağlı", "optional"),
        ("Gereksiz", "unnecessary"),
        ("Belirsiz", "unknown"),
    }
    assert found["levels"] and all(s["code"] == "" for s in found["groups"] + found["categories"] + found["merchants"])


def test_a_card_waiting_for_its_statement_says_its_cut(garanti_ws):
    found = get(client_for(garanti_ws), "/api/month-end/2026-10")
    assert found["month"]["status"] == "waiting"
    card = next(a for a in found["accounts"] if a["account"]["id"] == CARD)
    # The statement names its successor's cut: the one that holds October's last days, named by its own.
    assert (card["status"], card["next_cut"], card["next_cut_printed"], card["late"]) == (
        "waiting",
        "2026-11-04",
        True,
        False,
    )
    assert card["waiting_for"] == "6–31 Ekim, 6 Ekim–4 Kasım ekstresinde"
    late = get(client_for(garanti_ws, date(2026, 11, 12)), "/api/month-end/2026-10")
    card = next(a for a in late["accounts"] if a["account"]["id"] == CARD)
    assert card["late"] and card["waiting_for"] == "6–31 Ekim, 6 Ekim–4 Kasım ekstresinde (gecikti)"


def test_provisional_rows_and_receipts_no_statement_shows_are_listed_with_their_certainty(garanti_ws):
    add(garanti_ws, "kira.pdf", receipt(date(2026, 11, 3), "- 1.250,00 TL", "KASIM KİRA", "10.15.42.000009"))
    add(garanti_ws, "fazla.pdf", receipt(date(2026, 10, 20), "- 999,00 TL", "EKİM EK", "10.15.42.000010"))
    client = client_for(garanti_ws)
    november = get(client, "/api/month-end/2026-11")
    assert november["month"]["provisional"] == 2  # the rent and its fee: after the October list, provisional
    assert {(r["certainty"], r["counted"]) for r in november["provisional"]} == {("provisional", True)}
    october = get(client, "/api/month-end/2026-10")
    assert october["month"]["status"] == "check"  # the October list covers 20 October and does not show it
    # The transfer and its fee, both from the receipt: shown, never counted.
    assert {(r["day"], r["certainty"], r["counted"]) for r in october["unmatched"]} == {
        ("2026-10-20", "excluded", False)
    }
    assert max(r["amount"]["minor"] for r in october["unmatched"]) == 99900
    current = next(a for a in october["accounts"] if a["account"]["id"] == CURRENT)
    assert current["receipts"]["unmatched"] == len(october["unmatched"]) == 2


def test_an_older_month_is_built_on_request_and_a_month_not_in_the_calendar_refused(demo_client):
    found = get(demo_client, "/api/month-end/2025-01")
    assert (found["month"]["status"], found["month"]["summary"]) == (
        "missing",
        "Bu ay için hiçbir hesabın belgesi yok.",
    )
    assert demo_client.get("/api/month-end/2026-13", headers=bearer()).status_code == 422
