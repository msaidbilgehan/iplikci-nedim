"""The file formats the banks send, written from scratch: PDFs with a text layer, XLS and XLSX workbooks, and the
e-mails themselves."""

import hashlib
import io
import re
import struct
import zipfile
from collections.abc import Sequence
from datetime import datetime
from email.message import EmailMessage
from email.utils import format_datetime

# --- PDF ------------------------------------------------------------------------------------------------------

_UNICODE_MAP = (
    b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
    b"/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
    b"/CMapName /Adobe-Identity-UCS def /CMapType 2 def\n"
    b"1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
    b"1 beginbfrange <0020> <02FF> <0020> endbfrange\n"
    b"endcmap CMapName currentdict /CMap defineresource pop end end"
)
CHAR = 4.5  # width of every character at the default size: half an em of 9 points

type Run = tuple[float, float, str]  # x, top and text, in points from the page's top left


def text_pdf(*pages: list[Run], size: float = 9.0) -> bytes:
    """A PDF whose pages hold the given text runs, (x, top, text) in points from the top left as
    pdfplumber reports them. Its font maps each character to itself (Turkish letters too) and
    gives every one the same width, so a run's words land where a bank's layout puts them."""
    height = 842
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]  # the page tree follows once the pages exist

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    def stream(data: bytes) -> bytes:
        return b"<< /Length %d >>\nstream\n%s\nendstream" % (len(data), data)

    descriptor = add(
        b"<< /Type /FontDescriptor /FontName /Deneme /Flags 32 /FontBBox [0 -200 500 800] "
        b"/ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 /StemV 80 >>"
    )
    glyphs = add(
        b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Deneme /CIDSystemInfo << /Registry (Adobe) "
        b"/Ordering (Identity) /Supplement 0 >> /FontDescriptor %d 0 R /DW 500 /CIDToGIDMap /Identity >>" % descriptor
    )
    font = add(
        b"<< /Type /Font /Subtype /Type0 /BaseFont /Deneme /Encoding /Identity-H /DescendantFonts [%d 0 R] "
        b"/ToUnicode %d 0 R >>" % (glyphs, add(stream(_UNICODE_MAP)))
    )
    kids: list[int] = []
    for runs in pages:
        ops = b"".join(
            b"BT /F1 %.1f Tf 1 0 0 1 %.2f %.2f Tm <%s> Tj ET\n"
            % (size, x, height - top - 0.8 * size, text.encode("utf-16-be").hex().encode())
            for x, top, text in runs
        )
        content = add(stream(ops))
        kids.append(
            add(
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 %d] /Resources << /Font << /F1 %d 0 R >> >> "
                b"/Contents %d 0 R >>" % (height, font, content)
            )
        )
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % k for k in kids), len(kids))
    return pdf_file(objects)


def pdf_file(objects: list[bytes]) -> bytes:
    """A PDF of the given objects, numbered from 1 with the catalog first, and its cross-reference table."""
    out, offsets = b"%PDF-1.4\n", list[int]()
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)


def scan_pdf() -> bytes:
    """A PDF whose one page holds nothing but a picture, like a statement delivered as page images."""
    content = b"q 100 0 0 100 50 50 cm /Im1 Do Q"
    return pdf_file(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /XObject << /Im1 4 0 R >> >> "
                b"/Contents 5 0 R >>"
            ),
            (
                b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray /BitsPerComponent 8 "
                b"/Length 1 >>\nstream\n\x80\nendstream"
            ),
            b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        ]
    )


def right(x1: float, top: float, text: str) -> Run:
    """A right-aligned run ending at x1, like the amount columns of a statement."""
    return x1 - len(text) * CHAR, top, text


# --- XLS: a BIFF8 workbook in an OLE2 compound file ------------------------------------------------------------

type Cell = str | float | None


def xls_file(sheet: str, rows: Sequence[Sequence[Cell]]) -> bytes:
    """An Excel 97–2003 workbook of one sheet: text cells as text, numbers as numbers, None left empty."""
    return _compound(_workbook(sheet, rows))


def _record(kind: int, data: bytes) -> bytes:
    return struct.pack("<HH", kind, len(data)) + data


def _text(value: str, length: str) -> bytes:
    """A BIFF8 string in UTF-16, its length in characters as one byte ("B") or two ("H")."""
    return struct.pack(f"<{length}B", len(value), 1) + value.encode("utf-16-le")


