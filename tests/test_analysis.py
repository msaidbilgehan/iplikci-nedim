from datetime import date
from decimal import Decimal

from iplikci.analysis import _coverage, _link_foreign_currency, covered_days
from iplikci.domain.codes import TransactionKind
from iplikci.domain.models import Statement, Transaction


def txn(d, desc, amount, kind=TransactionKind.PURCHASE, account="isbank-4321"):
    return Transaction(date=d, description=desc, amount=amount, kind=kind, account=account)


def test_statement_check():
    s = Statement(
        account="a",
        cut_date=date(2024, 10, 7),
        currency="TRY",
        source="x",
        previous=Decimal(100),
        total=Decimal(150),
        transactions=[txn(date(2024, 9, 10), "A", Decimal(70)), txn(date(2024, 9, 11), "ODEME", Decimal(-20))],
    )
    assert s.verified and s.difference == 0
    s.total = Decimal(151)
    assert not s.verified and s.difference == Decimal(-1)


def test_foreign_currency_line_takes_merchant_names():
    usd = Statement(
        account="isbank-4321",
        cut_date=date(2024, 12, 15),
        currency="USD",
        source="usd.pdf",
        previous=0,
        total=Decimal(20),
        transactions=[txn(date(2024, 12, 9), "OPENAI *CHATGPT SUBSCR HTTPSOPENAI.C CA US", Decimal(20))],
    )
    line = txn(date(2024, 12, 15), "15/12/2024 EKSTRENIZDEKI USD/EUR BORCUNUZUN TL", Decimal(700))
    tl = Statement(
        account="isbank-4321",
        cut_date=date(2025, 1, 15),
        currency="TRY",
        source="tl.pdf",
        previous=0,
        total=Decimal(700),
        transactions=[line],
    )
    _link_foreign_currency([tl, usd])
    assert line.description.startswith("Yurt dışı harcama: OPENAI *CHATGPT")
    assert line.original == "20,00 USD"
    assert line.amount == Decimal(700)  # the TL amount the bank charged stays the expense


def _statements(*balances):
    """Card statements cut on the 7th of Feb, Mar and May 2024 with (previous, total) balances."""
    cuts = (date(2024, 2, 7), date(2024, 3, 7), date(2024, 5, 7))
    return [
        Statement(account="a", cut_date=d, currency="TRY", source="", previous=p, total=t)
        for d, (p, t) in zip(cuts, balances)
    ]


def test_coverage_marks_missing_months():
    cov = _coverage(covered_days(_statements((0, 100), (100, 250), (900, 1000))))["a"]  # April's statement is missing
    assert cov["2024-02"] == 1.0  # 8 Jan – 7 Feb and 8 Feb – 7 Mar cover February
    assert 0 < cov["2024-04"] < 1  # 8 Apr – 7 May only
    assert cov["2024-01"] < 1


def test_coverage_bridges_months_without_activity():
    # May starts from March's closing balance: the bank skipped April because nothing happened.
    cov = _coverage(covered_days(_statements((0, 100), (100, 250), (250, 300))))["a"]
    assert cov["2024-04"] == 1.0
