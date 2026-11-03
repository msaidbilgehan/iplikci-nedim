"""`iplikci mcp` (ADR-0011): through the running service, or from the database opened only to read while it is down."""

import hashlib
import io
import json
import threading
import time
from dataclasses import replace

import anyio
import pytest
import uvicorn
from mcp_types.jsonrpc import PARSE_ERROR
from test_service import TOKEN, free_port

from iplikci.api.app import create_app
from iplikci.app import calls, reading
from iplikci.app.workspace import Workspace
from iplikci.fakes import teb
from iplikci.mcp import bridge
from iplikci.mcp.tools import CANNOT_READ, OFFLINE, PLANNED, Session
from iplikci.service import runner
from iplikci.service.client import ServiceDown
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
    for name in ("build_report", "fetch_email"):
        found = offline.call(name, {})
        assert found.error and found.text == OFFLINE, name
    assert (fingerprint(read), read.rules.read_text(encoding="utf-8")) == before


def test_while_the_service_is_down_a_change_is_planned_but_never_applied(read):
    offline = Session(replace(read, offline=True), offline=True)
    before = (fingerprint(read), read.rules.read_text(encoding="utf-8"))
    for name, arguments in (
        ("add_rule", {"category": "Market & Gıda", "merchant": "Kahveci", "patterns": ["KAHVECI"]}),
        ("alerts", {"action": "add", "name": "X", "event": "transaction.large", "amount": 1}),
    ):
        planned = offline.call(name, arguments)
        plan = json.loads(planned.text)
        assert not planned.error and plan["note"].startswith(PLANNED), name
        found = offline.call(name, {"plan_id": plan["plan_id"]})
        assert found.error and found.text == OFFLINE, name
    assert (fingerprint(read), read.rules.read_text(encoding="utf-8")) == before
    assert not read.layout.alert_rules.exists()


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


# --- the bridge: each message to the service while it runs, to the database while it is down ------------------------


class Service:
    """A data folder's service, started and stopped as a test needs."""

    def __init__(self, ws: Workspace) -> None:
        self.ws = ws
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        config = uvicorn.Config(
            create_app(runner.context(self.ws)), host="127.0.0.1", port=self.ws.port, log_level="warning"
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            assert time.monotonic() < deadline, "the service did not start"
            time.sleep(0.02)

    def stop(self) -> None:
        if self.server is not None and self.thread is not None:
            self.server.should_exit = True
            self.thread.join(timeout=10)
            self.server = self.thread = None


@pytest.fixture
def folder(tmp_path, monkeypatch):
    """A data folder with a port of its own and January's list read, its service not started."""
    home = tmp_path / "iplikci"
    home.mkdir()
    (home / "settings.toml").write_text(f"[server]\nport = {free_port()}\n", encoding="utf-8")
    monkeypatch.setenv("IPLIKCI_HOME", str(home))
    monkeypatch.setenv("IPLIKCI_API_TOKEN", TOKEN)
    ws = Workspace.load(home)
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    return ws


@pytest.fixture
def service(folder):
    found = Service(folder)
    yield found
    found.stop()


GREETING = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "deneme", "version": "1"}},
}
INITIALIZED = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def asked(mid, name, **arguments):
    return {"jsonrpc": "2.0", "id": mid, "method": "tools/call", "params": {"name": name, "arguments": arguments}}


class Client:
    """stdin as a client writes it, with what happens between its lines: the service starting or stopping."""

    def __init__(self, *steps) -> None:
        self.steps = steps

    def __aiter__(self):
        return self._lines()

    async def _lines(self):
        for step in self.steps:
            if callable(step):
                await anyio.to_thread.run_sync(step)
            else:
                yield (step if isinstance(step, str) else json.dumps(step)) + "\n"


def relayed(ws, *steps):
    """What the bridge writes back to a client that writes these lines, one answer a line."""
    out = io.StringIO()
    anyio.run(bridge.relay, ws, Client(*steps), anyio.wrap_file(out))
    return [json.loads(line) for line in out.getvalue().splitlines()]


