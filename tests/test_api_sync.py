"""The sync folder's routes and command (ADR-0025, F22): where it stands, the places it can go, turning it on and
off, the computer's name, sending the notifications from here and a round now."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import notify, sync
from iplikci.cli import main
from iplikci.settings import config
from iplikci.settings.paths import HOME_ENV
from iplikci.sync import library, machine, places

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
BEARER = {"Authorization": f"Bearer {TOKEN}"}
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}  # what the interface's own page sends with a change


@pytest.fixture(autouse=True)
def one_machine(monkeypatch):
    monkeypatch.setattr(machine, "fingerprint", lambda: "makine-1")
    monkeypatch.setattr(machine, "computer_name", lambda: "Deneme Bilgisayarı")
    sync._peers.clear()
    sync._beats.clear()


@pytest.fixture
def drive(tmp_path, monkeypatch) -> Path:
    """Google Drive's folder as this computer has it; the places the service finds are this one alone."""
    root = tmp_path / "CloudStorage" / "GoogleDrive-kisi@example.com" / "My Drive"
    root.mkdir(parents=True)
    monkeypatch.setattr(places, "found", lambda *args, **kwargs: [places.Place(places.GOOGLE_DRIVE, "kisi", root)])
    return root


@pytest.fixture
def client(ws) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN)), base_url=BASE)


@pytest.fixture
def browser(client) -> TestClient:
    url = client.post("/api/login-links", headers=BEARER).json()["url"]
    assert client.get(url, follow_redirects=False).status_code == 303
    return client


def test_the_state_says_off_and_the_places_name_google_drive_first(client, drive):
    found = client.get("/api/sync", headers=BEARER).json()
    assert (found["on"], found["folder"], found["devices"], found["name"]) == (False, "", [], "Deneme Bilgisayarı")
    [place] = client.get("/api/sync/places", headers=BEARER).json()
    assert place["service"] == "Google Drive" and place["folder"] == str(drive / library.DEFAULT_NAME)
    assert place["usable"] and not place["exists"]


def test_the_browser_turns_it_on_renames_the_computer_and_turns_it_off(browser, drive, ws):
    folder = str(drive / library.DEFAULT_NAME)
    on = browser.put("/api/sync", json={"folder": folder, "name": "Ev bilgisayarı"}, headers=OWN_PAGE)
    assert on.status_code == 200, on.text
    found = on.json()
    assert found["on"] and found["service"] == "Google Drive" and found["name"] == "Ev bilgisayarı"
    assert config.load(ws.layout.settings).sync.folder == folder
    assert browser.post("/api/sync/inspect", json={"folder": folder}, headers=OWN_PAGE).json()["exists"]
    assert (
        browser.put("/api/sync/name", json={"name": "Çalışma odası"}, headers=OWN_PAGE).json()["name"]
        == "Çalışma odası"
    )
    assert browser.post("/api/sync/round", headers=OWN_PAGE).status_code == 202
    off = browser.delete("/api/sync", headers=OWN_PAGE).json()
    assert not off["on"] and not config.load(ws.layout.settings).sync.folder
    assert (drive / library.DEFAULT_NAME / library.MARKER).is_file()  # the folder stays


def test_a_folder_holding_other_files_is_refused_with_the_reason(browser, tmp_path):
    busy = tmp_path / "Tatil"
    busy.mkdir()
    (busy / "deniz.jpg").write_bytes(b"resim")
    refused = browser.put("/api/sync", json={"folder": str(busy)}, headers=OWN_PAGE)
    assert refused.status_code == 400 and "boş değil" in refused.json()["title"]
    assert not browser.post("/api/sync/inspect", json={"folder": "goreli/yol"}, headers=OWN_PAGE).json()["usable"]


def test_the_computer_takes_the_notifications_it_can_send(browser, drive, ws, monkeypatch):
    browser.put("/api/sync", json={"folder": str(drive / library.DEFAULT_NAME)}, headers=OWN_PAGE)
    monkeypatch.setattr(notify, "external_ready", lambda _ws: ())
    assert browser.put("/api/sync/senders", json={"channels": ["telegram"]}, headers=OWN_PAGE).status_code == 409
    monkeypatch.setattr(notify, "external_ready", lambda _ws: ("telegram",))
    taken = browser.put("/api/sync/senders", json={"channels": []}, headers=OWN_PAGE).json()
    assert taken["senders"] == {"telegram": taken["device"]} and taken["ready"] == ["telegram"]


def test_the_command_line_may_read_but_only_the_browser_changes_it(client, drive):
    assert client.get("/api/sync", headers=BEARER).status_code == 200
    assert client.post("/api/sync/round", headers=BEARER).status_code == 202
    folder = str(drive / library.DEFAULT_NAME)
    assert client.put("/api/sync", json={"folder": folder}, headers=BEARER).status_code == 403
    assert client.delete("/api/sync", headers=BEARER).status_code == 403


def test_the_command_turns_it_on_tells_where_it_stands_and_turns_it_off(ws, drive, monkeypatch, capsys):
    monkeypatch.setenv(HOME_ENV, str(ws.home))
    folder = drive / library.DEFAULT_NAME
    assert main(["esitleme", "durum"]) == 0
    assert "Eşitleme kapalı." in capsys.readouterr().out
    assert main(["esitleme", "ac", str(folder), "--ad", "Masaüstü"]) == 0
    assert "Eşitleme açık" in capsys.readouterr().out
    assert main(["esitleme", "simdi"]) == 0
    assert "Tur bitti" in capsys.readouterr().out
    assert main(["esitleme", "durum"]) == 0
    said = capsys.readouterr().out
    assert "Masaüstü (bu bilgisayar)" in said and "Google Drive" in said
    assert main(["esitleme", "kapat"]) == 0
    assert "Eşitleme kapalı." in capsys.readouterr().out
    assert main(["esitleme", "ac", "goreli/yol"]) == 1
