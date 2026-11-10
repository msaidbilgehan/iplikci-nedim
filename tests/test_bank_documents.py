"""Receipts, passbooks and brokerage statements, read from synthetic PDFs laid out like the banks' own,
and the bank documents without money movements, which are named rather than called unknown."""

from datetime import date
from decimal import Decimal

import pytest

from iplikci import parsers
from iplikci.analysis import resolve_masked
from iplikci.app import intake
from iplikci.app.analysis import analyze
from iplikci.domain.codes import AccountType, TransactionKind
from iplikci.domain.models import Account, ParseResult, SourceRef, Statement
from iplikci.fakes import HOLDER, Move, garanti, isbank, qnb, teb, vakifbank
from iplikci.fakes.files import text_pdf
from iplikci.parsers.common import not_a_statement, set_business_names
from iplikci.parsers.contract import Document
from iplikci.vault.names import account_names, display_path

from conftest import put


def read(data: bytes, name: str = "belge.pdf") -> ParseResult:
    return parsers.parse_document(Document(name, "test", data, "sha"))


# --- Garanti BBVA receipts ------------------------------------------------------------------------


FAST = garanti.fast_body("EKİM KİRA ÖDEMESİ", "VELİ ÖRNEKSOY")


def test_garanti_fast_receipt_leaves_the_receiver_to_the_analysis():
    r = read(garanti.receipt("HESAPTAN FAST", "106/1234567", HOLDER, FAST, "- 650,00 TL"))
    assert [a.id for a in r.accounts] == ["garanti-1234567"]  # the id the Garanti account lists use
    assert (r.title, r.holder, r.receipt_key) == ("Giden FAST", HOLDER, "garanti-dekont-2024-10-22-00.03.19.000001")
    transfer, fee = r.transactions
    assert (transfer.date, transfer.amount, transfer.kind, transfer.counterparty) == (
        date(2024, 10, 22),
        Decimal(650),
        TransactionKind.TRANSFER_CANDIDATE,
        "VELİ ÖRNEKSOY",
    )
    assert transfer.description == "Giden FAST → VELİ ÖRNEKSOY (Ziraat Bankası) — EKİM KİRA ÖDEMESİ"
    assert (fee.amount, fee.kind, fee.account) == (Decimal("4.43"), TransactionKind.INTEREST_FEE, "garanti-1234567")


def test_garanti_havale_receipt_names_the_receiver_after_the_account_number():
    body = [
        (40, 322, "2024 OCAK KİRA"),
        (40, 350, "ALACAKLI HESAP"),
        (172, 350, ":"),
        (184, 350, "00759 / 7654321 VELİ ÖRNEKSOY"),
        (40, 421, "MASRAF TOPLAMI"),
        (172, 421, ":"),
        (184, 421, "4,43 TL"),
    ]
    r = read(garanti.receipt("HESAPTAN HESABA HAVALE", "106/1234567", HOLDER, body, "- 8.400,00 TL"))
    transfer, fee = r.transactions
    assert (r.title, transfer.amount, transfer.counterparty) == ("Giden Havale", Decimal(8400), "VELİ ÖRNEKSOY")
    assert transfer.description.endswith("— 2024 OCAK KİRA") and fee.amount == Decimal("4.43")


def test_a_masked_incoming_receipt_lands_on_the_account_the_lists_name():
    body = [
        (40, 336, "HAVALE ÖDEME - HESABA"),
        (40, 364, "GÖNDEREN"),
        (122, 364, ":"),
        (133, 364, "ÖRNEK FİRMA"),
        (40, 378, "GÖNDEREN BANKA"),
        (122, 378, ":"),
        (133, 378, "DENEME BANK NV (EX BANK)"),
    ]
    receipt = read(garanti.receipt("GELEN FON TRANSFERİ", "1012/****321", "ÖR***** KU*****", body, "+ 1.000,00 EUR"))
    [row] = receipt.transactions
    assert (receipt.title, receipt.holder, row.amount, row.original) == (
        "Gelen Transfer",
        "",
        Decimal(-1000),
        "1.000,00 EUR",
    )
    assert receipt.accounts[0].label == "Garanti BBVA Vadesiz EUR …321"
    eur = Account(
        "garanti-7654321", "Garanti BBVA Vadesiz EUR 7654321", "Garanti BBVA", AccountType.FX, "EUR", "7654321"
    )
    usd = Account(
        "garanti-1111321", "Garanti BBVA Vadesiz USD 1111321", "Garanti BBVA", AccountType.FX, "USD", "1111321"
    )
    resolve_masked([receipt, ParseResult("liste", accounts=[eur]), ParseResult("liste", accounts=[usd])])
    assert receipt.accounts == [eur] and row.account == "garanti-7654321"  # same bank, currency and visible digits


