"""İş Bankası's documents: the Maximum card statement and the account list."""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

from ..domain.labels import format_amount
from . import HOLDER, CardRow, Move, charged, with_balances
from .files import Cell, Run, right, text_pdf, xls_file

_DATE_X, _TEXT_X, _AMOUNT_X1, _INSTALLMENT_X, _POINTS_X = 40, 100, 400, 410, 520
_LINE = 11

# A Maximum card's month: a payment, purchases, an installment, an installment cash advance whose interest
# breakdown wraps onto the next line, its fee, a cancelled purchase and a line that only reports MaxiPuan.
MAXIMUM_PAGES: tuple[tuple[CardRow, ...], ...] = (
    (
        CardRow(date(2026, 9, 12), "9999-1234567 HESAPTAN AKTARIM İNTERAKTİF", Decimal(-3250)),
        CardRow(date(2026, 9, 14), "MIGROS ORNEK SUBE ISTANBUL", Decimal("1245.60")),
        CardRow(date(2026, 9, 16), "TEKNOSA ORNEK AVM", Decimal(500), "2/6 taksidi (3.000,00)"),
        CardRow(date(2026, 9, 19), "TAKSİTLİ NAKİT AVANS - HESABA HAVALE KALAN:3.000,00", Decimal(1500)),
        CardRow(None, "FZ:120.00 VR/FN:36.00"),
        CardRow(date(2026, 9, 19), "NAKİT AVANS ÜCRETİ", Decimal("34.50")),
        CardRow(date(2026, 9, 23), "ORNEK PETROL ISTANBUL TR İŞLEM İPTALI", Decimal("-234.56")),
        CardRow(date(2026, 9, 26), "BU DÖNEM 125 MAXIPUAN KAZANDINIZ"),
        CardRow(date(2026, 10, 2), "SPOTIFY ISTANBUL TR", Decimal("99.99")),
    ),
)


def maximum_statement(
    pages: Sequence[Sequence[CardRow]] = MAXIMUM_PAGES,
    cut: date = date(2026, 10, 5),
    previous: Decimal = Decimal(3250),
    last4: str = "1234",
    holder: str = HOLDER,
) -> bytes:
    """An İş Bankası Maximum card statement ("Kredi Kartı Hesap Özeti"): the previous debt, the rows page by page,
    and the debt they add up to. A fold mark sits in the left margin of every page."""
    total = previous + sum((charged(p) for p in pages), Decimal(0))
    summary: list[Run] = [
        (40, 40, "TÜRKİYE İŞ BANKASI A.Ş."),
        (40, 52, "Kredi Kartı Hesap Özeti"),
        (40, 100, f"SN. {holder}"),
        (40, 112, f"Hesap Kesim Tarihi: {cut:%d/%m/%Y}"),
        (330, 112, f"Kart Numarası: 4543 **** **** {last4}"),
        (40, 124, f"Son Ödeme Tarihi: {cut + timedelta(days=10):%d/%m/%Y}"),
        (330, 124, f"Hesap Özeti Borcu: {_amount(total)} TL"),
        (40, 136, f"Sonraki Hesap Kesim Tarihi: {cut + timedelta(days=31):%d/%m/%Y}"),
        (330, 136, f"Asgari Ödeme Tutarı: {format_amount(total * Decimal('0.4'))} TL"),
    ]
    out: list[list[Run]] = []
    for i, rows in enumerate(pages):
        top = 200 if i == 0 else 60
        runs = [*(summary if i == 0 else []), (12, 420, "-"), *_table(top, rows)]
        if i == 0:
            runs += [
                (_DATE_X, top + 3 + _LINE, "*** ÖNCEKİ DÖNEM BORCU"),
                right(_AMOUNT_X1, top + 3 + _LINE, _amount(previous)),
            ]
        out.append(runs)
    return text_pdf(*out)


def _amount(value: Decimal) -> str:
    """As İş Bankası prints an amount: a credit with a leading plus ("+3.250,00")."""
    return ("+" if value < 0 else "") + format_amount(abs(value))


