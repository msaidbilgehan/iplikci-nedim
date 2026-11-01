"""Garanti BBVA Bonus credit card statements (PDF)."""

from ...domain.codes import DocumentKind
from ...domain.models import ParseResult
from ..contract import Detection, Format, Probe, SourceDocument
from ..text import squash
from ._card import BONUS_ID, read_statement


class BonusCard:
    id = BONUS_ID
    version = 1
    bank = "Garanti BBVA"
    name = "Garanti BBVA Bonus kart ekstresi"
    document_type = DocumentKind.CARD_STATEMENT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        # The Paracard statement prints "Bonus" too; it is the Paracard reader's.
        if "BONUS" in s and "DONEMBORCUNUZ" in s and "PARACARDHESAP" not in s:
            return Detection(1.0, 'Bonus ve "Dönem Borcunuz" başlıkları')
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read_statement(doc)


PARSER = BonusCard()