# --- QNB transfer receipts ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "side, amount, who, text",
    [
        (qnb.INCOMING, Decimal(-2400), "AYŞE SOYADOĞLU", "Gelen transfer ← Garanti BBVA (kk odemesi)"),
        (qnb.OUTGOING, Decimal(2400), "VELİ ÖRNEKSOY", "Giden transfer (kira)"),
    ],
)
def test_qnb_transfer_receipt_names_the_other_side_and_leaves_the_rest_to_the_analysis(side, amount, who, text):
    r = read(qnb.transfer_receipt(side))
    [t] = r.transactions
    assert (t.date, t.amount, t.kind, t.counterparty, t.account) == (
        date(2026, 11, 3),
        amount,
        TransactionKind.TRANSFER_CANDIDATE,
        who,
        "qnb-12345678",
    )
    assert (t.description, r.receipt_key) == (text, "qnb-202611000000001")


# --- TEB card payment receipt -------------------------------------------------------------------------


def test_teb_card_payment_receipt_is_a_payment_to_a_card_with_no_statement_and_points_at_its_total():
    r = read(teb.card_payment_receipt(Decimal("3250.00"), date(2026, 10, 15)))
    [payment] = r.transactions
    assert (payment.date, payment.amount, payment.kind, payment.account) == (
        date(2026, 10, 15),
        Decimal(3250),
        TransactionKind.CARD_PAYMENT_NO_STATEMENT,
        "teb-1234",
    )
    assert (r.receipt_key, r.title) == ("teb-123456789", "Kart Ödemesi 1234")
    assert payment.ref == SourceRef(page=1, line=7)  # the TOPLAM line, not the first line holding the amount


# --- İş Bankası receipt and passbook ------------------------------------------------------------------


def test_isbank_fast_receipt_reads_both_columns():
    r = read(isbank.fast_receipt())
    assert ([a.id for a in r.accounts], r.title, r.holder) == (["isbank-1234-0123456"], "Giden FAST", HOLDER)
    transfer, fee = r.transactions
    assert (transfer.date, transfer.amount, transfer.kind, transfer.counterparty) == (
        date(2024, 2, 8),
        Decimal(8400),
        TransactionKind.TRANSFER_CANDIDATE,
        "Veli Örneksoy",
    )
    assert transfer.description == "Giden FAST → Veli Örneksoy (Yapı Kredi) — 2024 Şubat Kira Ödemesi"
    assert (fee.amount, fee.kind, r.receipt_key) == (
        Decimal("8.86"),
        TransactionKind.INTEREST_FEE,
        "isbank-dekont-100000000001",
    )


def test_isbank_passbook_is_a_verified_list_of_a_new_term_deposit():
    r = read(isbank.passbook())
    [account], [s] = r.accounts, r.statements
    assert (account.id, account.type, account.label) == (
        "isbank-1234-0765432",
        AccountType.DEPOSIT,
        "İş Bankası Vadeli TL 1234-0765432",
    )
    assert (s.start, s.cut_date, s.previous, s.total) == (
        date(2024, 1, 17),
        date(2024, 1, 17),
        Decimal(0),
        Decimal(7500),
    )
    assert s.verified and (s.checks_ok, s.checks_total) == (3, 3)  # from zero: the account was opened that day
    assert s.one_off  # sent once, when the account opened: no monthly list follows it
    [opening] = s.transactions  # rows of zero carry no money
    assert (opening.amount, opening.kind, opening.counterparty) == (
        Decimal(-7500),
        TransactionKind.TRANSFER_CANDIDATE,
        HOLDER,
    )  # from an own account


