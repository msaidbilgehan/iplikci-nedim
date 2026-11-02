"""The settings of the setup wizard and the Settings screen (F17): who the user is, how e-mail comes in, how long
backups are kept. Changed only from the service's own pages; a password is only taken in, the address shown masked,
and a refused login is never tried again."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import setup
from iplikci.app.analysis import analyze
from iplikci.app.workspace import Workspace
from iplikci.domain.codes import DocumentStatus
from iplikci.fakes import teb
from iplikci.parsers.common import business_names_signature
from iplikci.settings import config
from iplikci.storage import audit, documents

from conftest import ADDRESS, APP_PASSWORD, JANUARY, add

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}
COMPANY = "ÖRNEK TEKNOLOJİ ANONİM ŞİRKETİ"


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(ws: Workspace) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN, today=lambda: demo.AS_OF)), base_url=BASE)


def signed_in(client: TestClient) -> TestClient:
    url = client.post("/api/login-links", headers=bearer()).json()["url"]
    assert client.get(url, follow_redirects=False).status_code == 303
    return client


def test_the_settings_show_the_address_masked_and_no_secret(client, mail):
    response = client.get("/api/settings", headers=bearer())
    found = response.json()["mail"]
    assert (found["connector"], found["configured"], found["address"]) == ("imap", True, "k•••@example.com")
    assert (found["start"], found["server"], found["stopped"]) == ("2026-01-01", "imap.gmail.com", False)
    assert ADDRESS not in response.text and APP_PASSWORD not in response.text


def test_an_imap_account_is_set_up_with_one_login_and_its_password_goes_to_the_keychain(client, ws, imap):
    body = {"address": ADDRESS, "password": APP_PASSWORD, "start": "2026-01-01"}
    assert client.post("/api/settings/mail/imap", json=body, headers=bearer()).status_code == 403  # the pages only
    found = signed_in(client).post("/api/settings/mail/imap", json=body, headers=OWN_PAGE).json()
    assert found["in_keyring"] and found["folder"]
    assert imap.stored == {ADDRESS: APP_PASSWORD} and imap.connections == 1
    assert config.load(ws.layout.settings).mail.start_day == date(2026, 1, 1)
    with ws.db() as db:
        [entry] = audit.entries(db, setup.MAIL_CHANGED)
    assert ADDRESS not in str(entry.detail)


def test_a_refused_login_keeps_nothing_and_is_tried_once(client, ws, imap):
    body = {"address": ADDRESS, "password": "yanlis-sifre-0000"}
    refused = signed_in(client).post("/api/settings/mail/imap", json=body, headers=OWN_PAGE)
    assert (refused.status_code, refused.json()["code"]) == (400, "mail_refused")
    assert "yanlis-sifre" not in refused.text
    assert imap.stored == {} and [c for c in imap.commands if c[0] == "LOGIN"] == [("LOGIN", ADDRESS)]
    assert not config.load(ws.layout.settings).mail.address


def test_removing_the_imap_account_forgets_its_password(client, mail):
    signed_in(client)
    assert client.delete("/api/settings/mail/imap", headers=OWN_PAGE).status_code == 204
    assert mail.stored == {}
    found = client.get("/api/settings", headers=bearer()).json()["mail"]
    assert (found["configured"], found["address"]) == (False, "")
    again = client.delete("/api/settings/mail/imap", headers=OWN_PAGE)
    assert (again.status_code, again.json()["code"]) == (404, "mail_not_set_up")


def test_the_connector_turns_to_imap_only_with_an_account_and_the_start_day_is_never_ahead(client, ws):
    signed_in(client)
    imap = client.put("/api/settings/mail", json={"connector": "imap"}, headers=OWN_PAGE)
    assert (imap.status_code, imap.json()["code"]) == (400, "settings_refused")
    ahead = {"start": (date.today() + timedelta(days=1)).isoformat()}
    assert client.put("/api/settings/mail", json=ahead, headers=OWN_PAGE).status_code == 400
    found = client.put(
        "/api/settings/mail", json={"connector": "browser_bridge", "start": "2025-06-01"}, headers=OWN_PAGE
    ).json()["mail"]
    assert (found["connector"], found["start"]) == ("browser_bridge", "2025-06-01")
    assert client.put("/api/settings/mail", json={"connector": "pop3"}, headers=OWN_PAGE).status_code == 422


def test_each_name_is_kept_once_and_the_audit_log_keeps_none(client, ws):
    body = {"names": [" Ayşe  Örnek ", "ayşe örnek", ""], "business_names": ["Örnek Teknoloji A.Ş."]}
    found = signed_in(client).put("/api/settings/identity", json=body, headers=OWN_PAGE).json()
    assert (found["names"], found["business_names"]) == (["Ayşe Örnek"], ["Örnek Teknoloji A.Ş."])
    with ws.db() as db:
        [entry] = audit.entries(db, setup.IDENTITY_CHANGED)
    assert "Örnek" not in str(entry.detail)
    control = {"names": ["Ayşe\x1b[31m"], "business_names": []}
    assert client.put("/api/settings/identity", json=control, headers=OWN_PAGE).status_code == 422
    cleared = client.put("/api/settings/identity", json={"names": [], "business_names": []}, headers=OWN_PAGE)
    assert cleared.json()["business_names"] == [] and "Örnek" not in ws.layout.settings.read_text(encoding="utf-8")


def test_a_company_name_added_while_the_service_runs_takes_its_documents_out(client, ws, private_trash):
    [kept] = add(ws, "hareket.xls", teb.account_export(JANUARY, holder=COMPANY)).items
    before = business_names_signature()
    body = {"names": [], "business_names": ["Örnek Teknoloji"]}
    signed_in(client).put("/api/settings/identity", json=body, headers=OWN_PAGE)
    assert business_names_signature() != before  # this process reads with the new names at once
    analyze(ws)  # the service's own Workspace, loaded before the change
    with ws.db() as db:
        doc = documents.get(db, kept.sha256)
    assert doc is not None and doc.status is DocumentStatus.REMOVED
    assert not ws.vault.has(kept.sha256)


def test_backups_are_kept_for_one_day_to_a_year(client, ws):
    signed_in(client)
    found = client.put("/api/settings/backup", json={"keep_days": 30}, headers=OWN_PAGE).json()
    assert found["backup_days"] == 30 and config.load(ws.layout.settings).backup.keep_days == 30
    for days in (0, 366):
        assert client.put("/api/settings/backup", json={"keep_days": days}, headers=OWN_PAGE).status_code == 422


def test_the_wizard_says_where_each_step_stands_and_opens_on_the_first_run(client, ws, mail, monkeypatch):
    monkeypatch.setattr(setup, "service_installed", lambda: False)
    first = client.get("/api/setup", headers=bearer()).json()
    steps = {s["step"]: s for s in first["steps"]}
    assert list(steps)[:2] == ["data_folder", "names"] and steps["data_folder"]["note"] == str(ws.home)
    assert steps["mail"]["done"] and steps["mail"]["note"] == "IMAP hesabı kurulu."  # the fixture set one up
    assert not first["first_run"]  # e-mail is set up: no first run any more
    assert (steps["service"]["done"], steps["remote"]["optional"]) == (False, True)
    assert not steps["documents"]["done"] and steps["documents"]["note"] == "Henüz belge yok."


def test_without_anything_set_up_it_is_the_first_run(client, ws, monkeypatch):
    monkeypatch.setattr(setup, "service_installed", lambda: True)
    found = client.get("/api/setup", headers=bearer()).json()
    assert found["first_run"]
    assert next(s for s in found["steps"] if s["step"] == "service")["done"]
    assert client.get("/api/settings", headers=bearer()).json()["bank_senders"]  # the shipped banks
