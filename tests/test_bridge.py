"""The browser extension's side of the service (ADR-0016): pairing with a code, the proof of the paired service, a
token that opens only the mail intake and the login link of "İplikçi Nedim'i aç" (ADR-0019), revocation, and the
messages it delivers."""

import email
import email.policy
import hashlib
import hmac
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from iplikci.api import pages
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import bridge
from iplikci.app.bridge import MAX_WRONG_CODES, PairingCodes
from iplikci.domain.codes import DocumentStatus
from iplikci.fakes import teb
from iplikci.parsers.common import set_business_names
from iplikci.settings import config
from iplikci.storage import audit, documents, events

from conftest import FEBRUARY, bank_mail

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}
EXTENSION = {"Origin": "chrome-extension://abcdefghijklmnop"}


@pytest.fixture
def client(ws) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN)), base_url=BASE)


def signed_in(client: TestClient) -> TestClient:
    url = client.post("/api/login-links", headers={"Authorization": f"Bearer {TOKEN}"}).json()["url"]
    client.get(url, follow_redirects=False)
    return client


def code(client: TestClient) -> str:
    response = signed_in(client).post("/api/bridge/pairings", headers=OWN_PAGE)
    assert response.status_code == 200 and response.json()["expires_in"] == 600
    return response.json()["code"]


def paired(client: TestClient) -> dict[str, str]:
    extension = TestClient(client.app, base_url=BASE)  # no browser session
    response = extension.post(
        "/api/bridge/pair", json={"code": code(client), "name": "Chrome 140, macOS"}, headers=EXTENSION
    )
    assert response.status_code == 200, response.text
    return response.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_an_extension_pairs_with_a_code_and_becomes_the_mail_connector(client, ws):
    found = paired(client)
    assert set(found) == {"id", "token"} and len(found["token"]) > 30
    assert config.load(ws.layout.settings).mail.connector == "browser_bridge"
    with ws.db() as db:
        [stored] = db.rows("SELECT token_hash, name FROM bridges")
    assert stored["token_hash"] == hashlib.sha256(found["token"].encode()).hexdigest()  # never the token itself
    listed = client.get("/api/bridge").json()
    assert [(b["id"], b["name"], b["active"]) for b in listed] == [(found["id"], "Chrome 140, macOS", True)]
    assert "token" not in listed[0]
    mail = client.get("/api/system").json()["mail"]
    assert (mail["connector"], mail["configured"], mail["last_run"]) == ("browser_bridge", True, "")
    with ws.db() as db:
        assert [e.kind for e in events.entries(db, "bridge.paired")] == ["bridge.paired"]  # the page refreshes on it
        assert audit.targets(db, "bridge.paired") == {found["id"]}


def test_a_code_works_once(client):
    one = code(client)
    extension = TestClient(client.app, base_url=BASE)
    assert extension.post("/api/bridge/pair", json={"code": one}, headers=EXTENSION).status_code == 200
    again = extension.post("/api/bridge/pair", json={"code": one}, headers=EXTENSION)
    assert again.status_code == 403 and again.json()["code"] == "pairing_code_invalid"


def test_codes_expire_and_wrong_guesses_close_them():
    now = [0.0]
    codes = PairingCodes(clock=lambda: now[0])
    first, _ = codes.issue()
    now[0] += 601
    assert not codes.redeem(first)
    second, _ = codes.issue()
    for _ in range(MAX_WRONG_CODES):
        assert not codes.redeem("YANLISKD")
    assert not codes.redeem(second)  # five wrong ones closed it
    third, _ = codes.issue()
    assert codes.redeem(third.lower()[:4] + "-" + third[4:].lower())  # typed by hand, any case, with a dash


def test_a_web_page_cannot_pair_even_with_a_code(client):
    one = code(client)
    page = TestClient(client.app, base_url=BASE)
    refused = page.post("/api/bridge/pair", json={"code": one}, headers={"Origin": "https://kotu.example"})
    assert refused.status_code == 403 and refused.json()["code"] == "write_denied"
    assert page.post("/api/bridge/pair", json={"code": one}, headers=EXTENSION).status_code == 200  # still open


def test_only_a_signed_in_page_of_the_service_asks_for_a_code(client):
    assert client.post("/api/bridge/pairings").status_code == 401
    signed_in(client)
    assert client.post("/api/bridge/pairings").status_code == 403  # no Origin and X-Iplikci


