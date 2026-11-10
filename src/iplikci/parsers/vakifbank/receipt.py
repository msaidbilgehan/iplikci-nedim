"""Vakıfbank's receipts ("dekont") as its mobile app shares them (PDF): a transfer sent by FAST, EFT or havale.

Under the bank's name and "İŞLEM BİLGİLERİ" the receipt is a table of two label and value pairs a row: "İŞLEM TÜRÜ"
("FAST Giden Anlık Ödeme") and "İŞLEM TARİHİ", "ALICI BANKA" and "SORGU NO", "İŞLEM TUTARI" and "MASRAF TUTARI", the
sender's and the receiver's names, the receiver's IBAN and "İŞLEM NO"; the user's own text follows under "İŞLEM
AÇIKLAMASI". A cell's text wraps inside its column and the cells of a row are centred on its height, so a label's
value is the cell right of it whose middle is level with its own; an empty value prints no cell.

The receipt names the sender but not the sender's account: its row goes to the one Vakıfbank account of its currency
(analysis.resolve_masked). The notice the bank mails for the same transfer is dropped for it
(analysis._drop_told_twice), and the account list's row stands for it once the list comes.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal

from ...domain.codes import DocumentKind, TransactionKind
from ...domain.labels import format_amount
from ...domain.models import TRY, ParseResult, Transaction
from ...domain.text import fold
from ..accounts import bank_account
from ..common import BUSINESS_REASON, Skipped, currency_code, is_business
from ..contract import Detection, Format, Probe, SourceDocument
from ..pdf import Line, cells, page_lines
from ..text import parse_dmy, parse_tr_amount, squash

ID = "vakifbank.receipt"
_GAP = 10.0  # points between two cells of a line; the words of one are about four apart
# The table's labels, squashed (folded, no spaces): the sender's name wraps its label ("GÖNDEREN AD SOYAD /",
# "UNVAN") and the receiver's does not ("ALICI AD SOYAD/UNVAN").
_TYPE, _DAY, _AMOUNT, _FEE, _NUMBER = "ISLEMTURU", "ISLEMTARIHI", "ISLEMTUTARI", "MASRAFTUTARI", "ISLEMNO"
_TO, _FROM = "ALICIADSOYAD/UNVAN", "GONDERENADSOYAD/UNVAN"
_TO_BANK, _FROM_BANK = "ALICIBANKA", "GONDERENBANKA"
_NOTE = "ISLEMACIKLAMASI"  # a heading: the user's text is the cell under it
_LABELS = frozenset(
    {
        _TYPE,
        _DAY,
        _AMOUNT,
        _FEE,
        _NUMBER,
        _TO,
        _FROM,
        _TO_BANK,
        _FROM_BANK,
        _NOTE,
        "SORGUNO",
        "FISNO",
        "ALICIHESAPNO/IBAN",
    }
)
_FOOTER = "SICILNUMARASI"  # the bank's registry lines, under the receipt
_MONEY = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2}) ?([A-Z]{2,3})\b")


@dataclass
class _Cell:
    """A cell of the receipt: its column's left edge, its extent from its first line's top to its last line's bottom,
    and its lines."""

    x: float
    top: float
    bottom: float
    lines: list[Line] = field(default_factory=list[Line])

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines)

    @property
    def middle(self) -> float:
        return (self.top + self.bottom) / 2


def _bottom(line: Line) -> float:
    return max((w.bottom if w.bottom is not None else w.top) for w in line.words)


def _cells(lines: list[Line]) -> list[_Cell]:
    """The page's cells, top to bottom: a line's runs of words, those of one column (the same left edge) whose lines
    follow with less than half a line's height between them joined into one."""
    found: list[_Cell] = []
    for line in lines:
        for run in cells(line, _GAP):
            x, top, bottom = run.words[0].x0, run.top, _bottom(run)
            above = next((c for c in reversed(found) if abs(c.x - x) < 2), None)
            if above is not None and top - above.bottom < (bottom - top) / 2:
                above.lines.append(run)
                above.bottom = bottom
            else:
                found.append(_Cell(x, top, bottom, [run]))
    return found


