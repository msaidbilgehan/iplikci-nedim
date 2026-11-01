"""Vakıfbank's documents: the account list as an XLSX export."""

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from . import HOLDER, Move, with_balances
from .files import xlsx_file

# A month on a current account, oldest first: salary with the employer in its code, rent sent by FAST with its
# fee, a bill, money received by EFT and euros bought into an own account, each with the bank's transaction type.
ACCOUNT_MOVES: tuple[tuple[Move, str], ...] = (
    (Move(date(2026, 10, 1), "Maaş Ödemesi (1234_5678_ÖRNEK İŞVEREN A.Ş.)", Decimal(40000)), "MAAŞ"),
    (
        Move(
            date(2026, 10, 4),
            "Hesabınızdan Yapı ve Kredi Bankası A.Ş. Veli Örneksoy hesabına FAST ile gönderildi",
            Decimal(-15000),
        ),
        "FAST",
    ),
    (Move(date(2026, 10, 4), "FAST Ücreti", Decimal(-8)), "ÜCRET"),
    (Move(date(2026, 10, 10), "İGDAŞ Doğalgaz Faturası", Decimal(-450)), "FATURA"),
    (Move(date(2026, 10, 15), "Enpara Bank A.Ş. Kemal Denemeci hesabından gelen EFT", Decimal(2500)), "EFT"),
    (Move(date(2026, 10, 20), "Döviz Alış EUR", Decimal(-10000)), "DÖVİZ ALIŞ"),
)


def account_xlsx(
    moves: Sequence[tuple[Move, str]] = ACCOUNT_MOVES,
    opening: Decimal = Decimal(1000),
    holder: str = HOLDER,
    nickname: str = "Günlük",
    period: tuple[date, date] = (date(2026, 10, 1), date(2026, 10, 31)),
) -> bytes:
    """A Vakıfbank "Hesap Hareketleri" export (XLSX): the customer, the account and its nickname above a table of
    rows, oldest first, dated with the hour."""
    head: list[list[str | float | datetime | None]] = [
        ["T. VAKIFLAR BANKASI T.A.O."],
        ["HESAP HAREKETLERİ"],
        ["VB Müşteri No", "12345678"],
        ["HESAP SAHİBİ", holder],
        ["IBAN", "TR00 0001 5001 5800 0001 2345 67"],
        ["HESAP TÜRÜ", "BİREYSEL VADESİZ TL"],
        ["RUMUZ", nickname],
        ["TARİH ARALIĞI", f"{period[0]:%d.%m.%Y} - {period[1]:%d.%m.%Y}"],
        [],
        ["HESAP NO", "İŞLEM TARİHİ", "İŞLEM", "AÇIKLAMA", "TUTAR", "BAKİYE"],
    ]
    rows = [
        [
            "00158000000012345678",
            datetime(m.day.year, m.day.month, m.day.day, 10),
            kind,
            m.text,
            float(m.amount),
            float(balance),
        ]
        for (m, balance), (_, kind) in zip(with_balances([m for m, _ in moves], opening), moves, strict=True)
    ]
    return xlsx_file("Hesap Hareketleri", head + rows)
