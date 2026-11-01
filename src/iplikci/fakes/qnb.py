"""QNB's documents: the card statement and the account list as PDF exports, and the e-dekont of a transfer."""

import textwrap
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from . import HOLDER, CardRow, CardTerms, Move, Specimen, charged
from .files import Run, right, text_pdf

# QNB prints its rows in a font with no Unicode map for Turkish letters: pdfminer shows each as "(cid:N)". The
# fake writes them as private-use characters, which its own font leaves unmapped the same way.
_UNMAPPED = {c: chr(0xE000 + i) for i, c in enumerate("çğıöşüÇĞİÖŞÜ")}
_LINE = 11

# A card's month over two pages: a payment, purchases, and the interest and fee whose damaged labels the reader
# repairs. QNB spells "Tesekkür" with an s of its own.
CARD_PAGES: tuple[tuple[CardRow, ...], ...] = (
    (
        CardRow(date(2026, 9, 12), "Ödeme - Tesekkür Ederiz -", Decimal(-3250)),
        CardRow(date(2026, 9, 14), "MIGROS ORNEK SUBE İSTANBUL", Decimal("1245.60")),
        CardRow(date(2026, 9, 18), "ORNEK RESTORAN KADIKOY", Decimal(420)),
        CardRow(date(2026, 9, 24), "NETFLIX.COM", Decimal("229.99")),
    ),
    (
        CardRow(date(2026, 10, 5), "Alışveriş faizi", Decimal("45.30")),
        CardRow(date(2026, 10, 5), "Yıllık üyelik ücreti", Decimal(650)),
    ),
)


# A card statement's terms: the due date ten days after the cut, the only one the layout the MVP knew prints.
CARD_TERMS = CardTerms(date(2026, 10, 15))


def card_statement(
    pages: Sequence[Sequence[CardRow]] = CARD_PAGES,
    cut: date = date(2026, 10, 5),
    previous: Decimal = Decimal(3250),
    last4: str = "1234",
    holder: str = HOLDER,
    terms: CardTerms = CARD_TERMS,
) -> bytes:
    """A QNB card statement exported as PDF ("Ekstre Hareketleri"): US-format amounts, a leading minus for a
    credit, and the rows' Turkish letters lost to the font."""
    total = previous + sum((charged(p) for p in pages), Decimal(0))
    summary: list[Run] = [
        (40, 40, "QNB Kredi Kartı Ekstre Hareketleri"),
        (40, 70, f"Sn. {holder}"),
        (40, 90, f"Kredi Kartı Numarası : 5400 12** **** {last4}"),
        (40, 102, f"Hesap Kesim Tarihi : {cut:%d/%m/%Y}"),
        *([(40, 114, f"Son Ödeme Tarihi : {terms.due:%d/%m/%Y}")] if terms.due is not None else []),
        (40, 140, f"Önceki Dönem Bakiyeniz {us_amount(previous)}"),
        (40, 152, f"Genel Toplam - TL Hesap Ekstresi {us_amount(total)}"),
    ]
    out: list[list[Run]] = []
    for i, rows in enumerate(pages):
        top = 190 if i == 0 else 60
        runs = [
            *(summary if i == 0 else []),
            (40, top, "İşlem Tarihi"),
            (110, top, "Açıklama"),
            right(520, top, "Tutar"),
        ]
        for n, row in enumerate(rows, 1):
            y = top + 3 + n * _LINE
            runs += [(40, y, f"{row.day:%d/%m/%Y}" if row.day else ""), (110, y, unmapped(row.text))]
            if row.amount is not None:
                runs.append(right(520, y, us_amount(row.amount)))
        out.append(runs)
    return text_pdf(*out)


def us_amount(value: Decimal) -> str:
    """As QNB prints an amount: "1,245.60", "-3,250.00"."""
    return f"{value:,.2f}"


def unmapped(text: str) -> str:
    """text with its Turkish letters in the glyphs pdfminer cannot name."""
    return "".join(_UNMAPPED.get(c, c) for c in text)


# --- account lists --------------------------------------------------------------------------------------------

# A month on a current account over two pages, oldest first: salary, rent sent by FAST under a transfer heading
# whose note wraps onto the next line, its fee, a card payment, money received under a heading, a purchase.
# A row without text takes its heading's.
ACCOUNT_ROWS: tuple[tuple[tuple[Move, str, str], ...], ...] = (
    (
        (Move(date(2026, 10, 1), "MAAŞ ÖDEMESİ ÖRNEK İŞVEREN", Decimal(40000)), "MAAS", ""),
        (
            Move(date(2026, 10, 4), "", Decimal(-15000)),
            "FAST",
            "Transfer İşlemleri - Alıcı : VELİ ÖRNEKSOY Türkiye Garanti Bankası A.Ş. Sorgu No: 123|EKİM KİRA ÖDEMESİ",
        ),
        (Move(date(2026, 10, 4), "FAST ÜCRETİ", Decimal(-8)), "UCRET", ""),
        (Move(date(2026, 10, 10), "KREDİ KARTI ÖDEMESİ", Decimal(-3250)), "KART", ""),
    ),
    (
        (
            Move(date(2026, 10, 15), "", Decimal(2500)),
            "FAST",
            "Transfer İşlemleri - Gönderen : AYŞE SOYADOĞLU Enpara Bank A.Ş. Sorgu No: 456",
        ),
        (Move(date(2026, 10, 20), "ORNEK MARKET ATASEHIR", Decimal("-312.40")), "ALIŞVERİŞ", ""),
    ),
)


