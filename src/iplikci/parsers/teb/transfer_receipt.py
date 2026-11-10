"""TEB's receipts of a transfer between two TEB accounts ("Banka İçi Para Transfer Dekontu", PDF), as CEPTETEB's app
shares them.

A receipt tells the movement on one account, named by its number and currency ("Hesap Numarası:123456789-TL"): the
movement's own text before its value date and the amount with its sign after it ("vadeli para yatırma:
Valör:02/11/26 TL 2.500,00+"), + for money in. The other account is named only by its holder ("Borçlu Hesap
Sahibi", who paid) and its branch; the user's text follows "Açıklama:". A cell holds a label and its value
("Hesap Sahibi:…"), and a line's cells lie far apart.
"""

import re

from ...domain.codes import DocumentKind, TransactionKind
from ...domain.labels import format_amount
from ...domain.models import TRY, ParseResult, Transaction
from ...domain.text import fold
from ..accounts import bank_account
from ..common import BUSINESS_REASON, Skipped, is_business
from ..contract import Detection, Format, Probe, SourceDocument
from ..pdf import Line, cells, page_lines
from ..text import parse_dmy, parse_tr_amount, squash

ID = "teb.transfer_receipt"
_GAP = 10.0  # points between two cells of a line; the words of one are about four apart
_SIGNED = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})([+-])$")
# The other side's holder: who paid when the money came in, who was paid when it went out.
_PAYER, _PAYEE = "BORCLU HESAP SAHIBI", "ALACAKLI HESAP SAHIBI"


def _fields(lines: list[Line]) -> dict[str, str]:
    """The cells' values by their folded labels, the first of each."""
    out: dict[str, str] = {}
    for line in lines:
        for cell in cells(line, _GAP):
            label, colon, value = cell.text.partition(":")
            if colon:
                out.setdefault(fold(label).strip(), value.strip())
    return out


def _moved(lines: list[Line]) -> tuple[list[Line], re.Match[str]] | None:
    """The cells of the line that tells the movement, the one with the value date, and its signed amount: its last
    cell."""
    for line in lines:
        found = cells(line, _GAP)
        if any(fold(c.text).startswith("VALOR:") for c in found):
            signed = _SIGNED.search(found[-1].text)
            return (found, signed) if signed else None
    return None


def read(doc: SourceDocument) -> ParseResult:
    lines = page_lines(doc.pdf.pages[0])
    fields = _fields(lines)
    holder = fields.get("HESAP SAHIBI", "")
    if is_business(holder):
        raise Skipped(BUSINESS_REASON, business=True)
    number = re.fullmatch(r"(\d+)-([A-Z]{2,3})", fold(fields.get("HESAP NUMARASI", "")))
    day = parse_dmy(fields.get("TARIH-SAAT", ""))
    moved = _moved(lines)
    value = parse_tr_amount(moved[1][1]) if moved else None
    if not (number and day and moved and value is not None):
        raise ValueError("TEB havale dekontunda hesap numarası, tarih ya da tutar bulunamadı")
    found, signed = moved
    out = signed[2] == "-"
    account = bank_account("TEB", number[1], number[2])
    title = "Giden Havale" if out else "Gelen Havale"
    party = fields.get(_PAYEE if out else _PAYER, "")
    own = found[0].text.removesuffix(":").strip() if not fold(found[0].text).startswith("VALOR:") else ""
    note = fields.get("ACIKLAMA") or own
    text = f"{title} {'→' if out else '←'} {party}" if party else title
    # Whether it came from the user's own account or someone else's is decided once every account is known
    # (analysis.py), like a transfer row of an account list.
    row = Transaction(
        date=day,
        description=text + (f" — {note}" if note else ""),
        amount=abs(value) if out else -abs(value),
        kind=TransactionKind.TRANSFER_CANDIDATE,
        account=account.id,
        counterparty=party,
        source=doc.name,
        ref=found[-1].ref,
        original=f"{format_amount(abs(value))} {account.currency}" if account.currency != TRY else "",
    )
    reference = re.match(r"\d+", fields.get("ISLEM NO", ""))
    # The two accounts' receipts of one transfer are two receipts: the key holds the account.
    return ParseResult(
        parser=ID,
        accounts=[account],
        transactions=[row],
        receipt_key=f"teb-havale-{number[1]}-{reference[0] if reference else doc.sha256}",
        holder=holder,
        title=title,
    )


class TransferReceipt:
    id = ID
    version = 1
    bank = "TEB"
    name = "TEB banka içi havale dekontu"
    document_type = DocumentKind.RECEIPT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        if "BANKAICIPARATRANSFERDEKONTU" in s and ("TURKEKONOMIBANKASI" in s or "TEB.COM.TR" in s):
            return Detection(1.0, 'TEB adı ve "Banka İçi Para Transfer Dekontu"')
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = TransferReceipt()
