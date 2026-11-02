"""New documents through the inbox: uploads, unreadable archives, missing documents, one writer at a time."""

import io
import zipfile
from datetime import date
from pathlib import PurePosixPath

import pytest

from iplikci.analysis import Dataset
from iplikci.app import intake, reading, uploads
from iplikci.app.analysis import analyze, document_gaps
from iplikci.app.uploads import inbox_files, safe_upload_path, save_upload
from iplikci.app.workspace import Busy, file_lock
from iplikci.domain.codes import AccountType, DocumentStatus
from iplikci.domain.models import Account, Statement
from iplikci.ingest.archives import ZIP_DAMAGED, ZIP_ENCRYPTED
from iplikci.parsers import ENCRYPTED_REASON, Unreadable

from conftest import put


@pytest.mark.parametrize(
    "name, safe",
    [
        ("ekstre.pdf", "ekstre.pdf"),
        ("../../etc/passwd.pdf", "etc/passwd.pdf"),  # never above the inbox
        ("/Users/x/Downloads/a.pdf", "Users/x/Downloads/a.pdf"),  # absolute becomes relative
        ("a/b/c/d/e/f.xls", "c/d/e/f.xls"),  # three folders at most
        ("C:\\Belgeler\\ekim.pdf", "C/Belgeler/ekim.pdf"),
        ("kötü\x00ad\x1f.pdf", "kötüad.pdf"),
    ],
)
def test_upload_names_stay_inside_the_inbox(name, safe):
    assert safe_upload_path(name) == PurePosixPath(safe)


@pytest.mark.parametrize("name", [".DS_Store", "klasor/.gizli.pdf", "", "../.."])
def test_hidden_or_empty_upload_names_are_refused(name):
    assert safe_upload_path(name) is None


def test_a_long_upload_name_is_shortened_within_the_file_systems_limit_and_keeps_its_extension():
    long = "Şubat ayı hesap özeti " * 20 + ".pdf"
    safe = safe_upload_path(f"klasör/{long}")
    assert safe is not None and safe.parent == PurePosixPath("klasör")
    assert safe.name.endswith(".pdf") and safe.name.startswith("Şubat ayı hesap özeti")
    assert len(safe.name.encode()) <= 200


def test_upload_never_replaces_a_waiting_file(ws):
    a = save_upload(ws, "ekim.pdf", io.BytesIO(b"bir"), 3)
    b = save_upload(ws, "ekim.pdf", io.BytesIO(b"iki"), 3)
    again = save_upload(ws, "baska-ad.pdf", io.BytesIO(b"bir"), 3)
    assert (a.status, a.name, b.status, b.name) == ("eklendi", "ekim.pdf", "eklendi", "ekim (2).pdf")
    assert (again.status, again.name) == ("zaten-var", "ekim.pdf")  # same bytes are kept once
    assert sorted(p.name for p in ws.inbox.iterdir()) == ["ekim (2).pdf", "ekim.pdf"]


def test_upload_refuses_other_file_types(ws):
    up = save_upload(ws, "foto.jpg", io.BytesIO(b"x"), 1)
    assert up.status == "reddedildi" and "desteklenmeyen" in up.reason
    assert list(ws.inbox.iterdir()) == []


def test_interrupted_upload_leaves_nothing_behind(ws):
    with pytest.raises(ConnectionError):
        save_upload(ws, "yarim.pdf", io.BytesIO(b"abc"), 10)
    assert list(ws.inbox.iterdir()) == []  # not even the hidden partial file


def test_unfinished_uploads_are_not_waiting_documents(ws):
    put(ws.inbox / ".yukleniyor-x", "yarım")
    put(ws.inbox / "alt" / "a.pdf", "a")
    assert inbox_files(ws) == [ws.inbox / "alt" / "a.pdf"]


def test_upload_works_where_the_disk_has_no_hard_links(ws, monkeypatch):
    def no_links(src, dst):
        raise PermissionError(1, "Operation not permitted")  # FAT and exFAT

    monkeypatch.setattr(uploads.os, "link", no_links)
    first = save_upload(ws, "ekim.pdf", io.BytesIO(b"bir"), 3)
    second = save_upload(ws, "ekim.pdf", io.BytesIO(b"iki"), 3)
    assert (first.name, second.name) == ("ekim.pdf", "ekim (2).pdf")  # still never replaced
    assert [p.read_bytes() for p in inbox_files(ws)] == [b"iki", b"bir"]
    assert sorted(p.name for p in ws.inbox.iterdir()) == ["ekim (2).pdf", "ekim.pdf"]  # no partial files left


