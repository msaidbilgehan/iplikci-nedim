"""TEB's "Dijital Hesap Cüzdanı": an account's movements between two days, as the bank's apps make it on request.

The first page names the account in "label: value" lines ("Hesap Numarası", "IBAN", "Hesap Türü", "Para Kodu",
"Bakiye", the report day and the period) and lists the movements oldest first under "Sıra No | Tarih | Açıklama |
İşlem Tutarı | Bakiye"; the last page holds the deposit terms. The bank calls its overdraft (KMH) account "Vadesiz",
as CEPTETEB's export does: a TL account that runs below zero is the overdraft account. An account that earns interest
prints its yearly gross rate below the balance ("Brüt Faiz Oranı (Yıllık)"), a CEPTETEB Marifetli account as well as a
term one, while a current account prints none: such an account is a deposit.

A row's cells are centred on its height, and a description too long for its column wraps inside it: a description of
two lines prints one above and one below the line of the row's number, day and amounts, which holds none of its words.
A line inside the description column belongs to the row whose line is nearest.
"""

from collections import defaultdict
from decimal import Decimal

from ...domain.codes import AccountType, DocumentKind
from ...domain.models import TRY, ParseResult
from ...domain.text import fold
from ..accounts import bank_account, bank_from_iban, period_of
from ..common import BUSINESS_REASON, Skipped, currency_code, is_business
from ..contract import Detection, Format, Probe, SourceDocument
from ..movements import Movement, build_statement
from ..pdf import Line, label_values, page_lines
from ..text import parse_dmy, parse_tr_amount, squash
from .account_html import sender_of

ID = "teb.passbook"

# The lines under the table on every page: the revision and page number, the bank's address.
_FOOTERS = ("REV.NO", "TURK EKONOMI BANKASI")
# The label of the yearly gross interest rate an interest-bearing account prints, folded.
_RATE = "BRUT FAIZ ORANI"


def _table(lines: list[Line]) -> tuple[int, float] | None:
    """The table's header line and where its amount column starts (the header's "İşlem Tutarı"); None when the page
    has no table."""
    for i, line in enumerate(lines):
        f = line.folded
        if "SIRA NO" in f and "ACIKLAMA" in f and "BAKIYE" in f:
            start = next((w.x0 for w in line.words if fold(w.text) == "ISLEM"), None)
            return (i, start) if start is not None else None
    return None


def _row(line: Line) -> Movement | None:
    """A row's line: its number, day, amount and balance, and the description words it holds, if any."""
    words = [w.text for w in line.words]
    if len(words) < 4 or not words[0].isdigit():
        return None
    day, amount, balance = parse_dmy(words[1]), parse_tr_amount(words[-2]), parse_tr_amount(words[-1])
    if day is None or amount is None or balance is None:
        return None
    return Movement(day, " ".join(words[2:-2]), amount, balance, "", "", line.ref)


def _movements(lines: list[Line], header: int, amounts_from: float) -> list[Movement]:
    """The page's rows. A line between the header and the footer that lies inside the description column (right of
    the rows' days, left of the amounts) is part of the description of the row whose line is nearest; a line as near
    to two rows goes on the upper one's."""
    body: list[Line] = []
    for line in lines[header + 1 :]:
        if any(line.folded.startswith(footer) for footer in _FOOTERS):
            break
        body.append(line)
    rows = [(line, move) for line in body if (move := _row(line)) is not None]
    if not rows:
        return []
    days_end = max(line.words[1].x1 for line, _ in rows)
    row_lines = {id(line) for line, _ in rows}
    pieces: dict[int, list[Line]] = defaultdict(list)
    for line in body:
        if id(line) in row_lines or line.words[0].x0 <= days_end or line.words[-1].x1 >= amounts_from:
            continue
        nearest = min(range(len(rows)), key=lambda i: (abs(rows[i][0].top - line.top), rows[i][0].top > line.top))
        pieces[nearest].append(line)
    for i, (line, move) in enumerate(rows):
        above = [p.text for p in pieces[i] if p.top < line.top]
        below = [p.text for p in pieces[i] if p.top > line.top]
        move.description = " ".join(part for part in (*above, move.description, *below) if part)
        move.counterparty = sender_of(move.description)
    return [move for _, move in rows]


def read(doc: SourceDocument) -> ParseResult:
    pages = [page_lines(p) for p in doc.pdf.pages]
    info = label_values(pages[0]) if pages else {}
    holder = info.get("MUSTERI ADI - SOYADI", "")
    if is_business(holder):
        raise Skipped(BUSINESS_REASON, business=True)
    number, iban = info.get("HESAP NUMARASI", ""), info.get("IBAN", "").replace(" ", "")
    currency = info.get("PARA KODU", "")
    if not number or not currency or bank_from_iban(iban) != "TEB":
        raise ValueError("TEB dijital hesap cüzdanında hesap numarası, IBAN ya da para kodu bulunamadı")
    moves: list[Movement] = []
    for lines in pages:
        table = _table(lines)
        if table is not None:
            moves += _movements(lines, *table)
    if not moves:
        raise Skipped("TEB dijital hesap cüzdanında bu aralıkta hareket yok")
    overdraft = currency_code(currency) == TRY and any((m.balance or 0) < -1 for m in moves)
    earns = "VADELI" in fold(info.get("HESAP TURU", "")) or any(label.startswith(_RATE) for label in info)
    account = bank_account(
        "TEB",
        number,
        currency,
        AccountType.OVERDRAFT if overdraft else AccountType.DEPOSIT if earns else None,
    )
    start, end = period_of(info.get("HESAP HAREKETI TARIH ARALIGI", ""))
    opened = parse_dmy(info.get("HESAP ACILIS TARIHI", ""))
    first, last = moves[0].date, moves[-1].date
    start, end = min(start or first, first), max(end or last, last)
    # A cüzdan that starts on the opening day starts from zero, so its first row is checked too.
    stmt = build_statement(
        doc,
        account,
        moves,
        start,
        end,
        oldest_first=True,
        opening=Decimal(0) if opened is not None and opened >= start else None,
    )
    return ParseResult(parser=ID, accounts=[account], statements=[stmt], holder=holder)


class Passbook:
    id = ID
    version = 4
    bank = "TEB"
    name = "TEB dijital hesap cüzdanı"
    document_type = DocumentKind.ACCOUNT_STATEMENT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        if "DIJITALHESAPCUZDANI" in s and "CUZDANNUMARASI" in s and ("TEB.COM.TR" in s or "TURKEKONOMIBANKASI" in s):
            return Detection(1.0, "TEB'in dijital hesap cüzdanı")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = Passbook()
