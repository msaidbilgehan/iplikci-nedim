"""İş Bankası's documents: the Maximum card statement."""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

from ..domain.labels import format_amount
from . import HOLDER, CardRow, charged
from .files import Run, right, text_pdf

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
