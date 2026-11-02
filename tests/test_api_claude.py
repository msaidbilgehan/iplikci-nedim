"""Claude's connection (K23): the address, the commands and the ready configurations the interface shows, the API
token behind its button, the masking setting, and the headers helper Claude Code runs."""

import json

import pytest
from fastapi.testclient import TestClient

from iplikci import cli
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import access
from iplikci.storage import audit

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
BEARER = {"Authorization": f"Bearer {TOKEN}"}
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}


@pytest.fixture
def client(ws):
    return TestClient(create_app(Context(ws=ws, token=TOKEN)), base_url=BASE)


def signed_in(client):
    url = client.post("/api/login-links", headers=BEARER).json()["url"]
    assert client.get(url, follow_redirects=False).status_code == 303
    return client


def test_the_connection_names_the_address_the_helper_and_both_configurations_but_never_the_token(client, ws):
    response = client.get("/api/mcp/connection", headers=BEARER)
    found = response.json()
    assert found["address"] == "http://127.0.0.1:8643/mcp" and found["name"] == "iplikci"
    assert found["helper"].endswith("-I -X utf8 -m iplikci mcp baslik")
    assert found["claude_code"] == {
        "mcpServers": {"iplikci": {"type": "http", "url": found["address"], "headersHelper": found["helper"]}}
    }
    desktop = found["claude_desktop"]["mcpServers"]["iplikci"]
    assert desktop["command"] == found["command"] and desktop["args"][-3:] == ["mcp", "--klasor", str(ws.home)]
    assert found["sak_add"].startswith("sak store mcp add iplikci --url http://127.0.0.1:8643/mcp --headers-helper ")
    assert found["sak_remove"] == "sak store mcp remove iplikci --scope user"
    assert found["masking"] == "off" and TOKEN not in response.text


def test_the_token_is_shown_to_the_interfaces_own_pages_alone(client):
    assert client.post("/api/mcp/token", headers=BEARER).status_code == 403  # not to the command line's token
    browser = signed_in(client)
    assert browser.post("/api/mcp/token").status_code == 403  # a write from no page of the service's own
    shown = browser.post("/api/mcp/token", headers=OWN_PAGE)
    assert shown.status_code == 200 and shown.json() == {"token": TOKEN}
    assert shown.headers["cache-control"] == "no-store"


def test_the_masking_is_set_from_the_interface_and_recorded(client, ws):
    browser = signed_in(client)
    changed = browser.put("/api/mcp/masking", json={"masking": "accounts_and_names"}, headers=OWN_PAGE)
    assert changed.status_code == 200 and changed.json()["masking"] == "accounts_and_names"
    assert ws.fresh_settings().privacy.mcp_masking == "accounts_and_names"
    with ws.db() as db:
        (entry,) = audit.entries(db, "settings.privacy_changed")
    assert (entry.actor, entry.detail) == ("user", {"mcp_masking": "accounts_and_names"})
    refused = browser.put("/api/mcp/masking", json={"masking": "hepsi"}, headers=OWN_PAGE)
    assert refused.status_code == 422
    assert client.put("/api/mcp/masking", json={"masking": "off"}, headers=BEARER).status_code == 403


def test_the_headers_helper_prints_the_authorization_header_as_json(monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_API_TOKEN", TOKEN)
    assert cli.main(["mcp", "baslik"]) == 0
    assert json.loads(capsys.readouterr().out) == {"Authorization": f"Bearer {TOKEN}"}


def test_the_headers_helper_without_a_token_says_why_on_stderr(monkeypatch, capsys):
    monkeypatch.setattr(access, "api_token", lambda: None)
    assert cli.main(["mcp", "baslik"]) == 1
    out = capsys.readouterr()
    assert out.out == "" and "API belirteci yok" in out.err
