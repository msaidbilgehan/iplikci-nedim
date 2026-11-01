"""QNB (Finansbank) e-dekont receipts, delivered as HTML or PDF.

They cover consumer-loan installments, payments to a QNB credit card and
FAST/EFT transfers. A transfer names the other side ("GÖNDEREN : AD SOYAD",
"ALICI : …") and its bank ("KATILIMCI: Türkiye Garanti Bankası A.Ş."); whether
it is money between the user's own accounts or from/to someone else is decided
with the other documents (analysis.py).
"""

import re
from bisect import bisect_right
from collections.abc import Callable
from decimal import Decimal

from ...domain.codes import AccountType, DocumentKind, TransactionKind
from ...domain.models import Account, ParseResult, SourceRef, Transaction
from ...domain.money import round_half_up
from ...domain.text import fold, title_tr
from ..common import Skipped
from ..contract import Detection, Format, Probe, SourceDocument
from ..pdf import page_text
from ..text import parse_dmy, parse_us_amount, unfold_span

ID = "qnb.edekont"

_ROW = re.compile(r"(?:TR\d{24}\s+)?(?P<desc>.+?)\s+(?P<ba>[BA])\s+(?P<cur>TL|USD|EUR)\s+(?P<amt>[\d,]+\.\d{1,2})")
_BANKS = {
    "TURKIYE GARANTI BANKASI": "Garanti BBVA",
    "TURKIYE IS BANKASI": "İş Bankası",
    "TURK EKONOMI BANKASI": "TEB",
    "TURKIYE VAKIFLAR BANKASI": "VakıfBank",
}


def _account_main(text: str) -> Account:
    iban = re.search(r"TR\d{24}", text)
    number = iban[0][-16:].lstrip("0") if iban else "hesap"
    return Account(
        id=f"qnb-{number}",
        label=f"QNB Ek Hesap {number}",
        bank="QNB",
        type=AccountType.OVERDRAFT,
        number=number,
    )


def _locator(pages: list[str] | None) -> Callable[[tuple[int, int] | None], SourceRef]:
    """Where a span of the text is: the span, and for a PDF (pages: each page's text) the page it is on."""
    starts: list[int] = []
    offset = 0
    for page in pages or []:
        flat = " ".join(page.split())
        if flat:
            starts.append(offset)
            offset += len(flat) + 1

    def ref(span: tuple[int, int] | None) -> SourceRef:
        page = bisect_right(starts, span[0]) if span and starts else None
        return SourceRef(page=page, span=span)

    return ref


