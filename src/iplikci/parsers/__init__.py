"""Choose the reader of a document and let it read (ADR-0005).

Company documents are recognised first (by their file name, and by the header of a PDF's first page). Every reader
of the document's format then looks at the same Probe: the one reader that recognises the document reads it. Two
readers recognising it is an error, not a choice; none means the document is not one this program reads, and the
reason says what it is when that shows.
"""

from pdfminer.pdfdocument import PDFEncryptionError

from ..domain.models import ParseResult
from ..sources import Document, UnreadableArchive, from_zip
from .common import BUSINESS_REASON, Skipped, Unreadable, is_business, not_a_statement
from .contract import THRESHOLD, Format, Parser, Probe, SourceDocument
from .pdf import ocr_available, page_text
from .registry import readers
from .teb.account_html import holder_info

__all__ = ["ENCRYPTED_REASON", "NO_OCR_REASON", "PARSER_VERSION", "Skipped", "Unreadable", "parse_document"]

# Bump when what the readers make of a document changes: every stored document is read again. 13: English codes
# and ISO currencies. 14: exact decimals, halves rounded up. 15: plugin readers, named by their ids.
PARSER_VERSION = "15"

ENCRYPTED_REASON = (
    "şifreli PDF — Önizleme'de şifreyle açıp Dosya › PDF Olarak Dışa Aktar ile şifresiz kaydedin ve yeniden ekleyin"
)
NO_OCR_REASON = (
    "sayfa görüntüsü olarak gelmiş PDF: metin tanıma (OCR) yalnızca macOS'ta var — belgeyi bir Mac'te "
    "ekleyin ya da bankadan metinli PDF indirin"
)


def _encrypted(exc: Exception) -> bool:
    # pdfplumber wraps pdfminer's password error in its own exception.
    return any(isinstance(e, PDFEncryptionError) for e in (exc, exc.__context__, *exc.args))


def choose(probe: Probe) -> Parser | None:
    """The one reader that recognises the document; Unreadable when more than one does."""
    found = [
        reader
        for reader in readers()
        if probe.format in reader.formats
        and (seen := reader.detect(probe)) is not None
        and seen.confidence >= THRESHOLD
    ]
    if len(found) > 1:
        raise Unreadable(f"birden çok okuyucu tanıdı: {', '.join(r.id for r in found)}")
    return found[0] if found else None


def parse_document(doc: Document) -> ParseResult:
    if is_business(doc.name):
        raise Skipped(BUSINESS_REASON, business=True)
    if doc.ext == ".zip":  # only a zip the collector could not open is handed over as a document
        try:
            from_zip(doc.data, doc.name)
        except UnreadableArchive as exc:
            raise Unreadable(str(exc)) from exc
        raise Skipped("arşiv")
    source = SourceDocument(doc)
    try:
        return _read(source)
    finally:
        source.close()


def _read(source: SourceDocument) -> ParseResult:
    if source.kind in ("xls", "xlsx") or (source.kind == "html" and source.ext in (".xls", ".xlsx")):
        return _read_sheet(source)
    if source.ext in (".html", ".htm") or source.kind == "html":
        return _read_html(source)
    if source.ext != ".pdf":
        raise Skipped("desteklenmeyen dosya türü")
    return _read_pdf(source)


def _read_sheet(source: SourceDocument) -> ParseResult:
    rows = source.rows
    # Older TEB exports have no IBAN; their holder still marks company accounts.
    if source.kind == "html" and is_business(holder_info(rows).get("Hesap Sahibi", "")):
        raise Skipped(BUSINESS_REASON, business=True)
    reader = choose(Probe(source.name, Format.SHEET, rows=rows[:20], sheet=source.kind))
    if reader is None:
        raise Skipped("tanınmayan tablo")
    result = reader.parse(source)
    if is_business(result.holder):
        raise Skipped(BUSINESS_REASON, business=True)
    return result


def _read_html(source: SourceDocument) -> ParseResult:
    text = source.text
    reader = choose(Probe(source.name, Format.HTML, text=text))
    if reader is not None:
        return reader.parse(source)
    if is_business(text[:600]):  # e.g. TEB's yearly withholding-tax letter to the company
        raise Skipped(BUSINESS_REASON, business=True)
    raise Skipped(not_a_statement(text) if text.strip() else "tanınmayan HTML")


def _read_pdf(source: SourceDocument) -> ParseResult:
    try:
        pdf = source.pdf
    except Exception as exc:  # malformed or encrypted PDF
        # Some banks e-mail statements as password-protected PDFs: still a bank document, never "unused".
        if _encrypted(exc):
            raise Unreadable(ENCRYPTED_REASON) from exc
        raise Skipped(f"PDF açılamadı: {exc}") from exc
    if not pdf.pages:
        raise Skipped("boş PDF")
    first = page_text(pdf.pages[0])
    if is_business(first[:600]):
        raise Skipped(BUSINESS_REASON, business=True)
    reader = choose(Probe(source.name, Format.PDF, text=first))
    if reader is not None:
        return reader.parse(source)
    scanned = len(first.strip()) < 80 and any(p.images for p in pdf.pages)
    if scanned and ocr_available():
        source.scanned = True
        text = "\n".join(line.text for page in source.ocr_pages for line in page)
        reader = choose(Probe(source.name, Format.SCAN, text=text))
        if reader is not None:
            return reader.parse(source)
    elif scanned:
        # Without OCR nobody can tell whether it is a statement (TEB sends some as page images):
        # kept for a manual look rather than set aside as unused.
        raise Unreadable(NO_OCR_REASON)
    raise Skipped(not_a_statement(first))
