"""`iplikci mcp` (ADR-0011): through the running service, or from the database opened only to read while it is down."""

import hashlib
import io
import json
import threading
import time
from dataclasses import replace

import pytest
import uvicorn
from test_service import TOKEN, free_port

from iplikci.api.app import create_app
from iplikci.app import calls, reading
from iplikci.app.workspace import Workspace
from iplikci.fakes import teb
from iplikci.mcp import bridge
from iplikci.mcp.tools import CANNOT_READ, OFFLINE, Session
from iplikci.service import runner
from iplikci.storage import audit

from conftest import JANUARY, add


def answer(session, name, **arguments):
    found = session.call(name, arguments)
    return (json.loads(found.text) if not found.error else found.text), found.error


@pytest.fixture
def read(ws):
    """A data folder whose January list was read into the database, as the service leaves it."""
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    return ws


def fingerprint(ws: Workspace) -> str:
    return hashlib.sha256(ws.layout.database.read_bytes()).hexdigest()


# --- while the service is down: the database alone ------------------------------------------------------------------


def test_while_the_service_is_down_the_tools_that_read_answer_from_the_database(read):
    offline = Session(replace(read, offline=True), offline=True)
    status, failed = answer(offline, "status")
    assert not failed and status["read"]["accountStatements"] == 1
    rows, _ = answer(offline, "transactions", text="kahveci")
    assert rows["count"] == 1
    rules, failed = answer(offline, "alerts")  # listing the alert rules only reads
    assert not failed and rules["rules"]


def test_while_the_service_is_down_a_tool_that_would_change_something_is_refused(read):
    offline = Session(replace(read, offline=True), offline=True)
    before = (fingerprint(read), read.rules.read_text(encoding="utf-8"))
    for name, arguments in (
        ("add_rule", {"category": "Market & Gıda", "merchant": "Kahveci", "patterns": ["KAHVECI"]}),
        ("alerts", {"action": "add", "name": "X", "event": "transaction.large", "amount": 1}),
        ("build_report", {}),
        ("fetch_email", {}),
    ):
        found = offline.call(name, arguments)
        assert found.error and found.text == OFFLINE, name
    assert (fingerprint(read), read.rules.read_text(encoding="utf-8")) == before


def test_while_the_service_is_down_no_document_is_read_again(read, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("an offline analysis read a document")

    monkeypatch.setattr(reading, "read_pending", refuse)
    before = fingerprint(read)
    status, failed = answer(Session(replace(read, offline=True), offline=True), "status")
    assert not failed and status["read"]["accountStatements"] == 1  # the stored readings as they are
    assert fingerprint(read) == before


def test_a_database_the_program_cannot_read_alone_is_said_so(ws):
    text, failed = answer(Session(replace(ws, offline=True), offline=True), "status")
    assert failed and text.startswith(CANNOT_READ)


# --- while the service runs: every message through its /mcp ---------------------------------------------------------


@pytest.fixture
def served(tmp_path, monkeypatch):
    """A data folder whose service runs on a free port, with January's list read."""
    home = tmp_path / "iplikci"
    home.mkdir()
    (home / "settings.toml").write_text(f"[server]\nport = {free_port()}\n", encoding="utf-8")
    monkeypatch.setenv("IPLIKCI_HOME", str(home))
    monkeypatch.setenv("IPLIKCI_API_TOKEN", TOKEN)
    ws = Workspace.load(home)
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    server = uvicorn.Server(
        uvicorn.Config(create_app(runner.context(ws)), host="127.0.0.1", port=ws.port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "the service did not start"
        time.sleep(0.02)
    yield ws
    server.should_exit = True
    thread.join(timeout=10)


def messages(*sent):
    return io.StringIO("".join(json.dumps(m) + "\n" for m in sent) + "bu json değil\n")


def test_the_bridge_passes_each_message_to_the_service_and_its_answer_back(served):
    out = io.StringIO()
    sent = messages(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "deneme", "version": "1"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "status", "arguments": {}}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "transactions", "arguments": {"limit": "x"}},
        },
    )
    assert bridge.forward(served, sent, out) == 0
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [1, 2, 3, None]  # the notification gets no answer
    assert replies[0]["result"]["serverInfo"]["name"] == "iplikci"
    status = json.loads(replies[1]["result"]["content"][0]["text"])
    assert status["read"]["accountStatements"] == 1
    assert replies[2]["result"]["isError"] and "'limit' integer" in replies[2]["result"]["content"][0]["text"]
    assert replies[3]["error"]["code"] == bridge.PARSE_ERROR


def test_a_service_that_refuses_the_token_is_said_so_on_each_request(served, monkeypatch):
    monkeypatch.setenv("IPLIKCI_API_TOKEN", "eski-belirteç")
    out = io.StringIO()
    bridge.forward(served, io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/list"}) + "\n"), out)
    (reply,) = [json.loads(line) for line in out.getvalue().splitlines()]
    assert reply["id"] == 7 and reply["error"]["message"].startswith(bridge.UNREACHABLE)


def test_a_service_gone_away_is_an_error_for_the_request_and_silence_for_a_notification(ws, monkeypatch):
    monkeypatch.setenv("IPLIKCI_API_TOKEN", TOKEN)
    gone = replace(ws, settings=replace(ws.settings, server=replace(ws.settings.server, port=free_port())))
    out = io.StringIO()
    sent = messages(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}, {"jsonrpc": "2.0", "id": 4, "method": "ping"}
    )
    bridge.forward(gone, sent, out)
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [4, None]
    assert replies[0]["error"]["message"].startswith(bridge.UNREACHABLE)


def test_a_call_answered_while_the_service_was_down_reaches_the_audit_log_when_it_starts(read):
    answer(Session(replace(read, offline=True), offline=True), "transactions", text="kahveci")
    waiting = read.run / calls.WAITING
    assert waiting.is_file()
    with read.db() as db:
        assert audit.entries(db, calls.ACTION) == []  # the database was only read
    assert calls.take_waiting(read) == 1 and not waiting.exists()
    with read.db() as db:
        (entry,) = audit.entries(db, calls.ACTION)
    assert (entry.actor, entry.target, entry.detail) == ("mcp", "transactions", {"arguments": ["text"], "ok": True})
    assert calls.take_waiting(read) == 0
