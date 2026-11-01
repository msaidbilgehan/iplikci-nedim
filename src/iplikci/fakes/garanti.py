"""Garanti BBVA's documents: receipts, and Garanti BBVA Yatırım's brokerage statements."""

from datetime import date

from . import HOLDER
from .files import Run, text_pdf


def receipt(
    heading: str,
    account: str,
    holder: str,
    body: list[Run],
    amount: str,
    day: date = date(2024, 10, 22),
    sequence: str = "00.03.19.000001",
) -> bytes:
    """A Garanti BBVA receipt ("Dekont") for an account such as "106/1234567"."""
    return text_pdf(
        [
            (453, 38, "T. Garanti Bankası A.Ş."),
            (163, 49, "Dekont"),
            (250, 106, heading),
            (40, 146, "ŞUBE ADI"),
            (142, 146, ":"),
            (154, 146, "MERKEZ"),
            (315, 146, "SAYIN"),
            (40, 160, "MÜŞTERİ NUMARASI"),
            (142, 160, ":"),
            (154, 160, "11112222"),
            (315, 160, holder),
            (40, 174, "HESAP NUMARASI"),
            (142, 174, ":"),
            (154, 174, account),
            (315, 174, "DENEME MAH. 1. SOK."),
            (40, 188, "İŞLEM TARİHİ"),
            (142, 188, ":"),
            (154, 188, f"{day:%d/%m/%Y}"),
            (315, 188, "NO:1"),
            (40, 245, f"DÜZENLENME TARİHİ:{day:%d.%m.%Y}"),
            (40, 259, "IBAN:TR00 0006 2000 1000 0001 2345 67"),
            *body,
            (40, 563, f"SIRA NO : {day:%Y-%m-%d}-{sequence}"),
            (315, 563, "TUTAR :"),
            (441, 563, amount),
        ]
    )


def fast_body(note: str, receiver: str, receiver_iban: str = "TR00 0001 0000 0000 0000 0000 01") -> list[Run]:
    """The middle of an outgoing FAST receipt: reference, receiver and the fee lines."""
    return [
        (40, 322, f"FAST REF NO - 1234567890 - {note}"),
        (40, 336, "ALACAKLI"),
        (142, 336, ":"),
        (154, 336, receiver),
        (40, 350, "ALACAKLI IBAN"),
        (142, 350, ":"),
        (154, 350, receiver_iban),
        (40, 364, "KOMİSYON HESABI"),
        (142, 364, ":"),
        (154, 364, "00106 / 1234567 IBAN:TR00 0006 2000 1000 0001 2345 67"),
        (40, 378, "MASRAF"),
        (142, 378, ":"),
        (262, 378, "4,22 TL"),
        (40, 393, "BSMV"),
        (142, 393, ":"),
        (262, 393, "0,21 TL"),
        (40, 407, "KOMİSYON TOPLAMI"),
        (142, 407, ":"),
        (262, 407, "4,43 TL"),
    ]


def brokerage_page(kind: str, emanet: str, day: str) -> list[Run]:
    """The head of a Garanti BBVA Yatırım page: "Hesap Durumu" (holdings) or "Hesap Ekstresi" (cash)."""
    return [
        (37, 71, "Ticaret Sicil No: 000000-0"),
        (326, 71, kind),
        (37, 80, "www.garantibbvayatirim.com.tr"),
        (43, 100, "Emanet No"),
        (139, 100, ":"),
        (150, 100, emanet),
        (497, 100, day),
    ]


def holdings_page(
    day: str, rows: list[tuple[str, str, str, str]], total: str, portfolio: str, cash: str = "0.00"
) -> list[Run]:
    """The holdings page: (code, name, quantity, value) rows, their total and the portfolio total."""
    page = brokerage_page("Hesap Durumu", "1234567-101", day) + [
        (43, 114, "Tarih"),
        (139, 114, ":"),
        (150, 114, day),
        (334, 114, HOLDER),
        (146, 160, "Cari Bakiye"),
        (86, 188, "Mevcudu"),
        (215, 188, "Rezervi (T + 1)"),
        (145, 211, cash),
        (287, 211, "0.00"),
        (192, 398, "MEVCUT MENKUL KIYMETLER"),
        (40, 426, "Kıymetin Kodu / Unvanı / Mevcut Piyasa Rezerv"),
    ]
    for i, (code, name, quantity, value) in enumerate(rows):
        page += [
            (55, 454 + 11 * i, "HS"),
            (85, 454 + 11 * i, code),
            (150, 454 + 11 * i, name),
            (344, 454 + 11 * i, quantity),
            (443, 454 + 11 * i, value),
            (532, 454 + 11 * i, "0.000"),
        ]
    top = 454 + 11 * len(rows)
    return page + [
        (150, top, "Hisse toplamı :"),
        (443, top, total),
        (471, 743, "toplamı(TL ) :"),
        (522, 769, portfolio),
    ]
