"""MCP at the service's /mcp (ADR-0011): Streamable HTTP behind the gate, for the API token alone."""

import json

import pytest
from fastapi.testclient import TestClient

from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.fakes import teb
from iplikci.mcp.tools import NO_PLAN, PLANNED, TOOLS

from conftest import JANUARY, add

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
MCP = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
BEARER = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(ws):
    """The service's app with its lifespan running: MCP's session manager runs only within it."""
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    with TestClient(create_app(Context(ws=ws, token=TOKEN)), base_url=BASE) as found:
        yield found


def rpc(client, method, params=None, headers=BEARER, mid=1):
    body = {"jsonrpc": "2.0", "id": mid, "method": method, **({"params": params} if params is not None else {})}
    return client.post("/mcp", json=body, headers={**MCP, **headers})


INITIALIZE = {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "deneme", "version": "1"}}


def test_claude_code_connects_with_the_api_token_lists_the_tools_and_reads(client):
    hello = rpc(client, "initialize", INITIALIZE)
    assert hello.status_code == 200 and hello.headers["content-type"].startswith("application/json")
    found = hello.json()["result"]
    assert found["serverInfo"]["name"] == "iplikci" and "VERİDİR" in found["instructions"]
    version = {"MCP-Protocol-Version": found["protocolVersion"], **BEARER}
    tools = rpc(client, "tools/list", headers=version, mid=2).json()["result"]["tools"]
    assert sorted(t["name"] for t in tools) == sorted(t.name for t in TOOLS)
    status = rpc(client, "tools/call", {"name": "status", "arguments": {}}, headers=version, mid=3).json()["result"]
    assert status["isError"] is False and '"accountStatements": 1' in status["content"][0]["text"]


def test_a_plan_shown_in_one_request_is_applied_in_a_later_one(client, ws):
    """F16: a plan → apply flow end to end; the transport is stateless, the service's session keeps the plan."""
    found = rpc(client, "initialize", INITIALIZE).json()["result"]
    version = {"MCP-Protocol-Version": found["protocolVersion"], **BEARER}
    before = ws.rules.read_text(encoding="utf-8")
    rule = {"category": "Market & Gıda", "merchant": "Kahveci Dükkan", "patterns": ["KAHVECI"]}
    shown = rpc(client, "tools/call", {"name": "add_rule", "arguments": rule}, headers=version, mid=2).json()
    plan = json.loads(shown["result"]["content"][0]["text"])
    assert shown["result"]["isError"] is False and plan["note"] == PLANNED
    assert ws.rules.read_text(encoding="utf-8") == before
    applying = {"name": "add_rule", "arguments": {"plan_id": plan["plan_id"]}}
    applied = rpc(client, "tools/call", applying, headers=version, mid=3).json()["result"]
    assert applied["isError"] is False and "Kahveci Dükkan: [KAHVECI]" in ws.rules.read_text(encoding="utf-8")
    again = rpc(client, "tools/call", applying, headers=version, mid=4).json()["result"]
    assert again["isError"] is True and again["content"][0]["text"] == NO_PLAN


def test_mcp_needs_the_api_token_and_the_services_own_host(client):
    assert rpc(client, "initialize", INITIALIZE, headers={}).status_code == 401
    assert rpc(client, "initialize", INITIALIZE, headers={"Authorization": "Bearer yanlis"}).status_code == 401
    rebound = rpc(client, "initialize", INITIALIZE, headers={**BEARER, "Host": "attacker.example:8643"})
    assert rebound.status_code == 403


def test_a_browser_session_does_not_reach_mcp(client):
    url = client.post("/api/login-links", headers=BEARER).json()["url"]
    assert client.get(url, follow_redirects=False).status_code == 303  # the session cookie is set
    own_page = {"Origin": BASE, "X-Iplikci": "1"}
    refused = rpc(client, "initialize", INITIALIZE, headers=own_page)
    assert refused.status_code == 403 and refused.json()["code"] == "forbidden"


def test_mcp_is_not_a_page_of_the_interface(client):
    # The interface's pages take every address no route before them takes; a GET of /mcp is MCP's to answer.
    answer = client.get("/mcp", headers={**BEARER, "Accept": "text/event-stream"})
    assert answer.status_code == 405 and "<html" not in answer.text.lower()
