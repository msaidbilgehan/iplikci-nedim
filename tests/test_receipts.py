"""Receipts before and after their statement: provisional until the statement comes, then confirmed by
its row or flagged when it does not show them; balances and card debt move with the provisional ones."""

from datetime import date
from decimal import Decimal

import pytest

from iplikci.analysis import CONFIRMED, NO_STATEMENT, NOT_ON_STATEMENT, PROVISIONAL, build
from iplikci.categorize import Categorizer
from iplikci.domain.codes import AccountType, TransactionKind
from iplikci.domain.models import Account, ParseResult, Statement, Transaction
from iplikci.insights import interpret
from iplikci.parsers.contract import Document

from conftest import PEOPLE_RULES

HOLDER = "ÖRNEK İSİM SOYADOĞLU"
CHECKING = Account(
    "garanti-1234567", "Garanti BBVA Vadesiz TL 1234567", "Garanti BBVA", AccountType.CURRENT, number="1234567"
)
OVERDRAFT = Account("qnb-11112222", "QNB Ek Hesap 11112222", "QNB", AccountType.OVERDRAFT, number="11112222")
CARD = Account("qnb-4321", "QNB Mastercard •4321", "QNB", AccountType.CREDIT_CARD, number="4321")


@pytest.fixture(scope="module")
def cat(tmp_path_factory):
    rules = tmp_path_factory.mktemp("kurallar") / "kategoriler.yaml"
    rules.write_text(PEOPLE_RULES, encoding="utf-8")
    return Categorizer(rules)


def row(
    d: date,
    desc: str,
    amount: Decimal,
    account: Account,
    kind: TransactionKind = TransactionKind.TRANSFER_CANDIDATE,
    who: str = "",
) -> Transaction:
    return Transaction(d, desc, amount, kind, account.id, counterparty=who, source="belge")


def listing(
    account: Account, start: date, end: date, *rows: Transaction, closing: Decimal = Decimal(10000)
) -> ParseResult:
    """An account movement list that checks out, closing at the given balance."""
    opening = round(closing + sum(r.amount for r in rows), 2)
    s = Statement(
        account.id,
        end,
        "TRY",
        "liste.xls",
        opening,
        closing,
        list(rows),
        start=start,
        checks_ok=1,
        checks_total=1,
        balances={f"{end:%Y-%m}": closing},
    )
    return ParseResult("liste", accounts=[account], statements=[s])


def card_statement(cut: date, *rows: Transaction, total: Decimal = Decimal(4000)) -> ParseResult:
    previous = round(total - sum(r.amount for r in rows), 2)
    s = Statement(CARD.id, cut, "TRY", "ekstre.pdf", previous, total, list(rows))
    return ParseResult("ekstre", accounts=[CARD], statements=[s])


def receipt(key: str, account: Account, *rows: Transaction) -> ParseResult:
    return ParseResult("dekont", accounts=[account], transactions=list(rows), receipt_key=key, holder=HOLDER)


def analyse(cat, *results: ParseResult):
    docs = [(Document(f"{i}.pdf", "test", b"", f"sha{i}"), r, None) for i, r in enumerate(results)]
    return build(docs, cat, {"ad_soyad": HOLDER})


def statuses(ds) -> list[tuple[str, str]]:
    return [(line.txn.description, line.status) for line in ds.receipts]


# --- what the statements say about a receipt ---------------------------------------------------


def test_a_receipt_after_the_newest_statement_counts_now_as_provisional(cat):
    ds = analyse(
        cat,
        listing(CHECKING, date(2026, 10, 1), date(2026, 10, 31)),
        receipt(
            "r1",
            CHECKING,
            row(date(2026, 11, 3), "Giden FAST → VELİ ÖRNEKSOY", Decimal(15000), CHECKING, who="VELİ ÖRNEKSOY"),
            row(date(2026, 11, 3), "FAST ücreti", Decimal(5), CHECKING, kind=TransactionKind.INTEREST_FEE),
        ),
    )
    assert statuses(ds) == [("Giden FAST → VELİ ÖRNEKSOY", PROVISIONAL), ("FAST ücreti", PROVISIONAL)]
    by_kind = {t.kind: t for t in ds.transactions}
    rent, fee = by_kind[TransactionKind.PURCHASE], by_kind[TransactionKind.INTEREST_FEE]
    assert (rent.category, rent.provisional) == ("Kira", True)  # resolved like a list row
    assert fee.provisional


