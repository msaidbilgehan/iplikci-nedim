"""Deciding what an account transfer is once every account is known."""

from datetime import date

import pytest

from iplikci.analysis import Own, _rates, _resolve_transfers, _to_tl, build
from iplikci.categorize import Categorizer
from iplikci.domain.models import Account, ParseResult, Statement, Transaction
from iplikci.parsers.hesap import CANDIDATE
from iplikci.sources import Document

from conftest import PEOPLE_RULES

ACCOUNTS = {
    "teb-111222333": Account("teb-111222333", "TEB Vadesiz TL 111222333", "TEB", "Vadesiz hesap", number="111222333"),
    "vakifbank-0999000000123456": Account(
        "vakifbank-0999000000123456", "Vakıfbank Vadesiz TL", "Vakıfbank", "Vadesiz hesap", number="0999000000123456"
    ),
    "garanti-9000001": Account(
        "garanti-9000001",
        "Garanti BBVA Vadesiz EUR 9000001",
        "Garanti BBVA",
        "Döviz hesabı",
        currency="EUR",
        number="9000001",
    ),
}


@pytest.fixture(scope="module")
def cat(tmp_path_factory):
    rules = tmp_path_factory.mktemp("kurallar") / "kategoriler.yaml"
    rules.write_text(PEOPLE_RULES, encoding="utf-8")
    return Categorizer(rules)


def cand(d, desc, amount, account="teb-111222333", counterparty=""):
    return Transaction(
        date=d, description=desc, amount=amount, kind=CANDIDATE, account=account, counterparty=counterparty
    )


def resolve(cat, txns, statements=()):
    own = Own(["ÖRNEK İSİM SOYADOĞLU"], ACCOUNTS)
    _resolve_transfers(txns, own, cat, list(statements), ACCOUNTS, [])
    return txns


def test_own_names_and_numbers():
    own = Own(["ÖRNEK İSİM SOYADOĞLU"], ACCOUNTS)
    assert own.is_self("Örnek İsim Soyadoğlu") and own.is_self("ORNEK SOYADOGLU")
    assert not own.is_self("Ayşe Soyadoğlu")
    assert own.mentions_own_account("222333444 no.lu hesaba gönderilmiştir 0111222333")
    assert not own.mentions_own_account("Fatura no 55512345")


def test_transfer_to_self_by_name(cat):
    (t,) = resolve(cat, [cand(date(2026, 1, 5), "FAST", 1000.0, counterparty="ÖRNEK İSİM SOYADOĞLU")])
    assert t.kind == "transfer"


def test_bank_only_row_inherits_the_named_payment(cat):
    # Vakıfbank names the landlord; TEB prints only the receiver's bank for the same rent.
    named = cand(
        date(2026, 1, 31),
        "FAST Anlık Ödeme: k (31/01/2026 tarihli 1 sorgu no'lu ÖRNEK İSİM SOYADOĞLU "
        "hesabından Yapı ve Kredi Bankası A.Ş. Veli Örneksoy hesabına giden FAST ödemesi)",
        15000.0,
        account="vakifbank-0999000000123456",
        counterparty="Veli Örneksoy",
    )
    bank_only = cand(date(2026, 3, 2), "YAPI VE KREDI BANKASI A.Ş.", 15000.0)
    resolve(cat, [named, bank_only])
    assert (named.kind, named.category) == ("harcama", "Kira")
    assert (bank_only.kind, bank_only.category) == ("harcama", "Kira")
    assert bank_only.description.endswith("(→ Veli Örneksoy)")


def test_opposite_rows_on_two_own_accounts_pair_up(cat):
    out = cand(date(2026, 2, 1), "Giden FAST", 5000.0)
    inc = cand(date(2026, 2, 2), "Gelen FAST", -5000.0, account="vakifbank-0999000000123456")
    far = cand(date(2026, 2, 20), "Gelen FAST", -5000.0, account="vakifbank-0999000000123456")
    resolve(cat, [out, inc, far])
    assert (out.kind, inc.kind) == ("transfer", "transfer")
    assert far.kind == "gelir"  # nothing left to pair with: money from someone else


