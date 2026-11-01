"""Garanti BBVA Yatırım: monthly stock account statements and trade result forms.

The statement ("Hesap Durumu", one per emanet account and month) prints the cash balance and
every security held at its market value; months with activity add a page of security moves and
one of cash moves ("Hesap Ekstresi": Tarih, Açıklama, İşlem, Kalan — US number format). The cash
only passes through: sale proceeds, dividends and fee money move to or from the user's bank
account the same day ("... Nolu Hesabın Banka Takas İşlemi").

The trade result form ("İşlem Sonuç Formu") lists the trades of a day and the fees charged
(Turkish number format with three decimals). A form is a receipt: it adds rows only for months
no statement of that emanet account covers.
"""

import calendar
import re
from datetime import date
from decimal import Decimal

from ...domain.codes import AccountType, DocumentKind, TransactionKind
from ...domain.models import TRY, Account, ParseResult, Security, Statement, Transaction
from ...domain.money import TOLERANCE, round_half_up
from ...domain.text import fold
from ..common import BUSINESS_REASON, Skipped, is_business
from ..contract import Detection, Format, Probe, SourceDocument
from ..movements import Movement, check_balances, month_end_balances
from ..pdf import Line, page_lines
from ..text import parse_dmy, parse_us_amount, squash

ID = "garanti.brokerage"
_HOLDER_X = 300  # the customer's name and address are printed right of this
_CHANGE_X1, _BALANCE_X1 = 445, 550  # right edges of the "İşlem" and "Kalan" columns of cash moves


def _account(number: str) -> Account:
    return Account(
        id=f"garanti-yatirim-{number}",
        label=f"Garanti BBVA Yatırım {number}",
        bank="Garanti BBVA",
        type=AccountType.BROKERAGE,
        number=number,
    )


def _us(text: str) -> Decimal | None:
    """'+123.40', '-0.12', '2,345.00', '20.000'."""
    value = parse_us_amount(text.lstrip("+-"))
    return -value if value is not None and text.startswith("-") else value


def _tr3(text: str) -> Decimal | None:
    """Turkish format with up to three decimals, as the trade form prints it: '1.234,560', '12,000'."""
    m = re.fullmatch(r"(\d{1,3}(?:\.\d{3})*|\d+),(\d{1,3})", text.strip())
    return Decimal(f"{m[1].replace('.', '')}.{m[2]}") if m else None


def _count(quantity: Decimal | float) -> str:
    return f"{float(quantity):g}".replace(".", ",")  # in a description only: "10 adet", "2,5 adet"


def _price(value: Decimal | float) -> str:
    return f"{float(value):.2f}".replace(".", ",")


# --- monthly statement ----------------------------------------------------------------------------


def _page_kind(lines: list[Line]) -> str:
    head = " ".join(line.folded for line in lines[:4])
    if "HESAP EKSTRESI" in head:
        return "nakit"
    if "HAREKET LISTESI" in head:
        return "menkul"
    return "durum"


def _securities(lines: list[Line], as_of: date) -> tuple[list[Security], list[Decimal]]:
    """Securities rows ("HS ORNEK ÖRNEK SANAYİ ... 20.000 1,234.50 0.000") and the group totals printed
    under them ("Hisse toplamı : 20.000 1,234.50 0.000")."""
    held, totals = [], []
    top = next((i for i, line in enumerate(lines) if "MEVCUT MENKUL KIYMETLER" in line.folded), None)
    end = next((i for i, line in enumerate(lines) if "TOPLAMI(TL" in line.folded.replace(" ", "")), len(lines))
    for line in lines[top + 1 : end] if top is not None else []:
        words = line.words
        value = next((_us(w.text) for w in words if 400 <= w.x0 < 480 and _us(w.text) is not None), None)
        if value is None:
            continue
        if any(fold(w.text) in ("TOPLAMI", "TOPLAM") for w in words):
            totals.append(value)
            continue
        if len(words) < 3 or not re.fullmatch(r"[A-Z]{2}", words[0].text) or words[0].x0 > 70:
            continue
        quantity = next((_us(w.text) for w in words if 300 <= w.x0 < 400 and _us(w.text) is not None), None)
        name = " ".join(w.text for w in words[2:] if w.x0 < 300)
        held.append(Security(words[1].text, name, quantity or Decimal(0), value, as_of))
    return held, totals


def _portfolio_total(lines: list[Line]) -> Decimal | None:
    """'Portföy toplamı(TL ) :' — its value is printed lower, at the right edge, often inside a footer line."""
    label = next((i for i, line in enumerate(lines) if "TOPLAMI(TL" in line.folded.replace(" ", "")), None)
    for line in lines[label + 1 :] if label is not None else []:
        value = next((_us(w.text) for w in line.words if w.x0 >= 500 and _us(w.text) is not None), None)
        if value is not None:
            return value
    return None