def test_the_statements_row_takes_the_place_of_a_confirmed_receipt(cat):
    # The list books the evening transfer the next day, and splits the fee into the fee and its tax.
    booked = row(date(2026, 11, 4), "FAST VELİ ÖRNEKSOY KIRA", Decimal(15000), CHECKING, who="VELİ ÖRNEKSOY")
    ds = analyse(
        cat,
        listing(
            CHECKING,
            date(2026, 11, 1),
            date(2026, 11, 30),
            booked,
            row(date(2026, 11, 4), "FAST ÜCRETİ", Decimal("4.76"), CHECKING, kind=TransactionKind.INTEREST_FEE),
            row(date(2026, 11, 4), "BSMV", Decimal("0.24"), CHECKING, kind=TransactionKind.INTEREST_FEE),
        ),
        receipt(
            "r1",
            CHECKING,
            row(date(2026, 11, 3), "Giden FAST → VELİ ÖRNEKSOY", Decimal(15000), CHECKING),
            row(date(2026, 11, 3), "FAST ücreti", Decimal(5), CHECKING, kind=TransactionKind.INTEREST_FEE),
        ),
    )
    assert statuses(ds) == [("Giden FAST → VELİ ÖRNEKSOY", CONFIRMED), ("FAST ücreti", CONFIRMED)]
    assert ds.receipts[0].match is booked
    assert [t.description for t in ds.transactions] == ["BSMV", "FAST VELİ ÖRNEKSOY KIRA", "FAST ÜCRETİ"]
    assert not any(t.provisional for t in ds.transactions)


def test_a_receipt_the_statement_does_not_show_is_left_out_and_flagged(cat):
    ds = analyse(
        cat,
        listing(CHECKING, date(2026, 11, 1), date(2026, 11, 30)),
        receipt("r1", CHECKING, row(date(2026, 11, 10), "Giden FAST → ALİ VELİ", Decimal(300), CHECKING)),
    )
    assert statuses(ds) == [("Giden FAST → ALİ VELİ", NOT_ON_STATEMENT)]
    assert ds.transactions == []
    findings = {f.title: f for f in interpret(ds).findings}
    assert "300" in findings["Ekstrede görünmeyen dekontlar"].text


def test_a_receipt_on_the_lists_last_days_waits_for_the_next_one(cat):
    # Made late on the last day the list covers: the bank may book it on the next day.
    ds = analyse(
        cat,
        listing(CHECKING, date(2026, 11, 1), date(2026, 11, 30)),
        receipt("r1", CHECKING, row(date(2026, 11, 30), "Giden FAST → ALİ VELİ", Decimal(300), CHECKING)),
    )
    assert statuses(ds) == [("Giden FAST → ALİ VELİ", PROVISIONAL)]


def test_a_receipt_from_before_the_accounts_documents_counts_as_it_is(cat):
    ds = analyse(
        cat,
        listing(CHECKING, date(2026, 10, 1), date(2026, 10, 31)),
        receipt(
            "r1",
            CHECKING,
            row(date(2024, 1, 16), "Giden Havale → VELİ ÖRNEKSOY", Decimal(8400), CHECKING, who="VELİ ÖRNEKSOY"),
        ),
    )
    assert statuses(ds) == [("Giden Havale → VELİ ÖRNEKSOY", NO_STATEMENT)]
    [rent] = ds.transactions
    assert (rent.category, rent.provisional) == ("Kira", False)


def test_an_own_transfer_receipt_is_told_apart_by_the_senders_name(cat):
    ds = analyse(
        cat,
        listing(OVERDRAFT, date(2026, 10, 1), date(2026, 10, 31), closing=Decimal(-2000)),
        receipt(
            "r1",
            OVERDRAFT,
            row(date(2026, 11, 2), "Gelen transfer ← Garanti BBVA", Decimal(-12750), OVERDRAFT, who=HOLDER),
        ),
        receipt(
            "r2",
            OVERDRAFT,
            row(date(2026, 11, 5), "Gelen transfer ← TEB", Decimal(-750), OVERDRAFT, who="AYŞE SOYADOĞLU"),
        ),
    )
    assert [(t.kind, t.provisional) for t in ds.transactions] == [
        (TransactionKind.OWN_TRANSFER, True),
        (TransactionKind.INCOME, True),
    ]


# --- card payments -----------------------------------------------------------------------------------


