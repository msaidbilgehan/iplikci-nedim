"""QNB account movements as PDF exports ("Hesap Hareketleri"): current and overdraft (Ek Hesap) accounts."""

import re

from ...domain.codes import AccountType, DocumentKind
from ...domain.models import Account, ParseResult, SourceRef
from ...domain.text import fold
from ..accounts import bank_from_iban
from ..contract import Detection, Format, Probe, SourceDocument
from ..movements import Movement, build_statement
from ..pdf import numbered_lines, page_text
from ..text import parse_dmy
from ._amounts import US_AMOUNT, us_signed

ID = "qnb.account_pdf"

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


def read(doc: SourceDocument) -> ParseResult:
    pages = [page_text(p) for p in doc.pdf.pages]
    text = "\n".join(pages)
    iban = re.search(r"Iban\s*:\s*(TR[\d ]+?)\s+Ad Soyad\s*:\s*(.+)", text)
    period = re.search(r"Tarih Aralığı\s*:\s*(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})", text)
    opening = re.search(r"DEVREDEN BAKİYE\s+(" + US_AMOUNT + ")", text)
    name = re.search(r"Hesap Adı\s*:\s*(.+?)(?:\s{2,}|Tckn|$)", text, re.MULTILINE)
    if not (iban and period):
        raise ValueError("QNB hesap bilgisi okunamadı")
    number = re.sub(r"\D", "", iban[1])[-16:].lstrip("0")
    overdraft = name and "EK HESAP" in fold(name[1])
    account = Account(
        id=f"qnb-{number}",
        label=f"QNB {'Ek Hesap' if overdraft else 'Vadesiz TL'} {number}",
        bank="QNB",
        type=AccountType.OVERDRAFT if overdraft else AccountType.CURRENT,
        number=number,
    )
    moves: list[Movement] = []
    head = ""
    last_from_head = False
    for page, number, raw in numbered_lines(pages):
        line = raw.strip()
        m = re.match(r"^(\d{2}/\d{2}/\d{4})\s+(\S+)\s*(.*?)\s*(" + US_AMOUNT + r")\s+(" + US_AMOUNT + r")$", line)
        if m:
            desc = m[3] or head
            moves.append(
                Movement(
                    parse_dmy(m[1]),
                    desc,
                    us_signed(m[4]),
                    us_signed(m[5]),
                    m[2],
                    _counterparty(head) if not m[3] else "",
                    SourceRef(page=page, line=number),
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
        opening=us_signed(opening[1]) if opening else None,
    )
    return ParseResult(parser=ID, accounts=[account], statements=[stmt], holder=iban[2].strip())


class AccountPdf:
    id = ID
    version = 1
    bank = "QNB"
    name = "QNB hesap hareketleri (PDF)"
    document_type = DocumentKind.ACCOUNT_STATEMENT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        iban = re.search(r"Iban\s*:\s*(TR[\d ]+)", probe.text)
        if "Hesap Hareketleri" in probe.text and iban and bank_from_iban(iban[1]) == "QNB":
            return Detection(1.0, '"Hesap Hareketleri" ve QNB IBAN\'ı')
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = AccountPdf()
