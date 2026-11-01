"""The HTTP API (ADR-0007): the gate (Host, session or token, and a browser's writes from the service's own pages),
the login link, the System screen's data and the event stream."""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import access, system
from iplikci.app.access import LoginKeys, SessionState
from iplikci.fakes import teb
from iplikci.fakes.files import text_pdf
from iplikci.parsers import registry
from iplikci.storage import events

from conftest import FEBRUARY, JANUARY, add

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}


@pytest.fixture
def context(ws) -> Context:
    return Context(ws=ws, token=TOKEN, stream_limit=0.05, poll=0.01)


@pytest.fixture
def client(context) -> TestClient:
    return TestClient(create_app(context), base_url=BASE)


def bearer(token: str = TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def signed_in(client: TestClient) -> TestClient:
    """client with a browser session, opened through a login link."""
    url = client.post("/api/login-links", headers=bearer()).json()["url"]
    response = client.get(url, follow_redirects=False)
    assert response.status_code == 303
    return client


def test_health_needs_no_session_but_the_right_host(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    refused = client.get("/healthz", headers={"Host": "evil.example:8643"})
    assert refused.status_code == 403
    assert refused.headers["content-type"] == "application/problem+json"
    assert refused.json()["code"] == "host_denied"


def test_a_rebound_name_reaches_nothing_even_with_the_token(client):
    response = client.get("/api/system", headers={**bearer(), "Host": "attacker.example"})
    assert response.status_code == 403


def test_without_a_session_the_api_answers_401_and_a_page_says_how_to_come_in(client):
    api = client.get("/api/system")
    assert api.status_code == 401
    assert api.json() == {
        "type": "urn:iplikci:problem:unauthenticated",
        "title": "Oturum açılmamış ya da süresi dolmuş.",
        "status": 401,
        "code": "unauthenticated",
    }
    page = client.get("/")
    assert page.status_code == 401
    assert "Önce giriş yapın" in page.text
    assert "terminal" not in page.text.lower()


def test_a_wrong_token_is_refused(client):
    assert client.get("/api/system", headers=bearer("yanlis")).status_code == 401


def test_a_login_link_opens_one_session_once(client):
    url = client.post("/api/login-links", headers=bearer()).json()["url"]
    assert url.startswith(f"{BASE}/giris?anahtar=")
    response = client.get(url, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("iplikci_oturum_8643=")
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie and f"Max-Age={90 * 24 * 3600}" in cookie
    assert "İplikçi Nedim çalışıyor" in client.get("/").text
    again = TestClient(client.app, base_url=BASE).get(url, follow_redirects=False)
    assert again.status_code == 403
    assert "artık geçerli değil" in again.text


def test_a_login_key_expires_after_two_minutes(ws):
    now = [1000.0]
    keys = LoginKeys(clock=lambda: now[0])
    client = TestClient(create_app(Context(ws=ws, token=TOKEN, keys=keys)), base_url=BASE)
    key = keys.issue()
    now[0] += access.LOGIN_KEY_SECONDS + 1
    assert client.get(f"/giris?anahtar={key}", follow_redirects=False).status_code == 403


def test_only_a_client_with_the_token_gets_a_login_link(client):
    signed_in(client)
    response = client.post("/api/login-links", headers=OWN_PAGE)
    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Iplikci": "1"}, {"Origin": BASE}, {"Origin": "http://evil.example", "X-Iplikci": "1"}],
    ids=["nothing", "header only", "origin only", "foreign origin"],
)
def test_a_browser_writes_only_from_the_services_own_pages(client, headers):
    signed_in(client)
    response = client.post("/api/logout", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "write_denied"


def test_signing_out_ends_the_session(client):
    signed_in(client)
    response = client.post("/api/logout", headers=OWN_PAGE)
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    client.cookies.clear()
    assert client.get("/api/system").status_code == 401


def test_a_session_lasts_ninety_days_and_use_pushes_that_back_at_most_daily(ws):
    start = datetime(2026, 11, 1, 12, tzinfo=UTC)
    day = timedelta(days=1)
    with ws.db() as db:
        used = access.open_session(db, now=start)
        assert access.check_session(db, used, now=start + timedelta(hours=5)) is SessionState.VALID
        assert access.check_session(db, used, now=start + 2 * day) is SessionState.RENEWED  # now ends on day 92
        assert access.check_session(db, used, now=start + 2 * day + timedelta(hours=1)) is SessionState.VALID
        assert access.check_session(db, used, now=start + 91 * day) is SessionState.RENEWED  # now ends on day 181
        assert access.check_session(db, used, now=start + 182 * day) is SessionState.NONE
        idle = access.open_session(db, now=start)
        assert access.check_session(db, idle, now=start + 90 * day) is SessionState.NONE
        assert access.check_session(db, "", now=start) is SessionState.NONE


def test_the_database_keeps_only_a_hash_of_the_session_token(ws):
    with ws.db() as db:
        token = access.open_session(db)
        stored = [row[0] for row in db.rows("SELECT token_hash FROM sessions")]
    assert token not in stored and len(stored[0]) == 64


def test_a_renewed_session_gets_its_cookie_again(client, ws):
    with ws.db() as db:
        token = access.open_session(db, now=datetime.now(UTC) - timedelta(days=3))
    client.cookies.set("iplikci_oturum_8643", token)
    response = client.get("/api/system")
    assert response.status_code == 200
    assert response.headers["set-cookie"].startswith(f"iplikci_oturum_8643={token};")


def test_every_answer_carries_the_security_headers(client):
    for response in (client.get("/healthz"), client.get("/"), client.get("/api/system", headers=bearer())):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["cache-control"] == "no-store"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
        assert "access-control-allow-origin" not in response.headers


def test_the_system_status_names_every_reader_and_what_it_read(client, ws):
    add(ws, "teb.xls", teb.account_export(teb.running_rows(teb.ACCOUNT_MOVES)))
    found = client.get("/api/system", headers=bearer()).json()
    assert found["service"]["home"] == str(ws.home)
    assert found["documents"] == {"processed": 1}
    readers = {r["parser"]: r for r in found["readers"]}
    assert set(readers) == {r.id for r in registry.readers()}
    assert readers["teb.account_html"] | {"last_read": ""} == {
        "parser": "teb.account_html",
        "name": registry.label("teb.account_html"),
        "version": registry.version_of(registry.find("teb.account_html")),
        "documents": 1,
        "statements": 1,
        "verified": 1,
        "last_read": "",
        "alarms": 0,
    }
    assert readers["teb.account_html"]["last_read"]
    assert found["disk"]["vault"] > 0 and found["disk"]["database"] > 0 and found["disk"]["free"] > 0
    assert found["mail"] == {
        "connector": "imap",
        "configured": False,
        "last_run": "",
        "last_error": "",
        "stopped": False,
        "start_day": f"{date.today().year - 2}-01-01",  # two years back by default
        "history_due": False,  # the IMAP connector reads its history by itself
        "refused": [],  # the extension's refused messages
    }


def test_events_come_as_a_page_and_as_a_stream_that_resumes(client, ws):
    with ws.db() as db:
        events.record(db, "parser.format_alarm", "a" * 64, parser="teb.bonus_card", version="1.3", reason="x")
        events.record(db, "document.processed", "b" * 64)
    page = client.get("/api/events", headers=bearer()).json()
    assert [(e["id"], e["kind"]) for e in page] == [(1, "parser.format_alarm"), (2, "document.processed")]
    assert page[0]["detail"] == {"parser": "teb.bonus_card", "reason": "x", "version": "1.3"}
    assert client.get("/api/events?after=1", headers=bearer()).json()[0]["id"] == 2

    stream = client.get("/api/events/stream", headers=bearer())
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert stream.text.startswith("retry: 3000\n\n")
    assert "id: 1\ndata: {" in stream.text and "id: 2\ndata: {" in stream.text
    resumed = client.get("/api/events/stream", headers={**bearer(), "Last-Event-ID": "1"})
    assert "id: 1\n" not in resumed.text and "id: 2\n" in resumed.text


def test_errors_are_problems_in_turkish(client, monkeypatch):
    missing = client.get("/api/yok", headers=bearer())
    assert (missing.status_code, missing.json()["code"]) == (404, "http_404")
    invalid = client.get("/api/events?limit=0", headers=bearer())
    assert (invalid.status_code, invalid.json()["code"]) == (422, "invalid_request")

    def broken(_ws):
        raise RuntimeError("iç ayrıntı")

    monkeypatch.setattr(system, "status", broken)
    crashed = TestClient(client.app, base_url=BASE, raise_server_exceptions=False).get("/api/system", headers=bearer())
    assert crashed.status_code == 500
    assert crashed.json()["title"] == "Beklenmeyen bir hata oldu; ayrıntısı günlükte."
    assert "iç ayrıntı" not in crashed.text


def test_the_schema_is_for_signed_in_callers_only(client):
    assert client.get("/api/openapi.json").status_code == 401
    paths = client.get("/api/openapi.json", headers=bearer()).json()["paths"]
    assert {"/api/system", "/api/events", "/api/events/stream", "/api/login-links", "/api/logout"} <= set(paths)
    assert "/giris" not in paths


# --- the Documents screen and the interface ------------------------------------------------------------------


def test_the_documents_come_newest_first_a_page_at_a_time(client, ws):
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    add(ws, "subat.xls", FEBRUARY)
    add(ws, "bilgi.pdf", text_pdf([(72, 72, "Bilgilendirme")]))  # nothing a reader takes: kept, not processed
    first = client.get("/api/documents", params={"limit": 2}, headers=bearer()).json()
    assert len(first["items"]) == 2 and first["next"]
    second = client.get("/api/documents", params={"limit": 2, "cursor": first["next"]}, headers=bearer()).json()
    assert len(second["items"]) == 1 and second["next"] == ""
    listed = first["items"] + second["items"]
    assert [d["added_at"] for d in listed] == sorted((d["added_at"] for d in listed), reverse=True)
    statement = next(d for d in listed if d["file"] == "ocak.xls")
    assert (statement["status"], statement["kind"], statement["sources"]) == (
        "processed",
        "account_statement",
        ["import"],
    )
    assert statement["verified"] is True and statement["period_start"].startswith("2026-01")
    assert statement["reader"] == registry.label("teb.account_html")
    [kept] = client.get("/api/documents", params={"status": "unprocessed"}, headers=bearer()).json()["items"]
    assert kept["file"] == "bilgi.pdf" and kept["reason"]


def test_a_page_asks_only_what_it_may(client):
    bad = client.get("/api/documents", params={"cursor": "bozuk"}, headers=bearer())
    assert (bad.status_code, bad.json()["code"]) == (400, "cursor_invalid")
    unknown = client.get("/api/documents", params={"status": "hepsi"}, headers=bearer())
    assert (unknown.status_code, unknown.json()["code"]) == (400, "status_invalid")
    removed = client.get("/api/documents", params={"status": "removed"}, headers=bearer())  # in the Trash: not listed
    assert (removed.status_code, removed.json()["code"]) == (400, "status_invalid")
    assert client.get("/api/documents").status_code == 401


def test_the_interface_gets_the_codes_labels_from_the_one_mapping(client):
    found = client.get("/api/labels", headers=bearer()).json()
    assert found["DocumentStatus"]["processed"] == "İşlendi" and found["SourceKind"]["email"]
    assert found["JobKind"]["backup.daily"] == "Günlük yedek"


def test_the_interface_is_served_from_its_build(ws, tmp_path):
    ui = tmp_path / "ui"
    (ui / "assets").mkdir(parents=True)
    (ui / "index.html").write_text("<!doctype html><title>arayüz</title>", encoding="utf-8")
    (ui / "assets" / "giris-1a2b.js").write_text("export {};", encoding="utf-8")
    (tmp_path / "gizli.toml").write_text("sir = 1", encoding="utf-8")
    client = signed_in(TestClient(create_app(Context(ws=ws, token=TOKEN, ui=ui)), base_url=BASE))
    for page in ("/", "/belgeler", "/sistem", "/kurulum/eklenti"):
        assert "arayüz" in client.get(page).text  # every page address opens the single-page app
    script = client.get("/assets/giris-1a2b.js")
    assert script.headers["content-type"].startswith("text/javascript")
    assert script.headers["cache-control"] == "private, max-age=31536000, immutable"
    assert client.get("/assets/yok-9z.js").status_code == 404
    assert "sir" not in client.get("/../gizli.toml").text and "sir" not in client.get("/%2e%2e/gizli.toml").text
    assert client.get("/api/yok").json()["code"] == "http_404"
    outsider = TestClient(client.app, base_url=BASE)
    assert outsider.get("/belgeler").status_code == 401  # the interface itself is behind the session
