"""TEB's documents: the CEPTETEB account export."""

from decimal import Decimal

from ..domain.labels import format_amount
from . import HOLDER, Move, with_balances


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
