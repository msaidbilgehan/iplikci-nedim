"""İş Bankası's documents: the Maximum card statement, the account list, the FAST receipt, the e-cüzdan and the
notice of a card debt collected from an account."""

from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from ..domain.labels import format_amount
from . import HOLDER, CardRow, CardTerms, Move, Specimen, charged, with_balances
from .files import Cell, Run, html_mail, right, text_pdf, xls_file

_DATE_X, _TEXT_X, _AMOUNT_X1, _INSTALLMENT_X, _POINTS_X = 40, 100, 400, 410, 520
_LINE = 11

# A Maximum card's month: a payment, purchases, an installment, an installment cash advance whose interest
# breakdown wraps onto the next line, its fee, a cancelled purchase and a line that only reports MaxiPuan.
MAXIMUM_PAGES: tuple[tuple[CardRow, ...], ...] = (
    (
        CardRow(date(2026, 9, 12), "9999-1234567 HESAPTAN AKTARIM İNTERAKTİF", Decimal(-3250)),
        CardRow(date(2026, 9, 14), "MIGROS ORNEK SUBE ISTANBUL", Decimal("1245.60")),
        CardRow(date(2026, 9, 16), "TEKNOSA ORNEK AVM", Decimal(500), "2/6 taksidi (3.000,00)"),
        CardRow(date(2026, 9, 19), "TAKSİTLİ NAKİT AVANS - HESABA HAVALE KALAN:3.000,00", Decimal(1500)),
        CardRow(None, "FZ:120.00 VR/FN:36.00"),
        CardRow(date(2026, 9, 19), "NAKİT AVANS ÜCRETİ", Decimal("34.50")),
        CardRow(date(2026, 9, 23), "ORNEK PETROL ISTANBUL TR İŞLEM İPTALI", Decimal("-234.56")),
        CardRow(date(2026, 9, 26), "BU DÖNEM 125 MAXIPUAN KAZANDINIZ"),
        CardRow(date(2026, 10, 2), "SPOTIFY ISTANBUL TR", Decimal("99.99")),
    ),
)


# A Maximum statement's terms: the due date ten days after the cut, a minimum of the 40 % its box of limits prints as
# the rate, the card's limit and the next cut, a day before the same day a month on.
MAXIMUM_TERMS = CardTerms(date(2026, 10, 15), Decimal("1258.21"), Decimal(60000), date(2026, 11, 4))
# The customer's limit and the cash limit, printed in the box beside the card's own.
_CUSTOMER_LIMIT, _CASH_LIMIT = Decimal(75000), Decimal(24000)


def maximum_statement(
    pages: Sequence[Sequence[CardRow]] = MAXIMUM_PAGES,
    cut: date = date(2026, 10, 5),
    previous: Decimal = Decimal(3250),
    last4: str = "1234",
    holder: str = HOLDER,
    note: str = "",
    terms: CardTerms = MAXIMUM_TERMS,
) -> bytes:
    """An İş Bankası Maximum card statement ("Kredi Kartı Hesap Özeti"): its summary with terms and its box of limits,
    the previous debt, the rows page by page, and the debt they add up to; note goes at the foot of the first page. A
    fold mark sits in the left margin of every page."""
    total = previous + sum((charged(p) for p in pages), Decimal(0))
    out: list[list[Run]] = []
    for i, rows in enumerate(pages):
        top = 290 if i == 0 else 60
        head = _maximum_head(cut, total, last4, holder, terms) if i == 0 else []
        runs = [*head, (12, 420, "-"), *_table(top, rows)]
        if i == 0 and note:
            runs.append((40, 800, note))
        if i == 0:
            runs += [
                (_DATE_X, top + 3 + _LINE, "*** ÖNCEKİ DÖNEM BORCU"),
                right(_AMOUNT_X1, top + 3 + _LINE, _amount(previous)),
            ]
        out.append(runs)
    return text_pdf(*out)


