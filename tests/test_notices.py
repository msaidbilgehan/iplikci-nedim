"""Bank notices (Phase 4): the e-mails a bank sends about one movement, read from their bodies into rows that are
evidence like a receipt's."""

import hashlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from email.message import EmailMessage

import pytest

from iplikci.app import mail, reading
from iplikci.domain.codes import DocumentKind, DocumentStatus, TransactionKind
from iplikci.fakes import vakifbank
from iplikci.fakes.files import html_mail
from iplikci.parsers import Skipped, Unreadable, messages, parse_document
from iplikci.parsers.common import BUSINESS_REASON, MESSAGE_REASON, set_business_names
from iplikci.parsers.contract import Document
from iplikci.parsers.mail import Mail, read_mail
from iplikci.parsers.messages import message_reason
from iplikci.settings.config import BANK_SENDERS
from iplikci.storage import documents

NOTICES = "vakifbank.notice.transfer"


def read(data: bytes, name: str = "bildirim.eml"):
    return parse_document(Document(name, "deneme", data, hashlib.sha256(data).hexdigest()))


# --- the body of a kept e-mail ----------------------------------------------------------------------------------


def test_a_mails_body_is_its_visible_text_without_styles_or_invisible_characters():
    msg = EmailMessage()
    msg["From"] = "VakıfBank <bilgi@VakifBank.com.tr>"
    msg["Subject"] = "=?utf-8?b?xLDFn2xlbSBiaWxkaXJpbWk=?="  # "İşlem bildirimi", encoded as banks do
    msg["Date"] = "Thu, 15 Oct 2026 14:05:12 +0300"
    msg.set_content("Düz metin hali")
    msg.add_alternative(
        "<html><head><style>p { color: red; }</style></head>"
        "<body><p>İşlem\u200b Tutarı&nbsp;:\n  2.500 TL</p><script>gizli()</script></body></html>",
        subtype="html",
    )
    msg.add_attachment(b"%PDF-1.4", maintype="application", subtype="pdf", filename="dekont.pdf")
    seen = read_mail(msg.as_bytes())
    assert (seen.sender, seen.subject, seen.attached) == ("vakifbank.com.tr", "İşlem bildirimi", True)
    assert seen.sent == datetime(2026, 10, 15, 14, 5, 12, tzinfo=timezone(timedelta(hours=3)))
    assert seen.text == "İşlem Tutarı : 2.500 TL"  # the HTML part, not the plain one or the attachment


def test_a_broken_body_gives_less_text_never_an_error():
    raw = (
        b"From: bilgi@vakifbank.com.tr\r\nSubject: deneme\r\nContent-Type: text/plain; charset=yok-boyle-bir-kume\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\n!!! bozuk !!!\r\n"
    )
    seen = read_mail(raw)
    assert (seen.sender, seen.subject, seen.sent, seen.attached) == ("vakifbank.com.tr", "deneme", None, False)
    assert isinstance(seen.text, str)


# --- Vakıfbank's transfer notices -------------------------------------------------------------------------------


def test_a_fast_payment_that_came_in_is_money_in_with_the_balance_after_it():
    data = vakifbank.fast_in()
    result = read(data)
    [row] = result.transactions
    assert (result.parser, result.title, result.receipt_key) == (NOTICES, "Gelen FAST", "vakifbank-20261015-1234567890")
    assert (row.date, row.amount, row.balance, row.kind) == (
        date(2026, 10, 15),
        Decimal("-2500.00"),
        Decimal("3500.00"),
        TransactionKind.TRANSFER_CANDIDATE,
    )
    assert (row.counterparty, row.description) == ("Ke**** De******", "Gelen FAST ← Ke**** De****** (Enpara Bank A.Ş.)")
    [account] = result.accounts
    assert (account.id, account.label, account.currency) == ("vakifbank-****1234", "Vakıfbank Vadesiz TL …1234", "TRY")
    assert result.holder == ""  # "Sayın Ör**** Ku******": masked, so unknown
    assert row.ref is not None and row.ref.span is not None
    start, end = row.ref.span
    assert read_mail(data).text[start:end] == "2.500 TL"  # the row points at its amount in the body


