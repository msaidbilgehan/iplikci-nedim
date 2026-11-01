from datetime import date
from decimal import Decimal

import pytest
from pdfminer.pdfdocument import PDFPasswordIncorrect
from pdfplumber.utils.exceptions import PdfminerException

from iplikci import parsers
from iplikci.domain.codes import TransactionKind
from iplikci.domain.models import Transaction
from iplikci.fakes.files import pdf_file
from iplikci.parsers import contract
from iplikci.parsers.common import (
    business_names_signature,
    classify_kind,
    installment_label,
    is_business,
    pair_deferrals,
    set_business_names,
    split_interest,
)
from iplikci.parsers.pdf import Line, Word, take_amount
from iplikci.sources import Document


def line(*words):
    return Line(top=100.0, words=[Word(t, x0, x1, 100.0) for t, x0, x1 in words])


def test_take_amount_right_aligned_with_detached_sign():
    ln = line(("30/09/2024", 28, 63), ("OTOMATİK", 153, 188), ("-", 354, 357), ("123,45", 359, 380))
    amount, used = take_amount(ln, edge=382)
    assert amount == Decimal("-123.45")
    assert [w.text for w in used] == ["-", "123,45"]


def test_take_amount_ignores_other_columns():
    # 289,90 is the amount (TUTAR column ends at 428), 0,04 sits in the points column.
    ln = line(("23/09/2024", 64, 96), ("TURKNET", 101, 140), ("289,90", 407, 428), ("0,04", 551, 565))
    amount, _ = take_amount(ln, edge=428)
    assert amount == Decimal("289.90")


def test_take_amount_left_aligned():
    ln = line(("09/12/2023", 30, 65), ("SHELL", 75, 97), ("TL.1.500,-", 458, 490))
    assert take_amount(ln, edge=458, align="left")[0] == Decimal(1500)


def test_classify_kind():
    assert (
        classify_kind("9999-123456 HESAPTAN AKTARIM 1234 İNTERAKTİF", Decimal("-12345.67"))
        == TransactionKind.CARD_PAYMENT
    )
    assert classify_kind("9999-123456HESAPTANAKTARIM1234İNTERAKTİF", Decimal("-275.5")) == TransactionKind.CARD_PAYMENT
    assert classify_kind("FAIZ TUTARI FZ:500.00 VR/FN:150.00", Decimal(650)) == TransactionKind.INTEREST_FEE
    assert classify_kind("TNA FAIZ İPTALI", Decimal("-30.5")) == TransactionKind.INTEREST_FEE
    assert classify_kind("NAKİTAVANSÜCRETİ", Decimal("34.5")) == TransactionKind.INTEREST_FEE
    assert classify_kind("4321 KARTTAN AKTARIM 9999/0123456 İSCEP", Decimal(1006)) == TransactionKind.CASH_ADVANCE
    assert classify_kind("ORNEK PETROL ISTANBUL TR İŞLEM İPTALI", Decimal("-1234.56")) == TransactionKind.REFUND
    assert classify_kind("0001234567 TURKNET ILETISI FAT.ÖDE.", Decimal("289.9")) == TransactionKind.PURCHASE
    assert classify_kind("TURKNET ILETISIM HIZMET FATURA ÖDEME ÜCRETI", Decimal("17.5")) == TransactionKind.INTEREST_FEE


def test_split_interest_of_installment_cash_advance():
    t = Transaction(
        date=date(2024, 10, 7),
        amount=Decimal(1500),
        kind=TransactionKind.CASH_ADVANCE,
        account="x",
        description="TAKSİTLİ NAKİT AVANS - HESABA HAVALE KALAN:3,000.00 FZ:120.00 VR/FN:36.00",
    )
    principal, interest = split_interest(t)
    assert (principal.kind, principal.amount) == (TransactionKind.LOAN_PRINCIPAL, Decimal(1344))
    assert (interest.kind, interest.amount) == (TransactionKind.INTEREST_FEE, Decimal(156))
    assert round(principal.amount + interest.amount, 2) == t.amount


def test_installment_label():
    assert installment_label("1/3 taksidi (1.234,00)") == "1/3"
    assert installment_label("1/12taksidi(12.345,67)") == "1/12"
    assert installment_label("250,00x12=3.000,00 8.Taksit") == "8/12"
    assert installment_label("0,07") == ""