def _maximum_head(cut: date, total: Decimal, last4: str, holder: str, terms: CardTerms) -> list[Run]:
    """The first page's head: the summary in the right column beside the holder's name, its dates with dots, and the
    box of limits and rates under it in two columns, which a page's text runs into one line. The summary prints the
    next statement's dates too, and the box prints the due date again with slashes."""
    left = (terms.limit if terms.limit is not None else _CUSTOMER_LIMIT) - total
    runs: list[Run] = [
        (40, 40, "TÜRKİYE İŞ BANKASI A.Ş."),
        (40, 52, "Kredi Kartı Hesap Özeti"),
        (40, 76, f"Kart Numarası: 4543 **** **** {last4}"),
        (40, 100, f"SN. {holder}"),
        (330, 100, f"Hesap Kesim Tarihi: {cut:%d.%m.%Y}"),
        (330, 124, f"Hesap Özeti Borcu: {_amount(total)} TL"),
        (40, 196, f"Müşteri Limiti: {format_amount(_CUSTOMER_LIMIT)} TL"),
        (330, 196, "Alışveriş Faiz Oranı: %4,25"),
        (40, 208, f"Kullanılabilir Müşteri Limiti: {format_amount(_CUSTOMER_LIMIT - total)} TL"),
        (330, 208, "Nakit Çekme Faiz Oranı: %4,25"),
        (330, 220, "Asgari Ödeme Oranı: %40,00"),
        (40, 232, f"Toplam Kullanılabilir Kart Limiti: {format_amount(left)} TL"),
        (330, 232, "Alışveriş Gecikme Faizi: %4,55"),
        (40, 244, f"Nakit Çekme Limiti: {format_amount(_CASH_LIMIT)} TL"),
        (330, 244, "Nakit Gecikme Faizi: %4,55"),
        (40, 256, f"Kullanılabilir Nakit Çekme Limiti: {format_amount(_CASH_LIMIT - total)} TL"),
    ]
    if terms.due is not None:
        runs += [
            (330, 112, f"Son Ödeme Tarihi: {terms.due:%d.%m.%Y}"),
            (40, 184, f"Son Ödeme Tarihi: {terms.due:%d/%m/%Y}"),
        ]
    if terms.minimum is not None:
        runs.append((330, 136, f"Ödenmesi Gereken Asgari Tutar: {_padded(terms.minimum)} TL"))
    if terms.next_cut is not None:
        runs += [
            (330, 148, f"Bir Sonraki Hesap Kesim Tarihi: {terms.next_cut:%d.%m.%Y}"),
            (330, 160, f"Bir Sonraki Son Ödeme Tarihi: {terms.next_cut + timedelta(days=10):%d.%m.%Y}"),
        ]
    if terms.limit is not None:
        runs.append((40, 220, f"Toplam Kart Limiti: {format_amount(terms.limit)} TL"))
    return runs


def _padded(value: Decimal) -> str:
    """The minimum due as the statement prints it, in a fixed width whose empty places are asterisks: "*1.258,21",
    and "*.597,67" for an amount under a thousand."""
    return ("*." if value < 1000 else "*") + format_amount(value)


def _amount(value: Decimal) -> str:
    """As İş Bankası prints an amount: a credit with a leading plus ("+3.250,00")."""
    return ("+" if value < 0 else "") + format_amount(abs(value))


def _table(top: float, rows: Sequence[CardRow]) -> list[Run]:
    """A page's table; on the first page the previous debt takes the row under the header."""
    runs: list[Run] = [
        (_DATE_X, top, "Tarih"),
        (_TEXT_X, top, "Açıklama"),
        right(_AMOUNT_X1, top, "Tutar"),
        (_INSTALLMENT_X, top, "Taksit"),
        (_POINTS_X, top, "MaxiPuan"),
    ]
    for n, row in enumerate(rows, 2):
        y = top + 3 + n * _LINE
        if row.day is not None:
            runs.append((_DATE_X, y, f"{row.day:%d/%m/%Y}"))
        runs.append((_TEXT_X, y, row.text))
        if row.amount is not None:
            runs.append(right(_AMOUNT_X1, y, _amount(row.amount)))
            if row.amount > 0:
                runs.append((_POINTS_X, y, format_amount(row.amount * Decimal("0.002"))))
        if row.extra:
            runs.append((_INSTALLMENT_X, y, row.extra))
    return runs


