"""Garanti BBVA's documents: the Bonus and Paracard card statements, the account list, receipts, and Garanti BBVA
Yatırım's brokerage statements."""

from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html import escape

from ..domain.labels import MONTHS, format_amount
from ..domain.text import fold
from . import HOLDER, CardRow, CardTerms, Move, Specimen, charged, with_balances
from .files import Cell, Run, html_mail, right, text_pdf, xls_file


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


# --- card statements ------------------------------------------------------------------------------------------

_DATE_X, _TEXT_X, _EXTRA_X, _AMOUNT_X1, _POINTS_X = 40, 110, 300, 470, 500
_LINE = 11  # points from one row to the next

# A Bonus card's month over two pages: a payment, purchases under the bank's own headings and under its general
# ones, an installment, a purchase abroad, an ATM withdrawal under the cash advance heading, a deferred statement
# with the payment that goes with it, and the period's undated interest and taxes.
BONUS_PAGES: tuple[tuple[CardRow, ...], ...] = (
    (
        CardRow(date(2026, 9, 12), "ÖDEMENİZ İÇİN TEŞEKKÜR EDERİZ", Decimal(-3250)),
        CardRow(None, "MARKET VE GIDA"),
        CardRow(date(2026, 9, 14), "MIGROS ORNEK SUBE ISTANBUL", Decimal("1245.60")),
        CardRow(date(2026, 9, 18), "ORNEK FIRIN KADIKOY", Decimal(185)),
        CardRow(None, "ELEKTRONİK"),
        CardRow(date(2026, 9, 20), "TEKNOSA ORNEK AVM", Decimal(250), "250,00x12=3.000,00 8.Taksit"),
        CardRow(None, "YURT DIŞI HARCAMALARINIZ"),
        CardRow(date(2026, 9, 22), "NETFLIX.COM AMSTERDAM NL", Decimal("695.40"), "19,99 USD"),
        CardRow(None, "NAKİT AVANS BİLGİLERİ"),
        CardRow(date(2026, 9, 25), "İBB ÖRNEK METROBÜS", Decimal(1000)),
    ),
    (
        CardRow(None, "DİĞER HARCAMALARINIZ"),
        CardRow(date(2026, 9, 28), "ÖDEMENİZ İÇİN TEŞEKKÜR EDERİZ", Decimal(-2000)),
        CardRow(date(2026, 9, 28), "ERTELENEN EKSTRE TUTARI", Decimal(2000)),
        CardRow(date(2026, 10, 1), "TURKCELL FATURA ODEME", Decimal(450)),
        CardRow(None, "DÖNEM FAİZİ", Decimal("45.30")),
        CardRow(None, "KKDF + BSMV", Decimal("13.59")),
    ),
)

# A Paracard month: purchases, and an ATM withdrawal under the cash heading.
PARACARD_PAGES: tuple[tuple[CardRow, ...], ...] = (
    (
        CardRow(None, "HARCAMALARINIZ"),
        CardRow(date(2026, 9, 8), "MIGROS ORNEK SUBE ISTANBUL", Decimal("845.30")),
        CardRow(date(2026, 9, 15), "ORNEK ECZANE BESIKTAS", Decimal("212.75")),
        CardRow(date(2026, 9, 21), "ORNEK MARKET UMRANIYE", Decimal("176.45")),
        CardRow(None, "NAKİT ÇEKİM"),
        CardRow(date(2026, 9, 24), "İBB ÖRNEK METROBÜS", Decimal(500)),
    ),
)


# A Bonus statement's terms: the due date ten days after the cut and the card's limit. Garanti prints no minimum
# payment on the pages the reader reads.
BONUS_TERMS = CardTerms(date(2026, 10, 15), limit=Decimal(45000))
# The customer's limit and the cash advance limit, printed above and below the card's own.
_CUSTOMER_LIMIT, _CASH_LIMIT = Decimal(50000), Decimal(18000)
_WEEKDAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")


def bonus_statement(
    pages: Sequence[Sequence[CardRow]] = BONUS_PAGES,
    cut: date = date(2026, 10, 5),
    previous: Decimal = Decimal(3250),
    last4: str = "1234",
    total: Decimal | None = None,
    terms: CardTerms = BONUS_TERMS,
) -> bytes:
    """A Garanti BBVA Bonus card statement: its summary with terms, the debt carried over (DEVİR), the rows page by
    page, and the debt it ends with, which they add up to unless total says otherwise, as when the reader would miss
    a row."""
    if total is None:
        total = previous + sum((charged(p) for p in pages), Decimal(0))
    head = _bonus_head(cut, total, last4, terms)
    return text_pdf(*_card_pages(head, pages, CardRow(None, "DEVİR", previous), CardRow(None, "TOPLAM", total)))


