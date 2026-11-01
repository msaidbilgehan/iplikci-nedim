"""Bank notices (Phase 4): the e-mails a bank sends about one movement, read from their bodies into rows that are
evidence like a receipt's."""

import hashlib
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from email.message import EmailMessage

import pytest

from iplikci.app import mail, reading
from iplikci.domain.codes import DocumentKind, DocumentStatus, TransactionKind
from iplikci.fakes import HOLDER, garanti, isbank, qnb, vakifbank
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


@pytest.mark.parametrize(
    "subject",
    ["Mart Ayının 2. Haftası Ödeme Bilgileriniz", "Kredi Vade Tarihi Bilgilendirme", "Kredi Kartı Ödeme Hatırlatması"],
)
def test_a_reminder_of_a_payment_due_moves_no_money_whatever_money_words_it_holds(subject):
    assert message_reason(mail_of(subject)) == messages.REMINDER


def test_a_message_no_reader_takes_is_a_companys_when_its_greeting_names_the_company():
    set_business_names(["Örnek Teknoloji A.Ş."])
    sent = datetime(2026, 10, 15, tzinfo=timezone(timedelta(hours=3)))
    greeted = "<p>Merhaba ÖRNEK TEKNOLOJİ ANONİM ŞİRKETİ,</p><p>Bugün son ödeme tarihi olan primleriniz var.</p>"
    with pytest.raises(Skipped) as raised:
        read(html_mail("bilgi@ornekbank.example", "SGK Prim Bilgileriniz", greeted, sent))
    assert (str(raised.value), raised.value.business) == (BUSINESS_REASON, True)
    # Named further down, the company is the other side of the user's own movement: the message stays the user's.
    named = "<p>Sayın ÖRNEK KULLANICI,</p><p>ÖRNEK TEKNOLOJİ A.Ş. hesabınıza 1.000,00 TL gönderdi.</p>"
    with pytest.raises(Skipped) as raised:
        read(html_mail("bilgi@ornekbank.example", "Para Girişi", named, sent))
    assert (str(raised.value), raised.value.business) == (MESSAGE_REASON, False)
    # A greeting without its comma is not read on into the sentence after it.
    unpunctuated = "<p>Sayın ÖRNEK KULLANICI</p><p>ÖRNEK TEKNOLOJİ A.Ş. hesabınıza para gönderdi, iyi günler.</p>"
    with pytest.raises(Skipped) as raised:
        read(html_mail("bilgi@ornekbank.example", "Para Girişi", unpunctuated, sent))
    assert not raised.value.business


def test_premiums_paid_under_a_workplace_number_are_a_payrolls_and_a_persons_own_are_not():
    sent = datetime(2026, 10, 15, tzinfo=timezone(timedelta(hours=3)))
    cells = ["SGK", "SSK Prim", "15-10-2026", "1" * 26, "1234-****567", "1,234.56 TL"]
    table = "<p>Sayın Müşterimiz,</p><table><tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr></table>"
    with pytest.raises(Skipped) as raised:
        read(html_mail("bilgi@ornekbank.example", "Son Ödeme Tarihi Bugün Olan SGK Prim Bilgileriniz", table, sent))
    assert (str(raised.value), raised.value.business) == (BUSINESS_REASON, True)
    own = table.replace("1" * 26, "1" * 11).replace("SSK Prim", "İsteğe Bağlı Prim")  # under an identity number
    with pytest.raises(Skipped) as raised:
        read(html_mail("bilgi@ornekbank.example", "Son Ödeme Tarihi Bugün Olan SGK Prim Bilgileriniz", own, sent))
    assert not raised.value.business


def test_a_notice_a_reader_takes_stays_the_users_when_the_company_sent_the_money():
    set_business_names(["Örnek Teknoloji A.Ş."])
    [row] = read(vakifbank.fast_in(sender="ÖRNEK TEKNOLOJİ A.Ş.")).transactions
    assert row.counterparty == "ÖRNEK TEKNOLOJİ A.Ş."


