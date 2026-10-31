"""QNB PDF exports: credit card statements ("EKSTRE HAREKETLERİ") and account
movements ("Hesap Hareketleri").

QNB's fonts lack Unicode maps for Turkish letters, so pdfminer prints them as
"(cid:N)" or drops them. Merchant names are ASCII anyway; the few damaged
labels that matter for classification are repaired by pattern.
"""

import re

from ..models import Account, ParseResult, Statement, Transaction
from ..pdfutil import page_text
from ..textutil import fold, parse_dmy, parse_us_amount
from .common import classify_kind
from .hesap import Movement, bank_from_iban, build_statement

NAME = "QNB"
_CID = re.compile(r"\(cid:\d+\)")
_US = r"-?[\d,]+\.\d{2}"
_REPAIRS = (
    (re.compile(r"^\s*\S?deme\s*-\s*Tesekk\S*r\s+Ederiz\s*-?\s*$", re.IGNORECASE), "ÖDEME TEŞEKKÜR EDERİZ"),
    (re.compile(r"Al\S*ver\S*\s+faizi", re.IGNORECASE), "Alışveriş faizi"),
    (re.compile(r"Y\S*ll\S*k\s+\S*yelik\s+\S*creti", re.IGNORECASE), "Yıllık üyelik ücreti"),
    (re.compile(r"(?<![A-ZİŞĞÜÖÇ])STANBU"), "İSTANBU"),
)


def _clean(text: str) -> str:
    return _CID.sub("", text)


def _repair(desc: str) -> str:
    for rx, replacement in _REPAIRS:
        desc = rx.sub(replacement, desc)
    return desc.strip()


def detect_card(first_page: str) -> bool:
    return "QNB Kredi Kart" in first_page and "Kredi Kartı Numarası" in first_page


def detect_account(first_page: str) -> bool:
    iban = re.search(r"Iban\s*:\s*(TR[\d ]+)", first_page)
    return "Hesap Hareketleri" in first_page and bool(iban) and bank_from_iban(iban[1]) == "QNB"


def parse_card(doc, pdf) -> ParseResult:
    text = _clean("\n".join(page_text(p) for p in pdf.pages))
    card = re.search(r"Kredi Kartı Numarası\s*:\s*\d{4}\s*\d{2}\*\*\s*\*{4}\s*(\d{4})", text)
    cut = re.search(r"Hesap Kesim Tarihi\s*:\s*(\d{2}/\d{2}/\d{4})", text)
    previous = re.search(r"nceki\s+D\S*nem\s+Bakiyeniz\s+(" + _US + ")", text)
    total = re.search(r"Genel Toplam - TL Hesap Ekstresi\s+(" + _US + ")", text)
    if not (card and cut):
        raise ValueError("QNB kart numarası / hesap kesim tarihi bulunamadı")
    last4 = card[1]
    account = Account(id=f"qnb-{last4}", label=f"QNB Mastercard •{last4}", bank="QNB", type="Kredi kartı", number=last4)
    stmt = Statement(
        account=account.id,
        cut_date=parse_dmy(cut[1]),
        currency="TL",
        source=doc.name,
        previous=_us(previous),
        total=_us(total),
    )
    for line in text.splitlines():
        m = re.match(r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(" + _US + r")$", line.strip())
        if not m:
            continue
        desc, amount = _repair(m[2]), parse_us_amount(m[3].lstrip("-"))
        amount = -amount if m[3].startswith("-") else amount
        stmt.transactions.append(
            Transaction(
                date=parse_dmy(m[1]),
                description=desc,
                amount=amount,
                kind=classify_kind(desc, amount),
                account=account.id,
                source=doc.name,
            )
        )
    holder = re.search(r"Sn\.\s*([A-ZÇĞİÖŞÜa-zçğıöşü. ]+?)(?:\s{2,}|\n|$)", text)
    return ParseResult(parser=NAME, accounts=[account], statements=[stmt], holder=holder[1] if holder else "")


def _us(match) -> float | None:
    if not match:
        return None
    value = parse_us_amount(match[1].lstrip("-"))
    return -value if match[1].startswith("-") else value


_HEAD = re.compile(r"^Transfer İşlemleri\s*-\s*(Alıcı|Gönderen)\s*:")
_FOOTER = ("Sayfa", "Bu doküman", "*ŞB", "uyuşmaması", "Hesap Hareketleri")
_BANK_START = re.compile(
    r"\s+(?:Türk Ekonomi|Türkiye|QNB|Vakıf|Yapı|Enpara|ING|Kuveyt|Akbank|Ziraat|Halk|Deniz|Garanti|Odea|Fibabanka)\b"
)


def _counterparty(head: str) -> str:
    m = re.match(r"Transfer İşlemleri\s*-\s*(?:Alıcı|Gönderen)\s*:\s*(.+)", head)
    if not m:
        return ""
    name = m[1].split("Sorgu")[0]
    return _BANK_START.split(name)[0].strip()


def parse_account(doc, pdf) -> ParseResult:
    text = "\n".join(page_text(p) for p in pdf.pages)
    iban = re.search(r"Iban\s*:\s*(TR[\d ]+?)\s+Ad Soyad\s*:\s*(.+)", text)
    period = re.search(r"Tarih Aralığı\s*:\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})", text)
    opening = re.search(r"DEVREDEN BAKİYE\s+(" + _US + ")", text)
    name = re.search(r"Hesap Adı\s*:\s*(.+?)(?:\s{2,}|Tckn|$)", text, re.MULTILINE)
    if not (iban and period):
        raise ValueError("QNB hesap bilgisi okunamadı")
    number = re.sub(r"\D", "", iban[1])[-16:].lstrip("0")
    overdraft = name and "EK HESAP" in fold(name[1])
    account = Account(
        id=f"qnb-{number}",
        label=f"QNB {'Ek Hesap' if overdraft else 'Vadesiz TL'} {number}",
        bank="QNB",
        type="Ek hesap (KMH)" if overdraft else "Vadesiz hesap",
        number=number,
    )
    moves: list[Movement] = []
    head = ""
    last_from_head = False
    for raw in text.splitlines():
        line = raw.strip()
        m = re.match(r"^(\d{2}/\d{2}/\d{4})\s+(\S+)\s*(.*?)\s*(" + _US + r")\s+(" + _US + r")$", line)
        if m:
            desc = m[3] or head
            moves.append(
                Movement(
                    parse_dmy(m[1]),
                    desc,
                    _us_signed(m[4]),
                    _us_signed(m[5]),
                    m[2],
                    _counterparty(head) if not m[3] else "",
                )
            )
            last_from_head, head = not m[3] and bool(head), ""
        elif _HEAD.match(line):
            head = line
        elif last_from_head and moves and line and not line.startswith(_FOOTER) and len(line) > 2:
            moves[-1].description += " " + line  # continuation of a wrapped transfer description
        else:
            last_from_head = False
    stmt = build_statement(
        doc,
        account,
        moves,
        parse_dmy(period[1]),
        parse_dmy(period[2]),
        oldest_first=True,
        opening=_us_signed(opening[1]) if opening else None,
    )
    return ParseResult(parser=NAME, accounts=[account], statements=[stmt], holder=iban[2].strip())


def _us_signed(text: str) -> float:
    value = parse_us_amount(text.lstrip("-"))
    return -value if text.startswith("-") else value