def _bonus_head(cut: date, total: Decimal, last4: str, terms: CardTerms) -> list[Run]:
    """The first page's head as Garanti prints it: the due date in the heading too, the summary on the left with its
    dates spelled out, and the address on the right, whose last lines fall on the summary's. The sentence under the
    summary names the next cut and the next due date."""
    next_cut = cut + timedelta(days=31)
    next_due = next_cut + timedelta(days=10)
    left = (terms.limit if terms.limit is not None else _CUSTOMER_LIMIT) - total
    later = (
        f"EKSTRE ÖZETİ Bir sonraki hesap kesiminiz {_spelled(next_cut)} {_WEEKDAYS[next_cut.weekday()]} ve son "
        f"ödemeniz {_spelled(next_due)} {_WEEKDAYS[next_due.weekday()]} 'dir."
    )
    available = (
        f"Hesap kesim tarihinizde kullanılabilir limitiniz {format_amount(left)} TL ,kullanılabilir nakit "
        f"limitiniz {format_amount(_CASH_LIMIT)} TL'dir."
    )
    runs: list[Run] = [
        (40, 40, "Garanti BBVA"),
        (40, 64, "Bonus Platinum Örnek Kart Bilgileriniz"),
        (40, 80, f"Kart Numarası 5555 12** **** {last4}"),
        (330, 86, HOLDER),
        (40, 92, f"Müşteri Limiti {format_amount(_CUSTOMER_LIMIT)} TL"),
        (330, 98, "DENEME MAH. 1. SOK. NO:1"),
        (40, 116, f"Nakit Avans Limiti {format_amount(_CASH_LIMIT)} TL"),
        (330, 116, "KAT:3 D:5"),
        (40, 128, f"Hesap Kesim Tarihi {_spelled(cut)}"),
        (330, 128, "34000 ÖRNEKKÖY İSTANBUL"),
        (40, 152, f"Dönem Borcunuz {format_amount(total)} TL"),
        (40, 170, later),
        (40, 182, available),
    ]
    if terms.due is not None:
        runs += [
            (330, 64, f"Son Ödeme Tarihi: {_spelled(terms.due)}"),
            (40, 140, f"Son Ödeme Tarihi {_spelled(terms.due)}"),
        ]
    if terms.limit is not None:
        runs.append((40, 104, f"Kart Limiti {format_amount(terms.limit)} TL"))
    return runs


def paracard_statement(
    pages: Sequence[Sequence[CardRow]] = PARACARD_PAGES, cut: date = date(2026, 10, 5), last4: str = "4321"
) -> bytes:
    """A Garanti BBVA Paracard statement ("Paracard Hesap Cetveli"): a debit card has no debt, only the sums of
    its purchases and of its cash withdrawals."""
    purchases = cash = Decimal(0)
    for page in pages:
        heading = ""
        for row in page:
            if row.amount is None:
                heading = row.text
            elif "NAKIT CEKIM" in fold(heading):
                cash += row.amount
            else:
                purchases += row.amount
    summary = [
        (40, 40, "Garanti BBVA"),
        (40, 52, "Paracard Hesap Cetveli"),
        *_address(),
        (330, 80, f"Kart No: 5555 12** **** {last4}"),
        (330, 92, f"Hesap Kesim Tarihiniz {_spelled(cut)}"),
        (330, 104, f"Toplam Alışveriş Tutarınız {format_amount(purchases)}"),
        (330, 116, f"Toplam Nakit Çekim Tutarınız {format_amount(cash)}"),
    ]
    return text_pdf(*_card_pages(summary, pages, None, CardRow(None, "TOPLAM", purchases + cash)))


def _address() -> list[Run]:
    return [(40, 80, HOLDER), (40, 92, "DENEME MAH. 1. SOK. NO:1"), (40, 104, "34000 İSTANBUL")]


