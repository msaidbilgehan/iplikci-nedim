"""The running service and the command line as its client: a real server on 127.0.0.1, in a thread."""

import socket
import threading
import time

import pytest
import uvicorn

from iplikci import cli
from iplikci.api.app import create_app
from iplikci.app.workspace import Workspace
from iplikci.service import runner

TOKEN = "deneme-belirteci"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def served(tmp_path, monkeypatch) -> Workspace:
    """A data folder whose service runs on a free port for the test."""
    home = tmp_path / "iplikci"
    home.mkdir()
    (home / "settings.toml").write_text(f"[server]\nport = {free_port()}\n", encoding="utf-8")
    monkeypatch.setenv("IPLIKCI_HOME", str(home))
    monkeypatch.setenv("IPLIKCI_API_TOKEN", TOKEN)
    ws = Workspace.load(home)
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


def test_the_command_line_gets_a_login_link_from_the_running_service(served, capsys):
    assert cli.main(["ac", "--yazdir"]) == 0
    url = capsys.readouterr().out.strip()
    assert url.startswith(f"http://127.0.0.1:{served.port}/giris?anahtar=")


def test_the_command_line_says_when_the_service_is_not_running(tmp_path, monkeypatch, capsys):
    home = tmp_path / "bos"
    home.mkdir()
    (home / "settings.toml").write_text(f"[server]\nport = {free_port()}\n", encoding="utf-8")
    monkeypatch.setenv("IPLIKCI_HOME", str(home))
    monkeypatch.setenv("IPLIKCI_API_TOKEN", TOKEN)
    assert cli.main(["ac"]) == 1
    assert "yanıt vermiyor" in capsys.readouterr().err


def test_the_service_context_uses_the_token_it_finds_and_forgets_expired_sessions(ws, monkeypatch):
    monkeypatch.setenv("IPLIKCI_API_TOKEN", TOKEN)
    with ws.db() as db:
        db.execute(
            "INSERT INTO sessions VALUES (?, '2020-01-01T00:00:00+00:00', '2020-01-01T00:00:00+00:00', "
            "'2020-03-31T00:00:00+00:00')",
            ("0" * 64,),
        )
    context = runner.context(ws)
    assert context.token == TOKEN
    with ws.db() as db:
        assert db.scalar("SELECT count(*) FROM sessions") == 0
