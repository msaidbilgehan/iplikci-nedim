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
    "garanti-1234567": Account(
        "garanti-1234567", "Garanti BBVA Vadesiz TL 1234567", "Garanti BBVA", AccountType.CURRENT, number="1234567"
    ),
    # A bank the table of printed bank names does not know: matched by the words left of both names.
    "ykb-5550001": Account("ykb-5550001", "Yapı Kredi Vadesiz TL 5550001", "Yapı Kredi", AccountType.CURRENT),
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


def test_two_sides_that_name_the_user_pair_with_each_other(cat):
    me = "ÖRNEK İSİM SOYADOĞLU"
    out = cand(date(2026, 2, 1), "Giden FAST", Decimal(5000), counterparty=me)
    inc = cand(date(2026, 2, 2), "Gelen FAST", Decimal(-5000), account="vakifbank-0999000000123456", counterparty=me)
    later = cand(date(2026, 2, 5), "Gelen FAST", Decimal(-5000), account="vakifbank-0999000000123456", counterparty=me)
    out.fingerprint, inc.fingerprint, later.fingerprint = "a" * 16, "b" * 16, "c" * 16
    resolve(cat, [out, inc, later])
    assert (out.reason.pair, inc.reason.pair) == ("b" * 16, "a" * 16)  # the closest in time
    assert (out.reason.transfer, inc.reason.transfer) == (TransferStep.OWN_NAME, TransferStep.OWN_NAME)
    assert later.kind == TransactionKind.OWN_TRANSFER and later.reason.pair == ""  # its other side is not shown


def test_a_strangers_payment_of_the_same_amount_does_not_take_a_side_that_names_the_user(cat):
    me = "ÖRNEK İSİM SOYADOĞLU"
    out = cand(date(2026, 2, 1), "Giden FAST", Decimal(5000), counterparty=me)
    inc = cand(date(2026, 2, 2), "Gelen FAST", Decimal(-5000), account="vakifbank-0999000000123456", counterparty=me)
    gift = cand(date(2026, 2, 1), "Gelen FAST", Decimal(-5000), account="vakifbank-0999000000123456")
    out.fingerprint, inc.fingerprint, gift.fingerprint = "a" * 16, "b" * 16, "c" * 16
    resolve(cat, [gift, out, inc])
    assert (out.reason.pair, inc.reason.pair) == ("b" * 16, "a" * 16)
    assert gift.kind == TransactionKind.INCOME and gift.reason.pair == ""


def test_a_payment_that_names_someone_else_never_takes_the_place_of_an_own_transfers_other_side(cat):
    # The user's FAST to their TEB account arrived at a TEB account no document shows; the day before, someone else
    # paid the same amount into the TEB account a document does show. That payment is theirs, not the FAST's arrival.
    me = "ÖRNEK İSİM SOYADOĞLU"
    sent = cand(
        date(2026, 11, 3),
        "FAST Anlık Ödeme: ödeme (03/11/2026 tarihli 1 sorgu no'lu ÖRNEK İSİM SOYADOĞLU hesabından Türk Ekonomi Bankası "
        "A.Ş. ÖRNEK İSİM SOYADOĞLU hesabına giden FAST ödemesi)",
        Decimal(750),
        account="vakifbank-0999000000123456",
        counterparty=me,
    )
    someone = "Deniz Yılmazer"
    paid_in = cand(date(2026, 11, 2), f"{someone} den gelen havale tutarı", Decimal(-750), counterparty=someone)
    sent_out = cand(date(2026, 11, 2), "Cem Örnektepe'ye giden havale", Decimal(750), counterparty="Cem Örnektepe")
    came_in = cand(date(2026, 11, 2), "Gelen FAST", Decimal(-750), account="garanti-1234567")
    for row, mark in zip((sent, paid_in, sent_out, came_in), "abcd", strict=True):
        row.fingerprint = mark * 16
    resolve(cat, [sent, paid_in, sent_out, came_in])
    assert (sent.kind, sent.reason.pair) == (TransactionKind.OWN_TRANSFER, "")  # its other side is in no document
    assert (paid_in.kind, paid_in.reason.transfer, paid_in.reason.pair) == (
        TransactionKind.INCOME,
        TransferStep.INCOME,
        "",
    )
    # Neither pairs with an open row that names nobody either: sent to a person, and money in from someone.
    assert (sent_out.kind, sent_out.reason.transfer, sent_out.reason.pair) == (
        TransactionKind.P2P_TRANSFER,
        TransferStep.PERSON,
        "",
    )
    assert (came_in.kind, came_in.reason.transfer, came_in.reason.pair) == (
        TransactionKind.INCOME,
        TransferStep.INCOME,
        "",
    )


