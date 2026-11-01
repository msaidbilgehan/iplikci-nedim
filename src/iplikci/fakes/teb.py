"""TEB's documents: the CEPTETEB account export and the card payment receipt."""

from datetime import date
from decimal import Decimal

from ..domain.labels import format_amount
from . import HOLDER, Move, with_balances
from .files import text_pdf


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
