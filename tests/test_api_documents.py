"""One document on the Documents screen (F03): its detail with the statements and rows read from it, how the viewer
shows it (a PDF's pages, a table's rows, an e-mail's text with its HTML only in a sandbox), its original, reading it
again and moving it to the Trash. Everything shown is made in the viewing process and kept with the document."""

from email.message import EmailMessage

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app.workspace import Workspace
from iplikci.domain.codes import DocumentStatus
from iplikci.storage import audit
from iplikci.storage import documents as stored
from iplikci.viewer import process as viewer

from conftest import add

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def client_for(ws: Workspace) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN, today=lambda: demo.AS_OF)), base_url=BASE)


@pytest.fixture
def demo_ws(tmp_path) -> Workspace:
    return Workspace.load(demo.build(tmp_path / "demo"))


def sha_of(ws: Workspace, parser: str) -> str:
    with ws.db() as db:
        return next(d.sha256 for d in stored.every(db) if d.parser == parser)


def test_a_documents_detail_says_how_it_arrived_and_lists_its_statement_and_rows_in_place(demo_ws):
    sha = sha_of(demo_ws, "teb.account_html")
    found = client_for(demo_ws).get(f"/api/documents/{sha}", headers=bearer()).json()
    assert found["document"]["sha256"] == sha and found["view"] == "table"
    assert found["arrivals"][0]["kind"] == "import"  # first arrival first
    [check] = found["checks"]
    assert check["verified"] and check["balance_checks"][0] == check["balance_checks"][1] > 0
    assert found["rows"] and all(r["counted"] and r["ref"]["row"] for r in found["rows"])
    rows = [r["ref"]["row"] for r in found["rows"]]
    assert rows == sorted(rows)  # in the document's own order


def test_a_receipts_rows_say_whether_a_statement_already_counts_them(demo_ws):
    sha = sha_of(demo_ws, "garanti.receipt")
    found = client_for(demo_ws).get(f"/api/documents/{sha}", headers=bearer()).json()
    assert found["checks"] == [] and found["rows"]
    assert all(r["evidence"] is not None for r in found["rows"])
    assert all(r["ref"]["page"] == 1 for r in found["rows"])


def test_a_pdf_is_shown_as_pages_drawn_once_and_kept_with_it(demo_ws, monkeypatch):
    sha = sha_of(demo_ws, "garanti.receipt")
    client = client_for(demo_ws)
    view = client.get(f"/api/documents/{sha}/view", headers=bearer()).json()
    assert view["kind"] == "pdf" and view["pages"][0]["width"] > 0 and not view["has_html"]
    page = client.get(f"/api/documents/{sha}/pages/1.png?width=700", headers=bearer())
    assert page.status_code == 200 and page.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert any(p.name.endswith("-1-800.png") for p in demo_ws.vault.derived(sha).iterdir())  # the next width up
    missing = client.get(f"/api/documents/{sha}/pages/9.png", headers=bearer())
    assert (missing.status_code, missing.json()["code"]) == (422, "document_unshown")

    def no_process(*_args: object) -> object:
        raise AssertionError("drawn again")

    monkeypatch.setattr(viewer, "render_page", no_process)
    again = client.get(f"/api/documents/{sha}/pages/1.png?width=800", headers=bearer())
    assert again.content == page.content
    lines = client.get(f"/api/documents/{sha}/pages/1/lines", headers=bearer()).json()["lines"]
    assert lines and all(isinstance(line, str) for line in lines)


def test_a_table_export_is_shown_as_the_rows_its_reader_counts(demo_ws):
    sha = sha_of(demo_ws, "teb.account_html")
    client = client_for(demo_ws)
    view = client.get(f"/api/documents/{sha}/view", headers=bearer()).json()
    assert view["kind"] == "table" and view["table"]["rows"]
    detail = client.get(f"/api/documents/{sha}", headers=bearer()).json()
    first = detail["rows"][0]
    printed = view["table"]["rows"][first["ref"]["row"] - 1]  # SourceRef.row counts from 1
    assert any(first["description"] in cell for cell in printed)


def a_message(html: str | None) -> bytes:
    msg = EmailMessage()
    msg["From"] = "Örnek Banka <bilgi@ornekbanka.com.tr>"
    msg["To"] = "kullanici@example.com"
    msg["Subject"] = "Hesap hareketi bildirimi"
    msg["Date"] = "Mon, 02 Nov 2026 09:30:00 +0300"
    msg["Message-ID"] = "<deneme-1@ornekbanka.com.tr>"
    msg.set_content("Sayın Müşterimiz,\nHesabınıza 1.250,00 TL geldi.")
    if html is not None:
        msg.add_alternative(html, subtype="html")
    return msg.as_bytes()


def test_an_email_is_shown_as_its_text_and_its_html_only_in_a_sandbox(ws):
    html = "<p>Sayın Müşterimiz,</p><p>Hesabınıza <b>1.250,00 TL</b> geldi.</p><script>alert(1)</script>"
    [kept] = add(ws, "ileti.eml", a_message(html), folder="Posta").stored
    client = client_for(ws)
    view = client.get(f"/api/documents/{kept.sha256}/view", headers=bearer()).json()
    assert view["kind"] == "mail" and view["has_html"] and view["mail"]["sender"] == "ornekbanka.com.tr"
    assert view["mail"]["lines"] == ["Sayın Müşterimiz,", "Hesabınıza 1.250,00 TL geldi."]
    detail = client.get(f"/api/documents/{kept.sha256}", headers=bearer()).json()
    assert detail["arrivals"][0]["gmail"].endswith("rfc822msgid%3Adeneme-1%40ornekbanka.com.tr")
    original = client.get(f"/api/documents/{kept.sha256}/original.html", headers=bearer())
    policy = original.headers["content-security-policy"]
    assert policy.startswith("sandbox;") and "default-src 'none'" in policy and "frame-ancestors 'self'" in policy
    assert original.headers["x-frame-options"] == "SAMEORIGIN" and "<b>1.250,00 TL</b>" in original.text


