"""Vakıfbank's documents: the account list as an XLSX export, and the e-cüzdan."""

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from . import HOLDER, Move, Specimen, with_balances
from .files import text_pdf, xlsx_file

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


def passbook(holder: str = HOLDER) -> bytes:
    """The e-cüzdan of a USD account opened on 2 May 2026: the deposit terms on the first page, the account and
    its one row, of no money, on the second."""
    return text_pdf(
        [
            (40, 72, "Tasarruf Mevduatı Hesabının Tabi Olduğu Koşullar:"),
            (40, 600, "İşbu cüzdanla işlem yapılacak olan hesaplar sözleşmeye tabidir."),
            (57, 816, "444 0 724 | vakifbank.com.tr"),
        ],
        [
            (26, 73, "Hesap No"),
            (196, 73, ":"),
            (211, 73, "00158000000012345678"),
            (26, 86, "IBAN"),
            (196, 86, ":"),
            (211, 86, "TR000001500158000000012345"),
            (26, 114, "Hesap Sahibi"),
            (196, 114, ":"),
            (211, 114, holder),
            (26, 142, "Rumuz"),
            (196, 142, ":"),
            (211, 142, "Birikim"),
            (26, 155, "Hesap Türü / Para Birimi"),
            (196, 155, ":"),
            (211, 155, "BİREYSEL VADESİZ / USD"),
            (26, 197, "Hesap Açılış Tarihi"),
            (196, 197, ":"),
            (211, 197, "02.05.2026"),
            (26, 224, "İşlem Tarihi"),
            (196, 224, ":"),
            (211, 224, "02.05.2026"),
            (26, 238, "Cüzdan Seri No"),
            (196, 238, ":"),
            (211, 238, "2026000000000001"),
            (29, 274, "NO İŞLEM TARİHİ İŞLEM TUTARI BAKİYE AÇIKLAMA"),
            (27, 288, "1"),
            (55, 288, "02.05.2026"),
            (217, 288, "0,00"),
            (324, 288, "0,00"),
            (353, 288, "Vadesiz Hesap Açma"),
            (57, 816, "444 0 724 | vakifbank.com.tr"),
        ],
    )


def specimens() -> list[Specimen]:
    return [
        Specimen(
            "vakifbank-hesap-hareketleri.xlsx",
            account_xlsx(),
            "vakifbank.account_xlsx",
            "vakifbank-0158000001234567",
            6,
        ),
        Specimen("vakifbank-e-cuzdan.pdf", passbook(), "vakifbank.passbook", "vakifbank-0158000000012345", 0),
    ]
