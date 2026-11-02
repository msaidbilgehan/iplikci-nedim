"""The to-do list (F19): what keeps the data from being complete and right, each item with its steps and where the
interface shows it; the user takes one off the list and it stays off until what it stands for changes."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import todos
from iplikci.app.analysis import analyze
from iplikci.app.workspace import Workspace
from iplikci.domain.codes import DocumentStatus, TodoAction, TodoKind
from iplikci.fakes import CardRow, garanti
from iplikci.parsers.messages import CAMPAIGN
from iplikci.storage import audit, documents

from conftest import add

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def client_for(ws: Workspace) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN, today=lambda: demo.AS_OF)), base_url=BASE)


@pytest.fixture
def demo_ws(tmp_path) -> Workspace:
    return Workspace.load(demo.build(tmp_path / "demo"))


def test_the_list_names_each_item_with_its_steps_and_where_it_is_shown(demo_ws):
    found = client_for(demo_ws).get("/api/todos", headers=bearer()).json()
    kinds = [t["kind"] for t in found["items"]]
    assert kinds == ["missing_documents", "unprocessed_document"]  # in F19's order
    gap, unread = found["items"]
    assert "eksik aylar: 2026-07" in gap["detail"] and gap["actions"] == ["upload", "ignore"]
    assert unread["link"] == {"screen": "document", "id": unread["target"], "query": {}}
    assert unread["actions"][:2] == ["open", "reparse"] and unread["prompt"].startswith("İplikçi Nedim'de")
    assert found["counts"]["unprocessed_document"] == 1 and found["ignored"] == 0


def test_an_item_taken_off_the_list_stays_off_and_comes_back_on_request(demo_ws):
    client = client_for(demo_ws)
    key = client.get("/api/todos", headers=bearer()).json()["items"][1]["key"]
    body = {"key": key, "ignored": True}
    assert client.post("/api/todos/ignored", json=body, headers=bearer()).status_code == 403  # the interface only
    url = client.post("/api/login-links", headers=bearer()).json()["url"]
    client.get(url, follow_redirects=False)
    assert client.post("/api/todos/ignored", json=body, headers=OWN_PAGE).status_code == 204
    found = client.get("/api/todos", headers=bearer()).json()
    assert key not in {t["key"] for t in found["items"]}
    assert found["counts"]["unprocessed_document"] == 0 and found["ignored"] == 1
    every = client.get("/api/todos?with_ignored=true", headers=bearer()).json()["items"]
    assert next(t for t in every if t["key"] == key)["ignored"]
    client.post("/api/todos/ignored", json={"key": key, "ignored": False}, headers=OWN_PAGE)
    assert key in {t["key"] for t in client.get("/api/todos", headers=bearer()).json()["items"]}
    with demo_ws.db() as db:
        assert [e.action for e in audit.entries(db)][-2:] == [todos.TODO_IGNORED, "todo.restored"]


def test_card_rows_no_rule_names_are_one_item_per_merchant_the_most_frequent_first(ws):
    rows = [
        CardRow(date(2026, 9, 12), "ORNEKDUKKAN ISTANBUL", Decimal("50.00")),
        CardRow(date(2026, 9, 20), "ORNEKDUKKAN ISTANBUL", Decimal("40.00")),
        CardRow(date(2026, 9, 25), "BASKAYER ANKARA", Decimal("60.00")),
    ]
    add(ws, "ekstre.pdf", garanti.bonus_statement(pages=[rows]))
    found = todos.items(ws, analyze(ws, today=demo.AS_OF), demo.AS_OF)
    shop, other = [t for t in found if t.kind is TodoKind.UNCATEGORIZED]
    assert (shop.count, other.count) == (2, 1) and shop.detail.startswith("2 işlem, toplam 90,00 TL")
    assert shop.link is not None and dict(shop.link.query)["q"] == shop.title
    assert shop.actions[0] is TodoAction.ADD_RULE and "add_rule" in shop.prompt


def test_a_message_knowingly_classified_is_no_item(ws):
    before = analyze(ws, today=demo.AS_OF)  # the documents below are only rows of the archive, never read
    with ws.db() as db:
        documents.add(db, "a" * 64, "kampanya.eml", 10)
        documents.set_status(db, "a" * 64, DocumentStatus.UNPROCESSED, CAMPAIGN)
        documents.add(db, "b" * 64, "bilinmeyen.pdf", 10)
        documents.set_status(db, "b" * 64, DocumentStatus.UNREADABLE, "bozuk PDF")
    found = todos.items(ws, before, demo.AS_OF)
    assert [t.target for t in found if t.kind is TodoKind.UNPROCESSED_DOCUMENT] == ["b" * 64]