def test_the_card_statement_confirms_a_card_payment_receipt(cat):
    credit = row(date(2026, 10, 2), "ÖDEME - TEŞEKKÜRLER", Decimal(-1500), CARD, kind=TransactionKind.CARD_PAYMENT)
    ds = analyse(
        cat,
        card_statement(date(2026, 10, 18), credit),
        receipt(
            "r1",
            CARD,
            row(
                date(2026, 10, 1),
                "QNB Mastercard •4321 borç ödemesi",
                Decimal(1500),
                CARD,
                kind=TransactionKind.CARD_PAYMENT_NO_STATEMENT,
            ),
        ),
    )
    assert statuses(ds) == [("QNB Mastercard •4321 borç ödemesi", CONFIRMED)]
    assert ds.receipts[0].match is credit


def test_a_payment_after_the_cut_lowers_the_card_debt_until_the_next_statement(cat):
    ds = analyse(
        cat,
        card_statement(date(2026, 10, 18), total=Decimal(4000)),
        receipt(
            "r1",
            CARD,
            row(
                date(2026, 10, 25),
                "QNB Mastercard •4321 borç ödemesi",
                Decimal(1500),
                CARD,
                kind=TransactionKind.CARD_PAYMENT_NO_STATEMENT,
            ),
        ),
    )
    [payment] = ds.transactions
    # The card's statements show its purchases: the payment is not spending on an unseen card.
    assert (payment.kind, payment.provisional) == (TransactionKind.CARD_PAYMENT, True)
    [card] = interpret(ds).holdings
    assert card.amount == Decimal(-2500) and "sonra ₺1.500 ödendi" in card.note


def test_the_paying_accounts_list_confirms_a_card_payment_receipt(cat):
    paid = row(
        date(2026, 10, 25),
        "123456******4321 NOLU KART ODEMESI",
        Decimal(1500),
        OVERDRAFT,
        kind=TransactionKind.CARD_PAYMENT,
    )
    ds = analyse(
        cat,
        card_statement(date(2026, 10, 18)),
        listing(OVERDRAFT, date(2026, 10, 1), date(2026, 10, 31), paid),
        receipt(
            "r1",
            CARD,
            row(
                date(2026, 10, 25),
                "QNB Mastercard •4321 borç ödemesi",
                Decimal(1500),
                CARD,
                kind=TransactionKind.CARD_PAYMENT_NO_STATEMENT,
            ),
        ),
    )
    assert statuses(ds) == [("QNB Mastercard •4321 borç ödemesi", CONFIRMED)]
    card = next(h for h in interpret(ds).holdings if h.kind == "kart")
    assert card.amount == Decimal(-2500)  # counted once, from the list


def test_a_payment_before_the_cards_statements_stays_a_payment_to_an_unseen_card(cat):
    ds = analyse(
        cat,
        card_statement(date(2026, 10, 18)),
        receipt(
            "r1",
            CARD,
            row(
                date(2024, 6, 7),
                "QNB Mastercard •4321 borç ödemesi",
                Decimal(900),
                CARD,
                kind=TransactionKind.CARD_PAYMENT_NO_STATEMENT,
            ),
        ),
    )
    assert statuses(ds) == [("QNB Mastercard •4321 borç ödemesi", NO_STATEMENT)]
    assert ds.transactions[0].kind == TransactionKind.CARD_PAYMENT_NO_STATEMENT


# --- balances and the interpretation -------------------------------------------------------------


def test_provisional_receipts_move_the_balance_their_list_closed_with(cat):
    ds = analyse(
        cat,
        listing(CHECKING, date(2026, 10, 1), date(2026, 10, 31), closing=Decimal(10000)),
        receipt(
            "r1",
            CHECKING,
            row(date(2026, 11, 3), "Giden FAST → ALİ VELİ", Decimal(2500), CHECKING),
            row(date(2026, 11, 3), "FAST ücreti", Decimal(5), CHECKING, kind=TransactionKind.INTEREST_FEE),
        ),
    )
    ins = interpret(ds)
    [cash] = ins.holdings
    assert (cash.amount, cash.as_of) == (Decimal(7495), date(2026, 11, 3))
    assert "31.10.2026 dökümünde ₺10.000; sonraki 2 dekontla −₺2.505 (geçici" in cash.note
    finding = next(f for f in ins.findings if f.title == "Ekstre gelmeden işlenen dekontlar")
    assert "2 işlem" in finding.text and "kişilere giden ₺2.500" in finding.text
    assert finding.filter == {"provisional": True}


