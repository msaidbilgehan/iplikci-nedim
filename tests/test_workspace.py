"""The data folder as the program opens it: where it lives, its settings, and whose documents are out of scope."""

import pytest

from iplikci.app import reading
from iplikci.app.analysis import analyze
from iplikci.app.workspace import Workspace
from iplikci.demo import teb_export
from iplikci.domain.codes import DocumentStatus
from iplikci.settings.config import SettingsError
from iplikci.settings.paths import HOME_ENV
from iplikci.storage import audit, documents

from conftest import JANUARY, add

COMPANY = "ÖRNEK TEKNOLOJİ ANONİM ŞİRKETİ"


def settings(ws: Workspace, text: str) -> Workspace:
    ws.layout.settings.write_text(text, encoding="utf-8")
    return Workspace.load(ws.home)


def test_the_home_variable_names_the_data_folder(tmp_path, monkeypatch):
    monkeypatch.setenv(HOME_ENV, str(tmp_path / "veri"))
    ws = Workspace.load()
    assert ws.home == tmp_path / "veri"
    assert ws.layout.objects.is_dir() and ws.inbox.is_dir()


def test_a_fresh_data_folder_has_the_default_settings(ws):
    assert ws.port == 8643
    assert ws.settings.identity.business_names == ()
    with ws.db() as db:
        assert documents.every(db) == []


def test_documents_of_the_companies_in_the_settings_are_never_kept(ws):
    ws = settings(ws, '[identity]\nbusiness_names = ["Örnek Teknoloji A.Ş."]\n')
    company = add(ws, "sirket.xls", teb_export(JANUARY, holder=COMPANY))
    personal = add(ws, "kisisel.xls", teb_export(JANUARY, number="987654321"))
    assert [c.verdict for c in company.items] == ["business"]
    assert [c.status for c in personal.items] == [DocumentStatus.PROCESSED]
    assert not ws.vault.has(company.items[0].sha256)
    with ws.db() as db:
        assert [d.name for d in documents.every(db)] == ["kisisel.xls"]
        assert audit.targets(db, "document.business") == {company.items[0].sha256}


@pytest.mark.parametrize(
    "text",
    [
        '[identity]\nbusiness_names = "Örnek Teknoloji"\n',  # a name, not a list of names
        "[identity]\nbusiness_names = [1, 2]\n",
        'identity = "Örnek Teknoloji"\n',
    ],
)
def test_company_names_of_the_wrong_shape_are_an_error(ws, text):
    with pytest.raises(SettingsError):
        settings(ws, text)


def test_a_kept_document_that_turns_out_to_be_a_company_one_goes_to_the_trash(ws, private_trash):
    [kept] = add(ws, "hareket.xls", teb_export(JANUARY, holder=COMPANY)).items
    assert kept.status is DocumentStatus.PROCESSED  # no company names yet: read as a personal account
    ws = settings(ws, '[identity]\nbusiness_names = ["Örnek Teknoloji"]\n')
    with ws.db() as db:
        assert reading.read_pending(ws, db) == 1  # other company names: read again
        doc = documents.get(db, kept.sha256)
        assert doc is not None and doc.status is DocumentStatus.REMOVED
        assert db.scalar("SELECT count(*) FROM transactions") == 0
        assert [e.action for e in audit.entries(db)][-2:] == ["document.business", "document.removed"]
    assert not ws.vault.has(kept.sha256)
    assert any(p.name == kept.sha256 for p in private_trash.rglob("*"))
    a = analyze(ws)
    assert a.stats["documents"] == 1 and [d.status for d in a.dataset.documents] == ["is"]


def test_readings_are_kept_until_the_readers_or_the_names_change(ws):
    add(ws, "hareket.xls", teb_export(JANUARY))
    with ws.db() as db:
        assert reading.read_pending(ws, db) == 0
        assert reading.read_pending(ws, db, every=True) == 1
