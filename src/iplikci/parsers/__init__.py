"""Pick the right parser for a document and run it."""

from pdfminer.pdfdocument import PDFEncryptionError

from ..domain.models import ParseResult
from ..sources import Document, UnreadableArchive, from_zip
from . import (
    garanti,
    garanti_dekont,
    garanti_yatirim,
    hesaplar,
    isbank,
    isbank_cuzdan,
    isbank_dekont,
    qnb,
    qnb_pdf,
    teb,
    vakifbank_cuzdan,
)
from .common import BUSINESS_REASON, Skipped, Unreadable, is_business, not_a_statement
from .pdf import ocr_available, ocr_page_lines, open_pdf, page_text
from .sheet import sniff

__all__ = ["ENCRYPTED_REASON", "NO_OCR_REASON", "PARSER_VERSION", "Skipped", "Unreadable", "parse_document"]

PDF_PARSERS = (isbank, garanti, teb, garanti_dekont, garanti_yatirim, isbank_dekont, isbank_cuzdan, vakifbank_cuzdan)

# Bump when what the readers make of a document changes: every stored document is read again. 13: English codes
# and ISO currencies. 14: exact decimals, halves rounded up.
PARSER_VERSION = "14"

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


def parse_document(doc: Document) -> ParseResult:
    if is_business(doc.name):
        raise Skipped(BUSINESS_REASON, business=True)
    if doc.ext == ".zip":  # only a zip the collector could not open is handed over as a document
        try:
            from_zip(doc.data, doc.name)
        except UnreadableArchive as exc:
            raise Unreadable(str(exc)) from exc
        raise Skipped("arşiv")
    kind = sniff(doc.data)
    if kind in ("xls", "xlsx") or (kind == "html" and doc.ext in (".xls", ".xlsx")):
        result = hesaplar.parse(doc)
        if is_business(result.holder):
            raise Skipped(BUSINESS_REASON, business=True)
        return result
    if doc.ext in (".html", ".htm") or kind == "html":
        text = qnb.html_text(doc.data)
        if qnb.detect_text(text):
            return qnb.parse_text(doc, text)
        if is_business(text[:600]):  # e.g. TEB's yearly withholding-tax letter to the company
            raise Skipped(BUSINESS_REASON, business=True)
        raise Skipped(not_a_statement(text) if text.strip() else "tanınmayan HTML")
    if doc.ext != ".pdf":
        raise Skipped("desteklenmeyen dosya türü")
    try:
        pdf = open_pdf(doc.data)
    except Exception as exc:  # malformed or encrypted PDF
        # Some banks e-mail statements as password-protected PDFs: still a bank document, never "unused".
        if _encrypted(exc):
            raise Unreadable(ENCRYPTED_REASON) from exc
        raise Skipped(f"PDF açılamadı: {exc}") from exc
    with pdf:
        if not pdf.pages:
            raise Skipped("boş PDF")
        first = page_text(pdf.pages[0])
        if is_business(first[:600]):
            raise Skipped(BUSINESS_REASON, business=True)
        for parser in PDF_PARSERS:
            if parser.detect(first):
                return parser.parse(doc, pdf)
        if qnb_pdf.detect_card(first):
            return qnb_pdf.parse_card(doc, pdf)
        if qnb_pdf.detect_account(first):
            return qnb_pdf.parse_account(doc, pdf)
        if qnb.detect_text(first):
            return qnb.parse_text(doc, " ".join(page_text(p) for p in pdf.pages))
        scanned = len(first.strip()) < 80 and any(p.images for p in pdf.pages)
        page_count = len(pdf.pages)
    if scanned and ocr_available():
        pages = [ocr_page_lines(doc.data, i) for i in range(page_count)]
        text = "\n".join(line.text for page in pages for line in page)
        if teb.detect_ocr(text):
            return teb.parse_ocr(doc, pages)
    elif scanned:
        # Without OCR nobody can tell whether it is a statement (TEB sends some as page images):
        # kept for a manual look rather than set aside as unused.
        raise Unreadable(NO_OCR_REASON)
    raise Skipped(not_a_statement(first))