def read_text(doc: SourceDocument, text: str, pages: list[str] | None = None) -> ParseResult:
    t = " ".join(text.split())
    f = fold(t)
    where = _locator(pages)
    when = re.search(r"ISLEM TARIHI (\d{2}/\d{2}/\d{4})", f)
    fis = re.search(r"FIS NO ?: ?(\d+)", f)
    if not when:
        raise ValueError("işlem tarihi bulunamadı")
    day = parse_dmy(when[1])
    key = f"qnb-{fis[1] if fis else doc.sha256}"
    holder = re.search(r"DEKONT\s+([A-ZÇĞİÖŞÜ ]+?)\s+(?:MUSTERI NO|[A-ZÇĞİÖŞÜ]+ MAH)", t)
    off = f.find("PARA CINSI TUTAR") + len("PARA CINSI TUTAR") if "PARA CINSI TUTAR" in f else 0
    table = t[off:]
    rows = [
        (m["desc"], m["ba"], m["cur"], parse_us_amount(m["amt"]), (off + m.start(), off + m.end()))
        for m in _ROW.finditer(table)
    ]
    result = ParseResult(parser=ID, receipt_key=key, holder=holder[1] if holder else "")

    loan = re.search(r"(\d{5}-BT-\d+) REFERANSLI KREDI (\d{2}/\d{2}/\d{4}) TARIHLI TAKSIT ODEMESI", f)
    parts = re.search(r"ODENEN ANAPARA: ?([\d.,]+) FAIZ: ?([\d.,]+) KKDF: ?([\d.,]+) BSMV: ?([\d.,]+)", f)
    card = re.search(r"(\d{6})\*{6}(\d{4}) NOLU KART", f)

    if loan and parts:
        ref = loan[1]
        acct = Account(
            id=f"qnb-kredi-{ref[-4:]}",
            label=f"QNB İhtiyaç Kredisi …{ref[-4:]}",
            bank="QNB",
            type=AccountType.LOAN,
            number=ref[-4:],
        )
        result.title = f"Kredi Taksiti {ref[-4:]}"
        principal = parse_us_amount(parts[1]) or Decimal(0)
        cost = sum((parse_us_amount(parts[i]) or Decimal(0) for i in (2, 3, 4)), Decimal(0))
        result.accounts.append(acct)
        result.transactions += [
            Transaction(
                date=day,
                description=f"QNB ihtiyaç kredisi taksiti ({loan[2]}) — anapara",
                amount=round_half_up(principal),
                kind=TransactionKind.LOAN_PRINCIPAL,
                account=acct.id,
                source=doc.name,
                ref=where(unfold_span(t, parts.start(1), parts.end(1))),
            ),
            Transaction(
                date=day,
                description=f"QNB ihtiyaç kredisi taksiti ({loan[2]}) — faiz, KKDF, BSMV",
                amount=round_half_up(cost),
                kind=TransactionKind.INTEREST_FEE,
                account=acct.id,
                source=doc.name,
                ref=where(unfold_span(t, parts.start(2), parts.end(4))),
            ),
        ]
        return result

    if card and rows:
        last4 = card[2]
        acct = Account(
            id=f"qnb-{last4}",
            label=f"QNB Mastercard •{last4}",
            bank="QNB",
            type=AccountType.CREDIT_CARD,
            number=last4,
        )
        result.title = f"Kart Ödemesi {last4}"
        result.accounts.append(acct)
        result.transactions.append(
            Transaction(
                date=day,
                description=f"QNB Mastercard •{last4} borç ödemesi",
                amount=rows[0][3],
                kind=TransactionKind.CARD_PAYMENT_NO_STATEMENT,
                account=acct.id,
                source=doc.name,
                ref=where(rows[0][4]),
            )
        )
        return result

    if not rows:
        raise Skipped("dekontta tutar yazmıyor")  # QNB sends some incoming-transfer notices without the amount row
    main = _account_main(table)
    result.accounts.append(main)
    result.title = "Transfer"
    note = re.search(r"ACIKLAMA: ?(.+?) (?:GONDEREN|ALICI) ", f)
    bank = re.search(r"(?:KATILIMCI|BANKA ADI/SUBESI): ?([A-Z ]+?BANKASI)", f)
    bank_name = _BANKS.get(bank[1].strip(), title_tr(bank[1].strip())) if bank else ""
    for desc, ba, cur, amount, span in rows:
        if amount is None or cur != "TL":
            continue
        if "UCRET" in fold(desc):
            result.transactions.append(
                Transaction(
                    date=day,
                    description="QNB EFT ücreti",
                    amount=amount,
                    kind=TransactionKind.INTEREST_FEE,
                    account=main.id,
                    source=doc.name,
                    ref=where(span),
                )
            )
            continue
        incoming = ba == "A"
        text = f"{'Gelen' if incoming else 'Giden'} transfer"
        if bank_name:
            text += f" {'←' if incoming else '→'} {bank_name}"
        if note:
            text += f" ({note[1].strip().lower()})"
        result.transactions.append(
            Transaction(
                date=day,
                description=text,
                amount=-amount if incoming else amount,
                kind=TransactionKind.TRANSFER_CANDIDATE,
                account=main.id,
                counterparty=_other_side(desc, t, incoming),
                source=doc.name,
                ref=where(span),
            )
        )
    return result


_NAME_ENDS = {"HESAP", "IBAN", "MUSTERI", "KATILIMCI", "SORGU", "ACIKLAMA"}


def _other_side(desc: str, text: str, incoming: bool) -> str:
    """The sender of an incoming transfer, the receiver of an outgoing one: the row prints it
    ("Gönderen: AD SOYAD"), and so does the block below the table ("GÖNDEREN : AD SOYAD HESAP NO: …")."""
    label = "GONDEREN" if incoming else "ALICI"
    for words in (desc.split(), text.split()):
        folded = [fold(w) for w in words]
        for i, word in enumerate(folded):
            if word.rstrip(":") != label:
                continue
            start = i + 2 if i + 1 < len(words) and folded[i + 1] == ":" else i + 1
            name = []
            for original, f in zip(words[start:], folded[start:]):
                if f in _NAME_ENDS or f.endswith(":"):
                    break
                name.append(original)
            if name:
                return " ".join(name)
    return ""


class Edekont:
    id = ID
    version = 1
    bank = "QNB"
    name = "QNB e-dekont"
    document_type = DocumentKind.RECEIPT
    formats = frozenset({Format.HTML, Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        f = fold(probe.text)
        if "QNB" in f and "DEKONT" in f and "HESAP/K.KART NO" in f:
            return Detection(1.0, 'QNB, dekont ve "Hesap/K.Kart No"')
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        if doc.kind == "html" or doc.ext in (".html", ".htm"):
            return read_text(doc, doc.text)
        pages = [page_text(p) for p in doc.pdf.pages]
        return read_text(doc, " ".join(pages), pages)


PARSER = Edekont()
