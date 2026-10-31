"""The organizer moves real files: nothing may be overwritten or lost."""

import csv
import hashlib
from datetime import date
from pathlib import Path

import pytest

from iplikci import duzenle
from iplikci.duzenle import BUSINESS, DUPLICATE, FAILED, KEEP, UNUSED, Item, account_names
from iplikci.models import Account, ParseResult, Statement, Transaction


def item(
    path: Path | None, action: str, target: Path | None = None, data: bytes = b"", archive: Path | None = None
) -> Item:
    data = data or (path.read_bytes() if path else b"")
    return Item(
        name=path.name if path else "uye.pdf",
        sha256=hashlib.sha256(data).hexdigest(),
        path=path,
        archive=archive,
        data=data,
        action=action,
        target=target,
    )


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_folder_and_file_names():
    card = Account("garanti-4321", "Garanti BBVA Garanti Bonus •4321", "Garanti BBVA", "Kredi kartı", number="4321")
    assert account_names(card) == ("Garanti Bonus Kredi Kartı 4321", "Garanti Bonus 4321")
    loan = Account("qnb-5678", "QNB İhtiyaç Kredisi …5678", "QNB", "Kredi", number="")
    assert account_names(loan) == ("İhtiyaç Kredisi 5678", "Kredi 5678")
    salary = Account(
        "vakifbank-1", "Vakıfbank Vadesiz TL …123456 (Maaş)", "Vakıfbank", "Vadesiz hesap", number="0999000000123456"
    )
    assert account_names(salary)[0] == "Vadesiz Hesap TL 0999000000123456 (Maaş)"


def test_apply_moves_trashes_and_logs(tmp_path):
    src, root, trash = tmp_path / "eski", tmp_path / "Bankalar", tmp_path / "cop"
    keep = write(src / "ekstre.pdf", "kişisel ekstre")
    company = write(src / "sirket.pdf", "şirket ekstresi")
    unread = write(src / "bozuk.pdf", "okunamadı")
    archive = write(src / "arsiv.zip", "zip")
    plans = [
        item(keep, KEEP, root / "TEB" / "Kart" / "2026-01-15 TEB Ekstre.pdf"),
        item(company, BUSINESS),
        item(unread, FAILED),
        item(archive, UNUSED),
        item(None, KEEP, root / "TEB" / "Kart" / "2026-02-15 TEB Ekstre.pdf", data=b"arsivden", archive=archive),
    ]
    log = tmp_path / "kayit.csv"
    counts = duzenle.apply(plans, root, trash, log)
    assert (root / "TEB" / "Kart" / "2026-01-15 TEB Ekstre.pdf").read_text() == "kişisel ekstre"
    assert (root / "TEB" / "Kart" / "2026-02-15 TEB Ekstre.pdf").read_bytes() == b"arsivden"  # extracted
    assert unread.exists()  # left for a manual look
    assert not company.exists() and not archive.exists()
    trashed = sorted(p.name for p in trash.rglob("*") if p.is_file())
    assert trashed == ["arsiv.zip", "sirket.pdf"]
    assert counts == {KEEP: 2, BUSINESS: 1, FAILED: 1, UNUSED: 1}
    rows = list(csv.reader(log.open(encoding="utf-8-sig"), delimiter=";"))
    assert rows[0] == ["İşlem", "Eski konum", "Yeni konum", "Neden"] and len(rows) == 6


def test_apply_never_overwrites_a_different_file(tmp_path):
    root, trash = tmp_path / "Bankalar", tmp_path / "cop"
    target = root / "TEB" / "2026-01-15 TEB Ekstre.pdf"
    write(target, "başka bir belge")
    new = write(tmp_path / "gelen" / "x.pdf", "yeni belge")
    same = write(tmp_path / "gelen" / "y.pdf", "başka bir belge")
    plans = [item(new, KEEP, target), item(same, KEEP, target)]
    duzenle.apply(plans, root, trash, tmp_path / "kayit.csv")
    assert target.read_text() == "başka bir belge"
    assert (root / "TEB" / "2026-01-15 TEB Ekstre (2).pdf").read_text() == "yeni belge"
    assert plans[1].action == DUPLICATE and not same.exists()  # identical bytes: a real copy, trashed
    assert [p.read_text() for p in trash.rglob("*") if p.is_file()] == ["başka bir belge"]


def test_apply_removes_emptied_folders(tmp_path):
    old = write(tmp_path / "Gmail" / "alt" / "a.pdf", "a")
    write(tmp_path / "Gmail" / "alt" / ".DS_Store", "")
    duzenle.apply([item(old, UNUSED)], tmp_path / "Bankalar", tmp_path / "cop", tmp_path / "kayit.csv")
    assert not (tmp_path / "Gmail").exists()


def test_apply_never_removes_a_named_source_folder(tmp_path):
    downloads = tmp_path / "Downloads"
    old = write(downloads / "ekstreler" / "a.pdf", "a")
    duzenle.apply(
        [item(old, UNUSED)], tmp_path / "Bankalar", tmp_path / "cop", tmp_path / "kayit.csv", keep=(downloads,)
    )
    assert downloads.is_dir() and not (downloads / "ekstreler").exists()


