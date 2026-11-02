"""The HTTP API (ADR-0007): the gate (Host, session or token, and a browser's writes from the service's own pages),
the login link, the System screen's data and the event stream."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import access, system
from iplikci.app.access import LoginKeys, SessionState
from iplikci.app.workspace import Busy, Workspace
from iplikci.domain.codes import InvoiceKind
from iplikci.domain.models import Invoice, InvoiceLine
from iplikci.fakes import teb
from iplikci.fakes.files import text_pdf
from iplikci.invoices import UNMATCHED_REASONS, UNPAID_REASON, match
from iplikci.parsers import registry
from iplikci.settings import config
from iplikci.storage import audit, events

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
        "coverage": {  # F01: no bank message kept yet
            "total": 0,
            "read": 0,
            "attached": 0,
            "no_money": 0,
            "business": 0,
            "unknown": 0,
            "share": 1.0,
            "left": [],
        },
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


def test_the_pwas_manifest_and_icons_open_without_a_session_and_its_worker_is_asked_again_each_time(ws, tmp_path):
    ui = tmp_path / "ui"
    ui.mkdir()
    (ui / "index.html").write_text("<!doctype html><title>arayüz</title>", encoding="utf-8")
    (ui / "manifest.webmanifest").write_text('{"name": "İplikçi Nedim"}', encoding="utf-8")
    (ui / "pwa-192x192.png").write_bytes(b"\x89PNG")
    (ui / "sw.js").write_text("self.addEventListener('fetch', () => {});", encoding="utf-8")
    outsider = TestClient(create_app(Context(ws=ws, token=TOKEN, ui=ui)), base_url=BASE)
    manifest = outsider.get("/manifest.webmanifest")  # a browser reads it without its cookies as it installs
    assert manifest.status_code == 200 and manifest.headers["content-type"].startswith("application/manifest+json")
    assert outsider.get("/pwa-192x192.png").status_code == 200
    assert outsider.get("/sw.js").status_code == 401  # the worker comes with the session, as every page does
    worker = signed_in(outsider).get("/sw.js")
    assert worker.status_code == 200 and worker.headers["cache-control"] == "no-store"


# --- the Subscriptions and Calendar screens (F08, F09) -------------------------------------------------------


@pytest.fixture(scope="module")
def demo_client(tmp_path_factory) -> TestClient:
    """The demo data folder's service, as on the day its baseline is taken, its analysis made once."""
    ws = Workspace.load(demo.build(tmp_path_factory.mktemp("demo")))
    context = Context(ws=ws, token=TOKEN, ui=tmp_path_factory.mktemp("arayuz"), today=lambda: demo.AS_OF)
    context.analysis.get()
    return TestClient(create_app(context), base_url=BASE)


def tl(minor: int) -> dict[str, object]:
    return {"minor": minor, "currency": "TRY"}


def test_the_subscriptions_are_the_series_with_their_status_next_payment_and_rows(demo_client):
    found = demo_client.get("/api/subscriptions", headers=bearer()).json()
    assert found["as_of"] == "2026-10-31" and found["window"][-1] == "2026-10"
    rent = next(s for s in found["series"] if s["payee"] == "Veli Örneksoy Kira Ödemesi")
    assert (rent["period"], rent["status"], rent["listed"], rent["note"]) == ("month", "active", True, "")
    assert (rent["amount"], rent["last_day"], rent["next_day"]) == (tl(1500000), "2026-10-03", "2026-11-03")
    assert rent["account"] == {"id": "teb-123456789", "label": "TEB Vadesiz TL 123456789"}
    assert len(rent["payments"]) == 9  # the first days of July were never downloaded: its rent is missing
    first = rent["payments"][0]
    assert (first["day"], first["amount"], first["certainty"]) == ("2026-01-03", tl(1500000), "confirmed")
    assert len(first["fingerprint"]) == 20 and first["document"].endswith("Hesap Hareketleri.xls")
    gas = next(s for s in found["series"] if s["payee"] == "Doğalgaz (İGDAŞ)")
    assert gas["amount"] == tl(20000) and gas["last_amount"] == tl(60000)  # a moving bill: the last three's median
    (salary,) = found["income"]
    # The next salary after the last one: a past day, as the documents end on 31 October.
    assert (salary["payee"], salary["amount"], salary["next_day"]) == ("Örnek İşveren A.Ş.", tl(4000000), "2026-11-01")
    assert found["installments"] == []  # the demo has no card statements


