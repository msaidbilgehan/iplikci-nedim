"""QNB's documents: the card statement and the account list as PDF exports."""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

from . import HOLDER, CardRow, Move, charged
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


def card_statement(
    pages: Sequence[Sequence[CardRow]] = CARD_PAGES,
    cut: date = date(2026, 10, 5),
    previous: Decimal = Decimal(3250),
    last4: str = "1234",
    holder: str = HOLDER,
) -> bytes:
    """A QNB card statement exported as PDF ("Ekstre Hareketleri"): US-format amounts, a leading minus for a
    credit, and the rows' Turkish letters lost to the font."""
    total = previous + sum((charged(p) for p in pages), Decimal(0))
    summary: list[Run] = [
        (40, 40, "QNB Kredi Kartı Ekstre Hareketleri"),
        (40, 70, f"Sn. {holder}"),
        (40, 90, f"Kredi Kartı Numarası : 5400 12** **** {last4}"),
        (40, 102, f"Hesap Kesim Tarihi : {cut:%d/%m/%Y}"),
        (40, 114, f"Son Ödeme Tarihi : {cut + timedelta(days=10):%d/%m/%Y}"),
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