def test_the_service_proves_it_is_the_one_the_extension_paired_with(client):
    found = paired(client)
    nonce = "a" * 32
    answer = client.get("/api/bridge/hello", params={"id": found["id"], "nonce": nonce})
    key = hashlib.sha256(found["token"].encode()).hexdigest().encode()
    assert answer.json()["proof"] == hmac.new(key, nonce.encode(), hashlib.sha256).hexdigest()
    assert client.get("/api/bridge/hello", params={"id": "baska", "nonce": nonce}).status_code == 404
    assert client.get("/api/bridge/hello", params={"id": found["id"], "nonce": "kisa"}).status_code == 422


def test_a_bridges_token_opens_the_mail_intake_and_its_login_link_and_nothing_else(client):
    found = paired(client)
    other = TestClient(client.app, base_url=BASE)
    assert other.get("/api/system", headers=bearer(found["token"])).json()["code"] == "forbidden"
    assert other.get("/api/ingest/mail/cursor", headers=bearer(found["token"])).status_code == 200
    assert other.get("/api/ingest/mail/cursor", headers=bearer(TOKEN)).status_code == 403  # the CLI's token
    assert other.get("/api/ingest/mail/cursor").status_code == 401
    assert other.post("/api/login-links", headers=bearer(found["token"])).json()["code"] == "forbidden"  # the CLI's


def test_a_paired_extension_gets_a_login_link_that_opens_one_browser_session_once(client):
    found = paired(client)
    extension = TestClient(client.app, base_url=BASE)  # its service worker: no cookie, its own origin
    answer = extension.post("/api/bridge/login-link", headers=bearer(found["token"]) | EXTENSION)
    assert answer.status_code == 200, answer.text
    url = answer.json()["url"]
    assert url.startswith(f"{BASE}/giris?anahtar=")  # the only links the extension opens
    tab = TestClient(client.app, base_url=BASE)  # the browser tab the extension opens the link in
    entered = tab.get(url, follow_redirects=False)
    assert (entered.status_code, entered.headers["location"]) == (303, "/")
    assert entered.headers["set-cookie"].startswith("iplikci_oturum_8643=")
    assert tab.get("/api/system").status_code == 200  # a browser session like the command line's links open
    again = TestClient(client.app, base_url=BASE).get(url, follow_redirects=False)
    assert again.status_code == 403 and f"<title>{pages.SIGN_IN_TITLE}</title>" in again.text
    second = extension.post("/api/bridge/login-link", headers=bearer(found["token"])).json()["url"]
    assert second != url  # a new key each time


def test_only_an_active_extensions_token_gets_a_login_link_from_the_bridges_endpoint(client):
    found = paired(client)
    other = TestClient(client.app, base_url=BASE)
    assert other.post("/api/bridge/login-link").status_code == 401
    cli = other.post("/api/bridge/login-link", headers=bearer(TOKEN))
    assert (cli.status_code, cli.json()["code"]) == (403, "forbidden")  # the command line has its own
    browser = client.post("/api/bridge/login-link", headers=OWN_PAGE)  # signed in while pairing
    assert (browser.status_code, browser.json()["code"]) == (403, "forbidden")
    assert other.post("/api/bridge/login-link", headers=bearer("baska-bir-belirtec")).status_code == 401
    assert client.delete(f"/api/bridge/{found['id']}", headers=OWN_PAGE).status_code == 204
    revoked = other.post("/api/bridge/login-link", headers=bearer(found["token"]))
    assert (revoked.status_code, revoked.json()["code"]) == (401, "unauthenticated")