# --- a bank's notice of the same movement ------------------------------------------------------


def notice(key: str, account: Account, *rows: Transaction) -> ParseResult:
    """A bank's notice: rows like a receipt's, read by a reader of notices."""
    return ParseResult("vakifbank.notice.transfer", accounts=[account], transactions=list(rows), receipt_key=key)


def test_a_notice_and_a_receipt_of_one_transfer_count_once_and_the_receipt_keeps_the_balance(cat):
    sent = row(date(2026, 3, 2), "Giden Havale → VELİ ÖRNEKSOY", Decimal(15000), CHECKING, who="VELİ ÖRNEKSOY")
    told = row(date(2026, 3, 2), "Giden FAST → VE** ÖR*****", Decimal(15000), CHECKING, who="VE** ÖR*****")
    told.balance = Decimal("8500.00")
    ds = analyse(cat, receipt("r1", CHECKING, sent), notice("n1", CHECKING, told))
    assert statuses(ds) == [("Giden Havale → VELİ ÖRNEKSOY", NO_STATEMENT)]
    assert [t.amount for t in ds.transactions] == [Decimal(15000)]
    assert ds.receipts[0].txn.balance == Decimal("8500.00")


def test_two_equal_transfers_of_a_day_stay_two_when_only_one_has_a_receipt(cat):
    day = date(2026, 3, 2)
    sent = row(day, "Giden Havale → VELİ ÖRNEKSOY", Decimal(1000), CHECKING, who="VELİ ÖRNEKSOY")
    first = row(day, "Giden FAST → VE** ÖR*****", Decimal(1000), CHECKING, who="VE** ÖR*****")
    second = row(day, "Giden FAST → AY** DE*****", Decimal(1000), CHECKING, who="AY** DE*****")  # someone else
    third = row(day, "Giden FAST → VE** ÖR*****", Decimal(1000), CHECKING, who="VE** ÖR*****")  # Veli again
    ds = analyse(
        cat, receipt("r1", CHECKING, sent), notice("n1", CHECKING, first, second), notice("n2", CHECKING, third)
    )
    assert sorted(description for description, _ in statuses(ds)) == [
        "Giden FAST → AY** DE*****",
        "Giden FAST → VE** ÖR*****",  # the receipt stands for one of Veli's two notices only
        "Giden Havale → VELİ ÖRNEKSOY",
    ]


UNNAMED = Account("qnb-****", "QNB Vadesiz TL", "QNB", AccountType.CURRENT, number="****")  # a FAST notice's


def test_a_notice_that_names_no_account_goes_to_the_banks_one_bank_account_never_its_card(cat):
    told = row(date(2026, 3, 2), "Giden FAST → VELİ ÖRNEKSOY", Decimal(1000), UNNAMED, who="VELİ ÖRNEKSOY")
    paid = row(date(2026, 2, 20), "MIGROS", Decimal(250), CARD, kind=TransactionKind.PURCHASE)
    ds = analyse(cat, receipt("r1", OVERDRAFT), card_statement(date(2026, 3, 1), paid), notice("n1", UNNAMED, told))
    assert [t.account for t in ds.transactions if t.description.startswith("Giden FAST")] == [OVERDRAFT.id]
    assert "qnb-****" not in ds.accounts
    second = Account("qnb-33334444", "QNB Vadesiz TL 33334444", "QNB", AccountType.CURRENT, number="33334444")
    ds = analyse(cat, receipt("r1", OVERDRAFT), receipt("r2", second), notice("n1", UNNAMED, told))
    assert ds.accounts["qnb-****"].label == "QNB Vadesiz TL"  # two bank accounts: which one is not guessed


def test_a_notice_gives_way_to_what_a_receipt_says_of_the_account(cat):
    named = Account("qnb-11112222", "QNB Vadesiz TL 11112222", "QNB", AccountType.CURRENT, number="11112222")
    told = row(date(2026, 3, 2), "Giden Transfer → VELİ ÖRNEKSOY", Decimal(1000), named, who="VELİ ÖRNEKSOY")
    ds = analyse(cat, notice("n1", named, told), receipt("r1", OVERDRAFT))
    assert (ds.accounts[OVERDRAFT.id].type, ds.accounts[OVERDRAFT.id].label) == (AccountType.OVERDRAFT, OVERDRAFT.label)