def test_the_calendar_lists_the_next_sixty_days_by_day(demo_client):
    found = demo_client.get("/api/calendar", headers=bearer()).json()
    assert (found["today"], found["end"]) == ("2026-11-15", "2027-01-13")
    days = [item["day"] for item in found["items"]]
    assert days == sorted(days) and days[0] == "2026-11-19"
    salary = next(item for item in found["items"] if item["kind"] == "income")
    assert (salary["day"], salary["direction"], salary["amount"]) == ("2026-12-01", "in", tl(4000000))
    rent = next(item for item in found["items"] if item["title"] == "Veli Örneksoy Kira Ödemesi")
    assert (rent["day"], rent["direction"], rent["amount"], rent["minimum"]) == ("2026-12-03", "out", tl(1500000), None)
    assert rent["basis"] == "son ödeme 03.10.2026: 15.000,00 TL" and len(rent["fingerprints"]) == 3
    subscriptions = demo_client.get("/api/subscriptions", headers=bearer()).json()
    assert rent["series"] in {s["id"] for s in subscriptions["series"]}  # the item names the series it continues


def test_the_forecast_runs_each_bank_account_day_by_day_as_an_estimate(demo_client):
    found = demo_client.get("/api/forecast", headers=bearer()).json()
    assert (found["label"], found["today"], found["end"]) == ("tahmin", "2026-11-15", "2027-01-13")
    (teb_account,) = found["accounts"]
    start = teb_account["start"]
    assert (start["source"], start["day"], start["moves"]) == ("statement", "2026-10-31", 0)
    assert start["balance"] == start["stated"] == tl(18438010)
    assert len(teb_account["days"]) == 60 and teb_account["negative"] is None
    assert teb_account["lowest"] == {"day": "2026-11-30", "balance": tl(18235583)}
    assert teb_account["end_balance"] == tl(22452450)
    assert teb_account["spend"] == {"monthly": tl(800), "months": found_months(), "after": None}  # the FAST fee
    assert teb_account["cards"] is None and teb_account["interest"] is None
    assert {item["kind"] for item in teb_account["items"]} == {"regular", "income"}
    assert found["skipped"] == [
        {
            "account": {"id": "garanti-1234567", "label": "Garanti BBVA Vadesiz TL 1234567"},
            "reason": "bakiyesi hiçbir belgede yazmıyor",  # known only from receipts
        }
    ]
    assert found["notes"][0].startswith("Bu bir tahmindir")


def found_months() -> list[str]:
    return ["2026-04", "2026-05", "2026-06", "2026-08", "2026-09", "2026-10"]  # July is not a complete month


def test_an_empty_folder_has_no_series_items_or_forecast(client):
    assert client.get("/api/subscriptions", headers=bearer()).json()["series"] == []
    assert client.get("/api/calendar", headers=bearer()).json()["items"] == []
    found = client.get("/api/forecast", headers=bearer()).json()
    assert found["accounts"] == [] and found["label"] == "tahmin"


def test_the_outlook_needs_a_session_and_says_when_the_documents_are_busy(client, context, monkeypatch):
    assert client.get("/api/calendar").status_code == 401

    def busy():
        raise Busy("başka bir işlem belgeleri işliyor; biraz sonra yeniden deneyin")

    monkeypatch.setattr(context.analysis, "get", busy)
    refused = client.get("/api/forecast", headers=bearer())
    assert (refused.status_code, refused.json()["code"]) == (503, "busy")


# --- the Bills screen and the non-bank senders (F14) ----------------------------------------------------------------


def extension_token(client: TestClient, context: Context) -> str:
    """A paired browser extension's token: it opens the mail intake and nothing else."""
    code, _ = context.pairing.issue()
    paired = TestClient(client.app, base_url=BASE).post("/api/bridge/pair", json={"code": code, "name": "Deneme"})
    return paired.json()["token"]


def test_the_invoices_need_a_session_or_the_token_and_say_when_the_documents_are_busy(client, context, monkeypatch):
    assert client.get("/api/invoices").status_code == 401
    refused = client.get("/api/invoices", headers=bearer(extension_token(client, context)))
    assert (refused.status_code, refused.json()["code"]) == (403, "forbidden")  # the extension delivers mail only
    nothing = {"items": [], "counts": {"pending": 0, "unmatched": 0, "matched": 0}}
    assert client.get("/api/invoices", headers=bearer()).json() == nothing
    assert signed_in(client).get("/api/invoices").json() == nothing

    def busy():
        raise Busy("başka bir işlem belgeleri işliyor; biraz sonra yeniden deneyin")

    monkeypatch.setattr(context.analysis, "get", busy)
    refused = client.get("/api/invoices")
    assert (refused.status_code, refused.json()["code"]) == (503, "busy")


