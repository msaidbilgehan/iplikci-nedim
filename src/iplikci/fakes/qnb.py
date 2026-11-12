"""QNB's documents: the card statement and the account list as PDF exports, the e-dekont of a transfer and the
movement notices it mails."""

import textwrap
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html import escape

from ..domain.labels import MONTHS
from . import HOLDER, CardRow, CardTerms, Move, Specimen, charged
from .files import Run, html_mail, right, text_pdf

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


# A card statement's terms: the due date ten days after the cut and the next cut, a day before the same day a month
# on. The reader does not read the minimum payment or the limit yet.
CARD_TERMS = CardTerms(date(2026, 10, 15), next_cut=date(2026, 11, 4))
_WEEKDAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")


def card_statement(
    pages: Sequence[Sequence[CardRow]] = CARD_PAGES,
    cut: date = date(2026, 10, 5),
    previous: Decimal = Decimal(3250),
    last4: str = "1234",
    holder: str = HOLDER,
    terms: CardTerms = CARD_TERMS,
) -> bytes:
    """A QNB card statement exported as PDF ("Ekstre Hareketleri"): US-format amounts, a leading minus for a
    credit, and the rows' Turkish letters lost to the font. The due date is spelled out beside the card's number,
    its Turkish letters lost too, and a note under the last page's rows names the next statement's cut and due date."""
    total = previous + sum((charged(p) for p in pages), Decimal(0))
    summary: list[Run] = [
        (40, 40, "QNB Kredi Kartı Ekstre Hareketleri"),
        (40, 70, f"Sn. {holder}"),
        (40, 90, f"Kredi Kartı Numarası : 5400 12** **** {last4}"),
        (40, 102, f"Hesap Kesim Tarihi : {cut:%d/%m/%Y}"),
        (40, 140, f"Önceki Dönem Bakiyeniz {us_amount(previous)}"),
        (40, 152, f"Genel Toplam - TL Hesap Ekstresi {us_amount(total)}"),
    ]
    if terms.due is not None:
        due = terms.due
        spelled = f"{due.day:02d} {MONTHS[due.month - 1]} {due.year}, {_WEEKDAYS[due.weekday()]}"
        summary.append((300, 90, unmapped(f"Son Ödeme Tarihi: {spelled}")))
    note: list[str] = []
    if terms.next_cut is not None:
        later = terms.next_cut + timedelta(days=10)
        note.append(
            unmapped(
                f"* Bir sonraki hesap kesim tarihiniz {terms.next_cut:%d/%m/%Y}, bir sonraki son ödeme tarihiniz "
                f"{later:%d/%m/%Y}"
            )
        )
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
        if i == len(pages) - 1:
            runs += [(40, top + 3 + (len(rows) + 3) * _LINE, line) for line in note]
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


# --- movement notices -------------------------------------------------------------------------------------------

NOTICE_SENDER = "bilgilendirme@email.qnb.com.tr"
OLD_NOTICE_SENDER = "bilgilendirme@email.qnbfinansbank.com"  # QNB Finansbank, until 2024
FAST_SUBJECT = "QNB - Fast Para transferi bildiriminiz"
TRANSFER_SUBJECT = "QNB - Para transferi bildiriminiz"
CASH_SUBJECT = "QNB FINANSBANK - ATM/Banka Kartı Para Çıkışı Bildiriminiz"
_ISTANBUL = timezone(timedelta(hours=3))
FAST_OUT = (
    "KADIKÖY şubesindeki hesabınızdan VELİ ÖRNEKSOY isimli alıcıya {amount} TL'lik FAST işleminiz gerçekleştirilmiştir."
)
FAST_IN = "KADIKÖY şubesindeki hesabınıza AYŞE SOYADOĞLU tarafından FAST aracılığı ile {amount} TL gönderilmiştir."
TRANSFER_IN = "KADIKÖY şubesindeki 12345678 no'lu hesabınıza AYŞE SOYADOĞLU tarafından {amount} TL gönderilmiştir."
TRANSFER_OUT = "KADIKÖY şubesindeki 12345678 no'lu hesabinizdan VELİ ÖRNEKSOY adına {amount} TL gönderilmiştir."
CASH_OUT = "KADIKÖY subesindeki 12345678 no'lu hesabınızdan {amount} TL para çıkışı olmuştur."
TRANSFER_IN_2026 = "Kadıköy Şubesi'ndeki hesabınıza Ayşe Soyadoğlu tarafından {amount} TL gönderilmiştir."
MASKED_HOLDER = "Örnek K***"  # HOLDER as the newest notices mask it


