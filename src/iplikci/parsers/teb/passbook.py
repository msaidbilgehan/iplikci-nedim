"""TEB's "Dijital Hesap Cüzdanı": an account's movements between two days, as the bank's apps make it on request.

The first page names the account in "label: value" lines ("Hesap Numarası", "IBAN", "Hesap Türü", "Para Kodu",
"Bakiye", the report day and the period) and lists the movements oldest first under "Sıra No | Tarih | Açıklama |
İşlem Tutarı | Bakiye"; the last page holds the deposit terms. The bank calls its overdraft (KMH) account "Vadesiz",
as CEPTETEB's export does: a TL account that runs below zero is the overdraft account.
"""

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


def _table(lines: list[Line]) -> float | None:
    """Where the amount column starts: its header's first word ("İşlem Tutarı"), None when the page has no table."""
    for line in lines:
        f = fold(line.text)
        if "SIRA NO" in f and "ACIKLAMA" in f and "BAKIYE" in f:
            return next((w.x0 for w in line.words if fold(w.text) == "ISLEM"), None)
    return None


def _row(line: Line) -> Movement | None:
    """A table row: its number, day, description, amount and balance."""
    words = [w.text for w in line.words]
    if len(words) < 5 or not words[0].isdigit():
        return None
    day, amount, balance = parse_dmy(words[1]), parse_tr_amount(words[-2]), parse_tr_amount(words[-1])
    if day is None or amount is None or balance is None:
        return None
    description = " ".join(words[2:-2])
    return Movement(day, description, amount, balance, "", sender_of(description), line.ref)


def _movements(lines: list[Line], amounts_from: float) -> list[Movement]:
    """The page's rows. A description too long for its column runs on below its row, inside the column: such a line
    has no number, day or amounts and ends before the amount column."""
    moves: list[Movement] = []
    left: float | None = None  # where the last row's description starts
    for line in lines:
        row = _row(line)
        if row is not None:
            moves.append(row)
            left = line.words[2].x0
            continue
        f = fold(line.text)
        if left is None or any(f.startswith(footer) for footer in _FOOTERS):
            left = None
            continue
        if line.words[0].x0 >= left - 2 and line.words[-1].x1 < amounts_from:
            moves[-1].description = f"{moves[-1].description} {line.text}"
            moves[-1].counterparty = sender_of(moves[-1].description)
        else:
            left = None
    return moves


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
        amounts_from = _table(lines)
        if amounts_from is not None:
            moves += _movements(lines, amounts_from)
    if not moves:
        raise Skipped("TEB dijital hesap cüzdanında bu aralıkta hareket yok")
    kind = fold(info.get("HESAP TURU", ""))
    overdraft = currency_code(currency) == TRY and any((m.balance or 0) < -1 for m in moves)
    account = bank_account(
        "TEB",
        number,
        currency,
        AccountType.OVERDRAFT if overdraft else AccountType.DEPOSIT if "VADELI" in kind else None,
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
    version = 1
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
