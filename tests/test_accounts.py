"""Account movement lists: row kinds, balance checks, and every bank's list end to end."""

from datetime import date
from decimal import Decimal

import pytest

from iplikci.domain.codes import AccountType, TransactionKind
from iplikci.domain.models import ParseResult
from iplikci.fakes import HOLDER, garanti, isbank, qnb, vakifbank
from iplikci.parsers import Skipped, parse_document
from iplikci.parsers.accounts import bank_from_iban
from iplikci.parsers.common import set_business_names
from iplikci.parsers.movements import Movement, check_balances, classify, receiver_after_bank, sender_after_bank
from iplikci.sources import Document


def move(desc, amount, balance=None, label=""):
    return Movement(date(2026, 1, 5), desc, amount, balance, label)


def test_bank_from_iban():
    assert bank_from_iban("TR00 0003 2000 0000 0111 2223 33") == "TEB"
    assert bank_from_iban("TR00 0006 2000 9990 0001 2345 67") == "Garanti BBVA"
    assert bank_from_iban("") == ""


def test_check_balances_newest_first():
    rows = [move("C", -50.0, 150.0), move("B", 100.0, 200.0), move("A", 100.0, 100.0)]
    assert check_balances(rows, oldest_first=False) == (2, 2)
    rows[0].balance = 149.0
    assert check_balances(rows, oldest_first=False) == (1, 2)


@pytest.mark.parametrize(
    "desc, amount, label, currency, kind",
    [
        ("FAST Ücreti", -7.97, "", "TRY", TransactionKind.INTEREST_FEE),
        ("Elektronik Fon Transferi (EFT) Ücreti", -12.5, "", "TRY", TransactionKind.INTEREST_FEE),
        ("MAAŞ ÖDEMESİ ÖRNEK A.Ş.", 100000.0, "", "TRY", TransactionKind.INCOME),
        ("KRE.KART BORC ODEME 2468", -5000.0, "", "TRY", TransactionKind.CARD_PAYMENT),
        ("DÖVİZ ALIŞ EUR", -10000.0, "", "TRY", TransactionKind.OWN_TRANSFER),  # currency bought into an own account
        ("DÖVİZ ALIŞ EUR", 200.0, "", "EUR", None),  # its EUR side is dropped
        ("BAKİYE YETERSİZ", 0.0, "", "TRY", None),
        ("İGDAŞ", -118.0, "Fatura", "TRY", TransactionKind.PURCHASE),
        (
            "Veli Örneksoy",
            -15000.0,
            "FAST",
            "TRY",
            TransactionKind.TRANSFER_CANDIDATE,
        ),  # decided later, with all accounts known
    ],
)
def test_classify(desc, amount, label, currency, kind):
    assert classify(move(desc, amount, label=label), currency) == kind


def test_counterparty_from_transfer_text():
    out = "Hesabınızdan Yapı ve Kredi Bankası A.Ş. Veli Örneksoy hesabına FAST ile gönderildi"
    assert receiver_after_bank(out) == "Veli Örneksoy"
    assert sender_after_bank("Enpara Bank A.Ş. Kemal Denemeci hesabından gelen") == "Kemal Denemeci"


def _teb_html(holder: str, rows: list[tuple]) -> bytes:
    info = [
        ("Şube", "999-DENEME"),
        ("Hesap", "111222333"),
        ("IBAN", "TR000003200000000111222333"),
        ("Hesap Türü", "Vadesiz TL"),
        ("Hesap Sahibi", holder),
        ("Bakiye", "0,00"),
    ]
    head = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in info)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return (
        "<html><body><table><tr><td></td><td>Hesap Hareketlerim</td></tr>" + head + "</table>"
        '<div class="prompt"> 01/01/2026 - 31/01/2026 tarihleri arasındaki işlemleriniz aşağıdadır.</div>'
        "<table><tr><td>Tarih</td><td>Valör</td><td>Saat</td><td>Açıklama</td><td>Tutar</td><td>Bakiye</td><td>Dekont</td></tr>"
        + body
        + "</table></body></html>"
    ).encode("utf-8")


TEB_ROWS = [  # newest first, as the bank prints them
    ("20/01/2026", "20/01/2026", "10:00", "YAPI VE KREDI BANKASI A.Ş.", "-15.000,00", "10.000,00", "3"),
    ("10/01/2026", "10/01/2026", "09:00", "FAST Ücreti", "-8,00", "25.000,00", "2"),
    ("05/01/2026", "05/01/2026", "08:00", "ÖRNEK İSİM SOYADOĞLU den gelen havale", "25.008,00", "25.008,00", "1"),
]


def test_teb_export_end_to_end():
    doc = Document("TEBHareket.xls", "test", _teb_html("ÖRNEK İSİM SOYADOĞLU", TEB_ROWS), "sha")
    result = parse_document(doc)
    s = result.statements[0]
    assert (s.start, s.cut_date) == (date(2026, 1, 1), date(2026, 1, 31))
    assert s.verified and (s.checks_ok, s.checks_total) == (2, 2)
    assert result.accounts[0].type == AccountType.CURRENT and result.holder == "ÖRNEK İSİM SOYADOĞLU"
    kinds = {t.description: (t.kind, t.amount) for t in s.transactions}
    assert kinds["FAST Ücreti"] == (TransactionKind.INTEREST_FEE, 8.0)  # money out is a positive expense
    assert kinds["YAPI VE KREDI BANKASI A.Ş."] == (TransactionKind.TRANSFER_CANDIDATE, 15000.0)
    assert s.transactions[-1].counterparty == "ÖRNEK İSİM SOYADOĞLU"
    # Opening and closing balance and the balance at the end of each month, for the balance sheet.
    assert (s.previous, s.total, s.balances) == (0.0, 10000.0, {"2026-01": 10000.0})


