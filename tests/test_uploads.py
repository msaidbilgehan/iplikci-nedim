"""Adding documents by hand (F02, ADR-0007): uploads wait in vault/staging until their plan is confirmed; the inbox
folder is taken in without a plan once it is quiet."""

import os
import time
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import background, uploads
from iplikci.domain.codes import SourceKind
from iplikci.ingest.inbox import InboxWatcher
from iplikci.storage import audit, documents, events

from conftest import FEBRUARY, put

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}


@pytest.fixture
def client(ws) -> TestClient:
    client = TestClient(create_app(Context(ws=ws, token=TOKEN)), base_url=BASE)
    url = client.post("/api/login-links", headers={"Authorization": f"Bearer {TOKEN}"}).json()["url"]
    client.get(url, follow_redirects=False)
    return client


def upload(client: TestClient, name: str, data: bytes, batch: str = "") -> dict:
    response = client.post(
        "/api/uploads",
        params={"batch": batch} if batch else None,
        content=data,
        headers=OWN_PAGE | {"X-Filename": quote(name)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def kept(ws) -> list[documents.DocumentRow]:
    with ws.db() as db:
        return documents.every(db)


def test_an_upload_waits_for_its_plan_and_goes_into_the_vault_on_confirmation(client, ws):
    first = upload(client, "Şubat Hesap Hareketleri.xls", FEBRUARY)
    assert first["status"] == "eklendi" and first["name"] == "Şubat Hesap Hareketleri.xls"
    assert kept(ws) == []  # nothing taken in before the plan is confirmed
    plan = client.post("/api/inbox/plan", json={"upload": first["batch"]}, headers=OWN_PAGE).json()
    assert plan["changes"] == 1 and plan["items"][0]["action"] == "processed"
    assert plan["items"][0]["document"]["kind"] == "hesap"
    done = client.post("/api/inbox/apply", json={"plan_id": plan["plan_id"]}, headers=OWN_PAGE).json()
    assert done["stored"] == 1
    [doc] = kept(ws)
    with ws.db() as db:
        assert documents.sources(db, doc.sha256)[0].kind is SourceKind.UPLOAD
    assert not (ws.layout.staging / uploads.UPLOADS / first["batch"]).exists()  # the staging copy left


def test_the_same_file_twice_in_a_batch_is_one_file(client):
    first = upload(client, "a.xls", FEBRUARY)
    again = upload(client, "b.xls", FEBRUARY, batch=first["batch"])
    assert (again["status"], again["name"]) == ("zaten-var", "a.xls")


def test_a_file_that_is_no_document_is_refused_with_the_reason(client, ws):
    refused = upload(client, "notlar.txt", b"merhaba")
    assert refused["status"] == "reddedildi" and "desteklenmeyen dosya türü" in refused["reason"]
    assert not any((ws.layout.staging / uploads.UPLOADS / refused["batch"]).iterdir())


def test_a_plan_is_applied_only_as_it_was_shown(client, ws):
    first = upload(client, "a.xls", FEBRUARY)
    plan = client.post("/api/inbox/plan", json={"upload": first["batch"]}, headers=OWN_PAGE).json()
    (ws.layout.staging / uploads.UPLOADS / first["batch"] / "a.xls").write_bytes(FEBRUARY + b" ")
    stale = client.post("/api/inbox/apply", json={"plan_id": plan["plan_id"]}, headers=OWN_PAGE)
    assert stale.status_code == 409 and stale.json()["code"] == "plan_stale"
    gone = client.post("/api/inbox/apply", json={"plan_id": "yok"}, headers=OWN_PAGE)
    assert gone.status_code == 404 and kept(ws) == []


def test_uploads_are_writes_of_the_services_own_pages(client):
    response = client.post("/api/uploads", content=FEBRUARY, headers={"X-Filename": "a.xls"})
    assert response.status_code == 403


def test_a_batch_name_must_be_one_the_service_gave(client):
    response = client.post("/api/uploads", params={"batch": "../../etc"}, content=FEBRUARY, headers=OWN_PAGE)
    assert response.status_code in (400, 422)


def test_the_inbox_can_be_planned_and_applied_through_the_api_too(client, ws):
    put(ws.inbox / "ekstre.xls", FEBRUARY)
    plan = client.post("/api/inbox/plan", json={}, headers=OWN_PAGE).json()
    assert plan["changes"] == 1 and plan["items"][0]["fromInbox"]
    assert client.post("/api/inbox/apply", json={"plan_id": plan["plan_id"]}, headers=OWN_PAGE).json()["stored"] == 1
    assert list(ws.inbox.iterdir()) == []


def test_the_service_takes_the_inbox_in_without_a_plan(ws):
    put(ws.inbox / "Banka" / "ekstre.xls", FEBRUARY)
    assert background.take_inbox(ws) == 1
    assert not (ws.inbox / "Banka").exists()
    with ws.db() as db:
        assert [e.kind for e in events.entries(db)][:2] == ["document.received", "document.processed"]


def test_the_inbox_watcher_waits_until_the_folder_is_quiet(tmp_path):
    now = [0.0]
    folder = tmp_path / "gelen"
    folder.mkdir()
    watcher = InboxWatcher(folder, lambda: None, quiet=20, clock=lambda: now[0])
    assert not watcher.look()  # empty
    put(folder / "a.pdf", b"%PDF-1.4")
    assert not watcher.look()  # just arrived
    now[0] += 10
    assert not watcher.look()  # quiet for 10 seconds only
    put(folder / "a.pdf", b"%PDF-1.4 still being written")
    now[0] += 15
    assert not watcher.look()  # it changed: the quiet time starts again
    now[0] += 21
    assert watcher.look()
    assert not watcher.look()  # told once for this state of the folder
    put(folder / ".yukleniyor-x", b"half")  # hidden files are not waiting documents
    now[0] += 30
    assert not watcher.look()


def test_upload_batches_nobody_applied_go_to_the_trash_after_a_day(client, ws, private_trash):
    first = upload(client, "a.xls", FEBRUARY)
    folder = ws.layout.staging / uploads.UPLOADS / first["batch"]
    old = time.time() - 2 * 24 * 3600
    os.utime(folder, (old, old))
    background.purge(ws)
    assert not folder.exists()
    with ws.db() as db:
        assert audit.targets(db, "upload.abandoned") == {""}
