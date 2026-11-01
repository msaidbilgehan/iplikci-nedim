"""İş Bankası e-cüzdan: the electronic passbook sent when an account (often a term deposit) is opened.

The first page names the account ("Hesap No: 1234-0765432", "Hesap Türü: Vadeli (31 gün)",
"Para Birimi: TL"), the second lists its movements newest first ("#", date and time, description,
"Yatan(+) / Çekilen(-) Tutar", "Kalan") — an account movement list like any other.
"""

import re
from decimal import Decimal

from ...domain.codes import AccountType, DocumentKind
from ...domain.models import ParseResult
from ...domain.text import fold
from ..accounts import bank_account, bank_from_iban
from ..common import BUSINESS_REASON, Skipped, is_business
from ..contract import Detection, Format, Probe, SourceDocument
from ..movements import Movement, build_statement
from ..pdf import Line, find_header, find_word, label_values, page_lines, take_amount
from ..text import parse_dmy, squash

ID = "isbank.passbook"
_ROW = re.compile(r"^(\d{2}/\d{2}/\d{4})-\d{2}:\d{2}:\d{2}$")


def _rows(lines: list[Line], holder: str) -> list[tuple[int, Movement]]:
    h = find_header(lines, "TARIH", "ACIKLAMA", "KALAN")
    if h is None:
        return []
    amount_edge, balance_edge = find_word(lines[h], "TUTAR").x1, find_word(lines[h], "KALAN").x1
    rows = []
    for line in lines[h + 1 :]:
        words = line.words
        if len(words) < 3 or not words[0].text.isdigit() or not _ROW.match(words[1].text):
            continue
        amount, used = take_amount(line, amount_edge)
        balance, _ = take_amount(line, balance_edge)
        if amount is None or balance is None:
            continue
        desc = " ".join(w.text for w in words[2:] if w.x1 <= used[0].x0)
        # "HESAP AÇMA İŞLEMİ 1234:0123456 -> 1234:0765432": money moved between the holder's own accounts.
        own = "->" in desc or "HESAP ACMA" in fold(desc)
        party = holder if own else ""
        rows.append(
            (int(words[0].text), Movement(parse_dmy(words[1].text), desc, amount, balance, "", party, line.ref))
        )
    return rows


def read(doc: SourceDocument) -> ParseResult:
    pdf = doc.pdf
    info = label_values(page_lines(pdf.pages[0]))
    holder = info.get("MUSTERI ADI / NUMARASI", "").split("/")[0].strip()  # "AD SOYAD / 111222333"
    if is_business(holder):
        raise Skipped(BUSINESS_REASON, business=True)
    number = re.search(r"\d{4}-\d{7}", info.get("HESAP NO", ""))
    currency = (info.get("PARA BIRIMI", "").split() or ["TL"])[0]
    opened = parse_dmy(info.get("ACILIS TARIHI", ""))
    if not number:
        raise ValueError("İş Bankası e-cüzdanında hesap numarası bulunamadı")
    kind = AccountType.DEPOSIT if "VADELI" in fold(info.get("HESAP TURU", "")) else None
    account = bank_account("İş Bankası", number[0], currency, kind)
    rows = [row for page in pdf.pages for row in _rows(page_lines(page), holder)]
    moves = [m for _, m in sorted(rows, key=lambda r: -r[0])]  # "#" counts from the newest
    if not moves:
        raise Skipped("e-cüzdanda hareket yok")
    start = min(opened or moves[0].date, moves[0].date)
    # A passbook that starts on the opening day starts from zero, so its first row is checked too.
    stmt = build_statement(
        doc,
        account,
        moves,
        start,
        moves[-1].date,
        oldest_first=True,
        opening=Decimal(0) if opened == moves[0].date else None,
    )
    stmt.one_off = True  # sent once: no monthly list follows it by e-mail
    return ParseResult(parser=ID, accounts=[account], statements=[stmt], holder=holder)


class Passbook:
    id = ID
    version = 2
    bank = "İş Bankası"
    name = "İş Bankası e-cüzdan"
    document_type = DocumentKind.ACCOUNT_STATEMENT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        iban = re.search(r"IBAN:(TR\d{24})", s)
        if "E-CUZDAN" in s and iban and bank_from_iban(iban[1]) == "İş Bankası":
            return Detection(1.0, "e-cüzdan başlığı ve İş Bankası IBAN'ı")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        return read(doc)


PARSER = Passbook()