def test_bank_only_payment_outside_coverage_goes_to_own_account(cat):
    covered = Statement(
        account="vakifbank-0999000000123456",
        cut_date=date(2026, 1, 31),
        currency="TL",
        source="",
        previous=None,
        total=None,
        start=date(2026, 1, 1),
    )
    t = cand(date(2025, 12, 15), "TÜRKİYE VAKIFLAR BANKASI T.A.O.", 3000.0)
    resolve(cat, [t], [covered])
    assert t.kind == "transfer"


def test_unknown_people(cat):
    out, inc = (
        cand(date(2026, 1, 5), "FAST", 300.0, counterparty="Ali Veli"),
        cand(date(2026, 1, 6), "FAST", -300.0, counterparty="Ali Veli"),
    )
    resolve(cat, [out, inc])
    assert (out.kind, inc.kind) == ("kisiye_transfer", "gelir")


def test_foreign_currency_rows_valued_in_tl():
    rate_row = Transaction(
        date=date(2026, 3, 1),
        description="Döviz alış EUR:54.44",
        amount=-10.0,
        kind="transfer",
        account="teb-111222333",
    )
    income = Transaction(
        date=date(2026, 3, 3),
        description="ORNEK MUSTERI",
        amount=-1500.0,
        kind="gelir",
        account="garanti-9000001",
        original="1.500,00 EUR",
    )
    moved = Transaction(
        date=date(2026, 3, 4), description="Kendi hesabıma", amount=500.0, kind="transfer", account="garanti-9000001"
    )
    warnings: list[str] = []
    out = _to_tl([rate_row, income, moved], ACCOUNTS, _rates([rate_row]), warnings)
    assert income.amount == round(-1500.0 * 54.44, 2) and "× 54,44" in income.original
    assert moved not in out and not warnings  # EUR moved between own accounts changes nothing


def test_missing_rate_is_reported():
    income = Transaction(date=date(2026, 3, 3), description="X", amount=-10.0, kind="gelir", account="garanti-9000001")
    warnings: list[str] = []
    assert _to_tl([income], ACCOUNTS, {}, warnings) == [] and "kur bulunamadı" in warnings[0]


def test_a_receipt_resolves_like_a_list_row_unless_a_list_covers_its_day(cat):
    tl = Account(
        "garanti-1234567", "Garanti BBVA Vadesiz TL 1234567", "Garanti BBVA", "Vadesiz hesap", number="1234567"
    )
    eur = ACCOUNTS["garanti-9000001"]
    eur_list = ParseResult(
        "liste",
        accounts=[eur],
        statements=[
            Statement(
                "garanti-9000001",
                date(2026, 10, 31),
                "EUR",
                "l.xls",
                0.0,
                0.0,
                start=date(2026, 10, 1),
                checks_ok=1,
                checks_total=1,
            )
        ],
    )
    rent = ParseResult(
        "dekont",
        accounts=[tl],
        receipt_key="kira",
        transactions=[
            cand(
                date(2024, 1, 16),
                "Giden Havale → VELİ ÖRNEKSOY — 2024 OCAK",
                8400.0,
                "garanti-1234567",
                "VELİ ÖRNEKSOY",
            )
        ],
    )
    masked = Account(
        "garanti-****001", "Garanti BBVA Vadesiz EUR …001", "Garanti BBVA", "Döviz hesabı", "EUR", "****001"
    )
    salary = ParseResult(
        "dekont",
        accounts=[masked],
        receipt_key="maas",
        transactions=[
            cand(date(2026, 10, 15), "Gelen Transfer ← ÖRNEK FİRMA", -1000.0, "garanti-****001", "ÖRNEK FİRMA")
        ],
    )
    results = [
        (Document(f"{r.receipt_key or 'liste'}.pdf", "test", b"", r.receipt_key or "liste"), r, None)
        for r in (eur_list, rent, salary)
    ]
    ds = build(results, cat, {"ad_soyad": "ÖRNEK İSİM SOYADOĞLU"})
    # The rent receipt fills a month no list covers; the masked salary receipt belongs to the EUR account,
    # whose list covers its day without showing it: left out (and flagged, see test_receipts.py).
    assert [(t.account, t.kind, t.category, t.amount) for t in ds.transactions] == [
        ("garanti-1234567", "harcama", "Kira", 8400.0)
    ]