def test_an_encrypted_pdf_is_kept_once_for_a_manual_look(ws, monkeypatch):
    real = reading.parse_document

    def parse(doc, business=None):
        if doc.name == "kilitli.pdf":
            raise Unreadable(ENCRYPTED_REASON)
        return real(doc, business)

    monkeypatch.setattr(reading, "parse_document", parse)
    put(ws.inbox / "kilitli.pdf", "%PDF şifreli")
    put(ws.inbox / "ikinci kopya" / "kilitli.pdf", "%PDF şifreli")
    plan = intake.plan_inbox(ws)
    first, second = plan.changes
    assert (first.status, first.reason) == (DocumentStatus.UNREADABLE, ENCRYPTED_REASON)
    assert second.verdict == "known"  # the same bytes are kept once
    intake.apply(ws, plan)
    assert inbox_files(ws) == []
    assert [(d.name, d.status, d.detail) for d in analyze(ws).dataset.documents] == [
        ("kilitli.pdf", "hata", ENCRYPTED_REASON)
    ]


def _encrypted_zip(member: str, data: bytes) -> bytes:
    """A zip whose member is marked as password-protected (zipfile cannot write real encryption; the
    flag is what makes a reader ask for the password)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(member, data)
    raw = bytearray(buf.getvalue())
    central = raw.rindex(b"PK\x01\x02")
    raw[central + 8] |= 0x1  # general purpose flag in the central directory: encrypted
    raw[6] |= 0x1  # and in the local header
    return bytes(raw)


@pytest.mark.parametrize(
    "data, reason", [(_encrypted_zip("ekstre.pdf", b"%PDF"), ZIP_ENCRYPTED), (b"PK\x03\x04 yarim inmis", ZIP_DAMAGED)]
)
def test_a_zip_that_cannot_be_opened_is_kept_for_a_manual_look(ws, data, reason):
    put(ws.inbox / "ekstreler.zip", data)
    [item] = intake.plan_inbox(ws).changes
    assert (item.status, item.reason) == (DocumentStatus.UNREADABLE, reason)  # never set aside as an archive
    intake.apply(ws, intake.plan_inbox(ws))
    a = analyze(ws)  # the report reads it as an unreadable document instead of failing
    assert [(d.name, d.status, d.detail) for d in a.dataset.documents] == [("ekstreler.zip", "hata", reason)]


def test_document_gaps_name_missing_and_stale_statements():
    def acc(n):
        return Account(f"a{n}", f"Hesap {n}", "TEB", AccountType.CREDIT_CARD, number=str(n))

    def stmt(n, cut):
        return Statement(f"a{n}", cut, "TRY", "x.pdf", 0.0, 0.0)

    ds = Dataset(
        accounts={"a1": acc(1), "a2": acc(2), "a3": acc(3)},
        statements=[stmt(1, date(2026, 10, 15)), stmt(2, date(2026, 8, 15)), stmt(3, date(2025, 1, 15))],
        transactions=[],
        documents=[],
        groups=[],
        categories={},
        coverage={
            "a1": {"2026-07": 1.0, "2026-08": 0.4, "2026-09": 1.0, "2026-10": 0.5},
            "a2": {"2026-07": 1.0, "2026-08": 0.5},
        },
    )
    gaps = {g.account: g for g in document_gaps(ds, today=date(2026, 10, 20))}
    assert gaps["Hesap 1"].months == ("2026-08",) and gaps["Hesap 1"].behind == 5
    assert gaps["Hesap 2"].behind == 66 and gaps["Hesap 2"].months == ()  # a newer statement must exist by now
    assert "Hesap 3" not in gaps  # stopped long before the others: probably closed
    nothing_new = document_gaps(ds, today=date(2027, 6, 1))  # no document added for months: all are behind
    assert [g.account for g in nothing_new] == ["Hesap 2", "Hesap 1"]


def test_one_process_at_a_time_holds_a_lock(ws):
    with ws.lock():
        with pytest.raises(Busy), ws.lock(timeout=0.1):
            pass
        with file_lock(ws.run, ".baska.kilit", timeout=0.1):  # another name is another lock
            pass
    with ws.lock(timeout=0.1):  # released
        pass
