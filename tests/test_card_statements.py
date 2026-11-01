"""Card statements, read from fake PDFs laid out like the banks' own (iplikci.fakes)."""

from datetime import date
from decimal import Decimal

from iplikci import parsers
from iplikci.domain.codes import AccountType, TransactionKind
from iplikci.domain.models import ParseResult, Statement
from iplikci.fakes import HOLDER, garanti, isbank, qnb, teb
from iplikci.fakes.files import scan_pdf
from iplikci.parsers import contract
from iplikci.sources import Document

K = TransactionKind


def read(data: bytes, name: str = "ekstre.pdf") -> ParseResult:
    return parsers.parse_document(Document(name, "test", data, "sha"))


def only(result: ParseResult) -> Statement:
    [statement] = result.statements
    return statement


def kinds(statement: Statement) -> list[tuple[str, Decimal, TransactionKind]]:
    return [(t.description, t.amount, t.kind) for t in statement.transactions]


# --- Garanti BBVA ----------------------------------------------------------------------------------------------


def test_garanti_bonus_statement_adds_its_rows_to_the_debt_it_carries_over():
    r = read(garanti.bonus_statement())
    s = only(r)
    assert (r.parser, r.accounts[0].id, r.accounts[0].type) == (
        "garanti.bonus_card",
        "garanti-1234",
        AccountType.CREDIT_CARD,
    )
    assert (s.cut_date, s.previous, s.total, s.verified) == (date(2026, 10, 5), Decimal(3250), Decimal("3884.89"), True)
    assert kinds(s) == [
        ("ÖDEMENİZ İÇİN TEŞEKKÜR EDERİZ", Decimal(-3250), K.CARD_PAYMENT),
        ("MIGROS ORNEK SUBE ISTANBUL", Decimal("1245.60"), K.PURCHASE),
        ("ORNEK FIRIN KADIKOY", Decimal(185), K.PURCHASE),
        ("TEKNOSA ORNEK AVM", Decimal(250), K.PURCHASE),
        ("NETFLIX.COM AMSTERDAM NL", Decimal("695.40"), K.PURCHASE),
        ("İBB ÖRNEK METROBÜS", Decimal(1000), K.CASH_ADVANCE),  # the ATM's place, under the cash advance heading
        ("ÖDEMENİZ İÇİN TEŞEKKÜR EDERİZ", Decimal(-2000), K.OWN_TRANSFER),  # paired with the deferral
        ("ERTELENEN EKSTRE TUTARI", Decimal(2000), K.OWN_TRANSFER),
        ("TURKCELL FATURA ODEME", Decimal(450), K.PURCHASE),
        ("DÖNEM FAİZİ", Decimal("45.30"), K.INTEREST_FEE),
        ("KKDF + BSMV", Decimal("13.59"), K.INTEREST_FEE),
    ]
    by_text = {t.description: t for t in s.transactions}
    assert [by_text[t].bank_category for t in ("MIGROS ORNEK SUBE ISTANBUL", "TEKNOSA ORNEK AVM")] == [
        "MARKET VE GIDA",
        "ELEKTRONİK",
    ]
    assert by_text["NETFLIX.COM AMSTERDAM NL"].bank_category == ""  # a general heading is no category
    assert (by_text["TEKNOSA ORNEK AVM"].installment, by_text["NETFLIX.COM AMSTERDAM NL"].original) == (
        "8/12",
        "19,99 USD",
    )
    assert by_text["DÖNEM FAİZİ"].date == s.cut_date  # undated period charges take the cut date
    assert [t.ref.page for t in s.transactions] == [1] * 6 + [2] * 5


def test_garanti_paracard_has_no_debt_only_its_purchases_and_withdrawals():
    r = read(garanti.paracard_statement())
    s = only(r)
    assert (r.parser, r.accounts[0].type, s.previous, s.total, s.total_is_sum) == (
        "garanti.paracard",
        AccountType.DEBIT_CARD,
        None,
        Decimal("1734.50"),
        True,
    )
    assert s.verified and [t.kind for t in s.transactions] == [K.PURCHASE] * 3 + [K.CASH_ADVANCE]