# --- account lists --------------------------------------------------------------------------------------------

# A month on a current account: salary, rent sent by FAST ("AD*" before the note) with its fee, a card payment,
# money back by havale and a debit card purchase, each with the bank's transaction type.
ACCOUNT_MOVES: tuple[tuple[Move, str], ...] = (
    (Move(date(2026, 10, 1), "ÖRNEK İŞVEREN A.Ş. MAAŞ ÖDEMESİ", Decimal(40000)), "Maaş"),
    (Move(date(2026, 10, 3), "VELİ ÖRNEKSOY*EKİM KİRA ÖDEMESİ", Decimal(-15000)), "FAST"),
    (Move(date(2026, 10, 3), "FAST ÜCRETİ", Decimal("-8.86")), "Ücret"),
    (Move(date(2026, 10, 12), "KREDİ KARTI ÖDEMESİ 4543****1234", Decimal(-3250)), "Ödeme"),
    (Move(date(2026, 10, 18), "AYŞE SOYADOĞLU*BORÇ İADESİ", Decimal(2500)), "Havale"),
    (Move(date(2026, 10, 25), "ORNEK MARKET UMRANIYE", Decimal("-312.40")), "Alışveriş"),
)


# What the bank prints under the table: blank rows, then its note on the sign of the amounts.
FOOTNOTE_ROWS: tuple[tuple[Cell, ...], ...] = ((), (), ("(*) Çekilen tutar '-' ile gösterilmiştir.",))


def account_xls(
    moves: Sequence[tuple[Move, str]] = ACCOUNT_MOVES,
    opening: Decimal = Decimal(1000),
    holder: str = HOLDER,
    period: tuple[date, date] = (date(2026, 10, 1), date(2026, 10, 31)),
    made: date | None = None,
    below: Sequence[Sequence[Cell]] = (),
    product: str = "Vadesiz - TL",
    iban: str = "TR00 0006 4000 0011 2340 1234 56",
) -> bytes:
    """An İş Bankası "Hesap Özeti" export (XLS) of account 1234-0123456 (the IBAN's last eleven digits): the holder
    and the account above a table of rows, newest first. The text column has an empty neighbour before the reference;
    the reader joins the cells between the two headings. made: the day the summary was made ("Belge Düzenleme
    Tarihi"), printed beside the balance it had then; below: what the bank prints under the rows (FOOTNOTE_ROWS);
    product: the account's "Ürün-Döviz Tipi"."""
    balanced = with_balances([m for m, _ in moves], opening)
    head: list[list[Cell]] = [
        ["TÜRKİYE İŞ BANKASI A.Ş."],
        ["Hesap Özeti"],
        [f"Sayın {holder}"],
        ["Ürün-Döviz Tipi", product, "IBAN", iban],
        ["Mevcut Bakiye", f"{format_amount(balanced[-1][1] if balanced else opening)} TL"],
        *([["Belge Düzenleme Tarihi", f"{made:%d.%m.%Y} - 10:30:00"]] if made else []),
        ["Sorgulama Kriterleri", f"{period[0]:%d.%m.%Y} - {period[1]:%d.%m.%Y}"],
        [],
        ["Tarih/Saat", "İşlem Tipi", "İşlem Tutarı*", "Bakiye", "Açıklama", None, "Referans"],
    ]
    rows: list[list[Cell]] = [
        [f"{m.day:%d/%m/%Y}-10:00:00", kind, float(m.amount), float(balance), m.text, None, f"{n:08d}"]
        for n, ((m, balance), (_, kind)) in enumerate(zip(balanced, moves, strict=True), 1)
    ]
    return xls_file("Hesap Özeti", head + rows[::-1] + [list(row) for row in below])