def _workbook(sheet: str, rows: Sequence[Sequence[Cell]]) -> bytes:
    bof = struct.pack("<HHHHII", 0x0600, 0x0005, 0x0DBB, 0x07CC, 0, 0x06)  # BIFF8, the workbook's globals
    font = _record(0x0031, struct.pack("<HHHHHBBBB", 200, 0, 0x7FFF, 400, 0, 0, 0, 0, 0) + _text("Arial", "B"))
    # Fifteen style formats and the cell format every cell uses (number 15): General, so numbers stay numbers.
    formats = b"".join(
        _record(0x00E0, struct.pack("<HHHBBBBIIH", 0, 0, 0xFFF5 if i < 15 else 0x0001, 0x20, 0, 0, 0, 0, 0, 0x20C0))
        for i in range(16)
    )
    head = _record(0x0809, bof) + _record(0x0042, struct.pack("<H", 1200)) + font * 5 + formats
    tail = _record(0x000A, b"")

    def sheet_entry(offset: int) -> bytes:  # where the sheet's records start in the stream, and its name
        return _record(0x0085, struct.pack("<IBB", offset, 0, 0) + _text(sheet, "B"))

    globals_ = head + sheet_entry(len(head) + len(sheet_entry(0)) + len(tail)) + tail
    cells = b""
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            if isinstance(value, str):
                cells += _record(0x0204, struct.pack("<HHH", r, c, 15) + _text(value, "H"))
            elif value is not None:
                cells += _record(0x0203, struct.pack("<HHHd", r, c, 15, value))
    width = max((len(row) for row in rows), default=0)
    body = (
        _record(0x0809, struct.pack("<HHHHII", 0x0600, 0x0010, 0x0DBB, 0x07CC, 0, 0x06))  # BIFF8, a worksheet
        + _record(0x0200, struct.pack("<IIHHH", 0, len(rows), 0, width, 0))
        + cells
        + _record(0x000A, b"")
    )
    return globals_ + body


_FREE, _END, _FAT, _NONE = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFF


def _compound(stream: bytes) -> bytes:
    """stream as the "Workbook" stream of a compound file with 512-byte sectors: the allocation table first, the
    stream next, the directory last. A stream under 4096 bytes would belong in the mini stream, so it is padded."""
    size = max(len(stream), 4096)
    data = stream.ljust(-(-size // 512) * 512, b"\0")
    sectors = len(data) // 512
    tables = 1
    while tables * 128 < tables + sectors + 1:
        tables += 1
    chain = [tables + i + 1 for i in range(sectors - 1)] + [_END]
    fat = [_FAT] * tables + chain + [_END]  # the directory is one sector
    fat += [_FREE] * (tables * 128 - len(fat))
    header = (
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        + bytes(16)
        + struct.pack("<HHHHH", 0x003E, 0x0003, 0xFFFE, 9, 6)
        + bytes(6)
        + struct.pack("<9I", 0, tables, tables + sectors, 0, 4096, _END, 0, _END, 0)
        + struct.pack("<109I", *range(tables), *[_FREE] * (109 - tables))
    )
    directory = (
        _entry("Root Entry", 5, 1, _END, 0)
        + _entry("Workbook", 2, _NONE, tables, size)
        + _entry("", 0, _NONE, 0, 0) * 2
    )
    return header + struct.pack(f"<{len(fat)}I", *fat) + data + directory


def _entry(name: str, kind: int, child: int, start: int, size: int) -> bytes:
    named = (name + "\0").encode("utf-16-le") if name else b""
    return (
        named.ljust(64, b"\0")
        + struct.pack("<HBB", len(named), kind, 1 if kind else 0)
        + struct.pack("<III", _NONE, _NONE, child)
        + bytes(16 + 4 + 16)  # class id, state, creation and modification times
        + struct.pack("<IQ", start, size)
    )


# --- XLSX -------------------------------------------------------------------------------------------------------


def xlsx_file(sheet: str, rows: Sequence[Sequence[str | float | datetime | None]]) -> bytes:
    """An Excel workbook of one sheet. openpyxl dates the workbook and its zip entries with the time of saving; they
    are dated 2026-01-01 instead, so that the same rows always make the same bytes."""
    import openpyxl

    book = openpyxl.Workbook()
    page = book.active
    assert page is not None
    page.title = sheet
    for row in rows:
        page.append(list(row))
    book.properties.created = datetime(2026, 1, 1)
    written = io.BytesIO()
    book.save(written)
    out = io.BytesIO()
    with zipfile.ZipFile(written) as source, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info)
            if info.filename == "docProps/core.xml":
                data = re.sub(rb"(<dcterms:modified[^>]*>)[^<]*", rb"\g<1>2026-01-01T00:00:00Z", data)
            target.writestr(zipfile.ZipInfo(info.filename, (2026, 1, 1, 0, 0, 0)), data, zipfile.ZIP_DEFLATED)
    return out.getvalue()


# --- e-mail -----------------------------------------------------------------------------------------------------

RECIPIENT = "ornek.kullanici@example.com"


def html_mail(sender: str, subject: str, html: str, sent: datetime) -> bytes:
    """An e-mail as a bank sends it and Gmail keeps it: Gmail's Authentication-Results on top (DMARC passes), an HTML
    body in UTF-8 and base64. The message id comes from the contents, so that the same message makes the same bytes."""
    domain = sender.rpartition("@")[2]
    msg = EmailMessage()
    msg["Authentication-Results"] = (
        f"mx.google.com; dkim=pass header.i=@{domain}; spf=pass smtp.mailfrom={domain}; "
        f"dmarc=pass (p=REJECT sp=REJECT dis=NONE) header.from={domain}"
    )
    msg["From"] = f"Banka <{sender}>"
    msg["To"] = RECIPIENT
    msg["Subject"] = subject
    msg["Date"] = format_datetime(sent)
    msg["Message-ID"] = f"<{hashlib.sha256((subject + html).encode()).hexdigest()[:20]}@{domain}>"
    msg.set_content(html, subtype="html", charset="utf-8", cte="base64")
    return msg.as_bytes()
