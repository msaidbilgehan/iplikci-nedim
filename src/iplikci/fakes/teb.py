"""TEB's documents: the Bonus card statement (with a text layer, or as OCR reads a scanned one), the card payment
receipt, the CEPTETEB account export, the digital passbook ("Dijital Hesap Cüzdanı") and the receipt of a transfer
between two TEB accounts."""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

from ..domain.labels import format_amount
from ..parsers.pdf import Line, Word
from . import HOLDER, CardRow, CardTerms, Move, Specimen, charged, with_balances
from .files import CHAR, Run, text_pdf


def account_export(
    rows: list[tuple[str, str, str, str]],
    number: str = "123456789",
    holder: str = HOLDER,
    period: str = "01/01/2026 - 31/01/2026",
    kind: str = "Vadesiz TL",
) -> bytes:
    """A CEPTETEB "Hesap Hareketlerim" export (HTML saved as .xls), rows newest first:
    (date, description, amount, balance). kind is the account's type as the export prints it: "Altın GR" makes a gold
    account, its amounts grams."""
    info = [
        ("Şube", "999-DENEME"),
        ("Hesap", number),
        ("IBAN", f"TR00000320000000000{number[-7:]}"),
        ("Hesap Türü", kind),
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


# A Bonus statement's terms: the due date ten days after the cut, the only one the layout the MVP knew prints.
BONUS_TERMS = CardTerms(date(2026, 10, 15))


def bonus_statement(
    cards: Sequence[Sequence[CardRow]] = BONUS_CARDS,
    cut: date = date(2026, 10, 5),
    previous: Decimal = Decimal(3250),
    last4: str = "1234",
    holder: str = HOLDER,
    note: str = "",
    terms: CardTerms = BONUS_TERMS,
) -> bytes:
    """A TEB Bonus card statement ("Kredi Kart Ekstre Özeti") with a text layer: a section per card, each under
    its own header and closed by the card's subtotal, and the period's debt and due date; note goes at the foot of
    the page."""
    total = previous + sum((charged(c) for c in cards), Decimal(0))
    runs: list[Run] = [
        (40, 40, "TÜRK EKONOMİ BANKASI A.Ş."),
        (40, 52, "Kredi Kart Ekstre Özeti"),
        (40, 100, f"SAYIN {holder}"),
        (40, 112, f"Hesap Kesim Tarihi: {cut:%d/%m/%Y}"),
        (330, 112, f"Kart Numarası: 545616******{last4}"),
        *([(40, 124, f"Son Ödeme Tarihi: {terms.due:%d/%m/%Y}")] if terms.due is not None else []),
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
    return text_pdf([*runs, (40, 800, note)] if note else runs)


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


# The overdraft account's November in the cüzdan: the month's interest and its taxes, a friend's transfer that clears
# the debt and the rest sent on (its description wraps around its row's line), then a transfer out with its fees, which
# the account's own sibling covers.
PASSBOOK_MOVES = (
    Move(date(2026, 11, 2), "Kredi Faiz Tutarı", Decimal("-120.00")),
    Move(date(2026, 11, 2), "KKDF Tutarı", Decimal("-18.00")),
    Move(date(2026, 11, 2), "BSMV Tutarı", Decimal("-18.00")),
    Move(date(2026, 11, 2), "VELİ ÖRNEKSOY den gelen\nhavale tutarı", Decimal("1500.00")),
    Move(date(2026, 11, 3), "101234567 no.lu hesaba gönderilmiştir.", Decimal("-1044.00")),
    Move(date(2026, 11, 5), "123456789 no.lu hesaba gönderilmiştir.", Decimal("400.00")),
    Move(date(2026, 11, 5), "QNB BANK A.Ş.", Decimal("-400.00")),
    Move(date(2026, 11, 5), "FAST Ücreti", Decimal("-7.97")),
    Move(date(2026, 11, 5), "FAST Ücreti BSMV", Decimal("-0.40")),
    Move(date(2026, 11, 5), "123456789 no.lu hesaba gönderilmiştir.", Decimal("8.37")),
)


# The distance between the lines of a description in the cüzdan, and half a row's height for each of its lines.
_PASSBOOK_WRAP, _PASSBOOK_HALF = 12.6, 5.0


def passbook(
    moves: Sequence[Move] = PASSBOOK_MOVES,
    opening: Decimal = Decimal(-300),
    number: str = "123456789",
    holder: str = HOLDER,
    period: tuple[date, date] = (date(2026, 11, 1), date(2026, 11, 10)),
    kind: str = "Vadesiz",
    rate: str = "",
    opened: date = date(2024, 6, 24),
) -> bytes:
    """A TEB "Dijital Hesap Cüzdanı": the account's "label: value" lines and its movements oldest first on the
    first page, the deposit terms on the second. rate is the yearly gross interest rate an account that earns interest
    prints below its balance ("Değişken faizlidir."). A move's text may hold line breaks: its lines are centred on the
    row's line, as the bank's are, so a description of two lines prints one above it and one below."""
    rows = with_balances(moves, opening)
    closing = rows[-1][1] if rows else opening
    start, end = period
    info = [
        ("Raporlama Tarihi:", f"{end:%d/%m/%Y}"),
        ("Hesap Hareketi Tarih Aralığı:", f"{start:%d/%m/%Y} - {end:%d/%m/%Y}"),
        ("Cüzdan Numarası:", "10000001"),
        ("Müşteri Adı - Soyadı:", holder),
        ("Müşteri Numarası:", "10000002"),
        ("Şube:", "Deneme Şubesi - 999"),
        ("Hesap Numarası:", number),
        ("IBAN:", f"TR00000320000000000{number[-7:]}"),
        ("Hesap Sahibi Sayısı:", "1"),
        ("Hesap Türü:", kind),
        ("Para Kodu:", "TL"),
        ("Hesap Açılış Tarihi:", f"{opened:%d/%m/%Y}"),
        ("Bakiye:", format_amount(closing)),
        *([("Brüt Faiz Oranı (Yıllık):", rate)] if rate else []),
    ]
    runs: list[Run] = [(297, 48, "Dijital Hesap Cüzdanı")]
    for i, (label, value) in enumerate(info):
        runs += [(31, 108 + 20 * i, label), (173, 108 + 20 * i, value)]
    runs += [(47, 444, "Sıra No"), (121, 444, "Tarih"), (246, 444, "Açıklama"), (391, 444, "İşlem Tutarı")]
    runs.append((502, 444, "Bakiye"))
    y = 462.0
    for i, (move, balance) in enumerate(rows, 1):
        parts = move.text.split("\n")
        y += _PASSBOOK_HALF * (len(parts) + 1)
        runs += [(59, y, str(i)), (109, y, f"{move.day:%d/%m/%Y}")]
        runs += [(425, y, format_amount(move.amount)), (520, y, format_amount(balance))]
        runs += [(170, y + _PASSBOOK_WRAP * (k - (len(parts) - 1) / 2), part) for k, part in enumerate(parts)]
        y += _PASSBOOK_HALF * (len(parts) + 1)
    footer = "Türk Ekonomi Bankası A.Ş. Ticaret Sicil:000000 Deneme Mah. Örnek Cad. No: 1 İstanbul www.teb.com.tr"
    first = [*runs, (502, 784, "Rev.No:0001 1 / 2"), (23, 801, footer)]
    terms: list[Run] = [
        (40, 21, "Değerli Müşterimiz, lütfen aşağıdaki hususları dikkatle okuyunuz."),
        (40, 44, "1- Bu cüzdanın mevduat hesabınızdan yapacağınız her türlü işlem sırasında Bankamıza ibrazı gerekir."),
        (40, 67, "2- Farklılık olması halinde Bankamız kayıtları esas alınır."),
        (40, 400, "Tasarruf Mevduatı Sigortası Hakkında Duyuru:"),
        (502, 784, "Rev.No:0001 2 / 2"),
        (23, 801, footer),
    ]
    return text_pdf(first, terms)


def transfer_receipt(
    amount: Decimal,
    day: date,
    number: str = "123456789",
    holder: str = HOLDER,
    payer: str = HOLDER,
    text: str = "vadeli para yatırma",
) -> bytes:
    """A TEB "Banka İçi Para Transfer Dekontu" of the account the money came into: the amount with its sign, the
    paying account named only by its holder and branch."""
    paid = format_amount(amount)
    return text_pdf(
        [
            (44, 97, "Türk Ekonomi Bankası A.Ş."),
            (44, 109, "Ticaret Sicil:000000,Mersis:0000000000000000"),
            (44, 132, "Deneme Mah. Örnek Cad. No: 1 Ümraniye 34768/İSTANBUL|www.teb.com.tr"),
            (199, 161, "BANKA İÇİ PARA TRANSFER DEKONTU"),
            (287, 179, f"Tarih-Saat: {day:%d/%m/%Y} 21.48"),
            (289, 188, "İşlem No: 00012345 SYS"),
            (48, 221, "Müşteri Numarası:10000002"),
            (169, 221, f"Hesap Sahibi:{holder}"),
            (48, 232, f"Hesap Numarası:{number}-TL"),
            (169, 232, "Hesap Şubesi:CEPTETEB-999"),
            (48, 242, f"IBAN:TR00 0003 2000 0000 0{number[:3]} {number[3:7]} {number[7:]}"),
            (48, 285, f"{text}:"),
            (287, 285, f"Valör:{day:%d/%m/%y}"),
            (368, 285, "TL"),
            (437, 285, f"{paid}+"),
            (48, 295, f"Hesaba toplam TL.{paid} ödeme yapılmıştır."),
            (48, 379, f"Borçlu Hesap Sahibi:{payer}"),
            (48, 390, "Hesap Şubesi:CEPTETEB-999"),
            (48, 429, f"Sayın {holder}"),
            (298, 429, f"Açıklama: {text}"),
            (298, 492, "İşlem Yeri: CEPTETEB Mobil Bankacılık Uygulaması"),
            (44, 577, "Elektronik olarak onaylanmıştır."),
        ],
        size=6.75,
    )


def specimens() -> list[Specimen]:
    payment = card_payment_receipt(Decimal(3250), date(2026, 10, 15))
    export = account_export(running_rows(list(ACCOUNT_MOVES)))
    transfer = transfer_receipt(Decimal(2500), date(2026, 11, 10))
    return [
        Specimen("teb-bonus-ekstre.pdf", bonus_statement(), "teb.bonus_card", "teb-1234", 7),
        Specimen("teb-kart-odeme-dekontu.pdf", payment, "teb.card_payment_receipt", "teb-1234", 1),
        Specimen("teb-hesap-hareketlerim.xls", export, "teb.account_html", "teb-123456789", 4),
        Specimen("teb-dijital-hesap-cuzdani.pdf", passbook(), "teb.passbook", "teb-123456789", 10),
        Specimen("teb-banka-ici-havale-dekontu.pdf", transfer, "teb.transfer_receipt", "teb-123456789", 1),
    ]
