"""Account movement lists: row kinds, balance checks and a TEB export end to end."""

from datetime import date

import pytest

from iplikci.parsers import Skipped, hesaplar
from iplikci.parsers.common import set_business_names
from iplikci.parsers.hesap import (
    CANDIDATE,
    Movement,
    bank_from_iban,
    check_balances,
    classify,
    receiver_after_bank,
    sender_after_bank,
)
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
        ("FAST Ücreti", -7.97, "", "TL", "faiz_ucret"),
        ("Elektronik Fon Transferi (EFT) Ücreti", -12.5, "", "TL", "faiz_ucret"),
        ("MAAŞ ÖDEMESİ ÖRNEK A.Ş.", 100000.0, "", "TL", "gelir"),
        ("KRE.KART BORC ODEME 2468", -5000.0, "", "TL", "kart_odemesi"),
        ("DÖVİZ ALIŞ EUR", -10000.0, "", "TL", "transfer"),  # currency bought into an own account
        ("DÖVİZ ALIŞ EUR", 200.0, "", "EUR", None),  # its EUR side is dropped
        ("BAKİYE YETERSİZ", 0.0, "", "TL", None),
        ("İGDAŞ", -118.0, "Fatura", "TL", "harcama"),
        ("Veli Örneksoy", -15000.0, "FAST", "TL", CANDIDATE),  # decided later, with all accounts known
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
    result = hesaplar.parse(doc)
    s = result.statements[0]
    assert (s.start, s.cut_date) == (date(2026, 1, 1), date(2026, 1, 31))
    assert s.verified and (s.checks_ok, s.checks_total) == (2, 2)
    assert result.accounts[0].type == "Vadesiz hesap" and result.holder == "ÖRNEK İSİM SOYADOĞLU"
    kinds = {t.description: (t.kind, t.amount) for t in s.transactions}
    assert kinds["FAST Ücreti"] == ("faiz_ucret", 8.0)  # money out is a positive expense
    assert kinds["YAPI VE KREDI BANKASI A.Ş."] == (CANDIDATE, 15000.0)
    assert s.transactions[-1].counterparty == "ÖRNEK İSİM SOYADOĞLU"
    # Opening and closing balance and the balance at the end of each month, for the balance sheet.
    assert (s.previous, s.total, s.balances) == (0.0, 10000.0, {"2026-01": 10000.0})


def test_company_account_export_is_business():
    set_business_names(["Örnek Teknoloji"])
    doc = Document("KMH.xls", "test", _teb_html("ÖRNEK TEKNOLOJİ A.Ş.", TEB_ROWS), "sha")
    with pytest.raises(Skipped) as exc:
        hesaplar.parse(doc)
    assert exc.value.business