def test_a_body_that_leaves_the_details_to_online_banking_moves_no_money_unless_it_holds_an_amount():
    pointer = "HGS ürününüzün aylık geçiş bilgilerini İnternet/Mobil Şube'den kontrol edebilirsiniz."
    assert message_reason(mail_of("HGS EKSTRE BİLGİLENDİRME", text=pointer)) == messages.ELSEWHERE
    with_amount = "Hesabınıza 1.250,00 TL yüklendi. Ayrıntıları İnternet Şube'den kontrol edebilirsiniz."
    assert message_reason(mail_of("HGS EKSTRE BİLGİLENDİRME", text=with_amount)) == MESSAGE_REASON


# --- Garanti BBVA's transfer notices ----------------------------------------------------------------------------

GARANTI = "garanti.notice.transfer"


def test_a_garanti_transfer_notice_of_2026_is_money_out_of_the_account_it_masks():
    data = garanti.transfer_notice()
    result = read(data)
    [row] = result.transactions
    assert (result.parser, result.title, result.holder) == (GARANTI, "Giden Transfer", "")
    assert (row.date, row.amount, row.kind, row.counterparty) == (
        date(2026, 10, 30),
        Decimal("12750.00"),
        TransactionKind.TRANSFER_CANDIDATE,
        "Ör**** Ku******",
    )
    assert row.description == "Giden Transfer → Ör**** Ku****** (QNB BANK A.Ş.) — KART ÖDEMESİ"
    [account] = result.accounts
    assert (account.id, account.label) == ("garanti-****567", "Garanti BBVA Vadesiz TL …567")
    assert result.receipt_key.split("-") == [
        "garanti",
        "pt",
        "202610301440",
        "567",
        "1275000",
    ]  # minute, account, kuruş
    assert row.ref is not None and row.ref.span is not None
    start, end = row.ref.span
    assert read_mail(data).text[start:end] == "12.750,00 TL"


def test_an_older_garanti_notice_names_the_account_whole_and_the_bank_from_the_iban():
    result = read(garanti.old_transfer_notice())
    [row] = result.transactions
    assert (result.title, result.holder, row.account) == ("Giden Havale", "ÖRNEK KULLANICI", "garanti-1234567")
    assert row.description == "Giden Havale → VELİ ÖRNEKSOY (Garanti BBVA) — EKİM KİRA ÖDEMESİ"
    order = garanti.old_transfer_notice(
        kind="EFT Emri Para transferi emriniz işleme alınmıştır.",
        receiver=("VELİ ÖRNEKSOY", "TR00 0011 1000 0000 0000 1234 56"),
    )
    assert read(order).transactions[0].description == "Giden EFT → VELİ ÖRNEKSOY (QNB) — EKİM KİRA ÖDEMESİ"
    inside = garanti.old_transfer_notice(receiver=("VELİ ÖRNEKSOY / KADIKÖY - 123 7654321",))
    assert read(inside).transactions[0].counterparty == "VELİ ÖRNEKSOY"


def test_a_garanti_notice_from_a_company_account_is_the_companys():
    set_business_names(["Örnek Teknoloji A.Ş."])
    with pytest.raises(Skipped) as raised:
        read(garanti.old_transfer_notice(holder="ÖRNEK TEKNOLOJİ A.Ş."))
    assert raised.value.business
    # Written to the person who uses the company's account: the sender's block still names the company.
    html = read_mail(garanti.old_transfer_notice()).text.replace(
        "Bilgileri: ÖRNEK KULLANICI", "Bilgileri: ÖRNEK TEKNOLOJİ A.Ş."
    )
    with pytest.raises(Skipped) as raised:
        read(
            html_mail(garanti.NOTICE_SENDER, "Para Transferi Bilgilendirmesi", f"<p>{html}</p>", datetime(2024, 10, 22))
        )
    assert raised.value.business


