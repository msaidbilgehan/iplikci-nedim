"""Receipts, passbooks and brokerage statements, read from synthetic PDFs laid out like the banks' own,
and the bank documents without money movements, which are named rather than called unknown."""

import textwrap
from datetime import date

import pytest

from iplikci import parsers
from iplikci.analysis import resolve_masked
from iplikci.app import intake
from iplikci.app.analysis import analyze
from iplikci.demo import HOLDER, brokerage_page, garanti_fast_body, garanti_receipt, holdings_page, right, text_pdf
from iplikci.domain.codes import AccountType, TransactionKind
from iplikci.domain.models import Account, ParseResult, Statement
from iplikci.parsers.common import not_a_statement, set_business_names
from iplikci.sources import Document
from iplikci.vault.names import account_names, display_path

from conftest import put


def read(data: bytes, name: str = "belge.pdf") -> ParseResult:
    return parsers.parse_document(Document(name, "test", data, "sha"))


# --- Garanti BBVA receipts ------------------------------------------------------------------------


FAST = garanti_fast_body("EKİM KİRA ÖDEMESİ", "VELİ ÖRNEKSOY")


def test_garanti_fast_receipt_leaves_the_receiver_to_the_analysis():
    r = read(garanti_receipt("HESAPTAN FAST", "106/1234567", HOLDER, FAST, "- 650,00 TL"))
    assert [a.id for a in r.accounts] == ["garanti-1234567"]  # the id the Garanti account lists use
    assert (r.title, r.holder, r.receipt_key) == ("Giden FAST", HOLDER, "garanti-dekont-2024-10-22-00.03.19.000001")
    transfer, fee = r.transactions
    assert (transfer.date, transfer.amount, transfer.kind, transfer.counterparty) == (
        date(2024, 10, 22),
        650.0,
        TransactionKind.TRANSFER_CANDIDATE,
        "VELİ ÖRNEKSOY",
    )
    assert transfer.description == "Giden FAST → VELİ ÖRNEKSOY (Ziraat Bankası) — EKİM KİRA ÖDEMESİ"
    assert (fee.amount, fee.kind, fee.account) == (4.43, TransactionKind.INTEREST_FEE, "garanti-1234567")


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
    r = read(garanti_receipt("HESAPTAN HESABA HAVALE", "106/1234567", HOLDER, body, "- 8.400,00 TL"))
    transfer, fee = r.transactions
    assert (r.title, transfer.amount, transfer.counterparty) == ("Giden Havale", 8400.0, "VELİ ÖRNEKSOY")
    assert transfer.description.endswith("— 2024 OCAK KİRA") and fee.amount == 4.43


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
    receipt = read(garanti_receipt("GELEN FON TRANSFERİ", "1012/****321", "ÖR***** KU*****", body, "+ 1.000,00 EUR"))
    [row] = receipt.transactions
    assert (receipt.title, receipt.holder, row.amount, row.original) == ("Gelen Transfer", "", -1000.0, "1.000,00 EUR")
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

QNB_TRANSFER = (
    "QNB Bank A.Ş. DEKONT ÖRNEK KULLANICI Müşteri No 100000001 İşlem Yeri HAZİNE MUHASEBELEŞME ŞUBESİ "
    "İşlem Tarihi {day} 15:22:04 Aşağıdaki hesap/kredi kartınızda karşılarında gösterilen hareketler "
    "gerçekleştirilmiştir. Hesap/K.Kart No IBAN Açıklama B/A Para Cinsi TUTAR "
    "TR000011100000000012345678 {row} TL 2,400.00 {block} SORGU NO: 1 Sıra No 00344-0 Fiş No : {fis}"
)