def test_a_card_statement_whose_total_the_rows_miss_does_not_verify():
    s = only(read(garanti.bonus_statement(previous=Decimal(3250), total=Decimal("3900.00"))))
    assert not s.verified and s.difference == Decimal("-15.11")


# --- İş Bankası ------------------------------------------------------------------------------------------------


def test_isbank_maximum_statement_splits_an_installment_cash_advance_into_principal_and_interest():
    r = read(isbank.maximum_statement())
    s = only(r)
    assert (r.parser, r.accounts[0].id, r.holder) == ("isbank.maximum_card", "isbank-1234", HOLDER)
    assert (s.cut_date, s.previous, s.total, s.verified) == (date(2026, 10, 5), Decimal(3250), Decimal("3145.53"), True)
    assert [(amount, kind) for _, amount, kind in kinds(s)] == [
        (Decimal(-3250), K.CARD_PAYMENT),  # a credit, printed with a leading plus
        (Decimal("1245.60"), K.PURCHASE),
        (Decimal(500), K.PURCHASE),
        (Decimal(1344), K.LOAN_PRINCIPAL),  # its FZ:/VR/FN: breakdown wrapped onto the next line
        (Decimal(156), K.INTEREST_FEE),
        (Decimal("34.50"), K.INTEREST_FEE),
        (Decimal("-234.56"), K.REFUND),
        (Decimal("99.99"), K.PURCHASE),
    ]
    assert s.transactions[2].installment == "2/6"


# --- TEB -------------------------------------------------------------------------------------------------------


def test_teb_bonus_statement_reads_every_card_section():
    r = read(teb.bonus_statement())
    s = only(r)
    assert (r.parser, r.accounts[0].id, r.holder) == ("teb.bonus_card", "teb-1234", HOLDER)
    assert (s.previous, s.total, s.verified) == (Decimal(3250), Decimal(4716), True)
    assert [t.description for t in s.transactions] == [
        "ÖDEMENİZ İÇİN TEŞEKKÜR EDERİZ",
        "MIGROS ORNEK SUBE ISTANBUL",  # without the day of purchase printed before it
        "TEKNOSA ORNEK AVM",
        "ornek.com",
        "ORNEK MOBILYA",
        "ORNEK KITAPEVI KADIKOY",  # the additional card's section
        "YILLIK KART ÜCRETİ",
    ]
    teknosa, abroad, whole = s.transactions[2:5]
    assert (teknosa.installment, abroad.original, whole.amount) == ("8/9", "25,75 EUR", Decimal(1500))


def test_a_teb_statement_delivered_as_page_images_is_read_with_ocr(monkeypatch):
    monkeypatch.setattr(parsers, "ocr_available", lambda: True)
    monkeypatch.setattr(contract.SourceDocument, "ocr_pages", property(lambda self: teb.scanned_statement()))
    s = only(read(scan_pdf()))
    assert (s.previous, s.total, s.verified, len(s.transactions)) == (Decimal(3250), Decimal(4716), True, 7)
    assert s.transactions[1].description == "MIGROS ORNEK SUBE ISTANBUL"  # the contactless icon ")))" is gone
    assert s.transactions[2].installment == "8/9" and all(t.ref for t in s.transactions)


# --- QNB -------------------------------------------------------------------------------------------------------


def test_qnb_card_statement_repairs_the_labels_its_font_breaks():
    r = read(qnb.card_statement())
    s = only(r)
    assert (r.parser, r.accounts[0].id, r.holder) == ("qnb.card_pdf", "qnb-1234", HOLDER)
    assert (s.previous, s.total, s.verified) == (Decimal(3250), Decimal("2590.89"), True)
    assert kinds(s)[0] == ("ÖDEME TEŞEKKÜR EDERİZ", Decimal(-3250), K.CARD_PAYMENT)
    assert [t.description for t in s.transactions[1:2] + s.transactions[4:]] == [
        "MIGROS ORNEK SUBE İSTANBUL",
        "Alışveriş faizi",
        "Yıllık üyelik ücreti",
    ]
    assert [(t.ref.page, t.ref.line) for t in s.transactions[-2:]] == [(2, 2), (2, 3)]