# --- QNB's movement notices -------------------------------------------------------------------------------------

QNB = "qnb.notice.transfer"


def test_a_qnb_fast_notice_is_read_with_us_amounts_onto_the_account_it_does_not_name():
    data = qnb.fast_out()
    result = read(data)
    [row] = result.transactions
    assert (result.parser, result.title, result.holder) == (QNB, "Giden FAST", HOLDER)
    assert (row.date, row.amount, row.balance, row.kind) == (
        date(2026, 10, 20),
        Decimal("1250.00"),
        Decimal("-3480.25"),  # an overdraft account below zero
        TransactionKind.TRANSFER_CANDIDATE,
    )
    assert (row.description, row.counterparty) == ("Giden FAST → VELİ ÖRNEKSOY", "VELİ ÖRNEKSOY")
    [account] = result.accounts
    assert (account.id, account.label, account.number) == ("qnb-****", "QNB Vadesiz TL", "****")
    assert row.ref is not None and row.ref.span is not None
    start, end = row.ref.span
    assert read_mail(data).text[start:end] == "1,250.00"
    received = read(qnb.fast_in()).transactions[0]  # mailed by QNB Finansbank, no thousands separator
    assert (received.amount, received.balance) == (Decimal("-2400.00"), Decimal("915.75"))
    assert received.description == "Gelen FAST ← AYŞE SOYADOĞLU"


def test_a_qnb_notice_that_names_the_account_prints_amounts_the_turkish_way():
    result = read(qnb.transfer_out())
    [row] = result.transactions
    assert (result.title, row.account, row.amount, row.balance) == (
        "Giden Transfer",
        "qnb-12345678",
        Decimal("3000.00"),
        Decimal("-2084.25"),
    )
    assert row.description == "Giden Transfer → VELİ ÖRNEKSOY"  # "hesabinizdan", written without its letters
    received = qnb.notice(qnb.TRANSFER_SUBJECT, qnb.TRANSFER_IN.format(amount="99,99"), "100,00", datetime(2026, 10, 1))
    assert read(received).transactions[0].amount == Decimal("-99.99")


def test_the_newest_qnb_notice_capitalises_the_branch_and_masks_the_greeting():
    result = read(qnb.transfer_in())
    [row] = result.transactions
    assert (result.title, result.holder, row.account) == (
        "Gelen Transfer",
        "",
        "qnb-****",
    )  # a masked name is no holder
    assert (row.amount, row.balance, row.description) == (
        Decimal("-7500.00"),
        Decimal("5415.75"),
        "Gelen Transfer ← Ayşe Soyadoğlu",
    )


def test_money_out_just_before_midnight_is_dated_by_the_balances_time_not_the_mail():
    result = read(qnb.cash_out())  # mailed at 00:01, the balance as of 23:58
    [row] = result.transactions
    assert (row.date, row.amount, row.description) == (
        date(2026, 10, 26),
        Decimal("500.00"),
        "Para Çıkışı (ATM/banka kartı)",
    )
    assert result.receipt_key.split("-", 4)[2:] == [
        "202610262358",
        "50000",
        "-258425",
    ]  # day and minute, amount, balance


@pytest.mark.parametrize(
    ("printed", "value"),
    [
        ("1,234.56", "1234.56"),
        ("1234.56", "1234.56"),
        ("1.234,56", "1234.56"),
        ("99,99", "99.99"),
        ("-1,234.56", "-1234.56"),
    ],
)
def test_a_qnb_amount_takes_the_separator_before_its_last_two_digits_as_the_decimal_one(printed, value):
    sentence = qnb.FAST_OUT.format(amount="1.00")
    row = read(qnb.notice(qnb.FAST_SUBJECT, sentence, printed, datetime(2026, 10, 1))).transactions[0]
    assert row.balance == Decimal(value)