def test_delivered_messages_go_through_the_trust_rule_and_move_the_cursor(client, ws):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)

    def deliver(raw: bytes, gmail_id: str, day: str) -> dict:
        headers = bearer(token) | {"Content-Type": "message/rfc822", "X-Gmail-Id": gmail_id, "X-Gmail-Date": day}
        response = other.post("/api/ingest/mail", content=raw, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()

    assert deliver(bank_mail(FEBRUARY), "18f0a1", "2026-02-02T10:00:00+03:00") == {"taken": "stored", "documents": 2}
    forged = bank_mail(FEBRUARY, results=("mx.google.com; dmarc=fail header.from=teb.com.tr",))
    assert deliver(forged, "18e001", "2026-01-15T09:00:00+03:00")["taken"] == "unverified"
    cursor = other.get("/api/ingest/mail/cursor", headers=bearer(token)).json()
    assert (cursor["last_id"], cursor["last_date"]) == ("18f0a1", "2026-02-02T10:00:00+03:00")  # the older one did not
    assert "teb.com.tr" in cursor["senders"] and cursor["start_day"]
    with ws.db() as db:
        assert len(documents.every(db)) == 2


def test_a_revoked_bridge_is_refused(client, ws):
    found = paired(client)
    assert client.delete(f"/api/bridge/{found['id']}", headers=OWN_PAGE).status_code == 204
    other = TestClient(client.app, base_url=BASE)
    assert other.get("/api/ingest/mail/cursor", headers=bearer(found["token"])).status_code == 401
    assert client.get("/api/bridge/hello", params={"id": found["id"], "nonce": "b" * 32}).status_code == 404
    assert [b["active"] for b in client.get("/api/bridge").json()] == [False]
    assert client.delete(f"/api/bridge/{found['id']}", headers=OWN_PAGE).status_code == 404
    with ws.db() as db:
        assert audit.targets(db, "bridge.revoked") == {found["id"]} and events.entries(db, "bridge.revoked")


def test_the_intake_refuses_empty_and_too_large_messages(client, monkeypatch):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)
    assert other.post("/api/ingest/mail", content=b"", headers=bearer(token)).json()["code"] == "message_empty"
    huge = other.post("/api/ingest/mail", content=b"x" * 10, headers=bearer(token) | {"Content-Length": str(41 << 20)})
    assert huge.status_code == 413


def test_a_layer_that_meets_an_unknown_gmail_page_is_told_once_per_version(client, ws):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)
    first = other.post("/api/ingest/mail/alarm", json={"layer": 3, "version": "0.1.0"}, headers=bearer(token))
    assert first.json() == {"news": True}
    again = other.post("/api/ingest/mail/alarm", json={"layer": 3, "version": "0.1.0"}, headers=bearer(token))
    assert again.json() == {"news": False}
    assert other.post("/api/ingest/mail/alarm", json={"layer": 4}, headers=bearer(token)).status_code == 422
    assert other.post("/api/ingest/mail/alarm", json={"layer": 1}, headers=bearer(TOKEN)).status_code == 403
    with ws.db() as db:
        [event] = events.entries(db, "mail.bridge_alarm")
    assert (event.target, event.detail) == ("katman-3", {"version": "0.1.0"})
    assert "ham ileti katmanı durdu" in client.get("/api/system", headers=bearer(TOKEN)).json()["mail"]["last_error"]


def test_an_alarm_keeps_what_the_page_without_the_message_showed(client, ws):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)
    page = {"length": 5120, "title": "Original Message", "download": True, "raw_id": False}
    told = other.post(
        "/api/ingest/mail/alarm", json={"layer": 3, "version": "0.3.1", "page": page}, headers=bearer(token)
    )
    assert told.json() == {"news": True}
    with ws.db() as db:
        [event] = events.entries(db, "mail.bridge_alarm")
    assert event.detail == {"version": "0.3.1", "page": page}
    long_title = {"layer": 3, "page": page | {"title": "x" * 81}}
    assert other.post("/api/ingest/mail/alarm", json=long_title, headers=bearer(token)).status_code == 422


def test_an_extension_not_seen_for_a_day_is_told_once(client, ws):
    found = paired(client)
    now = datetime.now(UTC)
    assert bridge.check_silence(ws, now) == []  # just paired
    with ws.db() as db:
        db.execute(
            "UPDATE bridges SET last_seen = ? WHERE id = ?", ((now - timedelta(days=2)).isoformat(), found["id"])
        )
    assert bridge.check_silence(ws, now) == [found["id"]]
    assert bridge.check_silence(ws, now) == []  # once
    with ws.db() as db:
        db.execute(
            "UPDATE bridges SET last_seen = ? WHERE id = ?", ((now - timedelta(hours=25)).isoformat(), found["id"])
        )
    assert bridge.check_silence(ws, now) == [found["id"]]  # back, then silent again


def test_a_scan_of_gmail_learns_which_messages_the_service_lacks(client, ws):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)
    stored = other.post(
        "/api/ingest/mail",
        content=bank_mail(FEBRUARY),
        headers=bearer(token) | {"Content-Type": "message/rfc822", "X-Gmail-Id": "1001"},  # from a scan: no date
    )
    assert stored.json()["taken"] == "stored"
    forged = bank_mail(FEBRUARY, results=("mx.google.com; dmarc=fail header.from=teb.com.tr",))
    other.post("/api/ingest/mail", content=forged, headers=bearer(token) | {"X-Gmail-Id": "1002"})
    asked = other.post("/api/ingest/mail/known", json={"ids": ["1003", "1001", "1002", "1003"]}, headers=bearer(token))
    assert asked.json() == {"missing": ["1003"]}  # held, or refused under these settings: not downloaded again
    cursor = other.get("/api/ingest/mail/cursor", headers=bearer(token)).json()
    assert (cursor["last_id"], cursor["last_date"]) == ("", "")  # a scan's messages leave the feed's cursor alone


