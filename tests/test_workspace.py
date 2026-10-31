"""The workspace folder and its settings: where it lives and whose documents are out of scope."""

import pytest

from iplikci import pipeline
from iplikci.sources import collect
from iplikci.workspace import HOME_ENV, SETTINGS, Workspace, home

from conftest import JANUARY, put, teb_export

BASE_SETTINGS = 'belge_klasoru = "Bankalar"\n'
COMPANY = "ÖRNEK TEKNOLOJİ ANONİM ŞİRKETİ"


def settings(base, extra: str = "") -> None:
    (base / SETTINGS).write_text(BASE_SETTINGS + extra, encoding="utf-8")


def test_the_home_variable_names_the_workspace_folder(tmp_path, monkeypatch):
    monkeypatch.setenv(HOME_ENV, str(tmp_path))
    settings(tmp_path)
    assert home() == tmp_path
    assert Workspace.load().base == tmp_path.resolve()


def test_without_the_home_variable_the_working_folder_is_the_workspace(tmp_path, monkeypatch):
    monkeypatch.delenv(HOME_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    assert home() == tmp_path


def test_documents_of_the_companies_in_the_settings_stay_out_of_scope(tmp_path):
    settings(tmp_path, '[identity]\nbusiness_names = ["Örnek Teknoloji A.Ş."]\n')
    ws = Workspace.load(tmp_path)
    put(ws.documents / "TEB" / "sirket.xls", teb_export(JANUARY, holder=COMPANY))
    put(ws.documents / "TEB" / "kisisel.xls", teb_export(JANUARY, number="987654321"))
    docs, _ = collect([ws.documents])
    statuses = {doc.name: status for doc, _, status in pipeline.parse_all(docs, None)}
    assert statuses["sirket.xls"][0] == "is"
    assert statuses["kisisel.xls"] is None


@pytest.mark.parametrize("extra", [
    '[identity]\nbusiness_names = "Örnek Teknoloji"\n',  # a name, not a list of names
    "[identity]\nbusiness_names = [1, 2]\n",
    'identity = "Örnek Teknoloji"\n',
])
def test_company_names_of_the_wrong_shape_are_an_error(tmp_path, extra):
    settings(tmp_path, extra)
    with pytest.raises(ValueError, match="business_names"):
        Workspace.load(tmp_path)


def test_the_parse_cache_is_read_again_when_the_company_names_change(tmp_path):
    settings(tmp_path)
    ws = Workspace.load(tmp_path)
    put(ws.documents / "TEB" / "hareket.xls", teb_export(JANUARY, holder=COMPANY))
    docs, _ = collect([ws.documents])
    [(_, result, status)] = pipeline.parse_all(docs, ws.output)
    assert result is not None and status is None  # no company names yet: read as a personal account
    settings(tmp_path, '[identity]\nbusiness_names = ["Örnek Teknoloji"]\n')
    Workspace.load(tmp_path)
    [(_, result, status)] = pipeline.parse_all(docs, ws.output)
    assert result is None and status[0] == "is"
