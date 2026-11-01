"""The reader plugin contract (ADR-0005): the registry, and choosing the one reader that recognises a document."""

from dataclasses import dataclass

import pytest

from iplikci import parsers
from iplikci.domain.codes import DocumentKind
from iplikci.domain.models import ParseResult
from iplikci.parsers import registry
from iplikci.parsers.contract import Detection, Format, Parser, Probe, SourceDocument

# Architecture §10: the readers that come from the MVP.
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