def test_company_account_export_is_business():
    set_business_names(["Örnek Teknoloji"])
    doc = Document("KMH.xls", "test", _teb_html("ÖRNEK TEKNOLOJİ A.Ş.", TEB_ROWS), "sha")
    with pytest.raises(Skipped) as exc:
        parse_document(doc)
    assert exc.value.business


# --- every bank's list, from fake documents (iplikci.fakes) ------------------------------------------------------


def _read(name: str, data: bytes) -> ParseResult:
    return parse_document(Document(name, "test", data, "sha"))


def test_garanti_account_xls_reads_newest_first_and_names_the_other_side_of_a_transfer():
    r = _read("HesapHareketleri.xls", garanti.account_xls())
    [s] = r.statements
    assert (r.parser, r.accounts[0].id, r.holder) == ("garanti.account_xls", "garanti-1234567", HOLDER)
    assert (s.start, s.cut_date, s.previous, s.total) == (
        date(2026, 10, 1),
        date(2026, 10, 31),
        1000,
        Decimal("23946.70"),
    )
    assert s.verified and (s.checks_ok, s.checks_total) == (6, 6)
    by_text = {t.description: t for t in s.transactions}
    assert by_text["FAST123456789-VELİ ÖRNEKSOY-EKİM KİRA"].counterparty == "VELİ ÖRNEKSOY"
    assert by_text["AYŞE SOYADOĞLU Havale"].counterparty == "AYŞE SOYADOĞLU"
    assert by_text["İGDAŞ FATURA ÖDEMESİ"].kind == TransactionKind.PURCHASE  # by its label, Fatura
    assert [t.ref.row for t in s.transactions] == list(range(8, 15))  # under the seven rows of the head


def test_isbank_account_xls_finds_branch_and_account_at_the_end_of_the_iban():
    r = _read("HesapOzeti.xls", isbank.account_xls())
    [s] = r.statements
    assert (r.parser, r.accounts[0].id, r.holder) == ("isbank.account_xls", "isbank-1234-0123456", HOLDER)
    assert s.verified and s.total == Decimal("24928.74")
    sent = next(t for t in s.transactions if t.amount == 15000)
    assert (sent.counterparty, sent.kind) == ("VELİ ÖRNEKSOY", TransactionKind.TRANSFER_CANDIDATE)  # "AD*" FAST text
    assert next(t for t in s.transactions if t.amount == Decimal("8.86")).kind == TransactionKind.INTEREST_FEE


def test_vakifbank_account_xlsx_names_the_employer_and_the_other_side_of_a_transfer():
    r = _read("HesapHareketleri.xlsx", vakifbank.account_xlsx())
    [s] = r.statements
    assert (r.parser, r.accounts[0].label) == ("vakifbank.account_xlsx", "Vakıfbank Vadesiz TL …234567 (Günlük)")
    assert s.verified and (s.start, s.cut_date) == (date(2026, 10, 1), date(2026, 10, 31))
    salary, sent, fee, bill, received, euros = s.transactions  # oldest first
    assert (salary.kind, salary.counterparty) == (TransactionKind.INCOME, "Örnek İşveren A.Ş.")
    assert (sent.counterparty, received.counterparty) == ("Veli Örneksoy", "Kemal Denemeci")
    assert (fee.kind, bill.kind, euros.kind) == (
        TransactionKind.INTEREST_FEE,
        TransactionKind.PURCHASE,
        TransactionKind.OWN_TRANSFER,
    )
    assert bill.description == "FATURA: İGDAŞ Doğalgaz Faturası"


def test_qnb_account_pdf_takes_a_rows_text_from_the_transfer_heading_above_it():
    r = _read("HesapHareketleri.pdf", qnb.account_pdf())
    [s] = r.statements
    assert (r.parser, r.accounts[0].id, r.accounts[0].type, r.holder) == (
        "qnb.account_pdf",
        "qnb-12345678",
        AccountType.CURRENT,
        HOLDER,
    )
    assert (s.previous, s.total, s.verified) == (1000, Decimal("24929.60"), True)  # opened by DEVREDEN BAKİYE
    sent = s.transactions[1]
    assert sent.counterparty == "VELİ ÖRNEKSOY" and sent.description.endswith("Sorgu No: 123 EKİM KİRA ÖDEMESİ")
    assert s.transactions[4].counterparty == "AYŞE SOYADOĞLU"  # on the second page
    assert [(t.ref.page, t.ref.line) for t in s.transactions[-2:]] == [(2, 2), (2, 3)]


def test_qnb_overdraft_account_is_its_own_type():
    r = _read("HesapHareketleri.pdf", qnb.account_pdf(overdraft=True))
    assert (r.accounts[0].type, r.accounts[0].label) == (AccountType.OVERDRAFT, "QNB Ek Hesap 12345678")
