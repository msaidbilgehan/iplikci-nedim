"""Vakıfbank e-cüzdan: the electronic passbook sent when an account is opened.

The first page holds the deposit terms only; a later page names the account ("Hesap No",
"IBAN", "Hesap Türü / Para Birimi : BİREYSEL VADESİZ / USD", "Rumuz") and lists its movements
oldest first ("NO", "İŞLEM TARİHİ", "İŞLEM TUTARI", "BAKİYE", "AÇIKLAMA").
"""

import re
from decimal import Decimal

from ...domain.codes import AccountType, DocumentKind
from ...domain.models import ParseResult
from ...domain.text import fold
from ..accounts import bank_account
from ..common import BUSINESS_REASON, Skipped, is_business
from ..contract import Detection, Format, Probe, SourceDocument
from ..movements import Movement, build_statement
from ..pdf import label_values, page_lines, page_text
from ..text import parse_dmy, parse_tr_amount, squash

ID = "vakifbank.passbook"


def read(doc: SourceDocument) -> ParseResult:
    page = next((p for p in doc.pdf.pages if "CUZDAN SERI NO" in fold(page_text(p))), None)
    if page is None:
        raise Skipped("e-cüzdanda hesap bilgisi yok")
    lines = page_lines(page)
    info = label_values(lines)
    holder = info.get("HESAP SAHIBI", "")
    if is_business(holder):
        raise Skipped(BUSINESS_REASON, business=True)
    iban = re.sub(r"\s", "", info.get("IBAN", ""))
    kind, _, currency = (part.strip() for part in fold(info.get("HESAP TURU / PARA BIRIMI", "")).partition("/"))
    if len(iban) < 16 or not currency:
        raise ValueError("Vakıfbank e-cüzdanında IBAN ya da para birimi bulunamadı")
    account = bank_account(
        "Vakıfbank",
        iban[-16:],
        currency,
        AccountType.DEPOSIT if "VADELI" in kind else None,
    )
    nickname = info.get("RUMUZ", "")
    if nickname:
        account.label += f" ({nickname})"
    moves = []
    for line in lines:
        words = [w.text for w in line.words]
        if len(words) < 4 or not words[0].isdigit() or not parse_dmy(words[1]):
            continue
        # NO, date, amount and balance, then the description.
        amount, balance = parse_tr_amount(words[2]), parse_tr_amount(words[3])
        if amount is None or balance is None:
            continue
        moves.append(Movement(parse_dmy(words[1]), " ".join(words[4:]), amount, balance, ref=line.ref))
    if not moves:
        raise Skipped("e-cüzdanda hareket yok")
    opened = parse_dmy(info.get("HESAP ACILIS TARIHI", ""))
    issued = parse_dmy(info.get("ISLEM TARIHI", "")) or moves[-1].date
    # A passbook that starts on the opening day starts from zero, so its first row is checked too.
    stmt = build_statement(
        doc,
        account,
        moves,
        min(opened or moves[0].date, moves[0].date),
        max(issued, moves[-1].date),
        oldest_first=True,
        opening=Decimal(0) if opened == moves[0].date else None,
    )
    stmt.one_off = True  # sent once: no monthly list follows it by e-mail
    return ParseResult(parser=ID, accounts=[account], statements=[stmt], holder=holder)


class Passbook:
    id = ID
    version = 3
    bank = "Vakıfbank"
    name = "Vakıfbank e-cüzdan"
    document_type = DocumentKind.ACCOUNT_STATEMENT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        if "VAKIFBANK.COM.TR" in s and "CUZDAN" in s and "TASARRUFMEVDUATI" in s:
            return Detection(1.0, "vakifbank.com.tr, cüzdan ve tasarruf mevduatı")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = Passbook()
