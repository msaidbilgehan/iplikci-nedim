"""The file formats the banks send, written from scratch: PDFs with a text layer, XLS and XLSX workbooks."""

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


def right(x1: float, top: float, text: str) -> Run:
    """A right-aligned run ending at x1, like the amount columns of a statement."""
    return x1 - len(text) * CHAR, top, text
