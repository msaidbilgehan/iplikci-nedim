"""İş Bankası receipts (dekont) of single FAST / EFT / havale transfers.

Two columns of "Label : value" pairs: the sender's account and the amounts on the left, the
receiver on the right. The holder's name opens the first line.
"""

import re
from decimal import Decimal

from ...domain.codes import DocumentKind, TransactionKind
from ...domain.models import ParseResult, Transaction
from ...domain.text import fold
from ..accounts import bank_account, bank_from_iban
from ..common import BUSINESS_REASON, Skipped, is_business
from ..contract import Detection, Format, Probe, SourceDocument
from ..pdf import Line, Word, page_lines
from ..text import parse_dmy, parse_tr_amount, squash

ID = "isbank.receipt"
_RIGHT = 290  # the right column's labels start here


def _columns(line: Line) -> list[list[Word]]:
    """A line holds a left and a right 'label : value' pair only when the right part has a label."""
    right = [w for w in line.words if w.x0 >= _RIGHT]
    if any(w.text.endswith(":") for w in right):
        return [[w for w in line.words if w.x0 < _RIGHT], right]
    return [line.words]


def _fields(lines: list[Line]) -> tuple[dict[str, str], dict[str, Line]]:
    """The 'label : value' pairs by folded label, and the line each one is printed on."""
    out: dict[str, str] = {}
    where: dict[str, Line] = {}
    for line in lines:
        for words in _columns(line):
            text = " ".join(w.text for w in words)
            if ":" in text:
                label, value = text.split(":", 1)  # "İşlem Tarihi : 08.02.2024 / 14:32:05"
                out.setdefault(fold(label), value.strip())
                where.setdefault(fold(label), line)
    return out, where


def _amount(text: str) -> Decimal | None:
    m = re.match(r"([\d.]+,\d{2})", text)
    return parse_tr_amount(m[1]) if m else None


def read(doc: SourceDocument) -> ParseResult:
    lines = page_lines(doc.pdf.pages[0])
    fields, where = _fields(lines)
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
        parser=ID,
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
            ref=where["ISLEM TUTARI"].ref,
        )
    )
    fee_label = next((k for k in fields if k.endswith("UCRETI VE VERGI")), "")
    fee = _amount(fields.get(fee_label, ""))
    if fee:
        result.transactions.append(
            Transaction(
                date=day,
                description=f"{title} ücreti ve vergisi",
                amount=fee,
                kind=TransactionKind.INTEREST_FEE,
                account=account.id,
                source=doc.name,
                ref=where[fee_label].ref,
            )
        )
    return result


class Receipt:
    id = ID
    version = 1
    bank = "İş Bankası"
    name = "İş Bankası FAST/EFT dekontu"
    document_type = DocumentKind.RECEIPT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        iban = re.search(r"IBAN:(TR\d{24})", s)
        if iban and bank_from_iban(iban[1]) == "İş Bankası" and "ISLEMTUTARI" in s and "BELGENO" in s:
            return Detection(1.0, "İş Bankası IBAN'ı, işlem tutarı ve belge no")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = Receipt()