def notice(
    subject: str,
    sentence: str,
    balance: str,
    sent: datetime,
    clock: str = "",
    holder: str = HOLDER,
    sender: str = NOTICE_SENDER,
) -> bytes:
    """A QNB notice laid out like the bank's: the greeting in a paragraph of its own, then the sentence, the balance at
    clock (the time it was sent by default) and the closing words, then the bank's details."""
    when = clock or f"{sent:%H:%M}"
    html = (
        '<html><body text="#000000"><table cellpadding="0" cellspacing="0" border="0"><tr><td width="50%">&nbsp;</td>'
        '<td align="center"><table style="width: 770px"><tr valign="top"><td style="background-color: #1C2455;">'
        '<p><span style="font-family: Tahoma; color: #FFFFFF; font-weight: bold;">'
        f"Sayın {escape(holder)}</span></p>"
        f'<p><span style="font-family: Tahoma; color: #FFFFFF;">{escape(sentence)}<br/><br/>'
        f"Hesabınızın bakiyesi saat {when} itibarıyla {balance} TL tutarındadır.<br/>Saygılarımızla,</span></p>"
        "</td></tr><tr><td><p>Mersis No: 0000-0000-0000-0000 Ticaret Sicil No: 000000 Ünvan: QNB Bank A.Ş.</p>"
        "<p>Bu e-maili düzgün görüntüleyemiyorsanız veya almak istemiyorsanız, lütfen şubeniz ile iletişime "
        "geçiniz.</p></td></tr></table></td></tr></table></body></html>"
    )
    return html_mail(sender, subject, html, sent)


def fast_out(
    sent: datetime = datetime(2026, 10, 20, 14, 6, 31, tzinfo=_ISTANBUL),
    amount: str = "1,250.00",
    balance: str = "-3,480.25",
    clock: str = "14:05",
) -> bytes:
    """A FAST payment sent from the overdraft account, its balance below zero after it: amounts the US way."""
    return notice(FAST_SUBJECT, FAST_OUT.format(amount=amount), balance, sent, clock)


def fast_in(
    sent: datetime = datetime(2026, 10, 22, 9, 40, 2, tzinfo=_ISTANBUL),
    amount: str = "2400.00",
    balance: str = "915.75",
) -> bytes:
    """A FAST payment received from a friend, mailed by QNB Finansbank: no thousands separator."""
    return notice(FAST_SUBJECT, FAST_IN.format(amount=amount), balance, sent, sender=OLD_NOTICE_SENDER)


def transfer_out(sent: datetime = datetime(2026, 10, 25, 19, 46, tzinfo=_ISTANBUL)) -> bytes:
    """A transfer sent from the account named by its number: amounts the Turkish way, a word without its letters."""
    return notice(TRANSFER_SUBJECT, TRANSFER_OUT.format(amount="3.000,00"), "-2.084,25", sent)


def transfer_in(sent: datetime = datetime(2026, 10, 29, 16, 34, tzinfo=_ISTANBUL)) -> bytes:
    """A transfer received, as the newest notices write it: the branch's name capitalised and the greeting masked."""
    return notice(TRANSFER_SUBJECT, TRANSFER_IN_2026.format(amount="7,500.00"), "5,415.75", sent, holder=MASKED_HOLDER)


def cash_out(sent: datetime = datetime(2026, 10, 27, 0, 1, 12, tzinfo=_ISTANBUL)) -> bytes:
    """Money taken out at an ATM just before midnight, mailed just after it."""
    return notice(CASH_SUBJECT, CASH_OUT.format(amount="500,00"), "-2.584,25", sent, "23:58")


def specimens() -> list[Specimen]:
    notices = "qnb.notice.transfer"
    return [
        Specimen("qnb-kart-ekstre.pdf", card_statement(), "qnb.card_pdf", "qnb-1234", 6),
        Specimen("qnb-hesap-hareketleri.pdf", account_pdf(), "qnb.account_pdf", "qnb-12345678", 6),
        Specimen("qnb-gelen-fast-dekont.pdf", transfer_receipt(), "qnb.edekont", "qnb-12345678", 1),
        Specimen("qnb-giden-fast-dekont.html", transfer_receipt_html(), "qnb.edekont", "qnb-12345678", 1),
        Specimen("qnb-giden-fast-bildirimi.eml", fast_out(), notices, "qnb-****", 1),
        Specimen("qnb-gelen-fast-bildirimi.eml", fast_in(), notices, "qnb-****", 1),
        Specimen("qnb-giden-transfer-bildirimi.eml", transfer_out(), notices, "qnb-12345678", 1),
        Specimen("qnb-gelen-transfer-bildirimi.eml", transfer_in(), notices, "qnb-****", 1),
        Specimen("qnb-para-cikisi-bildirimi.eml", cash_out(), notices, "qnb-12345678", 1),
    ]
