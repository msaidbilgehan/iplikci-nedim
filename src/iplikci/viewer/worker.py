"""The viewing process: one request in on stdin (a line of JSON, then the document's bytes), one line of JSON out.
Nothing crosses as pickle, and whatever a library prints goes to stderr, never among the replies.

A PDF's pages are measured and drawn with PDFium (pypdfium2), the same pages' text comes from pdfplumber as the
readers read it, a spreadsheet's cells and an e-mail's body come from the readers' own helpers: a row's place in its
document (SourceRef) points into exactly what is shown here.
"""

import base64
import io
import json
import logging
import os
import signal
import sys
from collections.abc import Callable
from typing import IO, Any

from ..parsers import mail as mails
from ..parsers import pdf, sheet
from ..parsers.worker import limit_memory

TIME_LIMIT = 30  # seconds a request may take
MEMORY_LIMIT = 1 << 30  # bytes of address space (only Linux enforces it; see parsers/worker.py)
MAX_PAGES = 500  # pages measured; a statement has a handful
MIN_WIDTH, MAX_WIDTH = 200, 2400  # pixels a page is drawn at
MAX_ROWS, MAX_COLUMNS, MAX_CELL = 2000, 40, 300  # what a spreadsheet shows
MAX_TEXT = 1 << 20  # characters of text shown
MAX_HTML = 2 << 20  # bytes of an e-mail's HTML shown

Reply = dict[str, Any]


class Refused(Exception):
    """The document cannot be shown this way; the message says why, in Turkish."""


def _pdf(data: bytes) -> Any:  # pypdfium2.PdfDocument; imported here, so the app side never loads PDFium
    import pypdfium2  # pyright: ignore[reportMissingTypeStubs] - it ships no types; only this process loads it

    try:
        return pypdfium2.PdfDocument(data)
    except pypdfium2.PdfiumError as exc:
        raise Refused("PDF açılamadı (bozuk ya da şifreli olabilir)") from exc


def pages(data: bytes, _args: Reply) -> Reply:
    """Every page's size in points, as the rows' boxes measure it."""
    document = _pdf(data)
    try:
        return {"pages": [list(document[i].get_size()) for i in range(min(len(document), MAX_PAGES))]}
    finally:
        document.close()


def render(data: bytes, args: Reply) -> Reply:
    """A page drawn as a PNG image width pixels wide."""
    number, width = int(args["page"]), max(MIN_WIDTH, min(int(args["width"]), MAX_WIDTH))
    document = _pdf(data)
    try:
        if not 1 <= number <= min(len(document), MAX_PAGES):
            raise Refused(f"belgede {number}. sayfa yok")
        page = document[number - 1]
        points, _ = page.get_size()
        image = page.render(scale=width / points).to_pil()
        out = io.BytesIO()
        image.save(out, format="PNG", optimize=True)
        return {"png": base64.b64encode(out.getvalue()).decode("ascii"), "width": image.width, "height": image.height}
    finally:
        document.close()


def lines(data: bytes, args: Reply) -> Reply:
    """A page's text line by line, as the readers that read text count its lines (SourceRef.line)."""
    number = int(args["page"])
    with pdf.open_pdf(data) as document:
        if not 1 <= number <= min(len(document.pages), MAX_PAGES):
            raise Refused(f"belgede {number}. sayfa yok")
        return {"lines": pdf.page_text(document.pages[number - 1]).splitlines()}


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= MAX_CELL else text[: MAX_CELL - 1] + "…"


def table(data: bytes, _args: Reply) -> Reply:
    """The first sheet's cells, or an HTML export's innermost table rows: what the readers read (SourceRef.row)."""
    kind = sheet.sniff(data)
    if kind == "xls":
        name, rows = sheet.read_xls(data)
    elif kind == "xlsx":
        name, rows = sheet.read_xlsx(data)
    elif kind == "html":
        name, rows = "", [list[Any](r) for r in sheet.html_rows(data)]
    else:
        raise Refused("tablo olarak okunamadı")
    shown = [[_cell(v) for v in row[:MAX_COLUMNS]] for row in rows[:MAX_ROWS]]
    return {"name": name, "rows": shown, "more": len(rows) > MAX_ROWS}


def message(data: bytes, _args: Reply) -> Reply:
    """An e-mail's subject, sender's domain and date, its body's text as a browser breaks it into lines, the same text
    collapsed (a notice row's span counts in it), and the HTML part to show in a sandbox."""
    import email

    read = mails.read_mail(data)
    parsed = email.message_from_bytes(data)
    _, body_lines = mails.body(parsed)
    html = mails.html_part(parsed)
    return {
        "subject": read.subject,
        "sender": read.sender,
        "sent": read.sent.isoformat() if read.sent else "",
        "lines": [line for line in (mails.collapse(x) for x in body_lines) if line][: MAX_TEXT // 80],
        "text": read.text[:MAX_TEXT],
        "html": html if len(html.encode()) <= MAX_HTML else "",
    }


def text(data: bytes, _args: Reply) -> Reply:
    """A text document (an e-invoice's XML, a plain text, an HTML document's markup) as it is, its characters
    decoded."""
    return {"text": sheet.decode_html(data)[:MAX_TEXT]}


def html_text(data: bytes, _args: Reply) -> Reply:
    """An HTML document's visible text, its whitespace collapsed: the text a row's span counts in."""
    return {"text": sheet.html_text(data)[:MAX_TEXT]}


OPS: dict[str, Callable[[bytes, Reply], Reply]] = {
    "pages": pages,
    "render": render,
    "lines": lines,
    "table": table,
    "message": message,
    "text": text,
    "html_text": html_text,
}


def _write(out: IO[bytes], reply: Reply) -> None:
    out.write(json.dumps(reply, ensure_ascii=False).encode() + b"\n")
    out.flush()


def _serve() -> None:
    limit_memory(MEMORY_LIMIT)
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    replies = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)  # whatever a library prints goes to stderr
    sys.stdout = sys.stderr
    if hasattr(signal, "alarm"):  # the request ends even should the app be gone
        signal.alarm(TIME_LIMIT + 5)
    header = json.loads(sys.stdin.buffer.readline())
    data = sys.stdin.buffer.read(int(header["size"]))
    try:
        reply = OPS[header["op"]](data, header)
    except Refused as exc:
        reply = {"refused": str(exc)}
    except MemoryError:
        reply = {"refused": "belge gösterilemeyecek kadar büyük"}
    except Exception as exc:  # whatever a document provokes leaves it unshown  # noqa: BLE001
        reply = {"refused": f"belge gösterilemedi ({type(exc).__name__})"}
    _write(replies, reply)


if __name__ == "__main__":
    _serve()