@pytest.mark.parametrize(
    "row, block, amount, who, text",
    [
        (
            "Gönderen: AYŞE SOYADOĞLU A",
            (
                "GELEN FAST EFT AÇIKLAMA: kk ödemesi GÖNDEREN : AYŞE SOYADOĞLU HESAP NO: 12345678 "
                "KATILIMCI: Türkiye Garanti Bankası A.Ş."
            ),
            -2400.0,
            "AYŞE SOYADOĞLU",
            "Gelen transfer ← Garanti BBVA (kk odemesi)",
        ),
        (
            "GİDEN FAST EFT B",
            "AÇIKLAMA: kira ALICI : VELİ ÖRNEKSOY IBAN: TR000006700000000000000001",
            2400.0,
            "VELİ ÖRNEKSOY",
            "Giden transfer (kira)",
        ),
    ],
)
def test_qnb_transfer_receipt_names_the_other_side_and_leaves_the_rest_to_the_analysis(row, block, amount, who, text):
    receipt = QNB_TRANSFER.format(day="03/11/2026", row=row, block=block, fis="202611000000001")
    r = read(text_pdf([(20, 40 + 12 * i, line) for i, line in enumerate(textwrap.wrap(receipt, 100))]))
    [t] = r.transactions
    assert (t.date, t.amount, t.kind, t.counterparty, t.account) == (
        date(2026, 11, 3),
        amount,
        TransactionKind.TRANSFER_CANDIDATE,
        who,
        "qnb-12345678",
    )
    assert (t.description, r.receipt_key) == (text, "qnb-202611000000001")


# --- İş Bankası receipt and passbook ------------------------------------------------------------------


