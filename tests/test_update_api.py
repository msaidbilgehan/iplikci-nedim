"""The updates' routes (ADR-0022, F21): where they stand, a check or an install asked for, and the mode."""

import json

import pytest
from fastapi.testclient import TestClient

from iplikci import __version__
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import update
from iplikci.settings import config
from iplikci.update import install
from iplikci.update.install import Installation, Kind

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}
BEARER = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(ws) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN)), base_url=BASE)


@pytest.fixture
def browser(client) -> TestClient:
    url = client.post("/api/login-links", headers=BEARER).json()["url"]
    assert client.get(url, follow_redirects=False).status_code == 303
    return client


@pytest.fixture
def app_installed(monkeypatch, tmp_path) -> Installation:
    found = Installation(Kind.MACOS_APP, tmp_path / "İplikçi Nedim.app")
    monkeypatch.setattr(update, "installation", lambda: found)
    return found


def found_release(ws, version: str = "99.0.0", size: int = 1000) -> None:
    """What a check that found a newer release keeps."""
    ws.run.mkdir(parents=True, exist_ok=True)
    available = {"version": version, "tag": f"v{version}", "date": "2026-11-11", "notes": "- Yeni.", "size": size}
    available["page"] = f"https://github.com/sahip/depo/releases/tag/v{version}"
    (ws.run / update.STATE).write_text(json.dumps({"checked_at": "2026-11-11T05:00:00+00:00", "available": available}))


def queued(ws, kind: str) -> list[dict]:
    with ws.db() as db:
        return [json.loads(r["payload"]) for r in db.rows("SELECT payload FROM jobs WHERE kind = ?", (kind,))]


def test_the_state_tells_the_running_version_and_the_mode(client, monkeypatch):
    monkeypatch.setattr(update, "installation", lambda: install.MANUAL)
    found = client.get("/api/update", headers=BEARER).json()
    assert found["version"] == __version__ and found["mode"] == "auto"
    assert (found["installation"], found["automatic"], found["available"], found["last"]) == (
        "manual",
        False,
        None,
        None,
    )
    assert client.get("/api/update").status_code == 401


def test_a_found_release_is_shown_with_its_notes(client, ws, app_installed):
    found_release(ws)
    found = client.get("/api/update", headers=BEARER).json()
    assert found["available"]["version"] == "99.0.0" and found["available"]["notes"] == "- Yeni."
    assert found["automatic"] and found["page"].endswith("/releases/tag/v99.0.0")


def test_a_check_is_asked_for_by_the_page_and_the_command_line(browser, ws):
    assert browser.post("/api/update/check", headers=OWN_PAGE).status_code == 202
    assert browser.post("/api/update/check", headers=BEARER).json() == {"queued": True, "version": ""}
    assert queued(ws, update.CHECK_JOB) == [{"forced": True}]


def test_an_install_is_asked_for_only_of_a_found_release(browser, ws, app_installed):
    refused = browser.post("/api/update/install", headers=OWN_PAGE)
    assert (refused.status_code, refused.json()["code"]) == (409, "update_unavailable")
    found_release(ws)
    asked = browser.post("/api/update/install", headers=OWN_PAGE)
    assert (asked.status_code, asked.json()) == (202, {"queued": True, "version": "99.0.0"})
    assert queued(ws, update.INSTALL_JOB) == [{"version": "99.0.0", "asked": True}]


def test_a_copy_installed_by_hand_is_told_where_the_release_is(browser, ws, monkeypatch):
    monkeypatch.setattr(update, "installation", lambda: install.MANUAL)
    found_release(ws)
    refused = browser.post("/api/update/install", headers=OWN_PAGE)
    assert refused.status_code == 409 and "elle kuruldu" in refused.json()["title"]


def test_only_the_page_changes_the_mode(browser, ws):
    assert browser.put("/api/update/mode", json={"mode": "ask"}, headers=BEARER).status_code == 403
    changed = browser.put("/api/update/mode", json={"mode": "off"}, headers=OWN_PAGE)
    assert changed.status_code == 200 and changed.json()["mode"] == "off"
    assert config.load(ws.layout.settings).updates.mode == "off"
    assert browser.put("/api/update/mode", json={"mode": "bazen"}, headers=OWN_PAGE).status_code == 422