DEPOSIT_MOVES: tuple[tuple[Move, str], ...] = (
    (Move(date(2026, 11, 10), f"1234/0123456 HESAPTAN {HOLDER} Hesaplar Arası Akt", Decimal(30000)), "Para Transferi"),
    (Move(date(2026, 11, 12), "BRÜT FAİZ %30.00 ÜZERİNDEN 1 GÜN", Decimal("25.00")), "Faiz"),
    (Move(date(2026, 11, 12), "BRÜT FAİZDEN %17.50 GELİR VERGİSİ STOPAJI", Decimal("-4.38")), "Vergi"),
)


def deposit_xls() -> bytes:
    """The "Hesap Özeti" of an interest-earning account, 1234-0234567: İş Bankası names its product "Vadeli Hesap", the
    daily-interest one too. Filled from the current account, it earns a day's gross interest and has the tax withheld
    from it."""
    period = (date(2026, 11, 10), date(2026, 11, 20))
    iban = "TR00 0006 4000 0011 2340 2345 67"
    return account_xls(DEPOSIT_MOVES, Decimal(0), period=period, product="Vadeli Hesap", iban=iban)


def quiet_account_xls() -> bytes:
    """A month of account 1234-0123456 without a movement, as İş Bankası sends it: no row, only blank ones down to
    its footnote, and the balance it had when the summary was made on the period's last day."""
    period = (date(2026, 10, 1), date(2026, 10, 31))
    return account_xls((), Decimal("2500.00"), period=period, made=period[1], below=FOOTNOTE_ROWS)


# --- receipts and passbooks -------------------------------------------------------------------------------------


def fast_receipt(holder: str = HOLDER) -> bytes:
    """An İş Bankası receipt of a FAST sent from account 1234-0123456 on 8 February 2024: 8.400,00 TRY of rent to
    Veli Örneksoy at Yapı Kredi and an 8,86 TRY fee, the sender's side on the left and the receiver's on the
    right."""
    return text_pdf(
        [
            (6, 78, holder),
            (301, 78, "İşlem Yeri"),
            (397, 78, ":"),
            (402, 78, "MOBİL BANKACILIK"),
            (301, 89, "İşlem Tarihi"),
            (397, 89, ":"),
            (402, 89, "08.02.2024 / 14:32:05"),
            (6, 100, "Müşteri No"),
            (67, 100, ":"),
            (72, 100, "111222333"),
            (301, 122, "Belge No"),
            (397, 122, ":"),
            (402, 122, "100000000001"),
            (6, 167, "Giden Fast İşlemi"),
            (6, 178, "IBAN"),
            (122, 178, ":"),
            (130, 178, "TR00 0006 4000 0011 2340 1234 56"),
            (298, 178, "Sorgu Numarası"),
            (370, 178, ":"),
            (378, 178, "1234567890"),
            (6, 189, "İşlem Tutarı"),
            (122, 189, ":"),
            (130, 189, "8.400,00 TRY"),
            (298, 189, "Alıcı Banka"),
            (370, 189, ":"),
            (378, 189, "67 - Yapı ve Kredi Bankası A.Ş."),
            (6, 200, "FAST Ücreti ve Vergi"),
            (122, 200, ":"),
            (130, 200, "8,86 TRY"),
            (298, 200, "Alıcı IBAN"),
            (370, 200, ":"),
            (378, 200, "TR00 0006 7010 0000 0012 3456 78"),
            (6, 211, "Toplam İşlem Tutarı"),
            (122, 211, ":"),
            (130, 211, "8.400,00 TRY"),
            (298, 211, "Alıcı Isim\\Unvan"),
            (370, 211, ":"),
            (378, 211, "Veli Örneksoy"),
            (6, 266, "Açıklama"),
            (64, 266, ":"),
            (81, 266, "2024 Şubat Kira Ödemesi"),
        ]
    )