def test_a_fast_payment_sent_out_and_an_eft_are_money_out():
    sent = read(vakifbank.fast_out()).transactions[0]
    assert (sent.amount, sent.balance, sent.counterparty) == (Decimal("1000.00"), Decimal("2500.00"), "ÖR**** KU******")
    assert sent.description == "Giden FAST → ÖR**** KU****** (QNB Bank A.Ş.)"
    result = read(vakifbank.outflow())
    [eft] = result.transactions
    assert (result.title, eft.amount, eft.balance, eft.counterparty) == ("Giden EFT", Decimal("2000.00"), None, "")
    assert (eft.account, eft.description) == ("vakifbank-****1234", "Giden EFT → TÜRK EKONOMİ BANKASI A.Ş.")


def test_amounts_drop_their_decimals_only_when_they_are_zero():
    row = read(vakifbank.fast_in(amount="12.345,67 TL", balance="0 TL")).transactions[0]
    assert (row.amount, row.balance) == (Decimal("-12345.67"), Decimal("0.00"))


def test_a_field_the_reader_does_not_know_raises_the_format_alarm():
    rows = [("İşlem Tarihi", "15.10.2026 14:05:12"), ("Hesap Numarası", "*************1234")]
    rows += [("Gönderen Adı Soyadı", "Ke**** De******"), ("Açıklama", "kira"), ("İşlem Tutarı", "2.500 TL")]
    sent = datetime(2026, 10, 15, 14, 5, 12, tzinfo=timezone(timedelta(hours=3)))
    with pytest.raises(Unreadable) as raised:
        read(vakifbank.notice(vakifbank.FAST_SUBJECT, vakifbank.FAST_IN, rows, sent))
    assert raised.value.parser == NOTICES  # the reader recognised it: the bank changed the notice


def test_the_same_body_from_another_sender_is_not_read_as_vakifbanks():
    html = read_mail(vakifbank.fast_in()).text
    raw = html_mail("bilgi@ornekbanka.example", vakifbank.FAST_SUBJECT, f"<p>{html}</p>", datetime(2026, 10, 15))
    with pytest.raises(Skipped) as raised:
        read(raw)
    assert (str(raised.value), raised.value.parser) == (MESSAGE_REASON, "")


def test_a_vakifbank_mail_that_moves_no_money_is_left_unread_without_an_alarm():
    raw = html_mail(
        vakifbank.NOTICE_SENDER, "Doğum Gününüz Kutlu Olsun!", "<p>Nice mutlu yıllara!</p>", datetime(2026, 10, 1)
    )
    with pytest.raises(Skipped) as raised:
        read(raw)
    assert (str(raised.value), raised.value.parser, raised.value.business) == (messages.CAMPAIGN, "", False)


def test_a_company_name_in_the_subject_or_as_the_holder_makes_the_notice_a_companys():
    set_business_names(["Örnek Teknoloji A.Ş."])
    sent = datetime(2026, 10, 15, tzinfo=timezone(timedelta(hours=3)))
    raw = html_mail(vakifbank.NOTICE_SENDER, "ÖRNEK TEKNOLOJİ hesap bildirimi", "<p>deneme</p>", sent)
    with pytest.raises(Skipped) as raised:
        read(raw)
    assert (str(raised.value), raised.value.business) == (BUSINESS_REASON, True)
    # A notice that prints the holder whole, after "Sayın".
    html = read_mail(vakifbank.fast_in()).text.replace(vakifbank.MASKED_HOLDER, "ÖRNEK TEKNOLOJİ A.Ş.")
    with pytest.raises(Skipped) as raised:
        read(html_mail(vakifbank.NOTICE_SENDER, vakifbank.FAST_SUBJECT, f"<p>{html}</p>", sent))
    assert raised.value.business


def test_a_kept_notice_is_a_bank_notice_named_by_its_day_and_title(ws):
    outcome = mail.take(ws, vakifbank.fast_in(), BANK_SENDERS)
    assert outcome.taken is mail.Taken.STORED
    with ws.db() as db:
        assert reading.read_pending(ws, db) == 0  # the intake read it as it kept it
        doc = documents.get(db, outcome.sha256)
    assert doc is not None
    assert (doc.status, doc.kind, doc.parser) == (DocumentStatus.PROCESSED, DocumentKind.NOTICE, NOTICES)
    assert doc.display_name == "2026-10-15 Vakıfbank Gelen FAST Bildirim.eml"


# --- what a message no reader took is ---------------------------------------------------------------------------


def mail_of(subject: str, sender: str = "ileti.ornekbank.example", text: str = "", attached: bool = False):
    return Mail(sender, subject, None, text, attached)