def _cash_moves(lines: list[Line]) -> list[Movement]:
    moves = []
    for line in lines:
        words = line.words
        day = parse_dmy(words[0].text) if words and words[0].x0 < 60 else None
        change = next((w for w in words if abs(w.x1 - _CHANGE_X1) < 8 and w.text[:1] in "+-"), None)
        balance = next((w for w in words if abs(w.x1 - _BALANCE_X1) < 8 and _us(w.text) is not None), None)
        if not (day and change and balance) or _us(change.text) is None:
            continue
        desc = " ".join(w.text for w in words[1:] if w.x1 <= change.x0)
        moves.append(Movement(day, desc, _us(change.text), _us(balance.text)))
    return moves


def _kind(m: Movement) -> tuple[TransactionKind, str]:
    """(kind, description) of a cash move; the bank side of a move is left to analysis.py."""
    f = fold(m.description)
    dividend = re.match(r"(\w+)\.E TEMETTU (\d+) ADET", f)
    trade = re.search(r"HS ([\d.]+)X([\d.]+) (\w+)", f)
    if dividend and m.amount > 0:
        return TransactionKind.INCOME, f"{dividend[1]} temettüsü ({dividend[2]} adet)"
    if trade:
        side = "satışı" if m.amount > 0 else "alışı"
        return (
            TransactionKind.INVESTMENT,
            f"Hisse {side}: {trade[3]} {_count(float(trade[2]))} adet × {_price(float(trade[1]))} TL",
        )
    if "KOMISYON" in f:
        return TransactionKind.INTEREST_FEE, "Hisse işlem komisyonu"
    if "MKK" in f and m.amount < 0 or any(p in f for p in ("UCRET", "STOPAJ", "VERGI")):
        return TransactionKind.INTEREST_FEE, m.description  # MKK fees, a dividend's withholding tax
    return TransactionKind.TRANSFER_CANDIDATE, m.description


def _statement(doc: SourceDocument, first: list[Line]) -> ParseResult:
    text = " ".join(line.folded for line in first)
    number = re.search(r"EMANET NO : (\d+-\d+)", text)
    printed = re.search(r"\bTARIH : (\d{2}/\d{2}/\d{4})", text)
    if not (number and printed):
        raise ValueError("Garanti Yatırım ekstresinde emanet numarası ya da tarih bulunamadı")
    holder = next(
        (
            " ".join(w.text for w in line.words if w.x0 >= _HOLDER_X)
            for line in first
            if line.folded.startswith("TARIH :")
        ),
        "",
    )
    if is_business(holder):
        raise Skipped(BUSINESS_REASON, business=True)
    day = parse_dmy(printed[1])
    # The statement is dated the month's last business day; it covers the whole calendar month.
    start, end = day.replace(day=1), day.replace(day=calendar.monthrange(day.year, day.month)[1])
    account = _account(number[1])
    cash_line = next((i for i, line in enumerate(first) if line.folded.startswith("MEVCUDU")), None)
    cash = (
        next((_us(w.text) for w in first[cash_line + 1].words if _us(w.text) is not None), None)
        if cash_line is not None and cash_line + 1 < len(first)
        else None
    )
    held, totals, moves = [], [], []
    for page in doc.pdf.pages:
        lines = page_lines(page)
        kind = _page_kind(lines)
        if kind == "durum":
            found, sums = _securities(lines, day)
            held += found
            totals += sums
        elif kind == "nakit":
            moves += _cash_moves(lines)
    if cash is None:
        raise ValueError("Garanti Yatırım ekstresinde nakit bakiye bulunamadı")
    # The first cash move is the carried-over balance ("Devir ... Cari TRY Bakiye Hareketleri").
    opening = cash
    if moves and "DEVIR" in fold(moves[0].description):
        opening = round_half_up(moves[0].balance - moves[0].amount)
        moves = moves[1:]
    ok, checks = check_balances(moves, oldest_first=True, opening=opening)
    # The parse is checked against what the statement prints: the closing cash, the securities total and
    # the portfolio total (securities plus cash).
    worth = round_half_up(sum((s.value for s in held), Decimal(0)))
    portfolio = _portfolio_total(first)
    expected = [(round_half_up(opening + sum((m.amount for m in moves), Decimal(0))), cash)]
    expected += [(worth, totals[-1] if len(totals) == 1 else round_half_up(sum(totals, Decimal(0))))] if totals else []
    expected += [(round_half_up(worth + cash), portfolio)] if portfolio is not None else []
    ok += sum(abs(a - b) <= TOLERANCE for a, b in expected)
    stmt = Statement(
        account=account.id,
        cut_date=end,
        currency=TRY,
        source=doc.name,
        previous=opening,
        total=cash,
        start=start,
        checks_ok=ok,
        checks_total=checks + len(expected),
        balances=month_end_balances(moves, oldest_first=True) or {f"{end:%Y-%m}": cash},
        securities=held,
    )
    for m in moves:
        kind, desc = _kind(m)
        stmt.transactions.append(
            Transaction(
                date=m.date,
                description=desc,
                amount=-m.amount,
                kind=kind,
                account=account.id,
                source=doc.name,
                # Proceeds, dividends and fee money moved to or from the user's bank account: their own transfer.
                counterparty=holder
                if kind == TransactionKind.TRANSFER_CANDIDATE
                and any(p in fold(m.description) for p in ("NOLU HESABIN BANKA", "TEMETTU"))
                else "",
            )
        )
    return ParseResult(parser=ID, accounts=[account], statements=[stmt], holder=holder)


