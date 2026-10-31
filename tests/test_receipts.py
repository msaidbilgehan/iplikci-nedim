"""Receipts before and after their statement: provisional until the statement comes, then confirmed by
its row or flagged when it does not show them; balances and card debt move with the provisional ones."""

from datetime import date

import pytest

from iplikci.analysis import CONFIRMED, NO_STATEMENT, NOT_ON_STATEMENT, PROVISIONAL, build
from iplikci.categorize import Categorizer
from iplikci.insights import interpret
from iplikci.models import Account, ParseResult, Statement, Transaction
from iplikci.parsers.hesap import CANDIDATE
from iplikci.sources import Document

from conftest import PEOPLE_RULES

HOLDER = "ÖRNEK İSİM SOYADOĞLU"
CHECKING = Account("garanti-1234567", "Garanti BBVA Vadesiz TL 1234567", "Garanti BBVA", "Vadesiz hesap",
                   number="1234567")
OVERDRAFT = Account("qnb-11112222", "QNB Ek Hesap 11112222", "QNB", "Ek hesap (KMH)", number="11112222")
CARD = Account("qnb-4321", "QNB Mastercard •4321", "QNB", "Kredi kartı", number="4321")


@pytest.fixture(scope="module")
def cat(tmp_path_factory):
    rules = tmp_path_factory.mktemp("kurallar") / "kategoriler.yaml"
    rules.write_text(PEOPLE_RULES, encoding="utf-8")
    return Categorizer(rules)


def row(d: date, desc: str, amount: float, account: Account, kind: str = CANDIDATE, who: str = "") -> Transaction:
    return Transaction(d, desc, amount, kind, account.id, counterparty=who, source="belge")


def listing(account: Account, start: date, end: date, *rows: Transaction, closing: float = 10000.0) -> ParseResult:
    """An account movement list that checks out, closing at the given balance."""
    opening = round(closing + sum(r.amount for r in rows), 2)
    s = Statement(account.id, end, "TL", "liste.xls", opening, closing, list(rows), start=start, checks_ok=1,
                  checks_total=1, balances={f"{end:%Y-%m}": closing})
    return ParseResult("liste", accounts=[account], statements=[s])


def card_statement(cut: date, *rows: Transaction, total: float = 4000.0) -> ParseResult:
    previous = round(total - sum(r.amount for r in rows), 2)
    s = Statement(CARD.id, cut, "TL", "ekstre.pdf", previous, total, list(rows))
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
    ds = analyse(cat,
                 listing(CHECKING, date(2026, 10, 1), date(2026, 10, 31)),
                 receipt("r1", CHECKING, row(date(2026, 11, 3), "Giden FAST → VELİ ÖRNEKSOY", 15000.0, CHECKING,
                                             who="VELİ ÖRNEKSOY"),
                         row(date(2026, 11, 3), "FAST ücreti", 5.0, CHECKING, kind="faiz_ucret")))
    assert statuses(ds) == [("Giden FAST → VELİ ÖRNEKSOY", PROVISIONAL), ("FAST ücreti", PROVISIONAL)]
    by_kind = {t.kind: t for t in ds.transactions}
    rent, fee = by_kind["harcama"], by_kind["faiz_ucret"]
    assert (rent.category, rent.provisional) == ("Kira", True)  # resolved like a list row
    assert fee.provisional


def test_the_statements_row_takes_the_place_of_a_confirmed_receipt(cat):
    # The list books the evening transfer the next day, and splits the fee into the fee and its tax.
    booked = row(date(2026, 11, 4), "FAST VELİ ÖRNEKSOY KIRA", 15000.0, CHECKING, who="VELİ ÖRNEKSOY")
    ds = analyse(cat,
                 listing(CHECKING, date(2026, 11, 1), date(2026, 11, 30), booked,
                         row(date(2026, 11, 4), "FAST ÜCRETİ", 4.76, CHECKING, kind="faiz_ucret"),
                         row(date(2026, 11, 4), "BSMV", 0.24, CHECKING, kind="faiz_ucret")),
                 receipt("r1", CHECKING, row(date(2026, 11, 3), "Giden FAST → VELİ ÖRNEKSOY", 15000.0, CHECKING),
                         row(date(2026, 11, 3), "FAST ücreti", 5.0, CHECKING, kind="faiz_ucret")))
    assert statuses(ds) == [("Giden FAST → VELİ ÖRNEKSOY", CONFIRMED), ("FAST ücreti", CONFIRMED)]
    assert ds.receipts[0].match is booked
    assert [t.description for t in ds.transactions] == ["BSMV", "FAST VELİ ÖRNEKSOY KIRA", "FAST ÜCRETİ"]
    assert not any(t.provisional for t in ds.transactions)


def test_a_receipt_the_statement_does_not_show_is_left_out_and_flagged(cat):
    ds = analyse(cat,
                 listing(CHECKING, date(2026, 11, 1), date(2026, 11, 30)),
                 receipt("r1", CHECKING, row(date(2026, 11, 10), "Giden FAST → ALİ VELİ", 300.0, CHECKING)))
    assert statuses(ds) == [("Giden FAST → ALİ VELİ", NOT_ON_STATEMENT)]
    assert ds.transactions == []
    findings = {f.title: f for f in interpret(ds).findings}
    assert "300" in findings["Ekstrede görünmeyen dekontlar"].text