def _spelled(day: date) -> str:
    """As Garanti writes a date: "5 Ekim 2026"."""
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def _card_amount(value: Decimal) -> str:
    """As Garanti prints an amount: a credit with a trailing plus ("3.250,00+")."""
    return format_amount(abs(value)) + ("+" if value < 0 else "")


def _card_pages(
    summary: list[Run], pages: Sequence[Sequence[CardRow]], first: CardRow | None, last: CardRow
) -> list[list[Run]]:
    """The statement's pages: the summary above the first page's table, every page's table under its own header,
    first opening the first table and last closing the last one."""
    out: list[list[Run]] = []
    for i, rows in enumerate(pages):
        top = 200 if i == 0 else 60
        table = [*([first] if first and i == 0 else []), *rows, *([last] if i == len(pages) - 1 else [])]
        out.append([*(summary if i == 0 else []), *_card_table(top, table)])
    return out


def _card_table(top: float, rows: Sequence[CardRow]) -> list[Run]:
    runs: list[Run] = [
        (_DATE_X, top, "İşlem Tarihi"),
        (_TEXT_X, top, "Dönem İçi İşlemler"),
        (_EXTRA_X, top, "Kalan Taksit"),
        right(_AMOUNT_X1, top, "Tutar (TL)"),
        (_POINTS_X, top, "Bonus"),
    ]
    for n, row in enumerate(rows, 1):
        y = top + 3 + n * _LINE
        if row.day is not None:
            runs.append((_DATE_X, y, _spelled(row.day)))
        runs.append((_TEXT_X, y, row.text))
        if row.extra:
            runs.append((_EXTRA_X, y, row.extra))
        if row.amount is not None:
            runs.append(right(_AMOUNT_X1, y, _card_amount(row.amount)))
            if row.day is not None and row.amount > 0:
                runs.append((_POINTS_X, y, format_amount(row.amount * Decimal("0.005"))))  # the Bonus it earned
    return runs


# --- account lists --------------------------------------------------------------------------------------------

# A month on a current account: salary, rent sent by FAST with its fee, a bill, a card payment, money received by
# havale and a debit card purchase.
ACCOUNT_MOVES: tuple[Move, ...] = (
    Move(date(2026, 10, 1), "MAAŞ ÖDEMESİ ÖRNEK İŞVEREN A.Ş.", Decimal(40000)),
    Move(date(2026, 10, 3), "FAST123456789-VELİ ÖRNEKSOY-EKİM KİRA", Decimal(-15000)),
    Move(date(2026, 10, 3), "FAST ÜCRETİ", Decimal(-8)),
    Move(date(2026, 10, 6), "İGDAŞ FATURA ÖDEMESİ", Decimal(-450)),
    Move(date(2026, 10, 10), "KRE.KART BORC ODEME 1234", Decimal(-3250)),
    Move(date(2026, 10, 15), "AYŞE SOYADOĞLU Havale", Decimal(2500)),
    Move(date(2026, 10, 20), "MIGROS ORNEK SUBE ISTANBUL", Decimal("-845.30")),
)
# The bank's own label of a row, by the start of its text.
_LABELS = (
    ("MAAŞ", "Maaş"),
    ("FAST1", "Para Transferi"),
    ("AYŞE", "Para Transferi"),
    ("İGDAŞ", "Fatura"),
    ("MIGROS", "Alışveriş"),
)


def account_xls(
    moves: Sequence[Move] = ACCOUNT_MOVES,
    opening: Decimal = Decimal(1000),
    number: str = "1234567",
    holder: str = HOLDER,
    period: tuple[date, date] = (date(2026, 10, 1), date(2026, 10, 31)),
) -> bytes:
    """A Garanti BBVA "Hesap Hareketleri" export (XLS): the account and its holder above a table of rows, newest
    first, each with the bank's label and the balance after it."""
    head: list[list[Cell]] = [
        ["T. Garanti Bankası A.Ş.", None, None, None, None],
        ["Hesap Hareketleri"],
        ["Hesap", f"106 - {number} TL", None, "Ad Soyad", holder],
        ["Başlangıç", f"{period[0]:%d.%m.%Y}", None, "Bitiş", f"{period[1]:%d.%m.%Y}"],
        ["IBAN", f"TR00 0006 2000 1060 000{number}"],
        [],
        ["Tarih", "Açıklama", "Etiket", "Tutar", "Bakiye"],
    ]
    rows: list[list[Cell]] = [
        [
            f"{m.day:%d.%m.%Y}",
            m.text,
            next((label for start, label in _LABELS if m.text.startswith(start)), ""),
            float(m.amount),
            float(balance),
        ]
        for m, balance in with_balances(moves, opening)
    ]
    return xls_file("Hesap Hareketleri", head + rows[::-1])


