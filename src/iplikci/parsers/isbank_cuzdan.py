"""İş Bankası e-cüzdan: the electronic passbook sent when an account (often a term deposit) is opened.

The first page names the account ("Hesap No: 1234-0765432", "Hesap Türü: Vadeli (31 gün)",
"Para Birimi: TL"), the second lists its movements newest first ("#", date and time, description,
"Yatan(+) / Çekilen(-) Tutar", "Kalan") — an account movement list like any other.
"""

import re

from ..domain.codes import AccountType
from ..domain.models import ParseResult
from ..pdfutil import Line, find_header, find_word, label_values, page_lines, take_amount
from ..textutil import fold, parse_dmy, squash
from .common import BUSINESS_REASON, Skipped, is_business
from .hesap import Movement, bank_from_iban, build_statement
from .hesaplar import bank_account

NAME = "İş Bankası e-cüzdan"
_ROW = re.compile(r"^(\d{2}/\d{2}/\d{4})-\d{2}:\d{2}:\d{2}$")


def detect(first_page: str) -> bool:
    s = squash(first_page)
    iban = re.search(r"IBAN:(TR\d{24})", s)
    return "E-CUZDAN" in s and bool(iban) and bank_from_iban(iban[1]) == "İş Bankası"


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
        rows.append(
            (int(words[0].text), Movement(parse_dmy(words[1].text), desc, amount, balance, "", holder if own else ""))
        )
    return rows


def parse(doc, pdf) -> ParseResult:
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
        doc, account, moves, start, moves[-1].date, oldest_first=True, opening=0.0 if opened == moves[0].date else None
    )
    return ParseResult(parser=NAME, accounts=[account], statements=[stmt], holder=holder)
