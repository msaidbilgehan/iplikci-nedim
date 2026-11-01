"""TEB's documents: the Bonus card statement (with a text layer, or as OCR reads a scanned one), the card payment
receipt and the CEPTETEB account export."""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

from ..domain.labels import format_amount
from ..parsers.pdf import Line, Word
from . import HOLDER, CardRow, Move, Specimen, charged, with_balances
from .files import CHAR, Run, text_pdf


def account_export(
    rows: list[tuple[str, str, str, str]],
    number: str = "123456789",
    holder: str = HOLDER,
    period: str = "01/01/2026 - 31/01/2026",
) -> bytes:
    """A CEPTETEB "Hesap Hareketlerim" export (HTML saved as .xls), rows newest first:
    (date, description, amount, balance)."""
    info = [
        ("Şube", "999-DENEME"),
        ("Hesap", number),
        ("IBAN", f"TR00000320000000000{number[-7:]}"),
        ("Hesap Türü", "Vadesiz TL"),
        ("Hesap Sahibi", holder),
        ("Bakiye", "0,00"),
    ]
    head = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in info)
    body = "".join(
        f"<tr><td>{d}</td><td>{d}</td><td>10:00</td><td>{desc}</td><td>{amount}</td><td>{balance}</td><td>{i}</td></tr>"
        for i, (d, desc, amount, balance) in enumerate(rows)
    )
    return (
        "<html><body><table><tr><td></td><td>Hesap Hareketlerim</td></tr>" + head + "</table>"
        f'<div class="prompt"> {period} tarihleri arasındaki işlemleriniz aşağıdadır.</div>'
        "<table><tr><td>Tarih</td><td>Valör</td><td>Saat</td><td>Açıklama</td><td>Tutar</td><td>Bakiye</td>"
        "<td>Dekont</td></tr>" + body + "</table></body></html>"
    ).encode("utf-8")


def running_rows(moves: list[Move], opening: Decimal = Decimal(0)) -> list[tuple[str, str, str, str]]:
    """account_export rows for moves in date order, each with the balance after it, newest first."""
    rows = [
        (f"{m.day:%d/%m/%Y}", m.text, format_amount(m.amount), format_amount(b))
        for m, b in with_balances(moves, opening)
    ]
    return rows[::-1]


def card_payment_receipt(
    amount: Decimal, day: date, last4: str = "1234", number: str = "123456789", holder: str = HOLDER
) -> bytes:
    """A TEB "Kredi Kartı Ödeme Dekontu": a payment to a card, its total printed twice."""
    paid = format_amount(amount)
    return text_pdf(
        [
            (40, 40, "Türk Ekonomi Bankası A.Ş."),
            (200, 70, "KREDİ KARTI ÖDEME DEKONTU"),
            (40, 110, f"TARİH-SAAT: {day:%d/%m/%Y} 14:22:05"),
            (330, 110, f"İŞLEM NO: {number}"),
            (40, 124, f"HESAP SAHİBİ: {holder}"),
            (330, 124, "HESAP NO: 999-123456789"),
            (40, 160, f"5456 16** **** {last4} NO.LU KREDİ KARTINA YAPILAN ÖDEME"),
            (40, 190, "ÖDEME TUTARI"),
            (330, 190, f"TL {paid}"),
            (40, 204, f"TOPLAM TL {paid}"),
        ]
    )


# --- card statements ------------------------------------------------------------------------------------------

_DATE_X, _TEXT_X, _AMOUNT_X, _POINTS_X = 40, 100, 400, 500
_LINE = 11

# A Bonus card's month in two card sections, the main card's and an additional card's: a payment, a purchase
# that prints the day it was made before its text, an installment, a purchase abroad, an amount whole to the lira
# ("TL.1.500,-") and a yearly card fee.
BONUS_CARDS: tuple[tuple[CardRow, ...], ...] = (
    (
        CardRow(date(2026, 9, 12), "ÖDEMENİZ İÇİN TEŞEKKÜR EDERİZ", Decimal(-3250)),
        CardRow(date(2026, 9, 14), "12/09 MIGROS ORNEK SUBE ISTANBUL", Decimal("1245.60")),
        CardRow(date(2026, 9, 20), "TEKNOSA ORNEK AVM (9/8. Taksit)", Decimal(250)),
        CardRow(date(2026, 9, 22), "ornek.com (Yurt dışı işlem tutarı EUR.25,75)", Decimal("950.40")),
        CardRow(date(2026, 9, 25), "ORNEK MOBILYA", Decimal(1500)),
    ),
    (
        CardRow(date(2026, 9, 27), "ORNEK KITAPEVI KADIKOY", Decimal(120)),
        CardRow(date(2026, 10, 1), "YILLIK KART ÜCRETİ", Decimal(650)),
    ),
)


