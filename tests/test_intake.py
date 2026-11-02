"""Taking documents into the vault (ADR-0003): a plan first, touching nothing; then exactly that plan. Nothing a
user owns is ever overwritten or lost: kept documents move into the vault, the rest goes to the Trash."""

import io
import zipfile

import pytest

from iplikci.app import intake
from iplikci.app.workspace import StalePlan, Workspace
from iplikci.domain.codes import DocumentKind, DocumentStatus, SourceKind
from iplikci.fakes import teb, vakifbank
from iplikci.fakes.files import text_pdf
from iplikci.ingest import archives
from iplikci.storage import audit, documents

from conftest import FEBRUARY, JANUARY, put

COMPANY = "ÖRNEK TEKNOLOJİ A.Ş."
FORM = text_pdf([(201, 97, "SGK Otomatik Ödeme Talimat Formu"), (70, 146, "Türk Ekonomi Bankası A.Ş.")])


@pytest.fixture
def ws(ws) -> Workspace:
    ws.layout.settings.write_text('[identity]\nbusiness_names = ["Örnek Teknoloji"]\n', encoding="utf-8")
    return Workspace.load(ws.home)


def zipped(**members: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buffer.getvalue()


def by_name(plan: intake.Plan) -> dict[str, intake.Candidate]:
    return {c.name: c for c in plan.items}


def stored_names(ws: Workspace) -> list[str]:
    with ws.db() as db:
        return sorted(d.name for d in documents.every(db))


# --- the inbox --------------------------------------------------------------------------------------


def test_the_inbox_plan_touches_nothing(ws):
    put(ws.inbox / "ocak.xls", teb.account_export(JANUARY))
    plan = intake.plan_inbox(ws)
    [c] = plan.changes
    assert (c.verdict, c.status, c.outcome.kind) == ("store", DocumentStatus.PROCESSED, DocumentKind.ACCOUNT_STATEMENT)
    assert (ws.inbox / "ocak.xls").exists()
    assert stored_names(ws) == [] and not list(ws.vault.objects())


def test_kept_documents_move_from_the_inbox_into_the_vault(ws):
    put(ws.inbox / "ocak.xls", teb.account_export(JANUARY))
    put(ws.inbox / "alt" / "subat.xls", FEBRUARY)
    done = intake.apply(ws, intake.plan_inbox(ws))
    assert sorted(c.name for c in done.stored) == ["ocak.xls", "subat.xls"]
    assert not any(ws.inbox.iterdir())  # emptied, the subfolder too
    assert stored_names(ws) == ["ocak.xls", "subat.xls"]
    with ws.db() as db:
        [doc] = [d for d in documents.every(db) if d.name == "subat.xls"]
        assert doc.display_name.endswith("Hesap Hareketleri.xls")
        [source] = documents.sources(db, doc.sha256)
        assert (source.kind, source.original, source.origin) == (SourceKind.INBOX, "subat.xls", "alt/subat.xls")


def test_company_documents_and_strangers_leave_the_inbox_for_the_trash(ws, private_trash):
    put(ws.inbox / "sirket.xls", teb.account_export(JANUARY, holder=COMPANY))
    put(ws.inbox / "notlar.txt", "bir not")
    plan = intake.plan_inbox(ws)
    assert {c.name: c.action for c in plan.changes} == {"sirket.xls": "business", "notlar.txt": "not_document"}
    done = intake.apply(ws, plan)
    assert stored_names(ws) == [] and not any(ws.inbox.iterdir())
    assert done.trash is not None and done.trash.is_relative_to(private_trash)
    assert sorted(p.name for p in done.trash.iterdir()) == ["notlar.txt", "sirket.xls"]
    with ws.db() as db:
        assert len(audit.targets(db, "document.business")) == 1
        assert [e.detail["files"] for e in audit.entries(db, "inbox.set_aside")] == [2]


def test_a_document_without_money_movements_is_kept_with_its_reason(ws):
    put(ws.inbox / "talimat.pdf", FORM)
    [c] = intake.apply(ws, intake.plan_inbox(ws)).stored
    assert (c.status, c.reason) == (DocumentStatus.UNPROCESSED, "talimat formu")
    assert stored_names(ws) == ["talimat.pdf"]


def test_an_unreadable_document_is_kept_for_a_manual_look(ws):
    put(ws.inbox / "bozuk.zip", b"PK\x03\x04yarim kalmis")
    [c] = intake.apply(ws, intake.plan_inbox(ws)).stored
    assert c.status is DocumentStatus.UNREADABLE and "zip" in c.reason
    assert stored_names(ws) == ["bozuk.zip"]


def test_an_archive_is_opened_and_then_set_aside(ws):
    put(
        ws.inbox / "e-posta.zip",
        zipped(**{"ocak.xls": teb.account_export(JANUARY), "sirket.xls": teb.account_export(JANUARY, holder=COMPANY)}),
    )
    plan = intake.plan_inbox(ws)
    assert {c.name: c.action for c in plan.items} == {
        "ocak.xls": "processed",
        "sirket.xls": "business",
        "e-posta.zip": "archive",
    }
    done = intake.apply(ws, plan)
    assert stored_names(ws) == ["ocak.xls"]
    assert done.trash is not None and [p.name for p in done.trash.iterdir()] == ["e-posta.zip"]
    assert not any(ws.inbox.iterdir())


def test_known_bytes_add_an_arrival_and_leave_the_inbox(ws):
    put(ws.inbox / "ocak.xls", teb.account_export(JANUARY))
    intake.apply(ws, intake.plan_inbox(ws))
    put(ws.inbox / "ocak (1).xls", teb.account_export(JANUARY))
    [c] = intake.plan_inbox(ws).changes
    assert (c.verdict, c.new_source) == ("known", True)
    intake.apply(ws, intake.plan_inbox(ws))
    assert not any(ws.inbox.iterdir())
    with ws.db() as db:
        assert documents.source_counts(db) == {c.sha256: 2}


def test_a_plan_is_refused_when_its_files_changed(ws):
    path = put(ws.inbox / "ocak.xls", teb.account_export(JANUARY))
    plan = intake.plan_inbox(ws)
    path.write_bytes(FEBRUARY)
    with pytest.raises(StalePlan):
        intake.apply(ws, plan)
    assert path.read_bytes() == FEBRUARY and stored_names(ws) == []


def test_the_same_bytes_twice_in_one_plan_are_one_document(ws):
    put(ws.inbox / "a.xls", teb.account_export(JANUARY))
    put(ws.inbox / "b.xls", teb.account_export(JANUARY))
    put(ws.inbox / "sirket-1.xls", teb.account_export(JANUARY, holder=COMPANY))
    put(ws.inbox / "sirket-2.xls", teb.account_export(JANUARY, holder=COMPANY))
    plan = intake.plan_inbox(ws)
    assert [c.action for c in plan.items] == ["processed", "known", "business", "business"]
    intake.apply(ws, plan)
    assert stored_names(ws) == ["a.xls"]


# --- paths the user names ---------------------------------------------------------------------------


def test_imported_files_stay_where_they_are(ws, tmp_path):
    downloads = tmp_path / "Downloads"
    original = put(downloads / "ekstreler" / "ocak.xls", teb.account_export(JANUARY))
    put(downloads / "notlar.txt", "bir not")
    plan = intake.plan_paths(ws, [downloads])
    assert [c.name for c in plan.changes] == ["ocak.xls"]  # a stranger outside the inbox is not ours to move
    intake.apply(ws, plan)
    assert original.exists() and (downloads / "notlar.txt").exists()
    assert stored_names(ws) == ["ocak.xls"]
    assert intake.plan_paths(ws, [downloads]).changes == []  # the same arrival again changes nothing


def test_paths_inside_the_data_folder_or_missing_are_refused(ws, tmp_path):
    with pytest.raises(ValueError, match="veri klasörünün içinde"):
        intake.plan_paths(ws, [ws.inbox])
    with pytest.raises(FileNotFoundError):
        intake.plan_paths(ws, [tmp_path / "yok"])


def test_a_plan_item_says_what_it_is_and_where_it_goes(ws):
    put(ws.inbox / "ocak.xls", teb.account_export(JANUARY))
    [c] = intake.plan_inbox(ws).changes
    item = intake.describe(c, ws)
    assert item["action"] == "processed" and item["fromInbox"]
    assert item["document"] == {
        "kind": "hesap",
        "account": "TEB Vadesiz TL 123456789",
        "start": "2026-01-01",
        "end": "2026-01-31",
        "rows": 2,
        "verified": True,
        "check": "bakiye 1/1 satır tutarlı",
    }
    assert str(item["target"]).startswith("2026-01-01 - 2026-01-31 TEB Vadesiz TL 123456789")


def test_a_document_is_known_by_its_content_whatever_its_name_says(ws, tmp_path):
    # A bank's download without an extension, one with a wrong one, and a file that is no document.
    folder = tmp_path / "indirilenler"
    put(folder / "Belge-2026-10-31", vakifbank.account_xlsx())
    put(folder / "alt" / "rapor.dat", vakifbank.passbook())
    put(folder / "notlar.txt", "alışveriş listesi")
    found = by_name(intake.plan_paths(ws, [folder]))
    assert sorted(found) == ["Belge-2026-10-31.xlsx", "rapor.dat.pdf"]
    assert all(c.status is DocumentStatus.PROCESSED for c in found.values())
    assert found["Belge-2026-10-31.xlsx"].outcome.kind is DocumentKind.ACCOUNT_STATEMENT
    assert found["Belge-2026-10-31.xlsx"].source.original == "Belge-2026-10-31"  # its own name is kept beside it


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"%PDF-1.7\n", ".pdf"),
        (b"\r\n%PDF-1.4\n", ".pdf"),  # a few bytes before the header
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(504), ".xls"),
        (zipped(**{"belge.pdf": b"%PDF-1.4"}), ".zip"),
        (b"\xef\xbb\xbf<html><body><table></table></body></html>", ".html"),
        (b'<?xml version="1.0"?><Invoice xmlns="urn:oasis"/>', ".xml"),
        (b"Received: from mail.example.com\r\nSubject: Ekstre\r\n\r\n", ".eml"),
        (b"merhaba", None),
        (b"\x89PNG\r\n\x1a\n", None),
    ],
)
def test_a_file_s_format_comes_from_its_bytes(data, expected):
    assert archives.sniffed_extension(data) == expected


def test_a_workbook_is_told_from_a_zip_by_what_it_holds():
    assert archives.sniffed_extension(vakifbank.account_xlsx()) == ".xlsx"
    assert archives.sniffed_extension(vakifbank.account_xlsx(), whole=False) == ".zip"  # the start alone cannot tell
