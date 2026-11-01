"""Card statements, read from fake PDFs laid out like the banks' own (iplikci.fakes)."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from iplikci import parsers
from iplikci.domain.codes import AccountType, TransactionKind
from iplikci.domain.models import ParseResult, Statement
from iplikci.fakes import HOLDER, CardTerms, garanti, isbank, qnb, teb
from iplikci.fakes.files import scan_pdf
from iplikci.parsers import contract
from iplikci.parsers.common import BUSINESS_REASON, is_business
from iplikci.parsers.contract import Document
from iplikci.parsers.pdf import open_pdf, page_text

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


def test_garanti_bonus_statement_reads_the_due_date_it_prints_twice_and_the_card_limit():
    s = only(read(garanti.bonus_statement()))
    # The heading and the summary print the due date, a sentence under them the next one; the customer's limit and the
    # cash advance limit stand around the card's. No minimum payment is printed.
    assert (s.due_date, s.minimum_payment, s.credit_limit) == (date(2026, 10, 15), None, Decimal(45000))


def test_garanti_paracard_has_no_debt_only_its_purchases_and_withdrawals():
    r = read(garanti.paracard_statement())
    s = only(r)
    assert (r.parser, r.accounts[0].type, s.previous, s.total, s.total_is_sum, s.due_date, s.credit_limit) == (
        "garanti.paracard",
        AccountType.DEBIT_CARD,
        None,
        Decimal("1734.50"),
        True,
        None,
        None,
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


def test_isbank_maximum_statement_reads_its_due_date_the_minimum_behind_its_asterisk_and_the_card_limit():
    s = only(read(isbank.maximum_statement()))
    # The summary prints the due date with dots and the box under it again with slashes; the next statement's dates,
    # the minimum payment rate and the customer's, available and cash limits stand beside them.
    assert (s.due_date, s.minimum_payment, s.credit_limit) == (date(2026, 10, 15), Decimal("1258.21"), Decimal(60000))


def test_a_maximum_minimum_under_a_thousand_is_read_through_the_asterisks_that_fill_its_width():
    terms = replace(isbank.MAXIMUM_TERMS, minimum=Decimal("597.67"))
    assert only(read(isbank.maximum_statement(terms=terms))).minimum_payment == Decimal("597.67")


@pytest.mark.parametrize("printed", ["Son Ödeme Tarihi: 16.10.2026", "Son Ödeme Tarihi: 31.02.2026"])
def test_a_due_date_printed_once_more_as_another_or_an_impossible_date_is_left_empty(printed):
    s = only(read(isbank.maximum_statement(note=printed)))
    assert (s.due_date, s.minimum_payment, s.verified) == (None, Decimal("1258.21"), True)


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


def test_teb_bonus_statement_reads_the_due_date_its_layout_prints():
    s = only(read(teb.bonus_statement()))
    assert (s.due_date, s.minimum_payment, s.credit_limit) == (date(2026, 10, 15), None, None)


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


def test_qnb_card_statement_reads_the_due_date_its_layout_prints():
    s = only(read(qnb.card_statement()))
    assert (s.due_date, s.minimum_payment, s.credit_limit) == (date(2026, 10, 15), None, None)


# --- every bank ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "statement", [garanti.bonus_statement, isbank.maximum_statement, teb.bonus_statement, qnb.card_statement]
)
def test_a_card_statement_that_prints_none_of_its_terms_leaves_them_empty_and_still_verifies(statement):
    # The next statement's due date, the other limits and the minimum payment rate are still on the page.
    s = only(read(statement(terms=CardTerms())))
    assert (s.due_date, s.minimum_payment, s.credit_limit, s.verified) == (None, None, None, True)


def test_a_company_card_that_shows_only_late_on_the_page_is_still_a_company_document():
    # The selection looks for company marks in the first 600 characters; the readers look at the whole first page.
    for statement in (
        teb.bonus_statement(note="TEB GİRİŞİMCİ KREDİ KARTI ÜYE İŞYERİ BİLGİLENDİRMESİ"),
        isbank.maximum_statement(note="BU HESAP ÖZETİ ŞİRKET KREDİ KARTINIZA AİTTİR"),
    ):
        first = page_text(open_pdf(statement).pages[0])
        assert not is_business(first[:600])
        with pytest.raises(parsers.Skipped) as found:
            read(statement)
        assert found.value.business and str(found.value) == BUSINESS_REASON
