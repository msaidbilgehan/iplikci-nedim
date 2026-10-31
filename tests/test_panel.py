"""The local web panel: who may reach it, and adding a document through it end to end."""

import http.client
import json
import threading
from urllib.parse import quote

import pytest

from iplikci import email_fetch
from iplikci.panel import make_server

from conftest import JANUARY, bank_mail, teb_export


@pytest.fixture
def panel(ws):
    server, panel = make_server(ws, 0)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    yield panel
    server.shutdown()
    server.server_close()


def request(panel, method, path, body=b"", cookie=True, host=None, origin=True, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", panel.port, timeout=10)
    h = {"Host": host or f"127.0.0.1:{panel.port}"}
    if cookie:
        h["Cookie"] = f"{panel.cookie}={panel.key}"
    if origin and method == "POST":
        h |= {"Origin": f"http://127.0.0.1:{panel.port}", "X-Iplikci": "1"}
    conn.request(method, path, body=body, headers=h | (headers or {}))
    res = conn.getresponse()
    data = res.read()
    conn.close()
    return res, data


def post_json(panel, path, value=None, headers=None, **kw):
    res, data = request(
        panel,
        "POST",
        path,
        json.dumps(value or {}).encode(),
        headers={"Content-Type": "application/json"} | (headers or {}),
        **kw,
    )
    return res.status, json.loads(data)


def upload(panel, name, data, **kw):
    res, body = request(panel, "POST", "/api/yukle", data, headers={"X-Dosya-Adi": quote(name)}, **kw)
    return res.status, json.loads(body)


def test_the_start_address_hands_out_the_session_cookie(panel):
    assert request(panel, "GET", "/", cookie=False)[0].status == 403
    assert request(panel, "GET", "/?anahtar=yanlis", cookie=False)[0].status == 403
    res, _ = request(panel, "GET", f"/?anahtar={panel.key}", cookie=False)
    assert res.status == 303 and res.getheader("Location") == "/"  # the key leaves the address bar
    cookie = res.getheader("Set-Cookie")
    assert cookie.startswith(f"{panel.cookie}={panel.key}") and "HttpOnly" in cookie and "SameSite=Strict" in cookie


def test_the_page_is_the_report_plus_the_upload_dialog(panel):
    res, body = request(panel, "GET", "/")
    page = body.decode()
    assert res.status == 200
    csp = res.getheader("Content-Security-Policy")
    assert "default-src 'none'" in csp and "connect-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert 'id="belge-dialog"' in page and 'id="panel-veri"' in page and 'id="veri"' in page
    assert res.getheader("Cache-Control") == "no-store"


def test_another_host_name_is_refused(panel):
    # DNS rebinding: a site whose name resolves to 127.0.0.1 still sends its own Host header.
    assert request(panel, "GET", "/", host=f"saldirgan.example:{panel.port}")[0].status == 403


def test_writes_need_the_panel_origin_and_header(panel):
    assert post_json(panel, "/api/plan", origin=False)[0] == 403
    status, _ = post_json(
        panel, "/api/plan", origin=False, headers={"Origin": "http://saldirgan.example", "X-Iplikci": "1"}
    )
    assert status == 403
    assert post_json(panel, "/api/plan", cookie=False)[0] == 403
    assert post_json(panel, "/api/plan")[0] == 200


def test_upload_plan_and_apply_through_the_panel(panel, ws):
    status, up = upload(panel, "../../Indirilenler/TEBHareket.xls", teb_export(JANUARY))
    assert status == 200 and up == {"status": "eklendi", "name": "Indirilenler/TEBHareket.xls", "reason": ""}
    assert (ws.inbox / "Indirilenler" / "TEBHareket.xls").exists()

    status, plan = post_json(panel, "/api/plan")
    assert status == 200 and plan["changes"] == 1
    [item] = plan["items"]
    assert item["action"] == "tut" and item["fromInbox"]
    assert item["target"].startswith("TEB/Vadesiz Hesap TL 123456789/2026-01-01 - 2026-01-31")
    assert item["document"]["verified"] and item["document"]["kind"] == "hesap"

    status, done = post_json(panel, "/api/uygula", {"plan": plan["id"]})
    assert status == 200 and (done["filed"], done["trashed"], done["unreadable"]) == (1, 0, 0)
    assert list(ws.documents.glob("TEB/*/*.xls")) and not list(ws.inbox.iterdir())
    assert post_json(panel, "/api/uygula", {"plan": plan["id"]})[0] == 409  # a plan is applied once

    page = request(panel, "GET", "/")[1].decode()
    assert "KAHVECI DUKKAN" in page  # the report now holds the filed statement


def test_unsupported_upload_is_refused_and_answered(panel, ws):
    status, up = upload(panel, "foto.jpg", b"\xff\xd8\xff")
    assert status == 200 and up["status"] == "reddedildi"
    assert list(ws.inbox.iterdir()) == []


def test_the_mail_button_needs_an_account(panel):
    status, body = post_json(panel, "/api/eposta")
    assert status == 409 and "eposta --kur" in body["error"]


def test_the_page_shows_an_account_set_up_while_the_panel_runs(panel, ws, imap):
    assert '"mail":{"configured":false' in request(panel, "GET", "/")[1].decode()
    email_fetch.setup(ws, "kullanici@example.com", "abcdefghijklmnop")  # `eposta --kur` in a terminal
    assert '"mail":{"configured":true' in request(panel, "GET", "/")[1].decode()


def test_mail_fetched_through_the_panel_waits_in_the_inbox(panel, ws, mail):
    mail.messages[101] = bank_mail(teb_export(JANUARY))
    status, body = post_json(panel, "/api/eposta")
    assert status == 200 and body["copied"] == ["HesapHareketleri.xls"] and body["lastRun"] and not body["more"]
    assert post_json(panel, "/api/plan")[1]["changes"] == 1
    assert '"mail":{"configured":true' in request(panel, "GET", "/")[1].decode()  # the page shows the button


def test_mail_server_trouble_comes_back_as_an_error(panel, ws, mail, monkeypatch):
    def offline(acc):
        raise OSError("ağ yok")

    monkeypatch.setattr(email_fetch, "connect", offline)
    status, body = post_json(panel, "/api/eposta")
    assert status == 502 and "bağlanılamadı" in body["error"]


def test_month_end_pages_need_the_session_and_carry_no_script(panel):
    assert request(panel, "GET", "/ay-sonu/index.html", cookie=False)[0].status == 403
    res, body = request(panel, "GET", "/ay-sonu/index.html")
    assert res.status == 200 and "Ay sonu raporları" in body.decode()
    csp = res.getheader("Content-Security-Policy")
    assert "default-src 'none'" in csp and "script-src" not in csp and "frame-ancestors 'none'" in csp
    assert request(panel, "GET", "/ay-sonu/1999-01.html")[0].status == 404  # no page for that month
    assert request(panel, "GET", "/ay-sonu/../kategoriler.yaml")[0].status == 404
