"""The service's own life from the interface (ADR-0017): stopped, restarted, a backup put back as it starts again,
and taken off the computer with the data folder to the Trash only when asked. The service's end, the service manager
and the Trash are stand-ins: nothing ends the test process, reaches launchd or the real Trash."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import backup, lifecycle, setup
from iplikci.app.workspace import Workspace
from iplikci.domain.codes import Actor
from iplikci.service import manager, runner
from iplikci.settings import config
from iplikci.storage import audit

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}


class FakeLife:
    def __init__(self) -> None:
        self.codes: list[int] = []

    def end(self, code: int) -> None:
        self.codes.append(code)


class FakeManager:
    name = "launchd"

    def __init__(self) -> None:
        self.unregistered = 0

    def unregister(self) -> bool:
        self.unregistered += 1
        return True


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def life() -> FakeLife:
    return FakeLife()


@pytest.fixture
def client(ws, life) -> TestClient:
    found = TestClient(create_app(Context(ws=ws, token=TOKEN, lifecycle=life)), base_url=BASE)
    url = found.post("/api/login-links", headers=bearer()).json()["url"]
    assert found.get(url, follow_redirects=False).status_code == 303
    return found


@pytest.fixture
def registered(ws, monkeypatch):
    """This data folder's service is registered with the computer's service manager."""
    monkeypatch.setattr(setup, "registered_home", lambda: ws.home)
    monkeypatch.setattr(manager, "for_platform", FakeManager)


def test_the_service_says_whether_the_computer_starts_it(client, ws, monkeypatch):
    monkeypatch.setattr(setup, "registered_home", lambda: None)
    found = client.get("/api/service", headers=bearer()).json()
    assert (found["registered"], found["can_end"]) == (False, True) and found["manager"]
    monkeypatch.setattr(setup, "registered_home", lambda: ws.home)
    assert client.get("/api/service", headers=bearer()).json()["registered"]


def test_a_stop_answers_first_and_then_ends_the_service_cleanly(client, life):
    assert client.post("/api/service/stop", headers=bearer()).status_code == 403  # the token reads, never stops
    found = client.post("/api/service/stop", headers=OWN_PAGE)
    assert (found.status_code, found.json()) == (202, {"ending": True, "restarts": False})
    assert life.codes == [lifecycle.STOP]


def test_a_restart_needs_the_service_registered_for_this_folder(client, life, registered, monkeypatch):
    found = client.post("/api/service/restart", headers=OWN_PAGE)
    assert (found.status_code, found.json()["restarts"], life.codes) == (202, True, [lifecycle.RESTART])
    monkeypatch.setattr(setup, "registered_home", lambda: None)  # run by hand, in the foreground
    refused = client.post("/api/service/restart", headers=OWN_PAGE)
    assert (refused.status_code, refused.json()["code"]) == (409, "service_not_registered")
    assert life.codes == [lifecycle.RESTART]


def test_without_the_service_nothing_can_be_ended(ws):
    found = TestClient(create_app(Context(ws=ws, token=TOKEN)), base_url=BASE)
    url = found.post("/api/login-links", headers=bearer()).json()["url"]
    found.get(url, follow_redirects=False)
    assert found.get("/api/service", headers=bearer()).json()["can_end"] is False
    assert found.post("/api/service/stop", headers=OWN_PAGE).json()["code"] == "service_unmanaged"


def test_removing_the_service_unregisters_it_and_leaves_the_data_folder_unless_asked(client, ws, life, registered):
    assert client.post("/api/service/remove", json={}, headers=OWN_PAGE).status_code == 202
    assert life.codes == [lifecycle.STOP] and not (ws.run / lifecycle.REMOVAL_REQUEST).exists()
    assert client.post("/api/service/remove", json={"data_to_trash": True}, headers=OWN_PAGE).status_code == 202
    assert json.loads((ws.run / lifecycle.REMOVAL_REQUEST).read_text(encoding="utf-8")) == {"data_to_trash": True}
    with ws.db() as db:
        removed = [e.detail for e in audit.entries(db) if e.action == lifecycle.REMOVED]
    assert removed == [{"data_to_trash": False}, {"data_to_trash": True}]


def test_the_data_folder_goes_to_the_trash_only_at_the_end_and_only_when_asked(ws, monkeypatch):
    moved: list[Path] = []
    monkeypatch.setattr(lifecycle, "move_to_system_trash", lambda path: moved.append(path) or path)
    assert lifecycle.finish_removal(ws) is None and moved == []
    (ws.run / lifecycle.REMOVAL_REQUEST).write_text('{"data_to_trash": true}', encoding="utf-8")
    assert lifecycle.finish_removal(ws) == ws.home and moved == [ws.home]
    assert not (ws.run / lifecycle.REMOVAL_REQUEST).exists()


@pytest.fixture
def demo_ws(tmp_path) -> Workspace:
    return Workspace.load(demo.build(tmp_path / "demo"))


def test_a_backup_is_checked_now_and_put_back_as_the_service_starts_again(demo_ws, life, monkeypatch):
    monkeypatch.setattr(setup, "registered_home", lambda: demo_ws.home)
    taken = backup.take(demo_ws)
    config.update(demo_ws.layout.settings, "backup", {"keep_days": 30})  # a change after the backup
    found = TestClient(create_app(Context(ws=demo_ws, token=TOKEN, lifecycle=life)), base_url=BASE)
    url = found.post("/api/login-links", headers=bearer()).json()["url"]
    found.get(url, follow_redirects=False)
    asked = found.post(f"/api/backups/{taken.name}/restore", headers=OWN_PAGE)
    assert (asked.status_code, asked.json(), life.codes) == (202, {"backup": taken.name, "restarts": True}, [75])
    restored = lifecycle.apply_pending_restore(demo_ws)  # what the next start does first
    assert restored is not None and restored.safety  # what there was is kept in a backup of its own
    assert config.load(demo_ws.layout.settings).backup.keep_days != 30
    assert not (demo_ws.run / lifecycle.RESTORE_REQUEST).exists()
    assert lifecycle.apply_pending_restore(demo_ws) is None  # once


@pytest.mark.parametrize("name", ["yok boyle bir yedek", "..%2F..%2Fbaska", "..%5Cbaska"])
def test_only_a_backup_of_the_backups_folder_can_be_put_back(client, life, registered, name):
    found = client.post(f"/api/backups/{name}/restore", headers=OWN_PAGE)
    assert 400 <= found.status_code < 500 and life.codes == []  # refused, whatever route the path reaches


def test_a_restore_that_cannot_be_done_at_the_start_is_dropped_and_the_data_stays(ws):
    (ws.run / lifecycle.RESTORE_REQUEST).write_text('{"backup": "yok"}', encoding="utf-8")
    assert lifecycle.apply_pending_restore(ws) is None and not (ws.run / lifecycle.RESTORE_REQUEST).exists()
    (ws.run / lifecycle.RESTORE_REQUEST).write_text("bozuk", encoding="utf-8")
    assert lifecycle.apply_pending_restore(ws) is None and not (ws.run / lifecycle.RESTORE_REQUEST).exists()


def test_the_running_service_ends_with_the_code_asked_for():
    class Server:
        should_exit = False

    life = runner.Life()
    life.server = Server()  # pyright: ignore[reportAttributeAccessIssue] - a stand-in for uvicorn's server
    life.end(lifecycle.RESTART)
    assert (life.server.should_exit, life.code) == (True, 75)


def test_unregistering_leaves_the_running_process_alone(tmp_path):
    calls: list[list[str]] = []

    def tools(args):
        calls.append(list(args))
        return manager.Completed(0, "", "")

    launchd = manager.Launchd(tmp_path, run=tools, uid=501)
    launchd.install(manager.Program(tmp_path / "python", tmp_path / "veri"))
    calls.clear()
    assert launchd.unregister() and not launchd.path.exists() and calls == []  # no bootout: it ends by itself
    assert launchd.unregister() is False
    systemd = manager.Systemd(tmp_path, run=tools, env={"XDG_CONFIG_HOME": str(tmp_path / "ayar")})
    systemd.path.parent.mkdir(parents=True)
    systemd.path.write_text("[Unit]\n", encoding="utf-8")
    assert systemd.unregister() and ["systemctl", "--user", "disable", "iplikci.service"] in calls
    assert not any("--now" in c for c in calls)
    scheduler = manager.TaskScheduler(run=tools, env={"USERNAME": "deneme"})
    assert scheduler.unregister() and calls[-1] == ["schtasks", "/Delete", "/TN", "iplikci", "/F"]


def test_a_restore_is_recorded_before_the_service_ends(demo_ws):
    taken = backup.take(demo_ws)
    lifecycle.request_restore(demo_ws, taken.name, Actor.USER)
    with demo_ws.db() as db:
        assert [e.target for e in audit.entries(db) if e.action == lifecycle.RESTORE_REQUESTED] == [taken.name]
