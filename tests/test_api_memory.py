"""Claude's memory on the Claude bağlantısı screen (K30, ADR-0023): every note in full for the interface and the command
line's token, removed by the interface's own pages alone."""

import pytest
from fastapi.testclient import TestClient

from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import memory
from iplikci.domain.codes import Actor, MemoryKind
from iplikci.storage import audit, memories

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
BEARER = {"Authorization": f"Bearer {TOKEN}"}
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}


@pytest.fixture
def client(ws):
    memory.write(ws, "ozet-bicimi", Actor.MCP, kind=MemoryKind.FEEDBACK, description="Tablo", body="Neden: okunur.")
    memory.write(
        ws, "meslek", Actor.MCP, kind=MemoryKind.USER, description="Serbest çalışıyor", body="Geliri düzensiz."
    )
    return TestClient(create_app(Context(ws=ws, token=TOKEN)), base_url=BASE)


def signed_in(client):
    url = client.post("/api/login-links", headers=BEARER).json()["url"]
    assert client.get(url, follow_redirects=False).status_code == 303
    return client


def test_every_note_comes_in_full_who_the_user_is_first(client):
    found = client.get("/api/memory", headers=BEARER).json()
    assert found["most"] == memory.MOST
    assert [(m["name"], m["kind"], m["by"]) for m in found["memories"]] == [
        ("meslek", "user", "mcp"),
        ("ozet-bicimi", "feedback", "mcp"),
    ]
    first = found["memories"][0]
    assert (first["description"], first["body"]) == ("Serbest çalışıyor", "Geliri düzensiz.")
    assert first["created_at"] == first["updated_at"]


def test_a_note_is_removed_by_the_interfaces_own_pages_alone(client, ws):
    assert client.delete("/api/memory/meslek", headers=BEARER).status_code == 403  # not with the command line's token
    browser = signed_in(client)
    assert browser.delete("/api/memory/meslek").status_code == 403  # a write from no page of the service's own
    left = browser.delete("/api/memory/meslek", headers=OWN_PAGE)
    assert left.status_code == 200 and [m["name"] for m in left.json()["memories"]] == ["ozet-bicimi"]
    gone = browser.delete("/api/memory/meslek", headers=OWN_PAGE)
    assert gone.status_code == 404 and gone.json()["code"] == "memory_not_found"
    assert browser.delete("/api/memory/Meslek Notu", headers=OWN_PAGE).status_code == 422  # never a handle
    with ws.db() as db:
        [removed] = audit.entries(db, memories.REMOVED)
    assert (removed.actor, removed.target) == (Actor.USER, "meslek")
