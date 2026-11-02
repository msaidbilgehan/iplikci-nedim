"""Deciding what an account transfer is once every account is known."""

from datetime import date
from decimal import Decimal

import pytest

from iplikci.analysis import Own, _rates, _resolve_transfers, _to_tl, build
from iplikci.categorize import Categorizer
from iplikci.domain.codes import AccountType, CategoryReason, TransactionKind, TransferStep
from iplikci.domain.models import Account, ParseResult, Statement, Transaction
from iplikci.parsers.contract import Document

from conftest import PEOPLE_RULES

ACCOUNTS = {
    "teb-111222333": Account(
        "teb-111222333", "TEB Vadesiz TL 111222333", "TEB", AccountType.CURRENT, number="111222333"
    ),
    "vakifbank-0999000000123456": Account(
        "vakifbank-0999000000123456",
        "Vakıfbank Vadesiz TL",
        "Vakıfbank",
        AccountType.CURRENT,
        number="0999000000123456",
    ),
    "garanti-9000001": Account(
        "garanti-9000001",
        "Garanti BBVA Vadesiz EUR 9000001",
        "Garanti BBVA",
        AccountType.FX,
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
        date=d,
        description=desc,
        amount=amount,
        kind=TransactionKind.TRANSFER_CANDIDATE,
        account=account,
        counterparty=counterparty,
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


def test_a_masked_name_is_the_users_when_every_word_starts_as_shown():
    own = Own(["ÖRNEK İSİM SOYADOĞLU"], ACCOUNTS)
    assert own.is_self("ÖR**** İS*** SO******") and own.is_self("Ör**** İs*** So*******")
    assert not own.is_self("ÖR**** SO******")  # the bank masks the whole name: two words are somebody else's
    assert not own.is_self("Ör**** Ay** So******")  # another middle name
    assert not own.is_self("Ö***** İ**** S*******")  # a letter a word: a relative's name could look the same


def test_transfer_to_self_by_name(cat):
    (t,) = resolve(cat, [cand(date(2026, 1, 5), "FAST", Decimal(1000), counterparty="ÖRNEK İSİM SOYADOĞLU")])
    assert t.kind == TransactionKind.OWN_TRANSFER and t.reason.transfer is TransferStep.OWN_NAME


def test_bank_only_row_inherits_the_named_payment(cat):
    # Vakıfbank names the landlord; TEB prints only the receiver's bank for the same rent.
    named = cand(
        date(2026, 1, 31),
        "FAST Anlık Ödeme: k (31/01/2026 tarihli 1 sorgu no'lu ÖRNEK İSİM SOYADOĞLU "
        "hesabından Yapı ve Kredi Bankası A.Ş. Veli Örneksoy hesabına giden FAST ödemesi)",
        Decimal(15000),
        account="vakifbank-0999000000123456",
        counterparty="Veli Örneksoy",
    )
    bank_only = cand(date(2026, 3, 2), "YAPI VE KREDI BANKASI A.Ş.", Decimal(15000))
    resolve(cat, [named, bank_only])
    assert (named.kind, named.category) == (TransactionKind.PURCHASE, "Kira")
    assert (bank_only.kind, bank_only.category) == (TransactionKind.PURCHASE, "Kira")
    assert bank_only.description.endswith("(→ Veli Örneksoy)")
    assert (named.reason.transfer, named.reason.category) == (TransferStep.RULE, CategoryReason.TRANSFER_RULE)
    assert (bank_only.reason.transfer, bank_only.reason.rule) == (TransferStep.LIKE_NAMED, named.reason.rule)


def test_opposite_rows_on_two_own_accounts_pair_up(cat):
    out = cand(date(2026, 2, 1), "Giden FAST", Decimal(5000))
    inc = cand(date(2026, 2, 2), "Gelen FAST", Decimal(-5000), account="vakifbank-0999000000123456")
    far = cand(date(2026, 2, 20), "Gelen FAST", Decimal(-5000), account="vakifbank-0999000000123456")
    out.fingerprint, inc.fingerprint = "a" * 16, "b" * 16
    resolve(cat, [out, inc, far])
    assert (out.kind, inc.kind) == (TransactionKind.OWN_TRANSFER, TransactionKind.OWN_TRANSFER)
    assert (out.reason.transfer, out.reason.pair, inc.reason.pair) == (TransferStep.PAIRED, "b" * 16, "a" * 16)
    assert far.kind == TransactionKind.INCOME  # nothing left to pair with: money from someone else
    assert far.reason.transfer is TransferStep.INCOME


def test_bank_only_payment_outside_coverage_goes_to_own_account(cat):
    covered = Statement(
        account="vakifbank-0999000000123456",
        cut_date=date(2026, 1, 31),
        currency="TRY",
        source="",
        previous=None,
        total=None,
        start=date(2026, 1, 1),
    )
    t = cand(date(2025, 12, 15), "TÜRKİYE VAKIFLAR BANKASI T.A.O.", Decimal(3000))
    resolve(cat, [t], [covered])
    assert t.kind == TransactionKind.OWN_TRANSFER and t.reason.transfer is TransferStep.UNCOVERED_BANK


def test_unknown_people(cat):
    out, inc = (
        cand(date(2026, 1, 5), "FAST", Decimal(300), counterparty="Ali Veli"),
        cand(date(2026, 1, 6), "FAST", Decimal(-300), counterparty="Ali Veli"),
    )
    resolve(cat, [out, inc])
    assert (out.kind, inc.kind) == (TransactionKind.P2P_TRANSFER, TransactionKind.INCOME)
    assert (out.reason.transfer, inc.reason.transfer) == (TransferStep.PERSON, TransferStep.INCOME)


def test_foreign_currency_rows_valued_in_tl():
    rate_row = Transaction(
        date=date(2026, 3, 1),
        description="Döviz alış EUR:54.44",
        amount=Decimal(-10),
        kind=TransactionKind.OWN_TRANSFER,
        account="teb-111222333",
    )
    income = Transaction(
        date=date(2026, 3, 3),
        description="ORNEK MUSTERI",
        amount=Decimal(-1500),
        kind=TransactionKind.INCOME,
        account="garanti-9000001",
        original="1.500,00 EUR",
    )
    moved = Transaction(
        date=date(2026, 3, 4),
        description="Kendi hesabıma",
        amount=Decimal(500),
        kind=TransactionKind.OWN_TRANSFER,
        account="garanti-9000001",
    )
    warnings: list[str] = []
    out = _to_tl([rate_row, income, moved], ACCOUNTS, _rates([rate_row]), warnings)
    assert income.amount == round(Decimal(-1500) * Decimal("54.44"), 2) and "× 54,44" in income.original
    assert (income.reason.rate, income.reason.rate_day) == (Decimal("54.44"), date(2026, 3, 1))
    assert moved not in out and not warnings  # EUR moved between own accounts changes nothing


def test_missing_rate_is_reported():
    income = Transaction(
        date=date(2026, 3, 3),
        description="X",
        amount=Decimal(-10),
        kind=TransactionKind.INCOME,
        account="garanti-9000001",
    )
    warnings: list[str] = []
    assert _to_tl([income], ACCOUNTS, {}, warnings) == [] and "kur bulunamadı" in warnings[0]


def test_a_receipt_resolves_like_a_list_row_unless_a_list_covers_its_day(cat):
    tl = Account(
        "garanti-1234567", "Garanti BBVA Vadesiz TL 1234567", "Garanti BBVA", AccountType.CURRENT, number="1234567"
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
                Decimal(0),
                Decimal(0),
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
                Decimal(8400),
                "garanti-1234567",
                "VELİ ÖRNEKSOY",
            )
        ],
    )
    masked = Account(
        "garanti-****001", "Garanti BBVA Vadesiz EUR …001", "Garanti BBVA", AccountType.FX, "EUR", "****001"
    )
    salary = ParseResult(
        "dekont",
        accounts=[masked],
        receipt_key="maas",
        transactions=[
            cand(date(2026, 10, 15), "Gelen Transfer ← ÖRNEK FİRMA", Decimal(-1000), "garanti-****001", "ÖRNEK FİRMA")
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
        ("garanti-1234567", TransactionKind.PURCHASE, "Kira", Decimal(8400))
    ]
