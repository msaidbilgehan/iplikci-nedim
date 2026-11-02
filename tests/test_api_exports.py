"""The exports (F20): what the analysis wrote, each downloaded as a file under a readable name, the month-end pages
zipped, and a request to make them again."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import exports
from iplikci.app.analysis import analyze
from iplikci.app.kinds import REFRESH
from iplikci.app.workspace import Workspace
from iplikci.storage import jobs

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(scope="module")
def written(tmp_path_factory) -> Workspace:
    """The demo data folder after an analysis that wrote its exports, as the service's refresh does."""
    ws = Workspace.load(demo.build(tmp_path_factory.mktemp("demo")))
    analyze(ws, write=True, today=demo.AS_OF)
    return ws


def client_for(ws: Workspace) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN)), base_url=BASE)


def test_the_exports_the_analysis_wrote_are_listed_with_their_download_names(written):
    found = client_for(written).get("/api/exports", headers=bearer()).json()
    assert [e["kind"] for e in found] == ["report", "csv", "xlsx", "month_end"]
    names = {e["kind"]: e["name"] for e in found}
    assert names["report"].startswith("iplikci-rapor-") and names["report"].endswith(".html")
    assert names["month_end"].startswith("iplikci-ay-sonu-") and names["month_end"].endswith(".zip")
    assert all(e["size"] > 0 for e in found)


def test_an_export_downloads_as_an_attachment_never_as_a_page(written):
    client = client_for(written)
    report = client.get("/api/exports/report", headers=bearer())
    assert report.status_code == 200 and report.headers["content-type"].startswith("text/html")
    assert report.headers["content-disposition"].startswith('attachment; filename="iplikci-rapor-')
    assert report.content == (written.exports / exports.FILES[exports.ExportKind.REPORT]).read_bytes()
    rows = client.get("/api/exports/csv", headers=bearer())
    assert rows.content.startswith("﻿Tarih;Ay;".encode())  # opens in Turkish Excel as it is


def test_the_month_end_pages_come_as_one_zip_with_their_index(written):
    found = client_for(written).get("/api/exports/month_end", headers=bearer())
    assert found.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(found.content)) as archive:
        names = archive.namelist()
    assert "ay-sonu/index.html" in names and all(n.startswith("ay-sonu/") for n in names)


def test_before_the_first_analysis_nothing_is_listed_and_a_download_says_why(ws):
    client = client_for(ws)
    assert client.get("/api/exports", headers=bearer()).json() == []
    missing = client.get("/api/exports/xlsx", headers=bearer())
    assert (missing.status_code, missing.json()["code"]) == (404, "export_missing")
    # Only the kinds named: no file a request makes up.
    assert client.get("/api/exports/settings", headers=bearer()).status_code == 422
    assert client.get("/api/exports/..%2Fsettings.toml", headers=bearer()).status_code == 404


def test_a_link_put_in_the_folder_is_never_served(written, tmp_path):
    outside = tmp_path / "baska.html"
    outside.write_text("başka bir dosya", encoding="utf-8")
    ws = Workspace.load(tmp_path / "iplikci")
    ws.exports.mkdir(parents=True, exist_ok=True)
    (ws.exports / exports.FILES[exports.ExportKind.REPORT]).symlink_to(outside)
    assert client_for(ws).get("/api/exports/report", headers=bearer()).status_code == 404


def test_making_them_again_queues_one_analysis(ws):
    client = client_for(ws)
    assert client.get("/api/exports").status_code == 401
    assert client.post("/api/exports", headers=bearer()).json() == {"queued": True}
    assert client.post("/api/exports", headers=bearer()).json() == {"queued": False}  # one waits already
    with ws.db() as db:
        assert jobs.counts(db) == {"queued": 1}
        assert [r["kind"] for r in db.rows("SELECT kind FROM jobs")] == [REFRESH]
