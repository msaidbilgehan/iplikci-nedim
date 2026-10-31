"""New documents: uploads into the inbox, plans, filing, importing."""

import io
import zipfile
from datetime import date
from pathlib import Path, PurePosixPath

import pytest

from iplikci import duzenle, pipeline, workspace
from iplikci.analysis import Dataset
from iplikci.models import Account, Statement
from iplikci.parsers import ENCRYPTED_REASON, Unreadable
from iplikci.sources import ZIP_DAMAGED, ZIP_ENCRYPTED
from iplikci.workspace import (
    Busy,
    StalePlan,
    analyze,
    apply,
    document_gaps,
    import_paths,
    inbox_files,
    output_lock,
    plan_inbox,
    safe_upload_path,
    save_upload,
)

from conftest import JANUARY, put, teb_export

TARGET = Path("TEB/Vadesiz Hesap TL 123456789/2026-01-01 - 2026-01-31 TEB Vadesiz TL 123456789 Hesap Hareketleri.xls")


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


def test_waiting_documents_count_in_the_report(ws):
    assert ws.report_sources() == [ws.documents, ws.inbox]
    put(ws.inbox / ".yukleniyor-x", "yarım")
    put(ws.inbox / "alt" / "a.pdf", "a")
    assert inbox_files(ws) == [ws.inbox / "alt" / "a.pdf"]


def test_plan_and_apply_file_an_upload(ws):
    put(ws.inbox / "indirilenler" / "TEBHareket.xls", teb_export(JANUARY))
    plan = plan_inbox(ws)
    [item] = plan.changes
    assert (item.action, item.target) == (duzenle.KEEP, ws.documents / TARGET)
    assert not (ws.documents / TARGET).exists()  # a plan touches nothing
    done = apply(ws, plan)
    assert (ws.documents / TARGET).read_bytes() == teb_export(JANUARY)
    assert ws.inbox.is_dir() and inbox_files(ws) == []  # emptied, but the inbox itself stays
    assert done.log and done.log.read_text(encoding="utf-8-sig").count("Düzenlendi") == 1


def test_a_second_copy_of_a_filed_statement_is_set_aside(ws, private_trash):
    put(ws.documents / TARGET, teb_export(JANUARY))
    put(ws.inbox / "kopya.xls", teb_export(JANUARY))
    plan = plan_inbox(ws)
    [item] = plan.changes
    assert item.action == duzenle.DUPLICATE
    done = apply(ws, plan)
    assert done.trash is not None and done.trash.is_relative_to(private_trash)
    assert [p.name for p in done.trash.rglob("*.xls")] == ["kopya.xls"]


def test_unreadable_upload_moves_to_the_unreadable_folder(ws, monkeypatch):
    real = pipeline.parse_document

    def parse(doc):
        if doc.name == "kilitli.pdf":
            raise Unreadable(ENCRYPTED_REASON)
        return real(doc)

    monkeypatch.setattr(pipeline, "parse_document", parse)
    put(ws.inbox / "kilitli.pdf", "%PDF şifreli")
    put(ws.inbox / "ikinci kopya" / "kilitli.pdf", "%PDF şifreli")
    plan = plan_inbox(ws)
    first, second = sorted(plan.changes, key=lambda it: len(it.path.parts))
    assert (first.action, first.target) == (duzenle.FAILED, ws.documents / duzenle.UNREADABLE_FOLDER / "kilitli.pdf")
    assert "şifreli" in first.reason
    assert second.action == duzenle.DUPLICATE  # the same bytes are kept once
    apply(ws, plan)
    assert (ws.documents / duzenle.UNREADABLE_FOLDER / "kilitli.pdf").exists() and inbox_files(ws) == []


def test_a_plan_is_not_applied_after_its_file_changed(ws):
    path = put(ws.inbox / "TEBHareket.xls", teb_export(JANUARY))
    plan = plan_inbox(ws)
    path.write_bytes(teb_export(JANUARY[:1]))
    with pytest.raises(StalePlan):
        apply(ws, plan)
    assert path.exists() and not (ws.documents / TARGET).exists()


def test_import_copies_new_documents_and_leaves_the_originals(ws, tmp_path):
    original = put(tmp_path / "Downloads" / "TEBHareket.xls", teb_export(JANUARY))
    put(tmp_path / "Downloads" / "notlar.pdf", "%PDF banka belgesi değil")
    found, copies = import_paths(ws, [str(tmp_path / "Downloads")])
    assert sorted(it.action for it in found) == [duzenle.UNUSED, duzenle.KEEP]
    assert [c.name for c in copies] == ["TEBHareket.xls"] and original.exists()
    assert import_paths(ws, [str(tmp_path / "Downloads")])[1] == []  # already waiting: not copied twice


def test_import_refuses_the_document_folder_itself(ws):
    with pytest.raises(ValueError):
        import_paths(ws, [str(ws.documents)])


def test_document_gaps_name_missing_and_stale_statements():
    def acc(n):
        return Account(f"a{n}", f"Hesap {n}", "TEB", "Kredi kartı", number=str(n))

    def stmt(n, cut):
        return Statement(f"a{n}", cut, "TL", "x.pdf", 0.0, 0.0)

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
    [item] = plan_inbox(ws).changes
    assert (item.action, item.reason) == (duzenle.FAILED, reason)  # never set aside as an emptied archive
    assert item.target == ws.documents / duzenle.UNREADABLE_FOLDER / "ekstreler.zip"
    a = analyze(ws)  # the report reads it as an unreadable document instead of failing
    assert [(d.name, d.status, d.detail) for d in a.dataset.documents] == [("ekstreler.zip", "hata", reason)]


def test_upload_works_where_the_disk_has_no_hard_links(ws, monkeypatch):
    def no_links(src, dst):
        raise PermissionError(1, "Operation not permitted")  # FAT and exFAT

    monkeypatch.setattr(workspace.os, "link", no_links)
    first = save_upload(ws, "ekim.pdf", io.BytesIO(b"bir"), 3)
    second = save_upload(ws, "ekim.pdf", io.BytesIO(b"iki"), 3)
    assert (first.name, second.name) == ("ekim.pdf", "ekim (2).pdf")  # still never replaced
    assert [p.read_bytes() for p in inbox_files(ws)] == [b"iki", b"bir"]
    assert sorted(p.name for p in ws.inbox.iterdir()) == ["ekim (2).pdf", "ekim.pdf"]  # no partial files left


def test_one_process_at_a_time_holds_a_lock(ws):
    with output_lock(ws.output):
        with pytest.raises(Busy), output_lock(ws.output, timeout=0.1):
            pass
        with output_lock(ws.output, timeout=0.1, name=".baska.kilit"):  # another name is another lock
            pass
    with output_lock(ws.output, timeout=0.1):  # released
        pass