def test_isbank_fast_receipt_reads_both_columns():
    r = read(
        text_pdf(
            [
                (6, 78, HOLDER),
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
    )
    assert ([a.id for a in r.accounts], r.title, r.holder) == (["isbank-1234-0123456"], "Giden FAST", HOLDER)
    transfer, fee = r.transactions
    assert (transfer.date, transfer.amount, transfer.kind, transfer.counterparty) == (
        date(2024, 2, 8),
        8400.0,
        TransactionKind.TRANSFER_CANDIDATE,
        "Veli Örneksoy",
    )
    assert transfer.description == "Giden FAST → Veli Örneksoy (Yapı Kredi) — 2024 Şubat Kira Ödemesi"
    assert (fee.amount, fee.kind, r.receipt_key) == (8.86, TransactionKind.INTEREST_FEE, "isbank-dekont-100000000001")


def test_isbank_passbook_is_a_verified_list_of_a_new_term_deposit():
    r = read(
        text_pdf(
            [
                (276, 61, "e-CÜZDAN"),
                (310, 105, "Müşteri Adı / Numarası :"),
                (310, 113, f"{HOLDER} / 111222333"),
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
                # newest first, like the bank prints it
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
    )
    [account], [s] = r.accounts, r.statements
    assert (account.id, account.type, account.label) == (
        "isbank-1234-0765432",
        AccountType.DEPOSIT,
        "İş Bankası Vadeli TL 1234-0765432",
    )
    assert (s.start, s.cut_date, s.previous, s.total) == (date(2024, 1, 17), date(2024, 1, 17), 0.0, 7500.0)
    assert s.verified and (s.checks_ok, s.checks_total) == (3, 3)  # from zero: the account was opened that day
    [opening] = s.transactions  # rows of zero carry no money
    assert (opening.amount, opening.kind, opening.counterparty) == (
        -7500.0,
        TransactionKind.TRANSFER_CANDIDATE,
        HOLDER,
    )  # from an own account


def test_vakifbank_passbook_reads_the_account_page_after_the_terms():
    r = read(
        text_pdf(
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
                (211, 114, HOLDER),
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
    )
    [account], [s] = r.accounts, r.statements
    assert (account.id, account.currency, account.label) == (
        "vakifbank-0158000000012345",
        "USD",
        "Vakıfbank Vadesiz USD …012345 (Birikim)",
    )
    assert (s.start, s.cut_date, s.verified, s.transactions) == (date(2026, 5, 2), date(2026, 5, 2), True, [])


# --- Garanti BBVA Yatırım ---------------------------------------------------------------------------


def test_brokerage_statement_holds_the_securities_and_the_cash_moves():
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
    held = [("ORNEK", "ÖRNEK SANAYİ A.Ş.", "20.000", "1,234.50"), ("DENEM", "DENEME HOLDİNG", "5.000", "100.00")]
    r = read(text_pdf(holdings_page("30/06/2026", held, "1,334.50", "1,334.50"), cash))
    [account], [s] = r.accounts, r.statements
    assert (account.id, account.type, r.holder) == ("garanti-yatirim-1234567-101", AccountType.BROKERAGE, HOLDER)
    # Dated the month's last business day, the statement covers the calendar month.
    assert (s.start, s.cut_date, s.previous, s.total) == (date(2026, 6, 1), date(2026, 6, 30), 0.0, 0.0)
    # Two running balances, the closing cash, the securities total and the portfolio total.
    assert s.verified and (s.checks_ok, s.checks_total) == (5, 5)
    assert [(x.code, x.name, x.quantity, x.value, x.as_of) for x in s.securities] == [
        ("ORNEK", "ÖRNEK SANAYİ A.Ş.", 20.0, 1234.5, date(2026, 6, 30)),
        ("DENEM", "DENEME HOLDİNG", 5.0, 100.0, date(2026, 6, 30)),
    ]
    dividend, moved = s.transactions
    assert (dividend.kind, dividend.amount, dividend.description) == (
        TransactionKind.INCOME,
        -10.0,
        "ORNEK temettüsü (20 adet)",
    )
    assert (moved.kind, moved.amount, moved.counterparty) == (
        TransactionKind.TRANSFER_CANDIDATE,
        10.0,
        HOLDER,
    )  # on to the user's bank account


def test_a_quiet_month_is_checked_against_the_totals_it_prints():
    page = holdings_page("26/05/2026", [("ORNEK", "ÖRNEK SANAYİ A.Ş.", "20.000", "1,234.50")], "1,234.50", "1,234.50")
    [s] = read(text_pdf(page)).statements
    assert (s.cut_date, s.verified, s.checks_total, s.transactions) == (date(2026, 5, 31), True, 3, [])
    wrong = holdings_page("26/05/2026", [("ORNEK", "ÖRNEK SANAYİ A.Ş.", "20.000", "1,234.50")], "1,300.00", "1,300.00")
    assert not read(text_pdf(wrong)).statements[0].verified  # a row the reader missed shows


def test_trade_form_is_a_receipt_of_the_sale_and_its_costs():
    r = read(
        text_pdf(
            [
                (36, 72, "Garanti Yatırım Menkul Kıymetler A.Ş."),
                (36, 118, "www.garantibbvayatirim.com.tr"),
                (248, 151, "İŞLEM SONUÇ FORMU"),
                (36, 171, "Müşteri Adı"),
                (113, 171, ":"),
                (121, 171, HOLDER),
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
    )
    assert (r.accounts[0].id, r.receipt_key, r.holder) == (
        "garanti-yatirim-1234567-101",
        "garanti-yatirim-form-99887766",
        HOLDER,
    )
    sale, costs = r.transactions
    assert (sale.kind, sale.amount, sale.description) == (
        TransactionKind.INVESTMENT,
        -123.4,
        "Hisse satışı: ORNEK 10 adet × 12,34 TL",
    )
    assert (costs.kind, costs.amount, costs.date) == (TransactionKind.INTEREST_FEE, 1.0, date(2024, 7, 1))


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
        "liste", accounts=[usd], statements=[Statement("garanti-1999", date(2026, 1, 31), "USD", "l.xls", 0.0, 0.0)]
    )
    resolve_masked([receipt, listed])
    assert receipt.accounts[0].id == "garanti-****999"  # the only candidate holds another currency


# --- filing --------------------------------------------------------------------------------------------


def test_brokerage_statements_are_kept_and_a_resent_month_is_one(ws):
    rows = [("ORNEK", "ÖRNEK SANAYİ A.Ş.", "20.000", "1,234.50")]
    put(ws.inbox / "HisseSenediEkstresi.pdf", text_pdf(holdings_page("30/06/2026", rows, "1,234.50", "1,234.50")))
    resent = holdings_page("30/06/2026", rows, "1,234.50", "1,234.50") + [(37, 830, "tekrar gönderildi")]
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