def passbook(holder: str = HOLDER) -> bytes:
    """The e-cüzdan of a 31-day term deposit, 1234-0765432, opened on 17 January 2024 with 7.500,00 TL from
    the current account: the account on the first page, its rows newest first on the second."""
    return text_pdf(
        [
            (276, 61, "e-CÜZDAN"),
            (310, 105, "Müşteri Adı / Numarası :"),
            (310, 113, f"{holder} / 111222333"),
            (310, 169, "Hesap No: 1234-0765432"),
            (310, 177, "IBAN: TR00 0006 4000 0011 2340 7654 32"),
            (310, 185, "Hesap Türü: Vadeli (31 gün)"),
            (310, 209, "Para Birimi: TL"),
            (310, 217, "Açılış Tarihi: 17/01/2024"),
        ],
        [
            (31, 39, "#"),
            (71, 39, "Tarih"),
            (145, 39, "Açıklama"),
            (330, 39, "Yatan(+) / Çekilen(-)"),
            right(461, 39, "Tutar"),
            right(577, 39, "Kalan"),
            (31, 50, "1"),
            (51, 50, "17/01/2024-10:42:08"),
            (145, 50, "CÜZDAN VERME"),
            right(461, 50, "0,00"),
            right(577, 50, "7.500,00"),
            (31, 60, "2"),
            (51, 60, "17/01/2024-10:42:07"),
            (145, 60, "HESAP AÇMA İŞLEMİ 1234:0123456 -> 1234:0765432"),
            right(461, 60, "7.500,00"),
            right(577, 60, "7.500,00"),
            (31, 70, "3"),
            (51, 70, "17/01/2024-10:42:07"),
            (145, 70, "HESABA 111222333 NOLU MÜŞTERİ EKLENDİ."),
            right(461, 70, "0,00"),
            right(577, 70, "0,00"),
        ],
    )


# --- notices ----------------------------------------------------------------------------------------------------

NOTICE_SENDER = "bilgilendirme@ileti.isbank.com.tr"
COLLECTION_SUBJECT = "Hesabınızdan Gecikmedeki Kredi Kartı Borcunuzun Tahsilatı"
_ISTANBUL = timezone(timedelta(hours=3))


def collection_notice(
    sent: datetime = datetime(2026, 10, 16, 9, 12, tzinfo=_ISTANBUL), amount: str = "1.258,21", account: str = "123456"
) -> bytes:
    """The bank took a Maximum card's overdue debt from account 1234-0123456, which the notice writes without its
    leading zero."""
    html = (
        "<html><body><table><tr><td>İş Bankası</td></tr>"
        "<tr><td>Bu mesajı düzgün görüntüleyemiyorsanız lütfen <a href='https://www.isbank.com.tr'>tıklayınız</a>."
        "</td></tr><tr><td><p>Merhaba,</p>"
        f"<p>1234 no ile biten kredi kartınıza ait son ödeme tarihinde ödenmeyen {amount} TL'lik borç tutarı, "
        f"1234-{account} no'lu hesabınızdan takas yoluyla tahsil edilmiştir.</p>"
        "<p>Kredi puanınızın düşmemesi ve gecikmenin devam etmemesi için kredi kartınıza ait borcun tamamının "
        "ödendiğinden emin olunuz.</p><p>Güzel günler dileriz.</p></td></tr>"
        "<tr><td>isbank.com.tr</td></tr></table></body></html>"
    )
    return html_mail(NOTICE_SENDER, COLLECTION_SUBJECT, html, sent)


def specimens() -> list[Specimen]:
    return [
        Specimen("isbank-maximum-ekstre.pdf", maximum_statement(), "isbank.maximum_card", "isbank-1234", 8),
        Specimen("isbank-hesap-ozeti.xls", account_xls(), "isbank.account_xls", "isbank-1234-0123456", 6),
        Specimen(
            "isbank-hesap-ozeti-hareketsiz.xls", quiet_account_xls(), "isbank.account_xls", "isbank-1234-0123456", 0
        ),
        Specimen("isbank-vadeli-hesap-ozeti.xls", deposit_xls(), "isbank.account_xls", "isbank-1234-0234567", 3),
        Specimen("isbank-fast-dekont.pdf", fast_receipt(), "isbank.receipt", "isbank-1234-0123456", 2),
        Specimen("isbank-e-cuzdan.pdf", passbook(), "isbank.passbook", "isbank-1234-0765432", 1),
        Specimen("isbank-kart-borcu-tahsilati.eml", collection_notice(), "isbank.notice.collection", "isbank-1234", 1),
    ]
