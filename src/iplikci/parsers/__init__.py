"""Choose the reader of a document and let it read (ADR-0005).

Company documents are recognised first (by their file name, a message's subject, and the header of a PDF's first
page). Every reader of the document's format then looks at the same Probe: the one reader that recognises the document
reads it. Two readers recognising it is an error, not a choice; none means the document is not one this program reads,
and the reason says what it is when that shows (a message no reader takes is a company's when its greeting names one).
"""

from pdfminer.pdfdocument import PDFEncryptionError

from ..domain.models import ParseResult
from ..ingest.archives import UnreadableArchive, from_zip
from .common import (
    BUSINESS_REASON,
    Skipped,
    Unreadable,
    caused_by,
    is_business,
    not_a_statement,
    pays_as_employer,
)
from .contract import THRESHOLD, Document, Format, Parser, Probe, SourceDocument
from .mail import Mail
from .messages import message_reason
from .pdf import ocr_available, page_text
from .registry import readers
from .teb.account_html import holder_info

__all__ = ["ENCRYPTED_REASON", "NO_OCR_REASON", "Skipped", "Unreadable", "parse_document"]

ENCRYPTED_REASON = (
    "şifreli PDF — Önizleme'de şifreyle açıp Dosya › PDF Olarak Dışa Aktar ile şifresiz kaydedin ve yeniden ekleyin"
)
NO_OCR_REASON = (
    "sayfa görüntüsü olarak gelmiş PDF: metin tanıma (OCR) yalnızca macOS'ta var — belgeyi bir Mac'te "
    "ekleyin ya da bankadan metinli PDF indirin"
)


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


def _parse(reader: Parser, source: SourceDocument) -> ParseResult:
    """reader's reading of source. What goes wrong on the way names the reader, so that only its next version
    reads the document again."""
    try:
        return reader.parse(source)
    except (Skipped, Unreadable) as exc:
        exc.parser = reader.id
        raise
    except Exception as exc:  # a reader that fails on one document leaves it unreadable, never stops the others
        raise Unreadable(f"{type(exc).__name__}: {exc}", parser=reader.id) from exc


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
    if source.ext == ".eml":  # kept whole (ADR-0015); its attachments are documents of their own
        return _read_mail(source)
    if source.ext == ".xml":
        return _read_xml(source)
    if source.kind in ("xls", "xlsx") or (source.kind == "html" and source.ext in (".xls", ".xlsx")):
        return _read_sheet(source)
    if source.ext in (".html", ".htm") or source.kind == "html":
        return _read_html(source)
    if source.ext != ".pdf":
        raise Skipped("desteklenmeyen dosya türü")
    return _read_pdf(source)


def mail_probe(source: SourceDocument) -> Probe:
    """What the readers of message bodies are shown of a kept e-mail."""
    mail = source.mail
    return Probe(source.name, Format.EMAIL, text=mail.text, sender=mail.sender, subject=mail.subject)


def _read_mail(source: SourceDocument) -> ParseResult:
    # The intake looks at the subject; a company name set later finds the messages kept before it.
    if is_business(source.mail.subject):
        raise Skipped(BUSINESS_REASON, business=True)
    reader = choose(mail_probe(source))
    if reader is not None:  # a reader looks for the holder where its bank prints it
        return _parse(reader, source)
    raise Skipped(*without_reader(source.mail))


def without_reader(mail: Mail) -> tuple[str, bool]:
    """Why a message no reader takes is kept unprocessed, and whether it is a company's. Of its body the greeting is
    looked at for a company, which names whom the message is for ("Merhaba ÖRNEK TEKNOLOJİ A.Ş.,"), not the text
    further down, where a personal account's message may name the company as the other side of a transfer; and
    premiums paid as an employer are a payroll's."""
    if is_business(mail.addressee) or pays_as_employer(mail.text):
        return BUSINESS_REASON, True
    return message_reason(mail), False


XML_PROBE = 4000  # characters of an XML document its probe shows: the root element and its namespaces come first
XML_REASON = "XML belgesi; bu tür belgeyi okuyan bir okuyucu yok"


def xml_probe(source: SourceDocument) -> Probe:
    """What the readers of XML documents are shown: the start of the document as written."""
    return Probe(source.name, Format.XML, text=source.xml[:XML_PROBE])


def _read_xml(source: SourceDocument) -> ParseResult:
    # The readers look for company buyers and sellers where the document names them; a file name was looked at already.
    reader = choose(xml_probe(source))
    if reader is None:
        raise Skipped(XML_REASON)
    return _parse(reader, source)


def _read_sheet(source: SourceDocument) -> ParseResult:
    rows = source.rows
    # Older TEB exports have no IBAN; their holder still marks company accounts.
    if source.kind == "html" and is_business(holder_info(rows).get("Hesap Sahibi", "")):
        raise Skipped(BUSINESS_REASON, business=True)
    reader = choose(Probe(source.name, Format.SHEET, rows=rows[:20], sheet=source.kind))
    if reader is None:
        raise Skipped("tanınmayan tablo")
    result = _parse(reader, source)
    if is_business(result.holder):
        raise Skipped(BUSINESS_REASON, business=True)
    return result


def _read_html(source: SourceDocument) -> ParseResult:
    text = source.text
    reader = choose(Probe(source.name, Format.HTML, text=text))
    if reader is not None:
        return _parse(reader, source)
    if is_business(text[:600]):  # e.g. TEB's yearly withholding-tax letter to the company
        raise Skipped(BUSINESS_REASON, business=True)
    raise Skipped(not_a_statement(text) if text.strip() else "tanınmayan HTML")


def _read_pdf(source: SourceDocument) -> ParseResult:
    try:
        pdf = source.pdf
    except Exception as exc:  # malformed or encrypted PDF
        # Some banks e-mail statements as password-protected PDFs: still a bank document, never "unused".
        if caused_by(exc, PDFEncryptionError):
            raise Unreadable(ENCRYPTED_REASON) from exc
        raise Skipped(f"PDF açılamadı: {exc}") from exc
    if not pdf.pages:
        raise Skipped("boş PDF")
    first = page_text(pdf.pages[0])
    if is_business(first[:600]):
        raise Skipped(BUSINESS_REASON, business=True)
    reader = choose(Probe(source.name, Format.PDF, text=first))
    if reader is not None:
        return _parse(reader, source)
    scanned = len(first.strip()) < 80 and any(p.images for p in pdf.pages)
    if scanned and ocr_available():
        source.scanned = True
        text = "\n".join(line.text for page in source.ocr_pages for line in page)
        reader = choose(Probe(source.name, Format.SCAN, text=text))
        if reader is not None:
            return _parse(reader, source)
    elif scanned:
        # Without OCR nobody can tell whether it is a statement (TEB sends some as page images):
        # kept for a manual look rather than set aside as unused.
        raise Unreadable(NO_OCR_REASON)
    raise Skipped(not_a_statement(first))