def test_vakifbank_passbook_reads_the_account_page_after_the_terms():
    r = read(vakifbank.passbook())
    [account], [s] = r.accounts, r.statements
    assert (account.id, account.currency, account.label) == (
        "vakifbank-0158000000012345",
        "USD",
        "Vakıfbank Vadesiz USD …012345 (Birikim)",
    )
    assert (s.start, s.cut_date, s.verified, s.transactions, s.one_off) == (
        date(2026, 5, 2),
        date(2026, 5, 2),
        True,
        [],
        True,
    )


# --- TEB dijital hesap cüzdanı ----------------------------------------------------------------------


def test_teb_passbook_reads_the_overdraft_accounts_movements_and_checks_every_balance():
    r = read(teb.passbook())
    [account], [s] = r.accounts, r.statements
    # The bank calls it "Vadesiz"; it runs below zero, so it is the overdraft account the CEPTETEB export names.
    assert (account.id, account.type, account.label) == (
        "teb-123456789",
        AccountType.OVERDRAFT,
        "TEB Ek Hesap 123456789",
    )
    assert (s.start, s.cut_date, s.previous, s.total, s.verified, s.one_off) == (
        date(2026, 11, 1),
        date(2026, 11, 10),
        Decimal("-300.00"),
        Decimal("0.00"),
        True,
        False,
    )
    # The first row has no balance before it to check against: nine checks for ten rows.
    assert (s.checks_ok, s.checks_total, len(s.transactions), r.holder) == (9, 9, 10, HOLDER)
    interest, *_ = s.transactions
    assert (interest.date, interest.amount, interest.kind) == (
        date(2026, 11, 2),
        Decimal("120.00"),
        TransactionKind.INTEREST_FEE,
    )
    [received] = [t for t in s.transactions if t.counterparty]
    assert (received.amount, received.kind, received.counterparty) == (
        Decimal("-1500.00"),
        TransactionKind.TRANSFER_CANDIDATE,
        "VELİ ÖRNEKSOY",
    )


def test_teb_passbook_keeps_a_description_that_runs_on_below_its_row():
    long = Move(date(2026, 11, 6), "VELİ ÖRNEKSOY den gelen havale tutarı\nKASIM AYI PAYI", Decimal(250))
    r = read(teb.passbook([*teb.PASSBOOK_MOVES, long]))
    [s] = r.statements
    last = s.transactions[-1]
    assert (last.description, last.counterparty, last.amount) == (
        "VELİ ÖRNEKSOY den gelen havale tutarı KASIM AYI PAYI",
        "VELİ ÖRNEKSOY",
        Decimal(-250),
    )
    assert s.verified and len(s.transactions) == 11


def test_teb_passbook_of_a_positive_term_account_is_a_deposit():
    moves = [Move(date(2026, 11, 3), "Vade Sonu Faiz", Decimal("85.00"))]
    r = read(teb.passbook(moves, opening=Decimal(10000), kind="Vadeli"))
    [account] = r.accounts
    assert (account.type, account.label) == (AccountType.DEPOSIT, "TEB Vadeli TL 123456789")


def test_teb_passbook_without_movements_says_so():
    with pytest.raises(parsers.Skipped, match="hareket yok") as found:
        read(teb.passbook([]))
    assert not found.value.business


def test_teb_passbook_of_a_company_stays_out_of_scope():
    set_business_names(["Örnek Teknoloji A.Ş."])
    with pytest.raises(parsers.Skipped) as found:
        read(teb.passbook(holder="ÖRNEK TEKNOLOJİ ANONİM ŞİRKETİ"))
    assert found.value.business


# --- Garanti BBVA Yatırım ---------------------------------------------------------------------------