def test_a_bank_only_payment_whose_other_side_names_the_user_is_no_payment_like_a_named_one(cat):
    # The landlord is paid by name at Yapı Kredi; months before, the same amount went to the user's own account there.
    named = cand(
        date(2026, 5, 2),
        "FAST Anlık Ödeme: k (02/05/2026 tarihli 1 sorgu no'lu ÖRNEK İSİM SOYADOĞLU "
        "hesabından Yapı ve Kredi Bankası A.Ş. Veli Örneksoy hesabına giden FAST ödemesi)",
        Decimal(15000),
        account="vakifbank-0999000000123456",
        counterparty="Veli Örneksoy",
    )
    bank_only = cand(date(2026, 1, 28), "YAPI VE KREDI BANKASI A.Ş.", Decimal(15000))
    arrived = cand(
        date(2026, 1, 28),
        "Gelen transfer",
        Decimal(-15000),
        account="ykb-5550001",
        counterparty="ÖRNEK İSİM SOYADOĞLU",
    )
    bank_only.fingerprint, arrived.fingerprint = "a" * 16, "b" * 16
    resolve(cat, [named, bank_only, arrived])
    assert (bank_only.kind, bank_only.reason.transfer, bank_only.reason.pair) == (
        TransactionKind.OWN_TRANSFER,
        TransferStep.PAIRED,
        "b" * 16,
    )
    assert bank_only.description == "YAPI VE KREDI BANKASI A.Ş."  # not "(→ Veli Örneksoy)"
    assert named.category == "Kira"


def test_of_two_bank_only_payments_of_one_amount_the_one_to_the_receiving_accounts_bank_is_the_own_transfer(cat):
    # TEB prints only the receivers' banks. The same day 2.500 went to Ziraat, where the user keeps no account, and
    # 2.500 to Garanti, where the user's account shows it coming in: the first is someone else's, whatever its order.
    to_ziraat = cand(date(2026, 3, 9), "TÜRKIYE CUMHURIYETI ZIRAAT BANKASI A.Ş.", Decimal(2500))
    to_garanti = cand(date(2026, 3, 9), "TÜRKIYE GARANTI BANKASI A.Ş.", Decimal(2500))
    arrived = cand(
        date(2026, 3, 9),
        "ÖRNEK İSİM SOYADOĞLU-kart borcu-FAST-123",
        Decimal(-2500),
        account="garanti-1234567",
        counterparty="ÖRNEK İSİM SOYADOĞLU",
    )
    to_garanti.fingerprint, arrived.fingerprint = "a" * 16, "b" * 16
    resolve(cat, [to_ziraat, to_garanti, arrived])
    assert (to_garanti.kind, to_garanti.reason.pair, arrived.reason.pair) == (
        TransactionKind.OWN_TRANSFER,
        "b" * 16,
        "a" * 16,
    )
    assert (to_ziraat.kind, to_ziraat.reason.transfer) == (TransactionKind.P2P_TRANSFER, TransferStep.PERSON)


def test_a_named_transfer_pairs_only_at_the_bank_it_names(cat):
    # A FAST to the user's own Garanti account and one of the same amount reaching their Vakıfbank account the same
    # day from elsewhere: each side names the user, but the Garanti one cannot have arrived at Vakıfbank.
    me = "ÖRNEK İSİM SOYADOĞLU"
    out = cand(
        date(2026, 4, 14),
        "FAST Anlık Ödeme: k (14/04/2026 tarihli 1 sorgu no'lu ÖRNEK İSİM SOYADOĞLU hesabından Türkiye Garanti "
        "Bankası A.Ş. ÖRNEK İSİM SOYADOĞLU hesabına giden FAST ödemesi)",
        Decimal(1000),
        account="vakifbank-0999000000123456",
        counterparty=me,
    )
    elsewhere = cand(date(2026, 4, 14), "Gelen havale", Decimal(-1000), account="teb-111222333", counterparty=me)
    arrived = cand(date(2026, 4, 15), "Gelen FAST", Decimal(-1000), account="garanti-1234567", counterparty=me)
    out.fingerprint, elsewhere.fingerprint, arrived.fingerprint = "a" * 16, "b" * 16, "c" * 16
    resolve(cat, [out, elsewhere, arrived])
    assert (out.reason.pair, arrived.reason.pair, elsewhere.reason.pair) == ("c" * 16, "a" * 16, "")


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
