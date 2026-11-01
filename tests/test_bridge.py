"""The browser extension's side of the service (ADR-0016): pairing with a code, the proof of the paired service, a
token that opens only the mail intake, revocation, and the messages it delivers."""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import bridge
from iplikci.app.bridge import MAX_WRONG_CODES, PairingCodes
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


def test_a_bridges_token_opens_the_mail_intake_and_nothing_else(client):
    found = paired(client)
    other = TestClient(client.app, base_url=BASE)
    assert other.get("/api/system", headers=bearer(found["token"])).json()["code"] == "forbidden"
    assert other.get("/api/ingest/mail/cursor", headers=bearer(found["token"])).status_code == 200
    assert other.get("/api/ingest/mail/cursor", headers=bearer(TOKEN)).status_code == 403  # the CLI's token
    assert other.get("/api/ingest/mail/cursor").status_code == 401


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
    assert asked.json() == {"missing": ["1003", "1002"]}  # a refused message is not held: asked again, refused again
    cursor = other.get("/api/ingest/mail/cursor", headers=bearer(token)).json()
    assert (cursor["last_id"], cursor["last_date"]) == ("", "")  # a scan's messages leave the feed's cursor alone


def test_only_a_paired_extension_asks_which_messages_are_missing_and_only_with_ids(client):
    token = paired(client)["token"]
    other = TestClient(client.app, base_url=BASE)
    assert other.post("/api/ingest/mail/known", json={"ids": ["1"]}, headers=bearer(TOKEN)).status_code == 403
    for ids in (["18f0a1"], ["1"] * 1001, [""]):
        assert other.post("/api/ingest/mail/known", json={"ids": ids}, headers=bearer(token)).status_code == 422
