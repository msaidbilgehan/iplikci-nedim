"""Non-bank bills and receipts against the bank's rows (F14): matched, waiting or information only, never counted."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from iplikci.analysis import build
from iplikci.categorize import Categorizer
from iplikci.domain.codes import AccountType, InvoiceKind, InvoiceStatus, TransactionKind
from iplikci.domain.models import Account, Invoice, ParseResult, Statement, Transaction
from iplikci.insights import interpret
from iplikci.invoices import UNMATCHED_REASONS, UNPAID_REASON, match, one_copy, settled_until, similar, window
from iplikci.parsers.contract import Document

from conftest import PEOPLE_RULES

CARD = Account("teb-1234", "TEB Bonus •1234", "TEB", AccountType.CREDIT_CARD, number="1234")


def bill(
    total: str = "412.90",
    issued: date = date(2026, 10, 3),
    due: date | None = date(2026, 10, 20),
    seller: str = "ÖRNEKCELL İLETİŞİM HİZMETLERİ A.Ş.",
    number: str = "ABC2026000000101",
    currency: str = "TRY",
) -> Invoice:
    return Invoice(InvoiceKind.BILL, seller, issued, Decimal(total), currency, number, due)


def receipt(
    total: str = "59.99", issued: date = date(2026, 10, 10), seller: str = "Örnek Uygulama Mağazası"
) -> Invoice:
    return Invoice(InvoiceKind.RECEIPT, seller, issued, Decimal(total), number="R-1")


def row(
    day: date,
    description: str,
    amount: str,
    kind: TransactionKind = TransactionKind.PURCHASE,
    original: str = "",
) -> Transaction:
    return Transaction(
        day, description, Decimal(amount), kind, CARD.id, original=original, fingerprint=f"{day}{amount}"
    )


def test_a_bill_matches_the_row_that_paid_it_by_its_due_date_and_marks_it():
    paid = row(date(2026, 10, 18), "ORNEKCELL FATURA ODEME", "412.90")
    [found] = match([("sha:0", bill(), "fatura.xml")], [paid], date(2026, 10, 31))
    assert (found.status, found.row, found.window) == (
        InvoiceStatus.MATCHED,
        paid,
        (date(2026, 10, 3), date(2026, 10, 23)),  # from its date to three days after its due date
    )
    assert paid.invoice == "sha:0"


def test_a_receipts_row_is_looked_for_a_day_before_it_to_three_days_after():
    assert window(receipt()) == (date(2026, 10, 9), date(2026, 10, 13))
    for day, status in ((date(2026, 10, 13), InvoiceStatus.MATCHED), (date(2026, 10, 14), InvoiceStatus.UNMATCHED)):
        charged = row(day, "ORNEK UYGULAMA MAGAZASI ISTANBUL", "59.99")
        [found] = match([("sha:0", receipt(), "makbuz.eml")], [charged], date(2026, 10, 31))
        assert found.status == status


@pytest.mark.parametrize(
    ("seller", "text", "alike"),
    [
        ("ÖRNEKCELL İLETİŞİM HİZMETLERİ A.Ş.", "ORNEKCELL FATURA ODEME", True),
        ("Örnek Uygulama Mağazası", "ORNEKUYGULAMA.COM/BILL", True),  # written together
        ("Örnek Uygulama Mağazası", "BASKA MAGAZA", False),
        ("Örnekenerji Elektrik Perakende Satış A.Ş.", "ORNEKENERJI FATURA", True),
        ("Örnekenerji Elektrik Perakende Satış A.Ş.", "ELEKTRIK FATURASI ODEME", False),  # a trade's word is no name
        ("ÖRNEKSU ANONİM ŞİRKETİ", "baska bir isyeri", False),
    ],
)
def test_a_sellers_name_is_alike_when_a_word_that_tells_who_it_is_is_in_the_rows_text(seller, text, alike):
    assert similar(seller, row(date(2026, 10, 1), text, "1.00")) is alike


def test_the_amount_must_be_the_bills_to_the_kurus_and_a_foreign_one_the_rows_original_amount():
    rows = [row(date(2026, 10, 18), "ORNEKCELL FATURA ODEME", "412.89")]
    assert match([("sha:0", bill(), "f.xml")], rows, date(2026, 10, 31))[0].status == InvoiceStatus.UNMATCHED
    abroad = bill(total="19.99", currency="USD", seller="Örnekflix International B.V.")
    charged = row(date(2026, 10, 12), "ORNEKFLIX.COM AMSTERDAM", "684.31", original="19,99 USD")
    assert match([("sha:0", abroad, "f.xml")], [charged], date(2026, 10, 31))[0].row is charged


def test_a_row_pays_one_document_and_two_months_bills_take_a_row_each():
    september = bill(issued=date(2026, 9, 3), due=date(2026, 9, 20), number="A1")
    october = bill(issued=date(2026, 10, 3), due=date(2026, 10, 20), number="A2")
    early = row(date(2026, 9, 18), "ORNEKCELL FATURA ODEME", "412.90")
    late = row(date(2026, 10, 19), "ORNEKCELL FATURA ODEME", "412.90")
    found = match([("s:1", october, "b.xml"), ("s:0", september, "a.xml")], [early, late], date(2026, 10, 31))
    assert [(f.key, f.row) for f in found] == [("s:0", early), ("s:1", late)]
    twin = bill(number="A3")  # another bill of the same amount and days: the one row pays the older key only
    found = match([("s:2", twin, "c.xml"), ("s:1", october, "b.xml")], [late], date(2026, 10, 31))
    assert [(f.key, f.status) for f in found] == [("s:1", InvoiceStatus.MATCHED), ("s:2", InvoiceStatus.UNMATCHED)]


def test_a_bill_waits_until_its_days_pass_and_the_documents_reach_them_then_is_information_with_its_reasons():
    [waiting] = match([("s:0", bill(), "f.xml")], [], date(2026, 10, 15))  # the statements end before its days do
    assert (waiting.status, waiting.reasons) == (InvoiceStatus.PENDING, ())
    [left] = match([("s:0", bill(), "f.xml")], [], date(2026, 10, 31))
    assert (left.status, left.reasons) == (InvoiceStatus.UNMATCHED, (*UNMATCHED_REASONS, UNPAID_REASON))
    [paid] = match([("s:0", receipt(), "m.eml")], [], date(2026, 10, 31))
    assert paid.reasons == UNMATCHED_REASONS  # a receipt was paid: only someone else or another account paid it
    assert match([("s:0", bill(), "f.xml")], [], None)[0].status == InvoiceStatus.PENDING  # no statement at all


def test_only_the_accounts_still_sent_decide_how_far_the_documents_reach():
    def days(last: date) -> set[date]:
        return {last - timedelta(days=n) for n in range(30)}

    covered = {"card": days(date(2026, 10, 5)), "list": days(date(2026, 10, 31)), "old": days(date(2025, 3, 31))}
    assert settled_until(covered) == date(2026, 10, 5)  # the card's next statement has not come; "old" stopped
    assert settled_until({}) is None


def test_a_bill_mailed_twice_is_one_bill():
    found = [("a:0", bill(), "a.xml"), ("b:0", bill(), "b.xml"), ("c:0", bill(number=""), "c.xml")]
    assert [key for key, _, _ in one_copy(found)] == ["a:0", "c:0"]  # one without a number is never taken for another


# --- in the ledger ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cat(tmp_path_factory):
    rules = tmp_path_factory.mktemp("kurallar") / "kategoriler.yaml"
    rules.write_text(PEOPLE_RULES, encoding="utf-8")
    return Categorizer(rules)


def statement() -> ParseResult:
    rows = [
        row(date(2026, 10, 18), "ORNEKCELL FATURA ODEME", "412.90"),
        row(date(2026, 10, 21), "MIGROS ORNEK SUBE", "1245.60"),
    ]
    total = sum((t.amount for t in rows), Decimal(0))
    s = Statement(CARD.id, date(2026, 11, 5), "TRY", "ekstre.pdf", Decimal(0), total, rows)
    return ParseResult("ekstre", accounts=[CARD], statements=[s])


def analyse(cat, *results: ParseResult):
    docs = [(Document(f"{i}.pdf", "test", b"", f"sha{i}"), r, None) for i, r in enumerate(results)]
    return build(docs, cat, {})


def test_bills_and_receipts_change_no_total_matched_or_not(cat):
    alone = analyse(cat, statement())
    unmatched = receipt(total="99.99", issued=date(2026, 10, 2), seller="Örnekflix International")
    mailed = ParseResult("invoice.ubl_tr", invoices=[bill(), unmatched])
    both = analyse(cat, statement(), mailed)
    assert [(i.status, i.document) for i in both.invoices] == [
        (InvoiceStatus.UNMATCHED, "1.pdf"),  # information only
        (InvoiceStatus.MATCHED, "1.pdf"),
    ]

    def totals(ds) -> tuple:
        ins = interpret(ds)
        rows = [(t.date, t.amount, t.kind, t.category, t.provisional) for t in ds.transactions]
        return rows, [(h.label, h.amount) for h in ins.holdings], [(b.label, b.now, b.plan) for b in ins.budget]

    assert totals(both) == totals(alone)
    [paid] = [t for t in both.transactions if t.invoice]
    assert (paid.description, paid.invoice) == ("ORNEKCELL FATURA ODEME", "sha1:0")
