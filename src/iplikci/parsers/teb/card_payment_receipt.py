"""TEB credit card payment receipts ("Kredi Kartı Ödeme Dekontu", PDF)."""

import re

from ...domain.codes import DocumentKind, TransactionKind
from ...domain.models import ParseResult, Transaction
from ...domain.text import fold
from ..contract import Detection, Format, Probe, SourceDocument
from ..pdf import page_text
from ..text import parse_dmy, parse_tr_amount, squash
from ._card import card_account

ID = "teb.card_payment_receipt"


def read(doc: SourceDocument) -> ParseResult:
    first = page_text(doc.pdf.pages[0])
    f = fold(first)
    card = re.search(r"(\d{4}) (\d{2})\*\* \*\*\*\* (\d{4}) NO\.? ?LU KREDI KARTINA", f)
    when = re.search(r"TARIH-SAAT: ?(\d{2}/\d{2}/\d{4})", f)
    amount = re.search(r"TOPLAM TL\.? ?([\d.]+,\d{2})", f)
    if not (card and when and amount):
        raise ValueError("TEB ödeme dekontu okunamadı")
    account = card_account(card[3])
    txn = Transaction(
        date=parse_dmy(when[1]),
        description=f"TEB Bonus •{card[3]} borç ödemesi",
        amount=abs(parse_tr_amount(amount[1])),
        kind=TransactionKind.CARD_PAYMENT_NO_STATEMENT,
        account=account.id,
        source=doc.name,
    )
    receipt = re.search(r"ISLEM NO: ?(\d+)", f)
    holder = re.search(r"HESAP SAHIBI:\s*([A-Z ]+?)\s+HESAP", f)
    return ParseResult(
        parser=ID,
        accounts=[account],
        transactions=[txn],
        receipt_key=f"teb-{receipt[1] if receipt else doc.sha256}",
        title=f"Kart Ödemesi {card[3]}",
        holder=holder[1] if holder else "",
    )


class CardPaymentReceipt:
    id = ID
    version = 1
    bank = "TEB"
    name = "TEB kredi kartı ödeme dekontu"
    document_type = DocumentKind.RECEIPT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        if "KREDIKARTIODEMEDEKONTU" in s and ("TURKEKONOMIBANKASI" in s or "KREDIKARTEKSTREOZETI" in s):
            return Detection(1.0, 'TEB adı ve "Kredi Kartı Ödeme Dekontu"')
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = CardPaymentReceipt()