PHONE = Invoice(
    InvoiceKind.BILL,
    "ÖRNEKCELL İLETİŞİM HİZMETLERİ A.Ş.",
    date(2026, 1, 3),
    Decimal("412.90"),
    number="OC2026000000101",
    due=date(2026, 1, 20),
    lines=[InvoiceLine("Aylık paket", Decimal("400.00"), Decimal(1)), InvoiceLine("Ek internet", Decimal("12.90"))],
)
COFFEE = Invoice(InvoiceKind.RECEIPT, "Kahveci Dükkan Ltd. Şti.", date(2026, 1, 20), Decimal("120.00"), number="K-7")
ENERGY = Invoice(
    InvoiceKind.BILL,
    "Örnekenerji Elektrik Perakende Satış A.Ş.",
    date(2026, 1, 25),
    Decimal(250),
    due=date(2026, 2, 10),
)
STREAMING = Invoice(InvoiceKind.RECEIPT, "Örnekflix International B.V.", date(2026, 1, 30), Decimal("9.99"), "USD")


def test_the_invoices_come_pending_first_then_unmatched_then_matched_with_their_rows_and_reasons(
    client, context, ws, monkeypatch
):
    add(ws, "ocak.xls", teb.account_export(JANUARY))  # pays the coffee on 20 January; the list ends on the 31st
    analysis = context.analysis.get()
    found = [
        (f"{'a' * 64}:0", COFFEE, "Kahveci makbuzu.eml"),
        (f"{'b' * 64}:0", PHONE, "Örnekcell faturası.xml"),
        (f"{'c' * 64}:0", ENERGY, "Enerji faturası.xml"),
        (f"{'c' * 64}:1", STREAMING, "Enerji faturası.xml"),  # a second bill of the same document
    ]
    analysis.dataset.invoices = match(found, analysis.dataset.transactions, date(2026, 1, 31))
    monkeypatch.setattr(context.analysis, "get", lambda: analysis)
    listed = client.get("/api/invoices", headers=bearer()).json()
    assert listed["counts"] == {"pending": 2, "unmatched": 1, "matched": 1}
    # Pending by the last day their row is looked for: the receipt's few days end before the bill's due date.
    assert [(i["seller"], i["status"]) for i in listed["items"]] == [
        ("Örnekflix International B.V.", "pending"),
        ("Örnekenerji Elektrik Perakende Satış A.Ş.", "pending"),
        ("ÖRNEKCELL İLETİŞİM HİZMETLERİ A.Ş.", "unmatched"),
        ("Kahveci Dükkan Ltd. Şti.", "matched"),
    ]
    streaming, energy, phone, coffee = listed["items"]
    assert phone == {
        "key": f"{'b' * 64}:0",
        "kind": "bill",
        "status": "unmatched",
        "seller": "ÖRNEKCELL İLETİŞİM HİZMETLERİ A.Ş.",
        "number": "OC2026000000101",
        "issued": "2026-01-03",
        "due": "2026-01-20",
        "total": tl(41290),
        "lines": [
            {"description": "Aylık paket", "amount": tl(40000), "quantity": "1"},
            {"description": "Ek internet", "amount": tl(1290), "quantity": None},
        ],
        "window": {"start": "2026-01-03", "end": "2026-01-23"},
        "document": "Örnekcell faturası.xml",
        "sha256": "b" * 64,
        "row": None,
        "reasons": [*UNMATCHED_REASONS, UNPAID_REASON],
    }
    (account,) = analysis.dataset.accounts.values()
    (paid,) = [t for t in analysis.dataset.transactions if t.invoice]
    assert (coffee["status"], coffee["reasons"]) == ("matched", [])
    assert coffee["row"] == {
        "fingerprint": paid.fingerprint,
        "day": "2026-01-20",
        "account": {"id": account.id, "label": account.label},
        "amount": tl(12000),  # in TL, as the ledger counts it
        "description": "KAHVECI DUKKAN",
    }
    assert (streaming["total"], streaming["due"], streaming["row"]) == ({"minor": 999, "currency": "USD"}, None, None)
    assert (streaming["sha256"], streaming["key"]) == ("c" * 64, f"{'c' * 64}:1")
    assert energy["window"] == {"start": "2026-01-25", "end": "2026-02-13"}  # its due date and three days more


