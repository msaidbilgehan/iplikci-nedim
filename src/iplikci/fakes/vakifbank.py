"""Vakıfbank's documents: the account list as an XLSX export, the e-cüzdan, and the transfer notices it e-mails."""

from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from html import escape

from . import HOLDER, Move, Specimen, with_balances
from .files import html_mail, text_pdf, xlsx_file

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


NOTICE_SENDER = "bilgilendirme@vakifbank.com.tr"
FAST_SUBJECT = "VAKIFBANK - FAST Anlık Ödeme Bilgilendirmesi"
OUTFLOW_SUBJECT = "Bilgilendirme: Mevduat Hesabı Para Çıkışları"
FAST_IN = "Hesabınıza FAST Anlık Ödeme gelmiştir."
FAST_OUT = "Bankamızdan gönderdiğiniz FAST Anlık Ödeme işleminiz başarı ile gerçekleştirilmiştir."
OUTFLOW = "Mevduat hesabınızdan gerçekleşen para çıkış detayları aşağıda yer almaktadır."
MASKED_HOLDER = "Ör**** Ku******"  # HOLDER as the bank masks it
_ISTANBUL = timezone(timedelta(hours=3))


def notice(subject: str, sentence: str, rows: Sequence[tuple[str, str]], sent: datetime) -> bytes:
    """A Vakıfbank notice laid out like the bank's: the title and a style in the head, the logo row, "Sayın" with the
    masked name, the sentence written straight into a table, the rows of label, colon and value, the closing words."""
    cells = "".join(
        f'<tr><td>{escape(label)}</td><td align="right">:</td><td>{escape(value)}</td></tr>' for label, value in rows
    )
    html = (
        '<html><head><title>VakıfBank</title><meta charset="utf-8"><style>td { font-family: Arial; }</style></head>'
        '<body><table width="100%" align="center"><tbody><tr><td align="center"><center><table width="700">'
        '<tr><td width="519"><a href="https://www.vakifbank.com.tr"><img width="519" alt=""></a></td></tr>'
        '<tr><td width="700" colspan="6"><table><tbody><tr><td width="25"></td><td><table width="700">'
        f'<tr><td width="22"></td><td class="notranslate">Sayın {escape(MASKED_HOLDER)}</td><td width="30"></td></tr>'
        f'<tr><td></td></tr><tr><td><table align="center">{escape(sentence)}<br><br><tr><td><table>{cells}</table>'
        '</td></tr></table><br><br></td><td width="25"></td></tr>'
        '<tr><td width="700" colspan="2">Saygılarımızla,<br>VakıfBank</td></tr>'
        '<tr><td width="700" colspan="2"><br><span>Not: Bu e-posta otomatik gönderilmiştir, lütfen bu adrese e-posta '
        "göndermeyiniz.<br>Herhangi bir sorununuz olduğu takdirde 0850 000 00 00 numaralı Müşteri İletişim "
        "Merkezimizi arayabilirsiniz.</span></td></tr></table></td></tr></tbody></table></td></tr></table></center>"
        "</td></tr></tbody></table></body></html>"
    )
    return html_mail(NOTICE_SENDER, subject, html, sent)


def fast_in(
    sent: datetime = datetime(2026, 10, 15, 14, 5, 12, tzinfo=_ISTANBUL),
    amount: str = "2.500 TL",
    balance: str = "3.500 TL",
    sender: str = "Ke**** De******",
) -> bytes:
    """A FAST payment that came in from a friend's account at another bank."""
    return notice(
        FAST_SUBJECT,
        FAST_IN,
        [
            ("İşlem Tarihi", f"{sent:%d.%m.%Y %H:%M:%S}"),
            ("Hesap Numarası", "*************1234"),
            ("Gönderen Banka", "Enpara Bank A.Ş."),
            ("Gönderen Adı Soyadı", sender),
            ("Sorgu Numarası", "1234567890"),
            ("İşlem Tutarı", amount),
            ("Güncel Bakiye", balance),
        ],
        sent,
    )


def fast_out(
    sent: datetime = datetime(2026, 10, 20, 9, 30, tzinfo=_ISTANBUL),
    amount: str = "1.000 TL",
    balance: str = "2.500 TL",
    receiver: str = "ÖR**** KU******",
) -> bytes:
    """A FAST payment sent to the user's own account at another bank: the receiver's name is the user's, masked."""
    return notice(
        FAST_SUBJECT,
        FAST_OUT,
        [
            ("İşlem Tarihi", f"{sent:%d.%m.%Y %H:%M:%S}"),
            ("Hesap Numarası", "*************1234"),
            ("Alıcı Banka", "QNB Bank A.Ş."),
            ("Alıcı Adı Soyadı", receiver),
            ("Sorgu Numarası", "1234567891"),
            ("İşlem Tutarı", amount),
            ("Güncel Bakiye", balance),
        ],
        sent,
    )


def outflow(sent: datetime = datetime(2026, 10, 25, 11, 0, tzinfo=_ISTANBUL), amount: str = "2.000,00 TL") -> bytes:
    """Money that left the account by EFT, to an IBAN the notice masks; no balance is printed."""
    return notice(
        OUTFLOW_SUBJECT,
        OUTFLOW,
        [
            ("Hesap Numarası", "00158********1234"),
            ("İşlem Tarihi", f"{sent:%d.%m.%Y %H:%M:%S}"),
            ("Sorgu Numarası", "7654321"),
            ("İşlem Kanalı", "Mobil Bankacılık"),
            ("Alıcı Banka", "TÜRK EKONOMİ BANKASI A.Ş."),
            ("Alıcı IBAN", "TR00 **** **** **** **** ** 12 34"),
            ("İşlem Tipi", "Hesaba EFT"),
            ("İşlem Tutarı", amount),
        ],
        sent,
    )


def specimens() -> list[Specimen]:
    notices = "vakifbank.notice.transfer"
    return [
        Specimen(
            "vakifbank-hesap-hareketleri.xlsx",
            account_xlsx(),
            "vakifbank.account_xlsx",
            "vakifbank-0158000001234567",
            6,
        ),
        Specimen("vakifbank-e-cuzdan.pdf", passbook(), "vakifbank.passbook", "vakifbank-0158000000012345", 0),
        Specimen("vakifbank-fast-gelen.eml", fast_in(), notices, "vakifbank-****1234", 1),
        Specimen("vakifbank-fast-giden.eml", fast_out(), notices, "vakifbank-****1234", 1),
        Specimen("vakifbank-para-cikisi.eml", outflow(), notices, "vakifbank-****1234", 1),
    ]