def account_pdf(
    pages: Sequence[Sequence[tuple[Move, str, str]]] = ACCOUNT_ROWS,
    opening: Decimal = Decimal(1000),
    holder: str = HOLDER,
    overdraft: bool = False,
    period: tuple[date, date] = (date(2026, 10, 1), date(2026, 10, 31)),
) -> bytes:
    """A QNB "Hesap Hareketleri" export (PDF): the account above rows of date, transaction type, text, amount and
    balance, oldest first and opened by the balance carried over. A row's heading comes in the line above it, and
    "|" in a heading starts the line under the row, where its note runs on."""
    balance = opening
    out: list[list[Run]] = []
    for i, rows in enumerate(pages):
        runs: list[Run] = []
        y = 60.0
        if i == 0:
            runs += [
                (40, 40, "QNB Hesap Hareketleri"),
                (40, 70, f"Iban : TR00 0011 1000 0000 0012 3456 78 Ad Soyad : {holder}"),
                (40, 82, f"Hesap Adı : {'EK HESAP' if overdraft else 'VADESİZ TL'}"),
                (40, 94, f"Tarih Aralığı : {period[0]:%d/%m/%Y} - {period[1]:%d/%m/%Y}"),
                (40, 120, "İşlem Tarihi İşlem Açıklama Tutar Bakiye"),
                (40, 132, f"DEVREDEN BAKİYE {us_amount(opening)}"),
            ]
            y = 144.0
        for move, kind, heading in rows:
            above, _, below = heading.partition("|")
            if above:
                runs.append((40, y, above))
                y += _LINE
            balance += move.amount
            line = f"{move.day:%d/%m/%Y} {kind} {move.text}".rstrip()
            runs += [(40, y, line), right(470, y, us_amount(move.amount)), right(540, y, us_amount(balance))]
            y += _LINE
            if below:
                runs.append((40, y, below))
                y += _LINE
        runs.append((40, 800, f"Sayfa {i + 1} / {len(pages)}"))
        out.append(runs)
    return text_pdf(*out)


# --- e-dekont ---------------------------------------------------------------------------------------------------

_TRANSFER = (
    "QNB Bank A.Ş. DEKONT {holder} Müşteri No 100000001 İşlem Yeri HAZİNE MUHASEBELEŞME ŞUBESİ "
    "İşlem Tarihi {day:%d/%m/%Y} 15:22:04 Aşağıdaki hesap/kredi kartınızda karşılarında gösterilen hareketler "
    "gerçekleştirilmiştir. Hesap/K.Kart No IBAN Açıklama B/A Para Cinsi TUTAR "
    "TR000011100000000012345678 {row} TL {amount} {block} SORGU NO: 1 Sıra No 00344-0 Fiş No : {number}"
)
# A FAST received from Ayşe Soyadoğlu at Garanti BBVA ("A", alacak) and one sent to Veli Örneksoy ("B", borç).
INCOMING = (
    "Gönderen: AYŞE SOYADOĞLU A",
    (
        "GELEN FAST EFT AÇIKLAMA: kk ödemesi GÖNDEREN : AYŞE SOYADOĞLU HESAP NO: 12345678 "
        "KATILIMCI: Türkiye Garanti Bankası A.Ş."
    ),
)
OUTGOING = ("GİDEN FAST EFT B", "AÇIKLAMA: kira ALICI : VELİ ÖRNEKSOY IBAN: TR000006700000000000000001")


def transfer_text(
    side: tuple[str, str] = INCOMING,
    amount: Decimal = Decimal(2400),
    day: date = date(2026, 11, 3),
    number: str = "202611000000001",
    holder: str = HOLDER,
) -> str:
    """The text of a QNB e-dekont of a transfer on account 12345678: side is its row and the block that names
    the other side (INCOMING, OUTGOING); number is its "Fiş No"."""
    row, block = side
    return _TRANSFER.format(holder=holder, day=day, row=row, amount=f"{amount:,.2f}", block=block, number=number)


def transfer_receipt(side: tuple[str, str] = INCOMING, amount: Decimal = Decimal(2400)) -> bytes:
    """A QNB e-dekont of a transfer as a PDF, its text wrapped at a hundred characters."""
    return text_pdf([(20, 40 + 12 * i, line) for i, line in enumerate(textwrap.wrap(transfer_text(side, amount), 100))])


def transfer_receipt_html(side: tuple[str, str] = OUTGOING, amount: Decimal = Decimal(2400)) -> bytes:
    """A QNB e-dekont of a transfer as the HTML of its e-mail."""
    return f"<html><body><p>{transfer_text(side, amount)}</p></body></html>".encode()


def specimens() -> list[Specimen]:
    return [
        Specimen("qnb-kart-ekstre.pdf", card_statement(), "qnb.card_pdf", "qnb-1234", 6),
        Specimen("qnb-hesap-hareketleri.pdf", account_pdf(), "qnb.account_pdf", "qnb-12345678", 6),
        Specimen("qnb-gelen-fast-dekont.pdf", transfer_receipt(), "qnb.edekont", "qnb-12345678", 1),
        Specimen("qnb-giden-fast-dekont.html", transfer_receipt_html(), "qnb.edekont", "qnb-12345678", 1),
    ]
