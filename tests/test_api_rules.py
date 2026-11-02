"""The category rules on the Rules screen (F15): read with their groups and colours, every change previewed against the
ledger (which rows move, from which category to which) and written only from the service's own pages, the file before
it kept in the history."""

import threading

import pytest
import yaml
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import rules
from iplikci.app.analysis import Current
from iplikci.app.workspace import Workspace
from iplikci.categorize import Categorizer
from iplikci.domain.codes import Actor
from iplikci.settings import locks
from iplikci.storage import audit

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}
COFFEE = {"action": "merchant", "category": "Market & Gıda", "merchant": "Ornek Kahve", "patterns": ["ORNEK KAHVE"]}


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def demo_ws(tmp_path) -> Workspace:
    return Workspace.load(demo.build(tmp_path / "demo"))


@pytest.fixture
def client(demo_ws) -> TestClient:
    return TestClient(create_app(Context(ws=demo_ws, token=TOKEN, today=lambda: demo.AS_OF)), base_url=BASE)


def signed_in(client: TestClient) -> TestClient:
    url = client.post("/api/login-links", headers=bearer()).json()["url"]
    assert client.get(url, follow_redirects=False).status_code == 303
    return client


def test_the_rules_come_with_their_groups_colours_and_the_users_own_file(client, demo_ws):
    found = client.get("/api/rules/categories", headers=bearer()).json()
    coffee = next(c for c in found["categories"] if c["name"] == "Kafe & Kahve")
    assert coffee["group"] == "Yeme & İçme" and 1 <= coffee["slot"] <= 8 and not coffee["own"]
    assert found["content"] == demo_ws.rules.read_text(encoding="utf-8") and found["history"] == []
    assert next(c for c in found["categories"] if c["group"] == "Diğer")["slot"] == 0  # "Diğer" is grey


def test_a_preview_says_which_rows_a_change_moves_and_writes_nothing(client, demo_ws):
    before = demo_ws.rules.read_text(encoding="utf-8")
    found = client.post("/api/rules/categories/preview", json=COFFEE, headers=bearer()).json()
    assert not found["saved"] and found["changed"] == 10
    [move] = found["moves"]
    assert (move["before"], move["after"], move["count"]) == ("Kafe & Kahve", "Market & Gıda", 10)
    assert found["examples"][0]["after"]["category"] == "Market & Gıda"
    assert "+    Ornek Kahve: [ORNEK KAHVE]" in found["diff"]
    assert demo_ws.rules.read_text(encoding="utf-8") == before


def test_a_change_is_written_only_from_the_services_own_pages_and_keeps_the_file_before_it(client, demo_ws):
    assert client.put("/api/rules/categories", json=COFFEE, headers=bearer()).status_code == 403
    saved = signed_in(client).put("/api/rules/categories", json=COFFEE, headers=OWN_PAGE).json()
    assert saved["saved"] and saved["changed"] == 10 and saved["backup"].startswith("personal ")
    assert (demo_ws.rules_history / saved["backup"]).exists()
    data = yaml.safe_load(demo_ws.rules.read_text(encoding="utf-8"))
    assert data["Yeme & İçme"]["Market & Gıda"]["Ornek Kahve"] == ["ORNEK KAHVE"]
    with demo_ws.db() as db:
        assert [e.action for e in audit.entries(db)][-1] == rules.RULES_CHANGED
    again = client.put("/api/rules/categories", json=COFFEE, headers=OWN_PAGE)
    assert (again.status_code, again.json()["code"]) == (400, "rules_refused")  # the same rule: nothing to change
    assert client.get("/api/rules/categories", headers=bearer()).json()["history"] == [saved["backup"]]


