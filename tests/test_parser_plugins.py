"""The reader plugin contract (ADR-0005): the registry, and choosing the one reader that recognises a document."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from iplikci import demo, parsers
from iplikci.app import reading
from iplikci.domain.codes import DocumentKind, DocumentStatus
from iplikci.domain.models import ParseResult
from iplikci.fakes import HOLDER, Move, garanti, teb
from iplikci.fakes.files import text_pdf
from iplikci.parsers import registry
from iplikci.parsers.common import set_business_names
from iplikci.parsers.contract import Detection, Document, Format, Parser, Probe, SourceDocument
from iplikci.storage import documents, events

from conftest import add

# Architecture §10: the readers that come from the MVP and those V1 adds.
SHIPPED = {
    "garanti.bonus_card",
    "garanti.paracard",
    "garanti.account_xls",
    "garanti.receipt",
    "garanti.brokerage",
    "isbank.maximum_card",
    "isbank.account_xls",
    "isbank.receipt",
    "isbank.passbook",
    "teb.bonus_card",
    "teb.card_payment_receipt",
    "teb.account_html",
    "qnb.card_pdf",
    "qnb.account_pdf",
    "qnb.edekont",
    "vakifbank.account_xlsx",
    "vakifbank.passbook",
    # Phase 4: the readers of bank notices (`<bank>.notice.*`).
    "garanti.notice.transfer",
    "isbank.notice.collection",
    "qnb.notice.transfer",
    "vakifbank.notice.transfer",
    # Phase 4: the readers of non-bank senders' documents (F14).
    "invoice.ubl_tr",
    # v0.9.14: TEB's digital passbook, which the user sends the Telegram bot.
    "teb.passbook",
    # v0.9.16: the receipts the banks' apps share, sent the same way.
    "teb.transfer_receipt",
    "vakifbank.receipt",
}


@dataclass
class Fake:
    """A reader that recognises every document whose text holds its word."""

    id: str
    word: str = "ORNEK"
    version: int = 1
    bank: str = "Örnek Bankası"
    name: str = "Örnek belge"
    document_type: DocumentKind = DocumentKind.RECEIPT
    formats: frozenset[Format] = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        return Detection(1.0, "örnek") if self.word in probe.text else None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return ParseResult(parser=self.id)


def test_the_shipped_readers_keep_the_contract_under_the_ids_of_the_architecture():
    readers = registry.BUILTIN
    assert {r.id for r in readers} == SHIPPED and len(readers) == len(SHIPPED)
    assert all(isinstance(r, Parser) for r in readers)
    assert all(r.version >= 1 and r.formats and r.name and r.bank for r in readers)


def test_every_reader_is_named_for_people():
    assert registry.label("garanti.receipt") == "Garanti BBVA dekontu"
    assert registry.label("eski.okuyucu") == "eski.okuyucu"  # a reader that is gone keeps its id


def test_two_readers_with_one_id_are_an_error():
    with pytest.raises(registry.RegistryError, match="kimliği aynı: ornek.belge"):
        registry.check((Fake("ornek.belge"), Fake("ornek.belge")))


def test_a_document_two_readers_recognise_is_unreadable(monkeypatch):
    monkeypatch.setattr(parsers, "readers", lambda: (Fake("a.belge"), Fake("b.belge"), Fake("c.belge", "BASKA")))
    with pytest.raises(parsers.Unreadable, match="birden çok okuyucu tanıdı: a.belge, b.belge"):
        parsers.choose(Probe("belge.pdf", Format.PDF, text="ORNEK DEKONT"))


def test_only_the_readers_of_a_format_look_at_its_documents(monkeypatch):
    sheet = Fake("tablo.okuyucu", formats=frozenset({Format.SHEET}))
    monkeypatch.setattr(parsers, "readers", lambda: (sheet, Fake("pdf.okuyucu")))
    assert parsers.choose(Probe("belge.pdf", Format.PDF, text="ORNEK")).id == "pdf.okuyucu"
    assert parsers.choose(Probe("belge.pdf", Format.HTML, text="ORNEK")) is None


def test_a_reader_unsure_of_a_document_does_not_read_it(monkeypatch):
    @dataclass
    class Unsure(Fake):
        def detect(self, probe: Probe) -> Detection | None:
            return Detection(0.2, "belki")

    monkeypatch.setattr(parsers, "readers", lambda: (Unsure("belki.okuyucu"),))
    assert parsers.choose(Probe("belge.pdf", Format.PDF, text="ORNEK")) is None


@dataclass
class _Entry:
    name: str
    value: str
    obj: object

    def load(self) -> object:
        return self.obj


def test_an_installed_package_adds_readers_by_object_or_class(monkeypatch):
    @dataclass
    class Plugin(Fake):
        id: str = "eklenti.belge"

    entries = [_Entry("nesne", "paket:OKUYUCU", Fake("paket.belge")), _Entry("sinif", "paket:Plugin", Plugin)]
    monkeypatch.setattr(registry, "entry_points", lambda group: entries if group == "iplikci.parsers" else [])
    assert [r.id for r in registry._installed()] == ["paket.belge", "eklenti.belge"]


def test_an_installed_reader_that_breaks_the_contract_is_refused(monkeypatch):
    entries = [_Entry("bozuk", "paket:bozuk", object())]
    monkeypatch.setattr(registry, "entry_points", lambda group: entries)
    with pytest.raises(registry.RegistryError, match="bozuk"):
        registry._installed()


# --- where every row is printed ------------------------------------------------------------------------------


def _rows(result: ParseResult) -> list:
    return [t for s in result.statements for t in s.transactions] + result.transactions


def test_every_row_of_the_demo_documents_says_where_it_is_printed():
    read = 0
    for path, data in demo.documents().items():
        try:
            result = parsers.parse_document(Document(path.rpartition("/")[2], "demo", data, "sha"))
        except parsers.Skipped:
            continue  # the company's list and the form that is no statement
        rows = _rows(result)
        read += len(rows)
        assert all(t.ref and (t.ref.box or t.ref.line or t.ref.row or t.ref.span) for t in rows), path
    assert read > 100


def test_a_pdf_row_is_its_page_and_the_box_of_its_line():
    fast = garanti.fast_body("ŞUBAT AİDAT", "ÖRNEK SİTE YÖNETİMİ")
    data = garanti.receipt("HESAPTAN FAST", "106/1234567", HOLDER, fast, "- 1.250,00 TL")
    transfer, fee = parsers.parse_document(Document("dekont.pdf", "test", data, "sha")).transactions
    assert transfer.ref.page == 1 and transfer.ref.box[1] == pytest.approx(563, abs=1)  # the SIRA NO … TUTAR line
    assert fee.ref.page == 1 and fee.ref.box[1] == pytest.approx(407, abs=1)  # KOMİSYON TOPLAMI


def test_a_table_row_is_its_row_number():
    rows = teb.running_rows([Move(date(2026, 1, 5), "ORNEK KAHVE", Decimal(-180))])
    result = parsers.parse_document(Document("liste.xls", "test", teb.account_export(rows), "sha"))
    (coffee,) = result.statements[0].transactions
    assert (coffee.ref.sheet, coffee.ref.row) == ("", 9)  # the HTML table's ninth row, under the header row


# --- a version per reader --------------------------------------------------------------------------------------


def _reread(ws) -> list[str]:
    names: list[str] = []
    with ws.db() as db:
        reading.read_pending(ws, db, progress=lambda i, n, name: names.append(name))
    return sorted(names)


def test_a_new_reader_version_reads_only_that_readers_documents_again(ws, monkeypatch):
    rows = teb.running_rows([Move(date(2026, 1, 5), "ORNEK KAHVE", Decimal(-180))])
    add(ws, "liste.xls", teb.account_export(rows))
    fast = garanti.fast_body("ŞUBAT AİDAT", "ÖRNEK SİTE YÖNETİMİ")
    add(ws, "dekont.pdf", garanti.receipt("HESAPTAN FAST", "106/1234567", HOLDER, fast, "- 1.250,00 TL"))
    assert _reread(ws) == []
    reader = registry.find("teb.account_html")
    monkeypatch.setattr(reader, "version", reader.version + 1)
    assert _reread(ws) == ["liste.xls"]
    assert _reread(ws) == []  # read once


def test_a_document_no_reader_took_is_shown_to_the_readers_again_when_they_change(ws, monkeypatch):
    add(ws, "form.pdf", text_pdf([(40, 40, "TALİMAT FORMU")]))
    fast = garanti.fast_body("ŞUBAT AİDAT", "ÖRNEK SİTE YÖNETİMİ")
    add(ws, "dekont.pdf", garanti.receipt("HESAPTAN FAST", "106/1234567", HOLDER, fast, "- 1.250,00 TL"))
    receipt = registry.find("garanti.receipt")
    monkeypatch.setattr(receipt, "version", receipt.version + 1)
    assert _reread(ws) == ["dekont.pdf", "form.pdf"]


def test_a_reader_that_fails_on_a_document_reads_it_again_in_its_next_version(ws, monkeypatch):
    broken = garanti.receipt("HESAPTAN FAST", "106/1234567", HOLDER, [], "TUTAR YOK")  # no amount
    [stored] = add(ws, "bozuk.pdf", broken).stored
    assert stored.status is DocumentStatus.UNREADABLE and stored.reason.startswith("ValueError: Garanti dekontunda")
    with ws.db() as db:
        assert documents.get(db, stored.sha256).parser == "garanti.receipt"
    other = registry.find("teb.account_html")
    monkeypatch.setattr(other, "version", other.version + 1)
    assert _reread(ws) == []  # another reader's version leaves it alone
    receipt = registry.find("garanti.receipt")
    monkeypatch.setattr(receipt, "version", receipt.version + 1)
    assert _reread(ws) == ["bozuk.pdf"]


# --- the format alarm ---------------------------------------------------------------------------------------


def _alarms(ws) -> list[tuple[str, dict]]:
    with ws.db() as db:
        return [(e.target, e.detail) for e in events.entries(db, reading.FORMAT_ALARM)]


def test_a_reader_that_recognises_a_document_and_fails_on_it_raises_a_format_alarm_once_per_version(ws, monkeypatch):
    broken = garanti.receipt("HESAPTAN FAST", "106/1234567", HOLDER, [], "TUTAR YOK")  # its amount line changed
    [stored] = add(ws, "bozuk.pdf", broken).stored
    [(target, detail)] = _alarms(ws)
    assert (target, detail["parser"], detail["version"]) == (
        stored.sha256,
        "garanti.receipt",
        f"{registry.SELECTION}.1",
    )
    assert detail["reason"].startswith("ValueError: Garanti dekontunda")
    with ws.db() as db:
        reading.read_pending(ws, db, every=True)
    assert len(_alarms(ws)) == 1  # the same alarm again is no news
    reader = registry.find("garanti.receipt")
    monkeypatch.setattr(reader, "version", reader.version + 1)
    _reread(ws)
    assert [d["version"] for _, d in _alarms(ws)] == [
        f"{registry.SELECTION}.{n}" for n in (1, 2)
    ]  # the new version fails too


def test_a_statement_that_does_not_verify_raises_a_format_alarm(ws):
    [stored] = add(ws, "ekstre.pdf", garanti.bonus_statement(total=Decimal("3900.00"))).stored
    assert _alarms(ws) == [
        (
            stored.sha256,
            {"parser": "garanti.bonus_card", "version": f"{registry.SELECTION}.2", "unverified": ["garanti-1234"]},
        )
    ]


def test_documents_that_say_nothing_of_a_format_raise_no_alarm(ws):
    set_business_names(["Örnek Teknoloji"])
    add(ws, "ekstre.pdf", garanti.bonus_statement())  # verifies
    add(ws, "form.pdf", text_pdf([(40, 40, "TALİMAT FORMU")]))  # no reader took it
    add(ws, "sirket.xls", teb.account_export(teb.running_rows(list(teb.ACCOUNT_MOVES)), holder="ÖRNEK TEKNOLOJİ A.Ş."))
    one = teb.running_rows([Move(date(2026, 1, 5), "ORNEK KAHVE", Decimal(-180))])
    add(ws, "tek.xls", teb.account_export(one, number="987654321"))  # one row: no balance to check
    assert _alarms(ws) == []