def test_log_lists_what_was_done_when_a_move_fails(tmp_path):
    root = tmp_path / "Bankalar"
    first = write(tmp_path / "gelen" / "a.pdf", "a")
    second = write(tmp_path / "gelen" / "b.pdf", "b")
    write(root / "TEB", "bir klasör olması gereken yerde dosya")  # the second target's folder cannot exist
    plans = [item(first, KEEP, root / "QNB" / "a.pdf"), item(second, KEEP, root / "TEB" / "Kart" / "b.pdf")]
    log = tmp_path / "kayit.csv"
    with pytest.raises(OSError):
        duzenle.apply(plans, root, tmp_path / "cop", log)
    rows = list(csv.reader(log.open(encoding="utf-8-sig"), delimiter=";"))
    assert len(rows) == 2 and rows[1][1] == str(first)  # the move that happened is on record
    assert (root / "QNB" / "a.pdf").exists() and second.exists()


def test_changes_leave_out_documents_already_in_place(tmp_path):
    root = tmp_path / "Bankalar"
    placed = write(root / "TEB" / "a.pdf", "a")
    new = write(tmp_path / "gelen" / "b.pdf", "b")
    copy = write(tmp_path / "gelen" / "c.pdf", "a")
    unread = write(root / "bozuk.pdf", "x")
    plans = [
        item(placed, KEEP, placed),
        item(new, KEEP, root / "TEB" / "b.pdf"),
        item(copy, DUPLICATE),
        item(unread, FAILED),
        item(None, UNUSED, data=b"arsiv-uyesi", archive=tmp_path / "x.zip"),
    ]
    assert [p.path for p in duzenle.changes(plans)] == [new, copy]


def test_trash_falls_back_next_to_the_documents(tmp_path, monkeypatch):
    monkeypatch.setattr(duzenle, "MAC_TRASH", tmp_path / "erisilemeyen")  # e.g. no Full Disk Access
    trash = duzenle.default_trash(tmp_path / "Bankalar")
    assert trash.parent == tmp_path and trash.name.startswith("iplikci silinenler ")


def test_linux_trash_notes_where_the_folder_came_from(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    trash = tmp_path / "share" / "Trash"
    first = write(tmp_path / "iplikci silinenler 1" / "a.pdf", "a").parent
    put_back = duzenle.freedesktop_trash(first)
    assert put_back == trash / "files" / first.name and (put_back / "a.pdf").read_text() == "a"
    note = (trash / "info" / f"{first.name}.trashinfo").read_text(encoding="utf-8")
    assert note.startswith("[Trash Info]\nPath=/") and "iplikci%20silinenler%201" in note
    again = write(tmp_path / "iplikci silinenler 1" / "b.pdf", "b").parent  # the same name once more
    assert duzenle.freedesktop_trash(again) == trash / "files" / f"{first.name} 2"
    assert (put_back / "a.pdf").exists()  # the first one was not replaced


def test_names_hold_nothing_windows_or_a_path_would_split_on():
    card = Account("x-1", 'Banka Kart: "Özel" <1> •1', "Banka", "Kredi kartı", number="1")
    folder, short = account_names(card)
    assert not any(ch in folder + short for ch in '/\\:*?"<>|')


def test_every_personal_receipt_is_filed_even_when_a_list_shows_its_transfer(tmp_path, monkeypatch):
    # The receipt came before the list and is the evidence the month closed with: kept beside the list.
    account = Account(
        "garanti-1234567", "Garanti BBVA Vadesiz TL 1234567", "Garanti BBVA", "Vadesiz hesap", number="1234567"
    )
    listing = ParseResult(
        "liste",
        accounts=[account],
        statements=[Statement(account.id, date(2026, 10, 31), "TL", "liste.xls", 0.0, 0.0, start=date(2026, 10, 1))],
    )
    own = ParseResult(
        "dekont",
        accounts=[account],
        receipt_key="k1",
        title="Giden FAST",
        transactions=[Transaction(date(2026, 10, 5), "Giden FAST → kendi hesabım", 500.0, "transfer", account.id)],
    )
    write(tmp_path / "gelen" / "liste.xls", "liste")
    write(tmp_path / "gelen" / "dekont.pdf", "dekont")
    parsed = {"liste.xls": listing, "dekont.pdf": own}
    monkeypatch.setattr(duzenle, "parse_all", lambda docs, *args, **kw: [(d, parsed[d.name], None) for d in docs])
    root = tmp_path / "Bankalar"
    plans = {it.name: it for it in duzenle.plan([tmp_path / "gelen"], root, None)}
    assert {name: it.action for name, it in plans.items()} == {"liste.xls": KEEP, "dekont.pdf": KEEP}
    assert plans["dekont.pdf"].target == (
        root / "Garanti BBVA" / "Vadesiz Hesap TL 1234567" / "2026-10-05 Garanti Giden FAST Dekont.pdf"
    )