def test_the_non_bank_senders_are_read_with_the_token_and_changed_only_from_the_services_own_pages(client, ws):
    path = "/api/settings/mail/other-senders"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=bearer()).json() == {"domains": []}
    refused = client.put(path, json={"domains": ["fatura.example"]}, headers=bearer())
    assert (refused.status_code, refused.json()["code"]) == (403, "forbidden")  # the command line and MCP only read
    signed_in(client)
    assert client.put(path, json={"domains": ["fatura.example"]}).json()["code"] == "write_denied"
    saved = client.put(path, json={"domains": ["Fatura.Example", " @ornekcell.example"]}, headers=OWN_PAGE)
    assert (saved.status_code, saved.json()) == (200, {"domains": ["fatura.example", "ornekcell.example"]})
    assert config.load(ws.layout.settings).mail.other_senders == ("fatura.example", "ornekcell.example")
    assert client.get(path).json() == {"domains": ["fatura.example", "ornekcell.example"]}
    again = client.put(path, json={"domains": ["fatura.example", "ornekcell.example"]}, headers=OWN_PAGE)
    assert again.json() == saved.json()  # the same list: nothing is written again
    with ws.db() as db:
        [entry] = audit.entries(db, "settings.changed")
    assert (entry.actor, entry.target, entry.detail) == ("user", "mail.other_senders", {"count": 2})  # never a domain
    assert client.put(path, json={"domains": []}, headers=OWN_PAGE).json() == {"domains": []}
    assert config.load(ws.layout.settings).mail.other_senders == ()


@pytest.mark.parametrize(
    ("domains", "says"),
    [
        (["teb.com.tr"], "teb.com.tr bir bankanın alan adı"),
        (["garantibbva.com.tr"], "garantibbva.com.tr bir bankanın alan adı"),  # a shipped bank off the bank list
        (["bilgi.teb.com.tr"], "bilgi.teb.com.tr bir bankanın alan adı"),
        (["com.tr"], "com.tr bankaların alan adlarını da kapsıyor"),
        (["fatura.example", "FATURA.example"], "fatura.example listede zaten var"),
        (["fatura example"], "“fatura example” bir alan adı değil"),
        ([""], "“” bir alan adı değil"),
    ],
    ids=["bank", "shipped bank", "under a bank", "above a bank", "twice", "no domain", "empty"],
)
def test_a_banks_domain_a_domain_named_twice_or_no_domain_is_refused_and_nothing_is_saved(client, ws, domains, says):
    config.update(ws.layout.settings, "mail", {"bank_senders": ["teb.com.tr"], "other_senders": ["eski.example"]})
    before = ws.layout.settings.read_text(encoding="utf-8")
    refused = signed_in(client).put("/api/settings/mail/other-senders", json={"domains": domains}, headers=OWN_PAGE)
    assert (refused.status_code, refused.json()["code"]) == (400, "sender_invalid")
    assert refused.json()["title"].startswith(says)
    assert ws.layout.settings.read_text(encoding="utf-8") == before


def test_a_sender_list_out_of_shape_or_a_settings_file_that_cannot_be_read_is_refused(client, ws):
    path = "/api/settings/mail/other-senders"
    signed_in(client)
    for body in ({"domains": "fatura.example"}, {"domains": ["a.example"] * 201}, {"domains": ["a" * 254]}, {}):
        refused = client.put(path, json=body, headers=OWN_PAGE)
        assert (refused.status_code, refused.json()["code"]) == (422, "invalid_request")
    ws.layout.settings.write_text("[mail\n", encoding="utf-8")
    broken = client.get(path)
    assert (broken.status_code, broken.json()["code"]) == (409, "settings_invalid")
    assert client.put(path, json={"domains": ["fatura.example"]}, headers=OWN_PAGE).status_code == 409
    assert ws.layout.settings.read_text(encoding="utf-8") == "[mail\n"


def test_a_new_sender_list_makes_the_extension_read_the_history_again(client, context):
    token = extension_token(client, context)
    extension = TestClient(client.app, base_url=BASE)
    cursor = extension.get("/api/ingest/mail/cursor", headers=bearer(token)).json()
    searched = {"start_day": cursor["start_day"], "senders": cursor["senders"]}
    assert extension.post("/api/ingest/mail/scanned", json=searched, headers=bearer(token)).json() == {
        "history_due": False
    }
    signed_in(client).put("/api/settings/mail/other-senders", json={"domains": ["fatura.example"]}, headers=OWN_PAGE)
    cursor = extension.get("/api/ingest/mail/cursor", headers=bearer(token)).json()
    assert cursor["history_due"] and "fatura.example" in cursor["senders"]
    assert client.get("/api/system").json()["mail"]["history_due"]
