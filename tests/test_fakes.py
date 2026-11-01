"""The fake documents (ADR-0005): every reader has some, each reads as it must, and the files they come in read back
as they were written."""

import io
import zipfile
from dataclasses import replace
from datetime import datetime

import pytest

from iplikci.fakes import Specimen, check, specimens
from iplikci.fakes.files import text_pdf, xls_file, xlsx_file
from iplikci.parsers import registry
from iplikci.parsers.sheet import read_xls, read_xlsx, sniff

SPECIMENS = specimens()


def test_every_reader_has_a_fake_document():
    assert {r.id for r in registry.BUILTIN} == {s.reader for s in SPECIMENS}
    assert len({s.name for s in SPECIMENS}) == len(SPECIMENS)


@pytest.mark.parametrize("specimen", SPECIMENS, ids=[s.name for s in SPECIMENS])
def test_every_fake_document_is_read_by_its_reader_with_its_rows_their_places_and_its_balance(specimen):
    assert check(specimen) == []


def test_a_check_names_what_goes_wrong():
    bonus = next(s for s in SPECIMENS if s.reader == "garanti.bonus_card")
    wrong = replace(bonus, reader="teb.bonus_card", account="teb-1234", rows=3)
    assert check(wrong) == [
        "garanti.bonus_card okudu, teb.bonus_card okumalıydı",
        "hesap garanti-1234, beklenen teb-1234",
        "11 satır, beklenen 3",
    ]
    assert check(Specimen("form.pdf", text_pdf([(40, 40, "TALİMAT FORMU")]), "x", "x", 0)) == [
        "okunmadı: talimat formu"
    ]


def test_the_fake_workbooks_read_back_as_written():
    rows = [["Hesap Özeti ĞÜŞİÖÇ", None, "TL"], [], ["05.10.2026", -1250.5, 3.0]]
    xls = xls_file("Sayfa Adı", rows)
    assert sniff(xls) == "xls"
    assert read_xls(xls) == (
        "Sayfa Adı",
        [["Hesap Özeti ĞÜŞİÖÇ", "", "TL"], ["", "", ""], ["05.10.2026", -1250.5, 3.0]],
    )
    xlsx = xlsx_file("Sayfa1", [["Tarih", datetime(2026, 10, 1, 9, 15)], [None, 12.5]])
    assert sniff(xlsx) == "xlsx"
    assert read_xlsx(xlsx) == ("Sayfa1", [["Tarih", datetime(2026, 10, 1, 9, 15)], [None, 12.5]])


def test_a_workbook_carries_no_clock():
    with zipfile.ZipFile(io.BytesIO(xlsx_file("Sayfa1", [["Tarih"]]))) as book:
        assert {entry.date_time for entry in book.infolist()} == {(2026, 1, 1, 0, 0, 0)}
        assert b">2026-01-01T00:00:00Z</dcterms:modified>" in book.read("docProps/core.xml")
    assert [s.data for s in specimens()] == [s.data for s in SPECIMENS]
