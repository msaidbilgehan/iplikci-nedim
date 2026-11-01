"""QNB (Finansbank) e-dekont receipts, delivered as HTML or PDF.

They cover consumer-loan installments, payments to a QNB credit card and
FAST/EFT transfers. A transfer names the other side ("GÖNDEREN : AD SOYAD",
"ALICI : …") and its bank ("KATILIMCI: Türkiye Garanti Bankası A.Ş."); whether
it is money between the user's own accounts or from/to someone else is decided
with the other documents (analysis.py).
"""

import re

from bs4 import BeautifulSoup

from ..domain.models import Account, ParseResult, Transaction
from ..textutil import fold, parse_dmy, parse_us_amount, title_tr
from .common import Skipped
from .hesap import CANDIDATE

NAME = "QNB dekont"

_ROW = re.compile(r"(?:TR\d{24}\s+)?(?P<desc>.+?)\s+(?P<ba>[BA])\s+(?P<cur>TL|USD|EUR)\s+(?P<amt>[\d,]+\.\d{1,2})")
_BANKS = {
    "TURKIYE GARANTI BANKASI": "Garanti BBVA",
    "TURKIYE IS BANKASI": "İş Bankası",
    "TURK EKONOMI BANKASI": "TEB",
    "TURKIYE VAKIFLAR BANKASI": "VakıfBank",
}


def detect_text(text: str) -> bool:
    f = fold(text)
    return "QNB" in f and "DEKONT" in f and "HESAP/K.KART NO" in f


def html_text(data: bytes) -> str:
    # TEB saves some reports as UTF-16 with a byte-order mark.
    encodings = ("utf-16",) if data[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8", "windows-1254")
    for enc in encodings:
        try:
            raw = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raw = data.decode("latin-1")
    return " ".join(BeautifulSoup(raw, "html.parser").get_text(" ").split())


def _account_main(text: str) -> Account:
    iban = re.search(r"TR\d{24}", text)
    number = iban[0][-16:].lstrip("0") if iban else "hesap"
    return Account(
        id=f"qnb-{number}",
        label=f"QNB Ek Hesap {number}",
        bank="QNB",
        type="Ek hesap (KMH)",
        number=number,
    )


def parse_text(doc, text: str) -> ParseResult:
    t = " ".join(text.split())
    f = fold(t)
    when = re.search(r"ISLEM TARIHI (\d{2}/\d{2}/\d{4})", f)
    fis = re.search(r"FIS NO ?: ?(\d+)", f)
    if not when:
        raise ValueError("işlem tarihi bulunamadı")
    day = parse_dmy(when[1])
    key = f"qnb-{fis[1] if fis else doc.sha256}"
    holder = re.search(r"DEKONT\s+([A-ZÇĞİÖŞÜ ]+?)\s+(?:MUSTERI NO|[A-ZÇĞİÖŞÜ]+ MAH)", t)
    table = t[f.find("PARA CINSI TUTAR") + len("PARA CINSI TUTAR") :] if "PARA CINSI TUTAR" in f else t
    rows = [(m["desc"], m["ba"], m["cur"], parse_us_amount(m["amt"])) for m in _ROW.finditer(table)]
    result = ParseResult(parser=NAME, receipt_key=key, holder=holder[1] if holder else "")

    loan = re.search(r"(\d{5}-BT-\d+) REFERANSLI KREDI (\d{2}/\d{2}/\d{4}) TARIHLI TAKSIT ODEMESI", f)
    parts = re.search(r"ODENEN ANAPARA: ?([\d.,]+) FAIZ: ?([\d.,]+) KKDF: ?([\d.,]+) BSMV: ?([\d.,]+)", f)
    card = re.search(r"(\d{6})\*{6}(\d{4}) NOLU KART", f)

    if loan and parts:
        ref = loan[1]
        acct = Account(
            id=f"qnb-kredi-{ref[-4:]}",
            label=f"QNB İhtiyaç Kredisi …{ref[-4:]}",
            bank="QNB",
            type="Kredi",
            number=ref[-4:],
        )
        result.title = f"Kredi Taksiti {ref[-4:]}"
        principal = parse_us_amount(parts[1]) or 0.0
        cost = sum(parse_us_amount(parts[i]) or 0.0 for i in (2, 3, 4))
        result.accounts.append(acct)
        result.transactions += [
            Transaction(
                date=day,
                description=f"QNB ihtiyaç kredisi taksiti ({loan[2]}) — anapara",
                amount=round(principal, 2),
                kind="kredi_anapara",
                account=acct.id,
                source=doc.name,
            ),
            Transaction(
                date=day,
                description=f"QNB ihtiyaç kredisi taksiti ({loan[2]}) — faiz, KKDF, BSMV",
                amount=round(cost, 2),
                kind="faiz_ucret",
                account=acct.id,
                source=doc.name,
            ),
        ]
        return result

    if card and rows:
        last4 = card[2]
        acct = Account(
            id=f"qnb-{last4}",
            label=f"QNB Mastercard •{last4}",
            bank="QNB",
            type="Kredi kartı",
            number=last4,
        )
        result.title = f"Kart Ödemesi {last4}"
        result.accounts.append(acct)
        result.transactions.append(
            Transaction(
                date=day,
                description=f"QNB Mastercard •{last4} borç ödemesi",
                amount=rows[0][3],
                kind="ekstresiz_kart",
                account=acct.id,
                source=doc.name,
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
    for desc, ba, cur, amount in rows:
        if amount is None or cur != "TL":
            continue
        if "UCRET" in fold(desc):
            result.transactions.append(
                Transaction(
                    date=day,
                    description="QNB EFT ücreti",
                    amount=amount,
                    kind="faiz_ucret",
                    account=main.id,
                    source=doc.name,
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
                kind=CANDIDATE,
                account=main.id,
                counterparty=_other_side(desc, t, incoming),
                source=doc.name,
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
