"""Turn PDF pages into positioned text lines.

Statement tables are parsed by column position rather than by regex on plain
text: a line such as "TURKNET ... 289,90 0,04" only makes sense once you know
that 0,04 sits in the reward-points column and 289,90 in the amount column.
"""

import io
import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import Any

import pdfplumber

from ..domain.models import SourceRef
from ..domain.text import fold
from .text import parse_tr_amount

# Garanti PDFs carry invisible "bosluk" spacer words; some fonts emit (cid:N) glyphs.
_JUNK = re.compile(r"[bosluk]{6,}|\(cid:\d+\).*")


@dataclass
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float | None = None


@dataclass
class Line:
    top: float
    words: list[Word]
    page: int | None = None  # 1-based

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def folded(self) -> str:
        return fold(self.text)

    @property
    def ref(self) -> SourceRef:
        """The line's page and the box around its words, in points rounded to a hundredth."""
        x0, x1 = min(w.x0 for w in self.words), max(w.x1 for w in self.words)
        bottom = max((w.bottom if w.bottom is not None else w.top) for w in self.words)
        return SourceRef(page=self.page, box=(round(x0, 2), round(self.top, 2), round(x1, 2), round(bottom, 2)))


def open_pdf(data: bytes) -> Any:  # pdfplumber.PDF; pdfplumber ships no types
    return pdfplumber.open(io.BytesIO(data))


def page_text(page: Any) -> str:  # page: a pdfplumber.Page
    return page.extract_text(x_tolerance=1.5) or ""


def _group_lines(words: list[Word], y_tolerance: float, page: int | None = None) -> list[Line]:
    lines: list[Line] = []
    for w in sorted(words, key=lambda w: w.top):
        if lines and w.top - lines[-1].top <= y_tolerance:
            lines[-1].words.append(w)
        else:
            lines.append(Line(w.top, [w], page))
    for line in lines:
        line.words.sort(key=lambda w: w.x0)
    return lines


def page_lines(page: Any, x_tolerance: float = 1.0, y_tolerance: float = 2.0) -> list[Line]:
    raw = page.extract_words(x_tolerance=x_tolerance, y_tolerance=y_tolerance, keep_blank_chars=False)
    words = [
        Word(w["text"], w["x0"], w["x1"], w["top"], w["bottom"])
        for w in raw
        # İş Bankası prints fold marks ("-") in the left page margin.
        if not _JUNK.fullmatch(w["text"]) and not (w["text"] == "-" and w["x1"] < 30)
    ]
    return _group_lines(words, y_tolerance, page.page_number)


# --- OCR for statements delivered as page images (macOS Vision framework) ----


def ocr_available() -> bool:
    try:
        import Vision  # noqa: F401
    except ImportError:
        return False
    return True


def ocr_page_lines(data: bytes, page_index: int, y_tolerance: float = 4.0) -> list[Line]:
    """Recognize text on a rendered page. Each Word is one recognized text run
    (usually a table cell), with coordinates in PDF points like page_lines()."""
    import pypdfium2 as pdfium
    import Vision
    from Foundation import NSData

    doc = pdfium.PdfDocument(data)
    page = doc[page_index]
    width, height = page.get_size()
    buf = io.BytesIO()
    page.render(scale=2.5).to_pil().save(buf, format="PNG")
    png = buf.getvalue()
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(
        NSData.dataWithBytes_length_(png, len(png)), None
    )
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["tr-TR", "en-US"])
    request.setUsesLanguageCorrection_(False)
    handler.performRequests_error_([request], None)
    words = []
    for obs in request.results() or []:
        box = obs.boundingBox()  # normalized, origin at the bottom left
        words.append(
            Word(
                str(obs.topCandidates_(1)[0].string()),
                box.origin.x * width,
                (box.origin.x + box.size.width) * width,
                (1 - box.origin.y - box.size.height) * height,
                (1 - box.origin.y) * height,
            )
        )
    return _group_lines(words, y_tolerance, page_index + 1)


def label_values(lines: list[Line]) -> dict[str, str]:
    """'Label : value' lines by folded label ("HESAP TURU / PARA BIRIMI"), the first of each. A label that
    ends its line takes the next line as its value."""
    out: dict[str, str] = {}
    for i, line in enumerate(lines):
        label, colon, value = line.text.partition(":")
        if not colon:
            continue
        if not value.strip() and i + 1 < len(lines):
            value = lines[i + 1].text
        out.setdefault(fold(label), value.strip())
    return out


def cells(line: Line, gap: float) -> list[Line]:
    """The line's cells: its runs of words less than gap points apart, each a line of its own."""
    found: list[Line] = []
    for w in line.words:
        if found and w.x0 - found[-1].words[-1].x1 < gap:
            found[-1].words.append(w)
        else:
            found.append(Line(line.top, [w], line.page))
    return found


def find_word(line: Line, *names: str) -> Word | None:
    """First word on the line whose folded text equals (or starts with) one of names."""
    for w in line.words:
        f = fold(w.text)
        if any(f == n or f.startswith(n) for n in names):
            return w
    return None


def find_header(lines: list[Line], *required: str) -> int | None:
    """Index of the first line containing all required (folded) words."""
    for i, line in enumerate(lines):
        if all(find_word(line, r) for r in required):
            return i
    return None


def take_amount(line: Line, edge: float, align: str = "right", tolerance: float = 8.0):
    """Find the amount printed in a column.

    The column is given by the header's right edge (right-aligned numbers) or
    left edge (left-aligned numbers). A detached sign word just before the
    number ("- 123,45") is merged into it. Returns (amount, words_used) or
    (None, []).
    """
    for i in range(len(line.words) - 1, -1, -1):
        w = line.words[i]
        pos = w.x1 if align == "right" else w.x0
        if abs(pos - edge) > tolerance:
            continue
        value = parse_tr_amount(w.text)
        if value is None:
            continue
        used = [w]
        if i > 0:
            prev = line.words[i - 1]
            if prev.text in ("-", "+") and w.x0 - prev.x1 < 8:
                used.insert(0, prev)
                if prev.text == "-":
                    value = -abs(value)
        return value, used
    return None, []


def numbered_lines(texts: list[str]) -> list[tuple[int, int, str]]:
    """(page, line on that page, line) for every line of the pages' texts joined with line breaks, so a reader that
    reads the joined text line by line still knows where each line is printed."""
    joined = "\n".join(texts)
    starts, offset = [], 0
    for text in texts:
        starts.append(offset)
        offset += len(text) + 1
    out: list[tuple[int, int, str]] = []
    offset, page, counted = 0, 0, 0
    for line in joined.splitlines(keepends=True):
        here = bisect_right(starts, offset)
        if here != page:
            page, counted = here, 0
        counted += 1
        out.append((page, counted, line.rstrip("\r\n")))
        offset += len(line)
    return out
