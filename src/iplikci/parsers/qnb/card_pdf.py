"""QNB credit card statements as PDF exports ("EKSTRE HAREKETLERİ").

QNB's fonts lack Unicode maps for Turkish letters, so pdfminer prints them as
"(cid:N)" or drops them. Merchant names are ASCII anyway; the few damaged
labels that matter for classification are repaired by pattern.
"""

import re
from datetime import date
from decimal import Decimal

from ...domain.codes import AccountType, DocumentKind
from ...domain.models import TRY, Account, ParseResult, SourceRef, Statement, Transaction
from ...domain.text import fold
from ..common import agreed, classify_kind, next_cut
from ..contract import Detection, Format, Probe, SourceDocument
from ..pdf import numbered_lines, page_text
from ..text import TR_MONTHS, parse_dmy, parse_tr_words_date
from ._amounts import US_AMOUNT, us_signed

ID = "qnb.card_pdf"
_CID = re.compile(r"\(cid:\d+\)")
# This statement's due date, spelled out beside the card's number: "Son Ödeme Tarihi: 28 Ağustos 2026, Cuma". The font
# loses the Ö and the month's Turkish letters, a (cid:N) for each, so it is read from the text as the font leaves it.
# A statement with nothing to pay prints none.
_DUE = re.compile(r"Son\s+(?:\(cid:\d+\)|Ö)?deme\s+Tarihi\s*:\s*(\d{1,2})\s+((?:\(cid:\d+\)|\w)+)\s+(\d{4})")
# The next statement's cut, in the note under the summary: "* Bir sonraki hesap kesim tarihiniz 18/11/2026, bir sonraki
# son ödeme tarihiniz 30/11/2026".
_NEXT_CUT = re.compile(r"Bir\s+sonraki\s+hesap\s+kesim\s+tarihiniz\s+(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
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


def _spelled(day: str, month: str, year: str) -> date | None:
    """A date QNB spells out, its month's name as the font leaves it: a (cid:N) for each letter it lost
    ("A(cid:6)ustos")."""
    pattern = ".".join(re.escape(fold(part)) for part in _CID.split(month))
    found = [name for name in TR_MONTHS if re.fullmatch(pattern, name)]
    return parse_tr_words_date(day, found[0], year) if len(found) == 1 else None


def read(doc: SourceDocument) -> ParseResult:
    raw = [page_text(p) for p in doc.pdf.pages]
    pages = [_clean(t) for t in raw]
    text = "\n".join(pages)
    card = re.search(r"Kredi Kartı Numarası\s*:\s*\d{4}\s*\d{2}\*\*\s*\*{4}\s*(\d{4})", text)
    cut = re.search(r"Hesap Kesim Tarihi\s*:\s*(\d{2}/\d{2}/\d{4})", text)
    previous = re.search(r"nceki\s+D\S*nem\s+Bakiyeniz\s+(" + US_AMOUNT + ")", text)
    total = re.search(r"Genel Toplam - TL Hesap Ekstresi\s+(" + US_AMOUNT + ")", text)
    if not (card and cut):
        raise ValueError("QNB kart numarası / hesap kesim tarihi bulunamadı")
    last4 = card[1]
    account = Account(
        id=f"qnb-{last4}", label=f"QNB Mastercard •{last4}", bank="QNB", type=AccountType.CREDIT_CARD, number=last4
    )
    cut_date = parse_dmy(cut[1])
    if cut_date is None:
        raise ValueError(f"QNB hesap kesim tarihi okunamadı: {cut[1]}")
    stmt = Statement(
        account=account.id,
        cut_date=cut_date,
        currency=TRY,
        source=doc.name,
        previous=_us(previous),
        total=_us(total),
        # The minimum payment and the limit are not read yet.
        due_date=agreed(_spelled(*m) for m in _DUE.findall("\n".join(raw))),
        next_cut=next_cut(cut_date, (parse_dmy(d) for d in _NEXT_CUT.findall(text))),
    )
    for page, number, line in numbered_lines(pages):
        m = re.match(r"^(\d{2}/\d{2}/\d{4})\s+(.+?)\s+(" + US_AMOUNT + r")$", line.strip())
        if not m:
            continue
        desc, amount = _repair(m[2]), us_signed(m[3])
        stmt.transactions.append(
            Transaction(
                date=parse_dmy(m[1]),
                description=desc,
                amount=amount,
                kind=classify_kind(desc, amount),
                account=account.id,
                source=doc.name,
                ref=SourceRef(page=page, line=number),
            )
        )
    holder = re.search(r"Sn\.\s*([A-ZÇĞİÖŞÜa-zçğıöşü. ]+?)(?:\s{2,}|\n|$)", text)
    return ParseResult(parser=ID, accounts=[account], statements=[stmt], holder=holder[1] if holder else "")


def _us(match: re.Match[str] | None) -> Decimal | None:
    return us_signed(match[1]) if match else None


class CardPdf:
    id = ID
    version = 3
    bank = "QNB"
    name = "QNB kredi kartı ekstre hareketleri (PDF)"
    document_type = DocumentKind.CARD_STATEMENT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        if "QNB Kredi Kart" in probe.text and "Kredi Kartı Numarası" in probe.text:
            return Detection(1.0, '"QNB Kredi Kart" ve kart numarası')
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = CardPdf()
