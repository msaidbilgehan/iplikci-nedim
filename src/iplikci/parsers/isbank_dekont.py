"""İş Bankası receipts (dekont) of single FAST / EFT / havale transfers.

Two columns of "Label : value" pairs: the sender's account and the amounts on the left, the
receiver on the right. The holder's name opens the first line.
"""

import re
from decimal import Decimal

from ..domain.codes import TransactionKind
from ..domain.models import ParseResult, Transaction
from ..pdfutil import Line, Word, page_lines
from ..textutil import fold, parse_dmy, parse_tr_amount, squash
from .common import BUSINESS_REASON, Skipped, is_business
from .hesap import bank_from_iban
from .hesaplar import bank_account

NAME = "İş Bankası dekont"
_RIGHT = 290  # the right column's labels start here


def detect(first_page: str) -> bool:
    s = squash(first_page)
    iban = re.search(r"IBAN:(TR\d{24})", s)
    return bool(iban) and bank_from_iban(iban[1]) == "İş Bankası" and "ISLEMTUTARI" in s and "BELGENO" in s


def _columns(line: Line) -> list[list[Word]]:
    """A line holds a left and a right 'label : value' pair only when the right part has a label."""
    right = [w for w in line.words if w.x0 >= _RIGHT]
    if any(w.text.endswith(":") for w in right):
        return [[w for w in line.words if w.x0 < _RIGHT], right]
    return [line.words]


def _fields(lines: list[Line]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in lines:
        for words in _columns(line):
            text = " ".join(w.text for w in words)
            if ":" in text:
                label, value = text.split(":", 1)  # "İşlem Tarihi : 08.02.2024 / 14:32:05"
                out.setdefault(fold(label), value.strip())
    return out


def _amount(text: str) -> Decimal | None:
    m = re.match(r"([\d.]+,\d{2})", text)
    return parse_tr_amount(m[1]) if m else None


def parse(doc, pdf) -> ParseResult:
    lines = page_lines(pdf.pages[0])
    fields = _fields(lines)
    first = lines[0].words if lines else []
    holder = (
        "" if any(":" in w.text for w in first if w.x0 < _RIGHT) else " ".join(w.text for w in first if w.x0 < _RIGHT)
    )
    if is_business(holder):
        raise Skipped(BUSINESS_REASON, business=True)
    digits = re.sub(r"\D", "", fields.get("IBAN", ""))
    branch_account = re.search(r"(\d{4})(\d{7})$", digits)  # the IBAN ends with branch (4) + account (7)
    day = parse_dmy(fields.get("ISLEM TARIHI", ""))
    amount = _amount(fields.get("ISLEM TUTARI", ""))
    heading = next((line.folded for line in lines if line.folded.endswith("ISLEMI") and ":" not in line.text), "")
    if not (branch_account and day and amount):
        raise ValueError("İş Bankası dekontunda IBAN, işlem tarihi ya da tutar bulunamadı")
    method = next((m for m in ("FAST", "EFT", "HAVALE") if m in heading), "Transfer")
    incoming = heading.startswith("GELEN")
    title = f"{'Gelen' if incoming else 'Giden'} {method.title() if method == 'HAVALE' else method}"
    account = bank_account("İş Bankası", f"{branch_account[1]}-{branch_account[2]}", "TL")
    result = ParseResult(
        parser=NAME,
        accounts=[account],
        holder=holder,
        title=title,
        receipt_key=f"isbank-dekont-{fields.get('BELGE NO') or doc.sha256}",
    )
    side = "GONDEREN" if incoming else "ALICI"
    party = fields.get(f"{side} ISIM\\UNVAN") or fields.get(f"{side} ISIM/UNVAN") or fields.get(f"{side} ADI", "")
    bank = bank_from_iban(fields.get(f"{side} IBAN", "")) or re.sub(r"^\d+\s*-\s*", "", fields.get(f"{side} BANKA", ""))
    note = fields.get("ACIKLAMA", "")
    text = f"{title} {'←' if incoming else '→'} {party}" + (f" ({bank})" if bank else "")
    text += f" — {note}" if note else ""
    result.transactions.append(
        Transaction(
            date=day,
            description=text,
            amount=-amount if incoming else amount,
            kind=TransactionKind.TRANSFER_CANDIDATE,
            account=account.id,
            counterparty=party,
            source=doc.name,
        )
    )
    fee = _amount(next((v for k, v in fields.items() if k.endswith("UCRETI VE VERGI")), ""))
    if fee:
        result.transactions.append(
            Transaction(
                date=day,
                description=f"{title} ücreti ve vergisi",
                amount=fee,
                kind=TransactionKind.INTEREST_FEE,
                account=account.id,
                source=doc.name,
            )
        )
    return result