def _table(top: float, rows: Sequence[CardRow]) -> list[Run]:
    """A page's table; on the first page the previous debt takes the row under the header."""
    runs: list[Run] = [
        (_DATE_X, top, "Tarih"),
        (_TEXT_X, top, "Açıklama"),
        right(_AMOUNT_X1, top, "Tutar"),
        (_INSTALLMENT_X, top, "Taksit"),
        (_POINTS_X, top, "MaxiPuan"),
    ]
    for n, row in enumerate(rows, 2):
        y = top + 3 + n * _LINE
        if row.day is not None:
            runs.append((_DATE_X, y, f"{row.day:%d/%m/%Y}"))
        runs.append((_TEXT_X, y, row.text))
        if row.amount is not None:
            runs.append(right(_AMOUNT_X1, y, _amount(row.amount)))
            if row.amount > 0:
                runs.append((_POINTS_X, y, format_amount(row.amount * Decimal("0.002"))))
        if row.extra:
            runs.append((_INSTALLMENT_X, y, row.extra))
    return runs


# --- account lists --------------------------------------------------------------------------------------------

# A month on a current account: salary, rent sent by FAST ("AD*" before the note) with its fee, a card payment,
# money back by havale and a debit card purchase, each with the bank's transaction type.
ACCOUNT_MOVES: tuple[tuple[Move, str], ...] = (
    (Move(date(2026, 10, 1), "ÖRNEK İŞVEREN A.Ş. MAAŞ ÖDEMESİ", Decimal(40000)), "Maaş"),
    (Move(date(2026, 10, 3), "VELİ ÖRNEKSOY*EKİM KİRA ÖDEMESİ", Decimal(-15000)), "FAST"),
    (Move(date(2026, 10, 3), "FAST ÜCRETİ", Decimal("-8.86")), "Ücret"),
    (Move(date(2026, 10, 12), "KREDİ KARTI ÖDEMESİ 4543****1234", Decimal(-3250)), "Ödeme"),
    (Move(date(2026, 10, 18), "AYŞE SOYADOĞLU*BORÇ İADESİ", Decimal(2500)), "Havale"),
    (Move(date(2026, 10, 25), "ORNEK MARKET UMRANIYE", Decimal("-312.40")), "Alışveriş"),
)


def account_xls(
    moves: Sequence[tuple[Move, str]] = ACCOUNT_MOVES,
    opening: Decimal = Decimal(1000),
    holder: str = HOLDER,
    period: tuple[date, date] = (date(2026, 10, 1), date(2026, 10, 31)),
) -> bytes:
    """An İş Bankası "Hesap Özeti" export (XLS) of account 1234-0123456: the holder and the account above a table
    of rows, newest first. The text column has an empty neighbour before the reference; the reader joins the
    cells between the two headings."""
    balanced = with_balances([m for m, _ in moves], opening)
    head: list[list[Cell]] = [
        ["TÜRKİYE İŞ BANKASI A.Ş."],
        ["Hesap Özeti"],
        [f"Sayın {holder}"],
        ["Ürün-Döviz Tipi", "Vadesiz - TL", "IBAN", "TR00 0006 4000 0011 2340 1234 56"],
        ["Mevcut Bakiye", f"{format_amount(balanced[-1][1] if balanced else opening)} TL"],
        ["Sorgulama Kriterleri", f"{period[0]:%d.%m.%Y} - {period[1]:%d.%m.%Y}"],
        [],
        ["Tarih/Saat", "İşlem Tipi", "İşlem Tutarı*", "Bakiye", "Açıklama", None, "Referans"],
    ]
    rows: list[list[Cell]] = [
        [f"{m.day:%d/%m/%Y}-10:00:00", kind, float(m.amount), float(balance), m.text, None, f"{n:08d}"]
        for n, ((m, balance), (_, kind)) in enumerate(zip(balanced, moves, strict=True), 1)
    ]
    return xls_file("Hesap Özeti", head + rows[::-1])