def brokerage_statement() -> bytes:
    """The June 2026 statement of brokerage account 1234567-101: two securities and the month-end totals on the
    holdings page, and on the cash page a dividend that came in and went on to the bank account."""
    held = [("ORNEK", "ÖRNEK SANAYİ A.Ş.", "20.000", "1,234.50"), ("DENEM", "DENEME HOLDİNG", "5.000", "100.00")]
    cash = brokerage_page("Hesap Ekstresi", "1234567-101", "30/06/2026") + [
        (43, 140, "Dönemi : 01/06/2026 - 30/06/2026"),
        (54, 242, "Tarih"),
        (196, 242, "Açıklama"),
        (381, 242, "İşlem"),
        (487, 242, "Kalan"),
        (40, 262, "03/06/2026"),
        (99, 262, "Devir 1234567-101 Cari TRY Bakiye Hareketleri"),
        right(445, 262, "+0.00"),
        right(550, 262, "0.00"),
        (40, 272, "03/06/2026"),
        (99, 272, "ORNEK.E Temettü 20 Adet Temettü Oranı : 50.00000000"),
        right(445, 272, "+10.00"),
        right(550, 272, "10.00"),
        (40, 283, "03/06/2026"),
        (99, 283, "ORNEK.E Temettü 20 Adet Temettü Oranı : 50.00000000-1234567-101"),
        right(445, 283, "-10.00"),
        right(550, 283, "0.00"),
    ]
    return text_pdf(holdings_page("30/06/2026", held, "1,334.50", "1,334.50"), cash)


def trade_form(holder: str = HOLDER) -> bytes:
    """A Garanti BBVA Yatırım "İşlem Sonuç Formu": ten ORNEK shares sold at 12,34 TL on 1 July 2024, 1,000 TL of
    costs."""
    return text_pdf(
        [
            (36, 72, "Garanti Yatırım Menkul Kıymetler A.Ş."),
            (36, 118, "www.garantibbvayatirim.com.tr"),
            (248, 151, "İŞLEM SONUÇ FORMU"),
            (36, 171, "Müşteri Adı"),
            (113, 171, ":"),
            (121, 171, holder),
            (302, 171, "Şube"),
            (379, 171, ":"),
            (387, 171, "XYZ"),
            (36, 182, "Müşteri No"),
            (113, 182, ":"),
            (121, 182, "1234567-101"),
            (36, 192, "Ait Olduğu Tarih"),
            (113, 192, ":"),
            (121, 192, "01.07.2024"),
            (36, 214, "Belge Sıra No"),
            (113, 214, ":"),
            (121, 214, "99887766"),
            (39, 273, "01.07.2024"),
            (106, 273, "ORNEK"),
            (160, 273, "SATIŞ"),
            (270, 273, "10,000"),
            (315, 273, "12,340"),
            (357, 273, "123,400"),
            (432, 273, "1,000"),
            (479, 273, "MOBIL"),
            (39, 365, "GENEL TOPLAM"),
            (537, 365, "1,000"),
        ]
    )


NOTICE_SENDER = "bilgilendirme@garantibbva.com.tr"
OLD_NOTICE_SENDER = "bilgilendirme@info.garantibbva.com.tr"
_ISTANBUL = timezone(timedelta(hours=3))
_NOTICE_FOOTER = (
    "<p>T.Garanti Bankası A.Ş. Genel Müdürlük: Örnek Mah. Deneme Cad. 1, İstanbul</p>"
    "<p>Bu e-posta'nın size ait olmadığını düşünüyorsanız Müşteri İletişim Merkezi'ni arayabilirsiniz.</p>"
)
_NOTICE_PURPOSE = (
    "Bilgilendirmeler, belirli tutarın üzerindeki para transferlerinizin istediğiniz şekilde gerçekleştiğini "
    "bildirmek amacıyla gönderilmektedir."
)


def _lines(*lines: str) -> str:
    return "".join(f"<div>{escape(line)}</div>" for line in lines)