def _fields(found: list[_Cell]) -> dict[str, _Cell]:
    """Each label's value: the nearest cell right of it whose middle is level with its own, unless that is another
    label; the user's text is the cell under its heading, unless that is the bank's registry lines."""
    out: dict[str, _Cell] = {}
    for i, cell in enumerate(found):
        key = squash(cell.text)
        if key not in _LABELS or key in out:
            continue
        if key == _NOTE:
            value = next((c for c in found[i + 1 :] if abs(c.x - cell.x) < 2), None)
            if value is not None and not squash(value.text).startswith(_FOOTER):
                out[key] = value
            continue
        level = [c for c in found if c.x > cell.x + 2 and abs(c.middle - cell.middle) <= (cell.bottom - cell.top) / 2]
        value = min(level, key=lambda c: c.x, default=None)
        if value is not None and squash(value.text) not in _LABELS:
            out[key] = value
    return out


def _text(fields: dict[str, _Cell], key: str) -> str:
    cell = fields.get(key)
    return cell.text if cell is not None else ""


def _money(text: str) -> tuple[Decimal, str] | None:
    """An amount as the receipt prints it ("2.500,00 TL"): the amount and its currency."""
    found = _MONEY.search(fold(text))
    value = parse_tr_amount(found[1]) if found else None
    return (value, currency_code(found[2])) if found and value is not None else None


def read(doc: SourceDocument) -> ParseResult:
    fields = _fields(_cells(page_lines(doc.pdf.pages[0])))
    kind = fold(_text(fields, _TYPE))
    out = "GIDEN" in kind
    if not out and "GELEN" not in kind:
        raise ValueError("Vakıfbank dekontunda paranın yönü bulunamadı")
    holder = _text(fields, _FROM if out else _TO)
    if is_business(holder):
        raise Skipped(BUSINESS_REASON, business=True)
    day, amount = parse_dmy(_text(fields, _DAY)), _money(_text(fields, _AMOUNT))
    if day is None or amount is None:
        raise ValueError("Vakıfbank dekontunda işlem tarihi ya da tutarı bulunamadı")
    value, currency = amount
    account = bank_account("Vakıfbank", "****", currency)
    account.label = account.label.removesuffix(" ****")
    word = "FAST" if "FAST" in kind else "EFT" if "EFT" in kind else "Havale" if "HAVALE" in kind else "Transfer"
    title = f"{'Giden' if out else 'Gelen'} {word}"
    party, bank = _text(fields, _TO if out else _FROM), _text(fields, _TO_BANK if out else _FROM_BANK)
    note = _text(fields, _NOTE)
    text = f"{title} {'→' if out else '←'} {party or bank or 'banka'}"
    text += (f" ({bank})" if party and bank else "") + (f" — {note}" if note else "")
    # Whether it went to the user's own account, the landlord or a friend is decided once every account is known
    # (analysis.py), like a transfer row of an account list.
    rows = [
        Transaction(
            date=day,
            description=text,
            amount=value if out else -value,
            kind=TransactionKind.TRANSFER_CANDIDATE,
            account=account.id,
            counterparty=party,
            source=doc.name,
            ref=fields[_AMOUNT].lines[0].ref,
            original=f"{format_amount(value)} {currency}" if currency != TRY else "",
        )
    ]
    fee = _money(_text(fields, _FEE))
    if fee is not None and fee[0] > 0 and fee[1] == currency:
        rows.append(
            Transaction(
                date=day,
                description=f"{title} masrafı",
                amount=fee[0],
                kind=TransactionKind.INTEREST_FEE,
                account=account.id,
                source=doc.name,
                ref=fields[_FEE].lines[0].ref,
            )
        )
    number = re.match(r"\d+", _text(fields, _NUMBER))
    return ParseResult(
        parser=ID,
        accounts=[account],
        transactions=rows,
        receipt_key=f"vakifbank-dekont-{number[0] if number else doc.sha256}",
        holder=holder,
        title=title,
    )


class Receipt:
    id = ID
    version = 1
    bank = "Vakıfbank"
    name = "Vakıfbank dekontu"
    document_type = DocumentKind.RECEIPT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        if "VAKIFLARBANKASI" in s and "ISLEMBILGILERI" in s and "SORGUNO" in s and "ISLEMTUTARI" in s:
            return Detection(1.0, "Vakıfbank dekontu: işlem bilgileri, sorgu no ve tutar")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = Receipt()
