"""Garanti BBVA Paracard debit card statements ("Paracard Hesap Cetveli", PDF)."""

from ...domain.codes import DocumentKind
from ...domain.models import ParseResult
from ..contract import Detection, Format, Probe, SourceDocument
from ..text import squash
from ._card import PARACARD_ID, read_statement


class Paracard:
    id = PARACARD_ID
    version = 1
    bank = "Garanti BBVA"
    name = "Garanti BBVA Paracard hesap cetveli"
    document_type = DocumentKind.CARD_STATEMENT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        if "PARACARDHESAP" in squash(probe.text):
            return Detection(1.0, '"Paracard Hesap" başlığı')
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read_statement(doc)


PARSER = Paracard()