def test_deferred_statement_is_not_spending():
    # Garanti books a deferral as a payment plus the same amount charged again.
    charge = Transaction(
        date=date(2025, 9, 22),
        description="ERTELENEN EKSTRE TUTARI",
        amount=Decimal("30000.5"),
        kind=classify_kind("ERTELENEN EKSTRE TUTARI", Decimal("30000.5")),
        account="x",
    )
    payment = Transaction(
        date=date(2025, 9, 22),
        description="ÖDEMENİZ İÇİN TEŞEKKÜR EDERİZ",
        amount=Decimal("-30000.5"),
        kind=classify_kind("ÖDEMENİZ İÇİN TEŞEKKÜR EDERİZ", Decimal("-30000.5")),
        account="x",
    )
    real = Transaction(
        date=date(2025, 10, 1),
        description="ÖDEMENİZ İÇİN TEŞEKKÜR EDERİZ",
        amount=Decimal(-20000),
        kind=TransactionKind.CARD_PAYMENT,
        account="x",
    )
    assert (charge.kind, payment.kind) == (TransactionKind.OWN_TRANSFER, TransactionKind.CARD_PAYMENT)
    pair_deferrals([charge, payment, real])
    assert (charge.kind, payment.kind, real.kind) == (
        TransactionKind.OWN_TRANSFER,
        TransactionKind.OWN_TRANSFER,
        TransactionKind.CARD_PAYMENT,
    )


def test_business_products_mark_company_documents():
    assert is_business("Şirket Kredi Kartı Hesap Özeti")
    assert is_business("GİRİŞİMCİ KREDİ KARTI")
    assert not is_business("ÖRNEK KULLANICI")


def test_a_company_name_counts_only_once_it_is_in_the_settings():
    assert not is_business("ÖRNEK TEKNOLOJİ ANONİM ŞİRKETİ")
    set_business_names(["Örnek Teknoloji A.Ş."])
    assert is_business("ÖRNEK TEKNOLOJİ ANONİM ŞİRKETİ")
    assert not is_business("ÖRNEK KULLANICI")


@pytest.mark.parametrize("name", ["Örnek Teknoloji", "ÖRNEK TEKNOLOJİ A.Ş.", "Örnek Teknoloji San. ve Tic. Ltd. Şti."])
def test_a_company_name_matches_whatever_legal_form_the_document_prints(name):
    set_business_names([name])
    assert is_business("ÖRNEK TEKNOLOJİ ANONİM ŞİRKETİ")
    assert is_business("ORNEKTEKNOLOJISANAYIVETICARETLIMITEDSIRKETI")  # a PDF that drops the spaces


def test_a_company_name_of_fewer_than_three_letters_is_ignored():
    set_business_names(["AB", "A.Ş."])
    assert not is_business("AB YAPI ANONİM ŞİRKETİ")
    assert business_names_signature() == ""


def test_the_signature_changes_with_the_company_names():
    assert business_names_signature() == ""
    set_business_names(["Örnek Teknoloji"])
    first = business_names_signature()
    set_business_names(["ÖRNEK TEKNOLOJİ A.Ş."])
    assert business_names_signature() == first  # the same name in another spelling
    set_business_names(["Başka Şirket"])
    assert business_names_signature() not in ("", first)


def test_password_protected_pdf_is_kept_for_a_manual_look(monkeypatch):
    # Some banks e-mail statements as password-protected PDFs: unreadable, but never "not a statement".
    def locked(data):
        try:
            raise PDFPasswordIncorrect()
        except PDFPasswordIncorrect as exc:
            raise PdfminerException(exc)  # what pdfplumber does

    monkeypatch.setattr(contract, "open_pdf", locked)
    with pytest.raises(parsers.Unreadable, match="şifreli PDF"):
        parsers.parse_document(Document("Ekstre.pdf", "test", b"%PDF-1.7", "sha"))


def _image_only_pdf() -> bytes:
    """One page that holds nothing but a picture, like a statement delivered as page images."""
    content = b"q 100 0 0 100 50 50 cm /Im1 Do Q"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /XObject << /Im1 4 0 R >> >> "
            b"/Contents 5 0 R >>"
        ),
        (
            b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray /BitsPerComponent 8 "
            b"/Length 1 >>\nstream\n\x80\nendstream"
        ),
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
    ]
    return pdf_file(objects)


def test_page_image_pdf_without_ocr_is_kept_for_a_manual_look(monkeypatch):
    # OCR (macOS Vision) is missing on Linux and Windows: such a PDF may be a TEB statement.
    monkeypatch.setattr(parsers, "ocr_available", lambda: False)
    with pytest.raises(parsers.Unreadable, match="OCR"):
        parsers.parse_document(Document("Ekstre.pdf", "test", _image_only_pdf(), "sha"))