def test_brokerage_statement_holds_the_securities_and_the_cash_moves():
    r = read(garanti.brokerage_statement())
    [account], [s] = r.accounts, r.statements
    assert (account.id, account.type, r.holder) == ("garanti-yatirim-1234567-101", AccountType.BROKERAGE, HOLDER)
    # Dated the month's last business day, the statement covers the calendar month.
    assert (s.start, s.cut_date, s.previous, s.total) == (date(2026, 6, 1), date(2026, 6, 30), Decimal(0), Decimal(0))
    # Two running balances, the closing cash, the securities total and the portfolio total.
    assert s.verified and (s.checks_ok, s.checks_total) == (5, 5)
    assert [(x.code, x.name, x.quantity, x.value, x.as_of) for x in s.securities] == [
        ("ORNEK", "ÖRNEK SANAYİ A.Ş.", Decimal(20), Decimal("1234.5"), date(2026, 6, 30)),
        ("DENEM", "DENEME HOLDİNG", Decimal(5), Decimal(100), date(2026, 6, 30)),
    ]
    dividend, moved = s.transactions
    assert (dividend.kind, dividend.amount, dividend.description) == (
        TransactionKind.INCOME,
        Decimal(-10),
        "ORNEK temettüsü (20 adet)",
    )
    assert (moved.kind, moved.amount, moved.counterparty) == (
        TransactionKind.TRANSFER_CANDIDATE,
        Decimal(10),
        HOLDER,
    )  # on to the user's bank account
    assert [(t.ref.page, t.ref.box[1]) for t in s.transactions] == [(2, 272), (2, 283)]  # their lines on the cash page


def test_a_quiet_month_is_checked_against_the_totals_it_prints():
    page = garanti.holdings_page(
        "26/05/2026", [("ORNEK", "ÖRNEK SANAYİ A.Ş.", "20.000", "1,234.50")], "1,234.50", "1,234.50"
    )
    [s] = read(text_pdf(page)).statements
    assert (s.cut_date, s.verified, s.checks_total, s.transactions) == (date(2026, 5, 31), True, 3, [])
    wrong = garanti.holdings_page(
        "26/05/2026", [("ORNEK", "ÖRNEK SANAYİ A.Ş.", "20.000", "1,234.50")], "1,300.00", "1,300.00"
    )
    assert not read(text_pdf(wrong)).statements[0].verified  # a row the reader missed shows


def test_trade_form_is_a_receipt_of_the_sale_and_its_costs():
    r = read(garanti.trade_form())
    assert (r.accounts[0].id, r.receipt_key, r.holder) == (
        "garanti-yatirim-1234567-101",
        "garanti-yatirim-form-99887766",
        HOLDER,
    )
    sale, costs = r.transactions
    assert (sale.kind, sale.amount, sale.description) == (
        TransactionKind.INVESTMENT,
        Decimal("-123.4"),
        "Hisse satışı: ORNEK 10 adet × 12,34 TL",
    )
    assert (costs.kind, costs.amount, costs.date) == (TransactionKind.INTEREST_FEE, Decimal(1), date(2024, 7, 1))


# --- documents without money movements ------------------------------------------------------------------


@pytest.mark.parametrize(
    "first_page, reason",
    [
        ("KATILIM SERTİFİKA NUMARASI : 1 ANINDA KREDİ HAYAT SİGORTASI", "sigorta poliçesi/bilgilendirmesi"),
        ("İHTİYAÇ KREDİSİ BİLGİ FORMU ÜRÜNE AİT BİLGİLER", "kredi sözleşmesi/formu"),
        ("TÜKETİCİ KREDİSİ SÖZLEŞMESİ - MESAFELİ ... HAYAT SİGORTASI POLİÇESİ", "kredi sözleşmesi/formu"),
        ("SGK OTOMATİK ÖDEME TALİMAT FORMU", "talimat formu"),
        ("ÖDEME HİZMETLERİ ÇERÇEVE SÖZLEŞMESİ ... sigorta poliçesi", "sözleşme"),  # its title names it first
        ("Kampanya duyurusu", "ekstre veya hesap hareketi değil"),
    ],
)
def test_documents_without_money_movements_say_what_they_are(first_page, reason):
    assert not_a_statement(first_page) == reason