def left_out(raw: bytes) -> bytes:
    """The message as Gmail's "Show original" gives it: every attachment's part keeps its headers and comes empty."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    for part in msg.walk():
        if part.get_filename() and part.get_content_type() != "text/html":
            part.set_payload("")
    return msg.as_bytes()


def test_a_message_held_with_its_attachments_left_out_is_asked_for_again_and_replaced_whole(client, ws, private_trash):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)

    def deliver(raw: bytes) -> dict:
        return other.post("/api/ingest/mail", content=raw, headers=bearer(token) | {"X-Gmail-Id": "3001"}).json()

    def missing() -> list[str]:
        return other.post("/api/ingest/mail/known", json={"ids": ["3001"]}, headers=bearer(token)).json()["missing"]

    whole = bank_mail(FEBRUARY)
    incomplete = left_out(whole)
    assert deliver(incomplete) == {"taken": "stored", "documents": 1}  # the message alone: its statement came empty
    assert missing() == ["3001"]
    assert deliver(whole) == {"taken": "stored", "documents": 2}
    assert missing() == []
    with ws.db() as db:
        kept = {d.name: d for d in documents.every(db)}
        copy = documents.get(db, hashlib.sha256(incomplete).hexdigest())
        assert audit.targets(db, "document.removed") == {copy.sha256}
    assert (copy.status, copy.reason) == (DocumentStatus.REMOVED, bridge.INCOMPLETE_REASON)
    assert not ws.vault.has(copy.sha256) and any(private_trash.iterdir())  # to the Trash, not deleted
    assert kept["HesapHareketleri.xls"].parent == hashlib.sha256(whole).hexdigest()


def test_messages_held_before_are_looked_at_for_attachments_left_out(client, ws):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)
    for gmail_id, raw in (("4001", left_out(bank_mail(FEBRUARY))), ("4002", bank_mail(None))):
        other.post("/api/ingest/mail", content=raw, headers=bearer(token) | {"X-Gmail-Id": gmail_id})
    with ws.db() as db:
        db.execute("UPDATE bridge_messages SET complete = NULL")  # kept before the service looked
    asked = other.post("/api/ingest/mail/known", json={"ids": ["4001", "4002"]}, headers=bearer(token))
    assert asked.json() == {"missing": ["4001"]}


def test_a_held_copy_goes_when_its_whole_message_shows_a_companys_attachment(client, ws, private_trash):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)
    company = teb.account_export(teb.running_rows(list(teb.ACCOUNT_MOVES)), holder="ÖRNEK TEKNOLOJİ A.Ş.")
    whole = bank_mail(company)
    set_business_names(["Örnek Teknoloji"])
    headers = bearer(token) | {"X-Gmail-Id": "5001"}
    assert other.post("/api/ingest/mail", content=left_out(whole), headers=headers).json()["taken"] == "stored"
    assert other.post("/api/ingest/mail", content=whole, headers=headers).json()["taken"] == "business"
    with ws.db() as db:
        assert [d.status for d in documents.every(db)] == [DocumentStatus.REMOVED]


def test_a_copy_kept_after_its_whole_message_was_refused_is_asked_for_again(client, ws, private_trash):
    # two extensions deliver the same new message: the whole one is refused as a company's, then an older version's
    # copy with the attachments left out passes
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)
    company = teb.account_export(teb.running_rows(list(teb.ACCOUNT_MOVES)), holder="ÖRNEK TEKNOLOJİ A.Ş.")
    whole = bank_mail(company)
    set_business_names(["Örnek Teknoloji"])
    headers = bearer(token) | {"X-Gmail-Id": "5002"}
    assert other.post("/api/ingest/mail", content=whole, headers=headers).json()["taken"] == "business"
    assert other.post("/api/ingest/mail", content=left_out(whole), headers=headers).json()["taken"] == "stored"
    asked = other.post("/api/ingest/mail/known", json={"ids": ["5002"]}, headers=bearer(token))
    assert asked.json() == {"missing": ["5002"]}  # not hidden behind the refusal before it
    assert other.post("/api/ingest/mail", content=whole, headers=headers).json()["taken"] == "business"
    with ws.db() as db:
        assert [d.status for d in documents.every(db)] == [DocumentStatus.REMOVED]


def test_a_refused_message_is_asked_for_again_once_the_settings_it_was_refused_under_change(client, ws):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)

    def deliver(raw: bytes, gmail_id: str) -> str:
        return other.post("/api/ingest/mail", content=raw, headers=bearer(token) | {"X-Gmail-Id": gmail_id}).json()[
            "taken"
        ]

    def missing(*ids: str) -> list[str]:
        return other.post("/api/ingest/mail/known", json={"ids": list(ids)}, headers=bearer(token)).json()["missing"]

    no_dmarc = bank_mail(FEBRUARY, results=("mx.google.com; dkim=pass header.i=@teb.com.tr; spf=pass",))
    assert deliver(no_dmarc, "2001") == "unverified"
    assert deliver(bank_mail(FEBRUARY, sender="haber@baska.example"), "2002") == "unlisted"
    assert missing("2001", "2002") == []
    mail = client.get("/api/system", headers=bearer(TOKEN)).json()["mail"]
    assert [(r["taken"], r["reason"], r["domain"], r["count"]) for r in mail["refused"]] == [
        ("unlisted", "", "", 1),  # the domain of a sender on no list is not kept
        ("unverified", "no-dmarc", "teb.com.tr", 1),
    ]
    assert mail["refused"][1]["label"] == "doğrulama başlığında DMARC sonucu yok"
    config.update(ws.layout.settings, "mail", {"other_senders": ["baska.example"]})
    assert missing("2001", "2002") == ["2001", "2002"]  # other senders: both are asked for again
    assert client.get("/api/system", headers=bearer(TOKEN)).json()["mail"]["refused"] == []


def test_only_a_paired_extension_asks_which_messages_are_missing_and_only_with_ids(client):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)
    assert other.post("/api/ingest/mail/known", json={"ids": ["1"]}, headers=bearer(TOKEN)).status_code == 403
    for ids in (["18f0a1"], ["1"] * 1001, [""]):
        assert other.post("/api/ingest/mail/known", json={"ids": ids}, headers=bearer(token)).status_code == 422


def test_the_history_is_scanned_once_until_the_start_day_or_the_senders_change(client, ws):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)

    def cursor() -> dict:
        return other.get("/api/ingest/mail/cursor", headers=bearer(token)).json()

    def system_mail() -> dict:
        return client.get("/api/system", headers=bearer(TOKEN)).json()["mail"]

    first = cursor()
    assert first["history_due"] and system_mail()["history_due"]  # just paired: Gmail was never scanned
    searched = {"start_day": first["start_day"], "senders": [s.upper() for s in reversed(first["senders"])]}
    assert other.post("/api/ingest/mail/scanned", json=searched, headers=bearer(token)).json() == {
        "history_due": False  # the same senders in any order and case
    }
    assert not cursor()["history_due"]
    assert (system_mail()["history_due"], system_mail()["start_day"]) == (False, first["start_day"])
    config.update(ws.layout.settings, "mail", {"start_day": date(2020, 1, 1)})
    assert cursor()["history_due"]  # an earlier start day: scanned again
    config.update(ws.layout.settings, "mail", {"start_day": date.fromisoformat(first["start_day"])})
    assert not cursor()["history_due"]
    config.update(ws.layout.settings, "mail", {"other_senders": ["fatura.example"]})
    assert cursor()["history_due"]  # a new sender: scanned again


def test_a_scan_that_searched_what_the_settings_no_longer_ask_for_leaves_the_history_due(client):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)
    old = {"start_day": "2019-01-01", "senders": ["teb.com.tr"]}  # the settings changed while it ran
    assert other.post("/api/ingest/mail/scanned", json=old, headers=bearer(token)).json() == {"history_due": True}


def test_only_a_paired_extension_reports_a_scan_and_only_in_shape(client):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)
    searched = {"start_day": "2024-01-01", "senders": ["teb.com.tr"]}
    assert other.post("/api/ingest/mail/scanned", json=searched, headers=bearer(TOKEN)).status_code == 403
    for bad in (
        {"start_day": "1 Ocak 2024", "senders": ["teb.com.tr"]},
        {"start_day": "", "senders": [""]},
        {"start_day": "", "senders": ["teb.com.tr"] * 501},
    ):
        assert other.post("/api/ingest/mail/scanned", json=bad, headers=bearer(token)).status_code == 422