# --- trade result form --------------------------------------------------------------------------------


def _form(doc: SourceDocument, lines: list[Line]) -> ParseResult:
    text = " ".join(line.folded for line in lines)
    number = re.search(r"MUSTERI NO : (\d+-\d+)", text)
    day = re.search(r"AIT OLDUGU TARIH : (\d{2}\.\d{2}\.\d{4})", text)
    sequence = re.search(r"BELGE SIRA NO : (\d+)", text)
    named = next((line for line in lines if line.folded.startswith("MUSTERI ADI")), None)
    colon = next((w.x1 for w in named.words if w.text == ":"), 0.0) if named else 0.0
    total = re.search(r"GENEL TOPLAM ([\d.]+,\d{1,3})", text)
    if not (number and day):
        raise ValueError("işlem sonuç formunda müşteri numarası ya da tarih bulunamadı")
    # "Müşteri Adı : AD SOYAD" on the left, "Şube : ..." from the middle of the page on.
    holder_name = " ".join(w.text for w in named.words if colon < w.x0 < _HOLDER_X) if named else ""
    if is_business(holder_name):
        raise Skipped(BUSINESS_REASON, business=True)
    account = _account(number[1])
    when = parse_dmy(day[1])
    result = ParseResult(
        parser=ID,
        accounts=[account],
        holder=holder_name,
        title="Hisse İşlemi",
        receipt_key=f"garanti-yatirim-form-{sequence[1] if sequence else doc.sha256}",
    )
    for line in lines:
        words = [w.text for w in line.words]
        if len(words) < 6 or not parse_dmy(words[0]) or fold(words[2]) not in ("SATIS", "ALIS"):
            continue
        quantity, price, amount = (_tr3(w) for w in words[3:6])
        if amount is None:
            continue
        sale = fold(words[2]) == "SATIS"
        result.transactions.append(
            Transaction(
                date=parse_dmy(words[0]),
                amount=-amount if sale else amount,
                kind=TransactionKind.INVESTMENT,
                account=account.id,
                description=f"Hisse {'satışı' if sale else 'alışı'}: {words[1]} {_count(quantity or 0)} adet × "
                f"{_price(price or 0)} TL",
                source=doc.name,
            )
        )
    fees = _tr3(total[1]) if total else None
    if fees:
        result.transactions.append(
            Transaction(
                date=when,
                description="Hisse senedi komisyon ve MKK ücretleri",
                amount=round_half_up(fees),
                kind=TransactionKind.INTEREST_FEE,
                account=account.id,
                source=doc.name,
            )
        )
    if not result.transactions:
        raise Skipped("işlem sonuç formunda tutar yok")
    return result


class Brokerage:
    id = ID
    version = 1
    bank = "Garanti BBVA"
    name = "Garanti BBVA Yatırım hesap ekstresi ve işlem sonuç formu"
    document_type = DocumentKind.ACCOUNT_STATEMENT
    formats = frozenset({Format.PDF})

    def detect(self, probe: Probe) -> Detection | None:
        s = squash(probe.text)
        brokerage = "GARANTIBBVAYATIRIM" in s or "GARANTIYATIRIMMENKUL" in s
        if brokerage and ("EMANETNO" in s or "ISLEMSONUCFORMU" in s):
            return Detection(1.0, "Garanti BBVA Yatırım adı ile emanet no ya da işlem sonuç formu")
        return None

    def parse(self, doc: SourceDocument) -> ParseResult:
        first = page_lines(doc.pdf.pages[0])
        if "ISLEMSONUCFORMU" in squash(" ".join(line.text for line in first)):
            return _form(doc, first)
        return _statement(doc, first)


PARSER = Brokerage()