def test_a_plain_email_has_no_original_view(ws):
    [kept] = add(ws, "duz.eml", a_message(None), folder="Posta").stored
    view = client_for(ws).get(f"/api/documents/{kept.sha256}/view", headers=bearer()).json()
    assert view["kind"] == "mail" and not view["has_html"] and view["mail"]["text"].startswith("Sayın Müşterimiz")


def test_the_original_downloads_under_its_readable_name_and_is_never_opened_here(demo_ws):
    sha = sha_of(demo_ws, "garanti.receipt")
    found = client_for(demo_ws).get(f"/api/documents/{sha}/download", headers=bearer())
    assert found.headers["content-type"] == "application/pdf"
    assert found.headers["content-disposition"].startswith("attachment; filename*=UTF-8''")
    assert found.content == demo_ws.vault.read(sha)


def test_a_document_is_read_again_on_request(demo_ws):
    sha = sha_of(demo_ws, "garanti.receipt")
    found = client_for(demo_ws).post(f"/api/documents/{sha}/reparse", headers=bearer())
    assert found.json() == {"status": "processed"}


def test_removing_a_document_takes_it_to_the_trash_and_out_of_the_ledger(demo_ws, private_trash):
    sha = sha_of(demo_ws, "garanti.receipt")
    client = client_for(demo_ws)
    assert client.post(f"/api/documents/{sha}/remove", headers=bearer()).status_code == 403  # the interface only
    url = client.post("/api/login-links", headers=bearer()).json()["url"]
    client.get(url, follow_redirects=False)
    removed = client.post(f"/api/documents/{sha}/remove", headers=OWN_PAGE).json()
    assert removed["trash"].startswith("iplikci silinenler")
    assert list(private_trash.rglob(f"*{sha}*")) and not demo_ws.vault.has(sha)
    with demo_ws.db() as db:
        assert stored.get(db, sha).status is DocumentStatus.REMOVED
        assert ("document.removed", sha) in {(e.action, e.target) for e in audit.entries(db)}
    assert client.get(f"/api/documents/{sha}", headers=bearer()).status_code == 404
    ledger = Context(ws=demo_ws, token=TOKEN).analysis.get().dataset
    assert not [t for t in ledger.transactions if t.document == sha]  # its rows went with it


def test_a_made_up_document_is_refused_before_anything_is_looked_up(demo_ws):
    client = client_for(demo_ws)
    assert client.get("/api/documents/xyz", headers=bearer()).status_code == 422
    assert client.get(f"/api/documents/{'0' * 64}", headers=bearer()).json()["code"] == "document_missing"


def test_the_list_finds_documents_by_their_words_kind_source_account_and_bank(demo_ws):
    client = client_for(demo_ws)

    def listed(**query: str | list[str]) -> list[dict]:
        response = client.get("/api/documents", params=query, headers=bearer())
        assert response.status_code == 200
        return response.json()["items"]

    every = listed(limit="200")
    teb = sha_of(demo_ws, "teb.account_html")
    by_words = listed(q="migros")  # a word of a row read from it, folded as the program compares Turkish
    assert teb in {d["sha256"] for d in by_words} and len(by_words) < len(every)
    shop, bank = listed(q="teknosa"), listed(q="garanti", limit="200")
    either = listed(q="teknosa, garanti", limit="200")  # a comma: the documents of either part
    assert {d["sha256"] for d in either} == {d["sha256"] for d in shop + bank}
    assert len(either) > max(len(shop), len(bank))
    assert listed(q="migros spotify, hiçyokböyle") == listed(q="migros spotify")
    statement = next(d for d in every if d["sha256"] == teb)
    assert statement["accounts"] == [{"id": "teb-123456789", "label": "TEB Vadesiz TL 123456789", "bank": "TEB"}]
    receipts = listed(kind="receipt", limit="200")
    assert receipts and {d["kind"] for d in receipts} == {"receipt"}
    one = listed(account="garanti-1234567", limit="200")
    bank = listed(bank="Garanti BBVA", limit="200")
    assert one and {d["sha256"] for d in one} < {d["sha256"] for d in bank}  # the bank has other accounts too
    assert all("garanti-1234567" in {a["id"] for a in d["accounts"]} for d in one)
    assert all("Garanti BBVA" in {a["bank"] for a in d["accounts"]} for d in bank)
    unread = listed(kind="none", limit="200")
    assert {d["kind"] for d in unread} <= {""} and {d["status"] for d in unread} <= {"unprocessed", "unreadable"}
    for source in {k for d in every for k in d["sources"]}:  # each arrival kind the demo's documents came by
        came = listed(source=source, limit="200")
        assert came and all(source in d["sources"] for d in came)
        assert len(came) == sum(source in d["sources"] for d in every)
    wrong = client.get("/api/documents", params={"kind": "faks"}, headers=bearer())
    assert (wrong.status_code, wrong.json()["code"]) == (400, "filter_invalid")