@pytest.mark.parametrize(
    ("sender", "subject", "reason"),
    [
        ("kampanya.ornekbank.example", "Ekstre borcunuza taksit fırsatı!", messages.CAMPAIGN),  # a campaign sender
        ("ileti.ornekbank.example", "Kampanya: Maaş ödemelerinize özel avantaj", messages.CAMPAIGN),  # the bank's label
        ("ileti.ornekbank.example", "Tanıtım: Girişimcilere özel buluşma", messages.CAMPAIGN),
        ("ornekbank.example", "Müşteri Şifresi Bloke Öncesi Bilgilendirme", messages.SECURITY),
        ("ornekbank.example", "Mobil'e Yeni Cihazdan Giriş Yapıldı", messages.SECURITY),
        ("ornekbank.example", "E-posta Adresinizi Doğrulayınız!", messages.SECURITY),
        ("ornekbank.example", "Kartınızı Kuryeye Teslim Ettik.", messages.CARD),
        ("ornekbank.example", "Kredi Kartı Limit Artışı Değerlendirme Sonucunuz", messages.CARD),
        ("ornekbank.example", "Ücret ve Komisyon Tahsilatında Değişiklik Hakkında", messages.ANNOUNCEMENT),
        ("bilgi.ornekbank.example", "Bayram Tatili İşlem Saatleri", messages.ANNOUNCEMENT),  # an announcement sender
        ("ornekbank.example", "Örnek Gıda Halka Arz Oluyor!", messages.ANNOUNCEMENT),
        ("ornekbank.example", "Yeni yılda size özel 500 TL bonus!", messages.CAMPAIGN),
        ("ornekbank.example", "Mobil ödemelerinizle bonus kazanın!", messages.CAMPAIGN),
        # Money moving or owed: unknown until a reader reads it, however it is worded.
        ("ornekbank.example", "Bonus Hesap Özetiniz", MESSAGE_REASON),
        ("ornekbank.example", "HGS EKSTRE BİLGİLENDİRME", MESSAGE_REASON),
        ("ornekbank.example", "Para Transferi Bilgilendirmesi", MESSAGE_REASON),
        ("ornekbank.example", "Son Ödeme Tarihi Bugün Olan SGK Prim Bilgileriniz", MESSAGE_REASON),
        ("ornekbank.example", "Hesabınızdan Gecikmedeki Kredi Kartı Borcunuzun Tahsilatı", MESSAGE_REASON),
        ("bilgi.ornekbank.example", "Harcamalarınızı döviz ekstre ile izleyin", MESSAGE_REASON),
        ("ornekbank.example", "Haftalık bildiriminiz", MESSAGE_REASON),  # a subject no rule knows
    ],
)
def test_a_message_no_reader_took_is_named_by_its_sender_and_subject(sender, subject, reason):
    assert message_reason(mail_of(subject, sender)) == reason


def test_a_message_with_documents_is_read_through_them_and_a_bare_subject_through_its_opening():
    assert message_reason(mail_of("Hesap Özetiniz", attached=True)) == messages.ATTACHED
    announced = "Değerli Müşterimiz, 01.10.2026 itibarıyla tahsilat işlemlerinde komisyonlarımız güncellenecektir."
    assert message_reason(mail_of("BİLGİLENDİRME [İletiNo:123]", text=announced)) == messages.ANNOUNCEMENT
    assert message_reason(mail_of("BİLGİLENDİRME [İletiNo:123]", text="Değerli Müşterimiz, ...")) == MESSAGE_REASON


def test_only_documents_count_as_attached_never_an_image_or_a_file_left_out():
    msg = EmailMessage()
    msg["From"] = "bilgi@ornekbank.example"
    msg["Subject"] = "Kampanya"
    msg.set_content("<p>Fırsat</p>", subtype="html")
    msg.add_attachment(b"\x89PNG", maintype="image", subtype="png", filename="logo.png")
    assert not read_mail(msg.as_bytes()).attached
    msg.add_attachment(b"", maintype="application", subtype="pdf", filename="ekstre.pdf")  # "Show original" left it out
    assert not read_mail(msg.as_bytes()).attached
    msg.add_attachment(b"%PDF-1.4", maintype="application", subtype="pdf", filename="ekstre.pdf")
    assert read_mail(msg.as_bytes()).attached