def told(reply):
    """A tool's answer as the model reads it."""
    return json.loads(reply["result"]["content"][0]["text"])


def answered_by(ws):
    """Which calls the service recorded itself, and which the database alone left waiting for it."""
    with ws.db() as db:
        service = [e.target for e in audit.entries(db, calls.ACTION)]
    waiting = ws.run / calls.WAITING
    alone = (
        [json.loads(line)["tool"] for line in waiting.read_text(encoding="utf-8").splitlines()]
        if waiting.exists()
        else []
    )
    return service, alone


def test_the_bridge_passes_each_message_to_the_service_and_its_answer_back(folder, service):
    service.start()
    replies = relayed(
        folder, GREETING, INITIALIZED, asked(2, "status"), asked(3, "transactions", limit="x"), "bu json değil"
    )
    assert [r.get("id") for r in replies] == [1, 2, 3, None]  # the notification gets no answer
    assert replies[0]["result"]["serverInfo"]["name"] == "iplikci"
    assert told(replies[1])["read"]["accountStatements"] == 1
    assert replies[2]["result"]["isError"] and "'limit' integer" in replies[2]["result"]["content"][0]["text"]
    assert replies[3]["error"]["code"] == PARSE_ERROR
    assert answered_by(folder) == (["status", "transactions"], [])


def test_while_the_service_is_down_the_bridge_answers_from_the_database(folder):
    before = fingerprint(folder)
    replies = relayed(folder, GREETING, INITIALIZED, asked(2, "status"), asked(3, "fetch_email"))
    assert [r.get("id") for r in replies] == [1, 2, 3]
    assert replies[0]["result"]["serverInfo"]["name"] == "iplikci"
    assert told(replies[1])["read"]["accountStatements"] == 1
    assert replies[2]["result"]["isError"] and replies[2]["result"]["content"][0]["text"] == OFFLINE
    assert answered_by(folder) == ([], ["status", "fetch_email"]) and fingerprint(folder) == before


def test_once_the_service_starts_the_bridge_passes_the_messages_to_it(folder, service):
    replies = relayed(folder, GREETING, INITIALIZED, asked(2, "status"), service.start, asked(3, "status"))
    assert [r.get("id") for r in replies] == [1, 2, 3] and told(replies[2])["read"]["accountStatements"] == 1
    assert answered_by(folder) == (["status"], ["status"])


def test_when_the_service_stops_the_database_answers_greeted_as_the_client_greeted_the_service(folder, service):
    service.start()
    replies = relayed(folder, GREETING, INITIALIZED, asked(2, "status"), service.stop, asked(3, "status"))
    assert [r.get("id") for r in replies] == [1, 2, 3]  # the local server's greeting is answered to the bridge alone
    assert told(replies[2])["read"]["accountStatements"] == 1
    assert answered_by(folder) == (["status"], ["status"])


def test_a_service_that_refuses_the_token_is_said_so_on_each_request(folder, service, monkeypatch):
    service.start()
    monkeypatch.setenv("IPLIKCI_API_TOKEN", "eski-belirteç")
    (reply,) = relayed(folder, {"jsonrpc": "2.0", "id": 7, "method": "tools/list"})
    assert reply["id"] == 7 and reply["error"]["message"].startswith(bridge.UNREACHABLE)


def test_a_running_service_that_does_not_answer_in_time_is_an_error_for_the_request_alone(folder, monkeypatch):
    def late(*args):
        raise ServiceDown("servis yanıt vermedi")

    monkeypatch.setattr(bridge, "mcp_message", late)
    monkeypatch.setattr(bridge, "healthy", lambda port: True)
    replies = relayed(folder, INITIALIZED, asked(4, "status"))
    assert [r.get("id") for r in replies] == [4] and replies[0]["error"]["message"].startswith(bridge.UNREACHABLE)
    assert answered_by(folder) == ([], [])  # the database did not answer in its place


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
