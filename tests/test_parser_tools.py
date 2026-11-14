"""`iplikci dev parser`: what the selection sees in a document, what its reader reads, and the fake documents'
check (ADR-0005)."""

from dataclasses import dataclass

import pytest

from iplikci import fakes, parsers
from iplikci.cli import main
from iplikci.domain.codes import DocumentKind
from iplikci.domain.models import ParseResult
from iplikci.fakes import garanti
from iplikci.fakes.files import text_pdf
from iplikci.parsers import registry, tools
from iplikci.parsers.contract import Detection, Document, Format, Probe, SourceDocument
from iplikci.settings.paths import HOME_ENV

SPECIMENS = fakes.specimens()


def doc(data: bytes, name: str = "belge.pdf") -> Document:
    return Document(name, "test", data, "sha")


@pytest.mark.parametrize("specimen", SPECIMENS, ids=[s.name for s in SPECIMENS])
def test_the_probe_chooses_the_reader_that_reads_the_document(specimen):
    lines = tools.probe(doc(specimen.data, specimen.name))
    assert lines[-1].startswith(f"Okuyacak: {specimen.reader} — ")
    assert any(line.startswith(f"  ✓ {specimen.reader} (güven 1,00): ") for line in lines)


@dataclass
class Fake:
    id: str
    version: int = 1
    bank: str = "Örnek Bankası"
    name: str = "Örnek belge"
    document_type: DocumentKind = DocumentKind.RECEIPT
    formats: frozenset[Format] = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        return Detection(1.0, "her şeyi tanır")

    def parse(self, doc: SourceDocument) -> ParseResult:
        return ParseResult(parser=self.id)


def test_the_probe_says_when_two_readers_recognise_a_document_or_none_does(monkeypatch):
    form = doc(text_pdf([(40, 40, "TALİMAT FORMU")]))
    assert tools.probe(form)[-1] == "Okuyacak: hiçbiri"
    monkeypatch.setattr(parsers, "readers", lambda: (Fake("a.belge"), Fake("b.belge")))
    assert tools.probe(form)[-3:] == [
        "  ✓ a.belge (güven 1,00): her şeyi tanır",
        "  ✓ b.belge (güven 1,00): her şeyi tanır",
        "Okuyamaz: birden çok okuyucu tanıdı: a.belge, b.belge",
    ]


def test_debug_shows_every_row_with_its_place():
    lines = tools.debug(doc(garanti.bonus_statement(), "ekstre.pdf"))
    assert lines[0] == f"ekstre.pdf → garanti.bonus_card (sürüm {registry.SELECTION}.4)"
    assert any(line.endswith("— doğrulandı (11 satır)") for line in lines)
    assert (
        "Ödeme: son ödeme 2026-10-15, asgari tutar 1.553,96, kart limiti 45.000,00, sonraki kesim 2026-11-04" in lines
    )
    assert any("Harcama: TEKNOSA ORNEK AVM (taksit 8/12)  [s.1 kutu " in line for line in lines)


def test_debug_shows_the_traceback_of_a_readers_error():
    lines = tools.debug(doc(garanti.receipt("HESAPTAN FAST", "106/1234567", "X", [], "TUTAR YOK")))
    assert lines[0].startswith("belge.pdf: okunamadı (garanti.receipt tanıdı): ValueError: Garanti dekontunda")
    assert lines[1] == "Traceback (most recent call last):" and any("garanti/receipt.py" in line for line in lines)


def test_the_test_command_fails_when_a_fake_document_reads_wrong(monkeypatch, capsys):
    assert main(["dev", "parser", "test"]) == 0
    assert capsys.readouterr().out.endswith(f"Sahte belgeler: {len(SPECIMENS)} · sorunlu: 0\n")
    monkeypatch.setattr(
        fakes, "check", lambda specimen: ["2 satır, beklenen 3"] if specimen.reader == "qnb.card_pdf" else []
    )
    assert main(["dev", "parser", "test", "qnb.card_pdf"]) == 1
    assert "  ✗ qnb-kart-ekstre.pdf: 2 satır, beklenen 3" in capsys.readouterr().out
    assert main(["dev", "parser", "test", "yok.okuyucu"]) == 1


def test_probe_and_debug_read_a_file_with_the_company_names_of_the_settings(tmp_path, monkeypatch, capsys):
    home = tmp_path / "veri"
    home.mkdir()
    (home / "settings.toml").write_text('[identity]\nbusiness_names = ["Örnek Tekstil A.Ş."]\n', encoding="utf-8")
    monkeypatch.setenv(HOME_ENV, str(home))
    path = tmp_path / "Ornek Tekstil ekstre.pdf"
    path.write_bytes(garanti.bonus_statement())
    assert main(["dev", "parser", "probe", str(path)]) == 0
    assert "Şirket belgesi (dosya adındaki işaret)" in capsys.readouterr().out
    assert main(["dev", "parser", "debug", str(path)]) == 0
    assert capsys.readouterr().out == "Ornek Tekstil ekstre.pdf: şirket belgesi — kapsam dışı\n"
    with pytest.raises(SystemExit):
        main(["dev", "parser", "debug", str(tmp_path / "yok.pdf")])


def test_the_tools_never_make_a_data_folder(tmp_path, monkeypatch):
    monkeypatch.setenv(HOME_ENV, str(tmp_path / "olmayan"))
    path = tmp_path / "ekstre.pdf"
    path.write_bytes(garanti.bonus_statement())
    assert main(["dev", "parser", "probe", str(path)]) == 0
    assert not (tmp_path / "olmayan").exists()