def bonus_statement(
    cards: Sequence[Sequence[CardRow]] = BONUS_CARDS,
    cut: date = date(2026, 10, 5),
    previous: Decimal = Decimal(3250),
    last4: str = "1234",
    holder: str = HOLDER,
) -> bytes:
    """A TEB Bonus card statement ("Kredi Kart Ekstre Özeti") with a text layer: a section per card, each under
    its own header and closed by the card's subtotal, and the period's debt."""
    total = previous + sum((charged(c) for c in cards), Decimal(0))
    runs: list[Run] = [
        (40, 40, "TÜRK EKONOMİ BANKASI A.Ş."),
        (40, 52, "Kredi Kart Ekstre Özeti"),
        (40, 100, f"SAYIN {holder}"),
        (40, 112, f"Hesap Kesim Tarihi: {cut:%d/%m/%Y}"),
        (330, 112, f"Kart Numarası: 545616******{last4}"),
        (40, 124, f"Son Ödeme Tarihi: {cut + timedelta(days=10):%d/%m/%Y}"),
        (330, 124, f"Dönem Borcu: {_amount(total)}"),
        (40, 136, f"Sonraki Hesap Kesim Tarihi: {cut + timedelta(days=31):%d/%m/%Y}"),
    ]
    y = 180.0
    for i, rows in enumerate(cards):
        runs += [(_DATE_X, y, f"5456 16** **** {int(last4) + 4444 * i:04d} {holder}")]
        y += 14
        runs += [(_DATE_X, y, "Tarih"), (_TEXT_X, y, "Açıklama"), (_AMOUNT_X, y, "Tutar"), (_POINTS_X, y, "Bonus")]
        if i == 0:
            y += _LINE
            runs += [(_TEXT_X, y, "DEVİR"), (_AMOUNT_X, y, _amount(previous))]
        for row in rows:
            y += _LINE
            if row.day is not None:
                runs.append((_DATE_X, y, f"{row.day:%d/%m/%Y}"))
            runs.append((_TEXT_X, y, row.text))
            if row.amount is not None:
                runs.append((_AMOUNT_X, y, _amount(row.amount)))
                if row.amount > 0:
                    runs.append((_POINTS_X, y, format_amount(row.amount * Decimal("0.005"))))
        y += _LINE
        runs += [(_TEXT_X, y, "KART TOPLAMI"), (_AMOUNT_X, y, _amount(charged(rows)))]
        y += 24
    return text_pdf(runs)


def _amount(value: Decimal) -> str:
    """As TEB prints an amount: "TL.1.245,60", "-TL.3.250,00" for a credit, "TL.1.500,-" when it is whole."""
    printed = format_amount(abs(value))
    if printed.endswith(",00"):
        printed = printed[:-2] + "-"
    return ("-" if value < 0 else "") + "TL." + printed


def scanned_statement(
    cards: Sequence[Sequence[CardRow]] = BONUS_CARDS,
    cut: date = date(2026, 10, 5),
    previous: Decimal = Decimal(3250),
    last4: str = "1234",
) -> list[list[Line]]:
    """What OCR reads off a TEB Bonus statement delivered as page images: every text run a word of its own,
    usually a table cell, with the contactless payment icon read as ")))"."""
    total = previous + sum((charged(c) for c in cards), Decimal(0))
    cells: list[list[str]] = [
        ["Kredi Kart Ekstre Özeti"],
        ["Hesap Kesim Tarihi", f"{cut:%d/%m/%Y}"],
        ["Kart Numarası", f"545616******{last4}"],
        ["Dönem Borcu", _amount(total)],
        ["Sonraki Hesap Kesim Tarihi", f"{cut + timedelta(days=31):%d/%m/%Y}"],
        ["Sıra", "Tarih", "Açıklama", "Tutar", "Bonus"],
        ["ÖNCEKİ DÖNEM BORCU", _amount(previous)],
    ]
    n = 0
    for rows in cards:
        for row in rows:
            if row.day is None or row.amount is None:
                continue
            n += 1
            text = row.text + (" )))" if n == 2 else "")  # a contactless purchase
            cells.append([str(n), f"{row.day:%d/%m/%Y}", text, _amount(row.amount), "0,00"])
    lines: list[Line] = []
    for i, line in enumerate(cells):
        top, x, words = 60.0 + 14 * i, 40.0, list[Word]()
        for cell in line:
            words.append(Word(cell, x, x + len(cell) * CHAR, top, top + 9))
            x += len(cell) * CHAR + 20
        lines.append(Line(top, words, 1))
    return [lines]


# A month on the CEPTETEB account: salary, rent sent with its fee, a purchase.
ACCOUNT_MOVES: tuple[Move, ...] = (
    Move(date(2026, 1, 1), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(40000)),
    Move(date(2026, 1, 3), "VELİ ÖRNEKSOY KİRA ÖDEMESİ", Decimal(-15000)),
    Move(date(2026, 1, 3), "FAST Ücreti", Decimal(-8)),
    Move(date(2026, 1, 12), "MIGROS ORNEK SUBE ISTANBUL", Decimal(-2150)),
)


def specimens() -> list[Specimen]:
    payment = card_payment_receipt(Decimal(3250), date(2026, 10, 15))
    export = account_export(running_rows(list(ACCOUNT_MOVES)))
    return [
        Specimen("teb-bonus-ekstre.pdf", bonus_statement(), "teb.bonus_card", "teb-1234", 7),
        Specimen("teb-kart-odeme-dekontu.pdf", payment, "teb.card_payment_receipt", "teb-1234", 1),
        Specimen("teb-hesap-hareketlerim.xls", export, "teb.account_html", "teb-123456789", 4),
    ]