def test_a_receipt_on_the_lists_last_days_waits_for_the_next_one(cat):
    # Made late on the last day the list covers: the bank may book it on the next day.
    ds = analyse(cat,
                 listing(CHECKING, date(2026, 11, 1), date(2026, 11, 30)),
                 receipt("r1", CHECKING, row(date(2026, 11, 30), "Giden FAST → ALİ VELİ", 300.0, CHECKING)))
    assert statuses(ds) == [("Giden FAST → ALİ VELİ", PROVISIONAL)]


def test_a_receipt_from_before_the_accounts_documents_counts_as_it_is(cat):
    ds = analyse(cat,
                 listing(CHECKING, date(2026, 10, 1), date(2026, 10, 31)),
                 receipt("r1", CHECKING, row(date(2024, 1, 16), "Giden Havale → VELİ ÖRNEKSOY", 8400.0, CHECKING,
                                             who="VELİ ÖRNEKSOY")))
    assert statuses(ds) == [("Giden Havale → VELİ ÖRNEKSOY", NO_STATEMENT)]
    [rent] = ds.transactions
    assert (rent.category, rent.provisional) == ("Kira", False)


def test_an_own_transfer_receipt_is_told_apart_by_the_senders_name(cat):
    ds = analyse(cat,
                 listing(OVERDRAFT, date(2026, 10, 1), date(2026, 10, 31), closing=-2000.0),
                 receipt("r1", OVERDRAFT, row(date(2026, 11, 2), "Gelen transfer ← Garanti BBVA", -12750.0, OVERDRAFT,
                                              who=HOLDER)),
                 receipt("r2", OVERDRAFT, row(date(2026, 11, 5), "Gelen transfer ← TEB", -750.0, OVERDRAFT,
                                              who="AYŞE SOYADOĞLU")))
    assert [(t.kind, t.provisional) for t in ds.transactions] == [("transfer", True), ("gelir", True)]


# --- card payments -----------------------------------------------------------------------------------

def test_the_card_statement_confirms_a_card_payment_receipt(cat):
    credit = row(date(2026, 10, 2), "ÖDEME - TEŞEKKÜRLER", -1500.0, CARD, kind="kart_odemesi")
    ds = analyse(cat,
                 card_statement(date(2026, 10, 18), credit),
                 receipt("r1", CARD, row(date(2026, 10, 1), "QNB Mastercard •4321 borç ödemesi", 1500.0, CARD,
                                         kind="ekstresiz_kart")))
    assert statuses(ds) == [("QNB Mastercard •4321 borç ödemesi", CONFIRMED)]
    assert ds.receipts[0].match is credit


def test_a_payment_after_the_cut_lowers_the_card_debt_until_the_next_statement(cat):
    ds = analyse(cat,
                 card_statement(date(2026, 10, 18), total=4000.0),
                 receipt("r1", CARD, row(date(2026, 10, 25), "QNB Mastercard •4321 borç ödemesi", 1500.0, CARD,
                                         kind="ekstresiz_kart")))
    [payment] = ds.transactions
    # The card's statements show its purchases: the payment is not spending on an unseen card.
    assert (payment.kind, payment.provisional) == ("kart_odemesi", True)
    [card] = interpret(ds).holdings
    assert card.amount == -2500.0 and "sonra ₺1.500 ödendi" in card.note


def test_the_paying_accounts_list_confirms_a_card_payment_receipt(cat):
    paid = row(date(2026, 10, 25), "123456******4321 NOLU KART ODEMESI", 1500.0, OVERDRAFT, kind="kart_odemesi")
    ds = analyse(cat,
                 card_statement(date(2026, 10, 18)),
                 listing(OVERDRAFT, date(2026, 10, 1), date(2026, 10, 31), paid),
                 receipt("r1", CARD, row(date(2026, 10, 25), "QNB Mastercard •4321 borç ödemesi", 1500.0, CARD,
                                         kind="ekstresiz_kart")))
    assert statuses(ds) == [("QNB Mastercard •4321 borç ödemesi", CONFIRMED)]
    card = next(h for h in interpret(ds).holdings if h.kind == "kart")
    assert card.amount == -2500.0  # counted once, from the list


def test_a_payment_before_the_cards_statements_stays_a_payment_to_an_unseen_card(cat):
    ds = analyse(cat,
                 card_statement(date(2026, 10, 18)),
                 receipt("r1", CARD, row(date(2024, 6, 7), "QNB Mastercard •4321 borç ödemesi", 900.0, CARD,
                                         kind="ekstresiz_kart")))
    assert statuses(ds) == [("QNB Mastercard •4321 borç ödemesi", NO_STATEMENT)]
    assert ds.transactions[0].kind == "ekstresiz_kart"


# --- balances and the interpretation -------------------------------------------------------------

def test_provisional_receipts_move_the_balance_their_list_closed_with(cat):
    ds = analyse(cat,
                 listing(CHECKING, date(2026, 10, 1), date(2026, 10, 31), closing=10000.0),
                 receipt("r1", CHECKING, row(date(2026, 11, 3), "Giden FAST → ALİ VELİ", 2500.0, CHECKING),
                         row(date(2026, 11, 3), "FAST ücreti", 5.0, CHECKING, kind="faiz_ucret")))
    ins = interpret(ds)
    [cash] = ins.holdings
    assert (cash.amount, cash.as_of) == (7495.0, date(2026, 11, 3))
    assert "31.10.2026 dökümünde ₺10.000; sonraki 2 dekontla −₺2.505 (geçici" in cash.note
    finding = next(f for f in ins.findings if f.title == "Ekstre gelmeden işlenen dekontlar")
    assert "2 işlem" in finding.text and "kişilere giden ₺2.500" in finding.text
    assert finding.filter == {"provisional": True}
