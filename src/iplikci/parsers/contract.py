"""The reader plugin contract (ADR-0005): what a reader declares, how it recognises a document and what it reads.

Every reader is an object with an id, a version, the bank and the kind of document it reads, the formats it
accepts, a cheap detect() and a parse(). The selector shows each reader the same Probe of a document and lets only
a reader that recognised it read the SourceDocument.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from functools import cached_property
from typing import Any, Protocol, runtime_checkable

from ..domain.codes import DocumentKind
from ..domain.models import ParseResult, SourceRef
from ..sources import Document
from .pdf import Line, ocr_page_lines, open_pdf
from .sheet import decode_html, html_rows, html_text, read_xls, read_xlsx, sniff

# A detection at least this sure lets a reader read the document; two such readers are an error.
THRESHOLD = 0.5


class Format(StrEnum):
    PDF = "pdf"  # a PDF with a text layer
    SCAN = "scan"  # a PDF of page images, read with OCR where the system has it (macOS)
    SHEET = "sheet"  # XLS, XLSX, and HTML tables saved as .xls
    HTML = "html"
    EMAIL = "email"  # a bank e-mail's body (Phase 3)


@dataclass(frozen=True)
class Detection:
    confidence: float  # 0–1: how sure the reader is that the document is its own
    reason: str  # what it recognised, in Turkish: `iplikci dev parser probe` shows it


@dataclass(frozen=True)
class Probe:
    """What the selector learnt about a document cheaply, shown to every reader of its format."""

    name: str  # the file name
    format: Format
    text: str = ""  # PDF: the first page's text (a scan: the text OCR found on every page); HTML: its text
    rows: list[list[Any]] = field(default_factory=list[list[Any]])  # SHEET: the first rows
    sheet: str = ""  # SHEET: "xls", "xlsx" or "html"


class SourceDocument:
    """A document a reader reads: its bytes and, opened once and only when asked for, what they hold."""

    def __init__(self, doc: Document) -> None:
        self.name = doc.name
        self.origin = doc.origin
        self.data = doc.data
        self.sha256 = doc.sha256
        self.ext = doc.ext
        self.scanned = False  # the selector read its pages with OCR

    @cached_property
    def kind(self) -> str:
        """What the bytes are, whatever the name says: "xls", "xlsx", "html" or "" (a PDF, a zip)."""
        return sniff(self.data)

    @cached_property
    def pdf(self) -> Any:  # pdfplumber.PDF; pdfplumber ships no types
        return open_pdf(self.data)

    @cached_property
    def _sheet(self) -> tuple[str, list[list[Any]]]:
        if self.kind == "xls":
            return read_xls(self.data)
        if self.kind == "xlsx":
            return read_xlsx(self.data)
        return "", [list(r) for r in html_rows(self.data)]

    @property
    def rows(self) -> list[list[Any]]:
        """A spreadsheet's rows: the first sheet of an XLS or XLSX file, or the innermost rows of an HTML table."""
        return self._sheet[1]

    @property
    def sheet_name(self) -> str:
        """The name of the sheet rows come from; "" for an HTML table."""
        return self._sheet[0]

    def row_ref(self, index: int) -> SourceRef:
        """Where rows[index] is: its sheet and its row number, counted from 1."""
        return SourceRef(sheet=self.sheet_name, row=index + 1)

    @cached_property
    def html(self) -> str:
        return decode_html(self.data)

    @cached_property
    def text(self) -> str:
        """The visible text of an HTML document, its whitespace collapsed."""
        return html_text(self.data)

    @cached_property
    def ocr_pages(self) -> list[list[Line]]:
        return [ocr_page_lines(self.data, i) for i in range(len(self.pdf.pages))]

    def close(self) -> None:
        if "pdf" in self.__dict__:
            self.pdf.close()


@runtime_checkable
class Parser(Protocol):
    id: str  # "garanti.bonus_card"
    version: int  # raised whenever what it makes of a document changes
    bank: str  # "Garanti BBVA"; the institution for a sender that is no bank
    name: str  # what it reads, in Turkish: "Garanti BBVA Bonus kart ekstresi"
    document_type: DocumentKind
    formats: frozenset[Format]

    def detect(self, probe: Probe) -> Detection | None: ...

    def parse(self, doc: SourceDocument) -> ParseResult: ...