def test_a_payment_is_ended_and_expected_again(client, demo_ws):
    signed_in(client)
    change = {"action": "ended", "merchant": "spotify", "month": "2026-10", "note": "iptal edildi"}
    assert client.put("/api/rules/categories", json=change, headers=OWN_PAGE).json()["saved"]
    ended = client.get("/api/rules/categories", headers=bearer()).json()["ended"]
    assert {"merchant": "Spotify", "month": "2026-10", "own": True} in ended  # as the ledger names it
    back = client.put("/api/rules/categories", json={"action": "not_ended", "merchant": "Spotify"}, headers=OWN_PAGE)
    assert back.json()["saved"]
    assert not [e for e in client.get("/api/rules/categories", headers=bearer()).json()["ended"] if e["own"]]
    unknown = client.post(
        "/api/rules/categories/preview",
        json={"action": "ended", "merchant": "Olmayan Dükkan", "month": "2026-10"},
        headers=bearer(),
    )
    assert unknown.status_code == 400 and "işlemlerde yok" in unknown.json()["title"]


def test_a_commitment_category_and_a_merchants_own_necessity_are_set_and_taken_back(client):
    signed_in(client)
    on = {"action": "commitment", "category": "Kafe & Kahve", "on": True}
    assert client.put("/api/rules/categories", json=on, headers=OWN_PAGE).json()["saved"]
    found = client.get("/api/rules/categories", headers=bearer()).json()
    assert next(c for c in found["categories"] if c["name"] == "Kafe & Kahve")["regular"]
    level = {"action": "necessity", "merchant": "Ornek Kahve", "necessity": "unnecessary"}
    assert client.put("/api/rules/categories", json=level, headers=OWN_PAGE).json()["changed"] == 10
    found = client.get("/api/rules/categories", headers=bearer()).json()
    assert {"merchant": "Ornek Kahve", "necessity": "unnecessary"} in found["merchant_necessity"]
    back = {"action": "necessity", "merchant": "Ornek Kahve", "necessity": None}
    assert client.put("/api/rules/categories", json=back, headers=OWN_PAGE).json()["saved"]
    off = {"action": "commitment", "category": "Kafe & Kahve", "on": False}
    assert client.put("/api/rules/categories", json=off, headers=OWN_PAGE).json()["saved"]


def test_a_rule_file_the_program_could_not_read_is_refused_and_nothing_changes(client, demo_ws):
    before = demo_ws.rules.read_text(encoding="utf-8")
    broken = signed_in(client).put(
        "/api/rules/categories", json={"action": "write", "content": "Yeme: [kapanmayan"}, headers=OWN_PAGE
    )
    assert (broken.status_code, broken.json()["code"]) == (400, "rules_refused")
    assert demo_ws.rules.read_text(encoding="utf-8") == before
    wrong = client.put("/api/rules/categories", json={"action": "faks"}, headers=OWN_PAGE)
    assert wrong.status_code == 422


def test_two_rule_changes_made_at_the_same_moment_both_stand(demo_ws):
    current = Current(demo_ws, write=False)
    edits = [
        lambda: rules.merchant_rule(demo_ws, "Market & Gıda", "Ornek Kahve", ["ORNEK KAHVE"]),
        lambda: rules.merchant_rule(demo_ws, "Elektronik", "Ornek Teknoloji", ["ORNEK TEKNO"]),
    ]
    start = threading.Barrier(len(edits))
    failed: list[Exception] = []

    def change(edit) -> None:
        start.wait()
        try:
            rules.save(demo_ws, current, edit, Actor.USER)
        except (rules.RulesError, locks.LockTimeout) as exc:
            failed.append(exc)

    threads = [threading.Thread(target=change, args=(edit,)) for edit in edits]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert failed == []
    homes = Categorizer.layered(demo_ws.rules).categories
    data = yaml.safe_load(demo_ws.rules.read_text(encoding="utf-8"))
    assert data[homes["Market & Gıda"]]["Market & Gıda"]["Ornek Kahve"] == ["ORNEK KAHVE"]
    assert data[homes["Elektronik"]]["Elektronik"]["Ornek Teknoloji"] == ["ORNEK TEKNO"]  # the first is not lost