def test_a_qnb_notice_whose_sentence_the_reader_does_not_know_raises_the_format_alarm():
    sentence = "KADIKÖY şubesindeki hesabınıza 1,000.00 TL yatırılmıştır."
    with pytest.raises(Unreadable) as raised:
        read(qnb.notice(qnb.FAST_SUBJECT, sentence, "1,000.00", datetime(2026, 10, 1)))
    assert raised.value.parser == QNB
    for broken in ("1,234,56", "1.234.56"):  # a separator used both ways
        with pytest.raises(Unreadable):
            read(qnb.notice(qnb.FAST_SUBJECT, qnb.FAST_OUT.format(amount=broken), "1.00", datetime(2026, 10, 1)))


def test_a_qnb_notice_greeting_the_company_is_the_companys():
    set_business_names(["Örnek Teknoloji A.Ş."])
    data = qnb.notice(
        qnb.FAST_SUBJECT,
        qnb.FAST_OUT.format(amount="1.00"),
        "1.00",
        datetime(2026, 10, 1),
        holder="ÖRNEK TEKNOLOJİ A.Ş.",
    )
    with pytest.raises(Skipped) as raised:
        read(data)
    assert (raised.value.business, raised.value.parser) == (True, QNB)


# --- İş Bankası's notices ---------------------------------------------------------------------------------------


def test_an_isbank_card_debt_collected_from_an_account_is_a_payment_to_the_card():
    data = isbank.collection_notice()
    result = read(data)
    [row] = result.transactions
    assert (result.parser, result.title, result.accounts[0].id) == (
        "isbank.notice.collection",
        "Kart Borcu Tahsilatı",
        "isbank-1234",
    )
    assert (row.date, row.amount, row.kind) == (
        date(2026, 10, 16),
        Decimal("1258.21"),
        TransactionKind.CARD_PAYMENT_NO_STATEMENT,  # booked on the card, like a card payment receipt
    )
    assert row.description == "Maximum •1234 gecikmiş borç tahsilatı (1234-0123456 no'lu hesaptan)"
    assert row.ref is not None and row.ref.span is not None
    start, end = row.ref.span
    assert read_mail(data).text[start:end] == "1.258,21"


def test_a_body_without_amounts_that_opens_with_a_change_of_fees_is_an_announcement_whatever_its_subject():
    text = "Değerli Müşterimiz, Örnek Mektup hizmetimize ait ücretler, 01.12.2026 tarihi itibarıyla güncellenecektir."
    assert message_reason(mail_of("Örnek Mektup Dönem Ücreti", text=text)) == messages.ANNOUNCEMENT
    with_amount = f"{text} Yeni dönem ücreti 150,00 TL olacaktır."
    assert message_reason(mail_of("Örnek Mektup Dönem Ücreti", text=with_amount)) == MESSAGE_REASON


def test_a_loans_progress_and_a_picture_with_the_banks_footer_are_announcements():
    progress = "Tebrikler, ÖR-12345 referans numaralı kredi ödemelerinizin yarısından fazlasını tamamladınız."
    assert message_reason(mail_of("Çoğu bitti azı kaldı!", text=progress)) == messages.ANNOUNCEMENT
    footer = (
        "Mesajı düzgün görüntüleyemiyorsanız lütfen tıklayınız. Gönderilen e-postalar sadece bilgilendirme amaçlıdır. "
        "Örnek Bankası A.Ş. Ticaret Sicil No: 123456"
    )
    assert message_reason(mail_of("BİLGİLENDİRME [İletiNo:123]", text=footer)) == messages.ANNOUNCEMENT
    paid = f"Hesabınıza 1.250,00 TL yatırılmıştır. {footer}"  # an amount: a notice no reader reads yet
    assert message_reason(mail_of("BİLGİLENDİRME [İletiNo:123]", text=paid)) == MESSAGE_REASON