def transfer_notice(
    sent: datetime = datetime(2026, 10, 30, 14, 40, tzinfo=_ISTANBUL),
    amount: str = "12.750,00",
    receiver: str = "Ör**** Ku******",
    note: str = "KART ÖDEMESİ",
) -> bytes:
    """A transfer notice as Garanti sends it since 2026: names masked but for the first letters of their words, the
    account but for its last three digits, the receiver's IBAN masked in the middle and its bank named."""
    html = (
        "<html><body>"
        + _lines(
            "Giden PT Bilgilendirmesi - 'Havale' işlem tipi için email",
            "Gerçekleşen İşlem",
            "Para Transferi Bilgilendirmesi",
            "Başka Bankaya Transfer",
            "Değerli Müşterimiz,",
            "Para transferi işleminiz gerçekleşmiştir.",
            _NOTICE_PURPOSE,
            "Gönderen Bilgileri:",
            "ÖR**** KU******",
            "MERKEZ - 106",
            "****567",
            "Alıcı Bilgileri:",
            receiver,
            "-",
            "TR000011100000********001",
            "QNB BANK A.Ş.",
            f"Tutar: {amount} TL",
            f"İşlem Tarihi: {sent:%d.%m.%Y %H:%M}",
            f"Açıklama: {note}",
            "İyi günler dileriz.",
        )
        + _NOTICE_FOOTER
        + "</body></html>"
    )
    return html_mail(NOTICE_SENDER, "Para Transferi Bilgilendirmesi", html, sent)


def old_transfer_notice(
    sent: datetime = datetime(2024, 10, 22, 9, 40, tzinfo=_ISTANBUL),
    amount: str = "650,00",
    kind: str = "Havale Para transferi işleminiz gerçekleşmiştir.",
    receiver: tuple[str, ...] = ("VELİ ÖRNEKSOY", "TR00 0006 2000 0000 0000 1234 56"),
    holder: str = HOLDER,
    note: str = "EKİM KİRA ÖDEMESİ",
) -> bytes:
    """A transfer notice as Garanti sent it until 2025: the customer greeted by name, names and numbers whole, the
    receiver's IBAN printed in groups (or a Garanti branch and account), the kind in the first sentence."""
    html = (
        "<html><body>"
        + _lines(
            "Garanti",
            f"Sayın {holder},",
            kind,
            _NOTICE_PURPOSE,
            "Gönderen Bilgileri:",
            holder,
            "MERKEZ - 106",
            "1234567",
            "Alıcı Bilgileri:",
            *receiver,
            f"Tutar: {amount} TL",
            f"İşlem Tarihi: {sent:%d.%m.%Y %H:%M}",
            f"Açıklama: {note}",
            "Para transferleri bilgilendirmeleri işlem limitlerinizi değiştirebilirsiniz.",
        )
        + _NOTICE_FOOTER
        + "</body></html>"
    )
    return html_mail(OLD_NOTICE_SENDER, "Para Transferi Bilgilendirmesi", html, sent)


def specimens() -> list[Specimen]:
    fast = receipt(
        "HESAPTAN FAST", "106/1234567", HOLDER, fast_body("EKİM KİRA ÖDEMESİ", "VELİ ÖRNEKSOY"), "- 500,00 TL"
    )
    brokerage = "garanti-yatirim-1234567-101"
    return [
        Specimen("garanti-bonus-ekstre.pdf", bonus_statement(), "garanti.bonus_card", "garanti-1234", 11),
        Specimen("garanti-paracard-cetvel.pdf", paracard_statement(), "garanti.paracard", "garanti-4321", 4),
        Specimen("garanti-hesap-hareketleri.xls", account_xls(), "garanti.account_xls", "garanti-1234567", 7),
        Specimen("garanti-fast-dekont.pdf", fast, "garanti.receipt", "garanti-1234567", 2),
        Specimen("garanti-yatirim-ekstre.pdf", brokerage_statement(), "garanti.brokerage", brokerage, 2),
        Specimen("garanti-yatirim-islem-sonuc-formu.pdf", trade_form(), "garanti.brokerage", brokerage, 2),
        Specimen("garanti-transfer-bildirimi.eml", transfer_notice(), "garanti.notice.transfer", "garanti-****567", 1),
        Specimen(
            "garanti-eski-transfer-bildirimi.eml",
            old_transfer_notice(),
            "garanti.notice.transfer",
            "garanti-1234567",
            1,
        ),
    ]