def test_an_unknown_pdf_from_a_bank_is_named_by_its_title():
    with pytest.raises(parsers.Skipped, match="talimat formu") as found:
        read(text_pdf([(201, 97, "SGK Otomatik Ödeme Talimat Formu"), (70, 146, "Türk Ekonomi Bankası A.Ş.")]))
    assert not found.value.business


def test_a_utf16_letter_to_the_company_stays_out_of_scope():
    set_business_names(["Örnek Teknoloji A.Ş."])
    letter = "<html><body>Türk Ekonomi Bankası A.Ş. ÖRNEK TEKNOLOJİ ANONİM ŞİRKETİ faiz ve stopaj</body></html>"
    with pytest.raises(parsers.Skipped) as found:
        read(b"\xff\xfe" + letter.encode("utf-16-le"), "Sonuc.htm")
    assert found.value.business


def test_a_masked_account_is_never_guessed_across_currencies():
    receipt = ParseResult(
        "dekont", accounts=[Account("garanti-****999", "x", "Garanti BBVA", AccountType.FX, "EUR", "****999")]
    )
    usd = Account("garanti-1999", "y", "Garanti BBVA", AccountType.FX, "USD", "1999")
    listed = ParseResult(
        "liste",
        accounts=[usd],
        statements=[Statement("garanti-1999", date(2026, 1, 31), "USD", "l.xls", Decimal(0), Decimal(0))],
    )
    resolve_masked([receipt, listed])
    assert receipt.accounts[0].id == "garanti-****999"  # the only candidate holds another currency


# --- filing --------------------------------------------------------------------------------------------


def test_brokerage_statements_are_kept_and_a_resent_month_is_one(ws):
    rows = [("ORNEK", "ÖRNEK SANAYİ A.Ş.", "20.000", "1,234.50")]
    put(
        ws.inbox / "HisseSenediEkstresi.pdf",
        text_pdf(garanti.holdings_page("30/06/2026", rows, "1,234.50", "1,234.50")),
    )
    resent = garanti.holdings_page("30/06/2026", rows, "1,234.50", "1,234.50") + [(37, 830, "tekrar gönderildi")]
    put(ws.inbox / "ikinci" / "HisseSenediEkstresi.pdf", text_pdf(resent))  # other bytes, the same statement
    plan = intake.plan_inbox(ws)
    first, second = plan.items
    assert (first.action, second.action, second.copy_of) == ("processed", "copy", "HisseSenediEkstresi.pdf")
    assert first.result is not None and str(display_path(first.result, ".pdf")) == (
        "Garanti BBVA/Yatırım Hesabı 1234567-101/"
        "2026-06-01 - 2026-06-30 Garanti Yatırım 1234567-101 Hesap Hareketleri.pdf"
    )
    intake.apply(ws, plan)
    a = analyze(ws)
    assert len(a.dataset.statements) == 1 and a.stats["documents"] == 2  # both originals kept, one in the ledger
    [again] = intake.plan_paths(ws, [put(ws.home.parent / "indirilen.pdf", text_pdf(resent + [(37, 845, "3")]))]).items
    assert again.copy_of == "HisseSenediEkstresi.pdf"  # the vault's copy is found too


@pytest.mark.parametrize(
    "account, names",
    [
        (
            Account(
                "garanti-yatirim-1234567-101",
                "Garanti BBVA Yatırım 1234567-101",
                "Garanti BBVA",
                AccountType.BROKERAGE,
                number="1234567-101",
            ),
            ("Yatırım Hesabı 1234567-101", "Yatırım 1234567-101"),
        ),
        (
            Account(
                "isbank-1234-0765432",
                "İş Bankası Vadeli TL 1234-0765432",
                "İş Bankası",
                AccountType.DEPOSIT,
                number="1234-0765432",
            ),
            ("Vadeli Hesap TL 1234-0765432", "Vadeli TL 1234-0765432"),
        ),
    ],
)
def test_brokerage_and_term_deposit_folders(account, names):
    assert account_names(account) == names
