from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from iplikci.analysis import _coverage, _link_foreign_currency, build, covered_days
from iplikci.categorize import Categorizer
from iplikci.domain.codes import AccountType, TransactionKind
from iplikci.domain.models import Account, ParseResult, Statement, Transaction
from iplikci.parsers.contract import Document

from conftest import PEOPLE_RULES


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


# --- movement lists of one account that cover the same days ------------------------------------------------------

LIST_ACCOUNT = Account("teb-111", "TEB Vadesiz TL 111", "TEB", AccountType.CURRENT, number="111")


@pytest.fixture(scope="module")
def categorizer(tmp_path_factory):
    rules = tmp_path_factory.mktemp("kurallar") / "kategoriler.yaml"
    rules.write_text(PEOPLE_RULES, encoding="utf-8")
    return Categorizer(rules)


def spent(d: date, minor: int) -> Transaction:
    """A card spending on a list: no transfer to resolve, so the row reaches the ledger as it was read."""
    return Transaction(d, f"POS ALISVERIS {minor}", Decimal(-minor) / 100, TransactionKind.PURCHASE, LIST_ACCOUNT.id)


def movement_list(start: date, end: date, *rows: Transaction) -> ParseResult:
    s = Statement(
        LIST_ACCOUNT.id,
        end,
        "TRY",
        "hareketler.xls",
        Decimal(5000),
        Decimal(5000) + sum((r.amount for r in rows), Decimal(0)),
        list(rows),
        start=start,
        checks_ok=1,
        checks_total=1,
    )
    return ParseResult("liste", accounts=[LIST_ACCOUNT], statements=[s])


def ledger(categorizer, *lists: ParseResult):
    docs = [(Document(f"{i}.xls", "test", b"", f"sha{i}"), r, None) for i, r in enumerate(lists)]
    return build(docs, categorizer, {"ad_soyad": "ÖRNEK İSİM"})


def counted(ds) -> list[tuple[date, Decimal]]:
    return sorted((t.date, t.amount) for t in ds.transactions if t.account == LIST_ACCOUNT.id)


def test_a_day_two_lists_cover_counts_its_rows_once_from_the_list_with_more_of_them(categorizer):
    # May's list was taken on 31 May at noon and lacks the day's later spending; June's starts on 31 May.
    may = movement_list(
        date(2026, 5, 1), date(2026, 5, 31), spent(date(2026, 5, 10), 100), spent(date(2026, 5, 31), 200)
    )
    june = movement_list(
        date(2026, 5, 31),
        date(2026, 6, 30),
        spent(date(2026, 5, 31), 200),
        spent(date(2026, 5, 31), 300),
        spent(date(2026, 6, 5), 400),
    )
    assert counted(ledger(categorizer, may, june)) == [
        (date(2026, 5, 10), Decimal(-1)),
        (date(2026, 5, 31), Decimal(-3)),
        (date(2026, 5, 31), Decimal(-2)),
        (date(2026, 6, 5), Decimal(-4)),
    ]


def test_the_list_reaching_further_gives_a_day_both_show_alike(categorizer):
    first = movement_list(date(2026, 1, 1), date(2026, 6, 30), spent(date(2026, 3, 3), 500))
    later = movement_list(date(2026, 3, 1), date(2026, 10, 31), spent(date(2026, 3, 3), 500))
    ds = ledger(categorizer, first, later)
    rows = [t for t in ds.transactions if t.account == LIST_ACCOUNT.id]
    assert [(t.date, t.document) for t in rows] == [(date(2026, 3, 3), "sha1")]


def test_the_choice_never_depends_on_the_order_the_lists_came_in(categorizer):
    # Two lists ending on the same day, both showing the day's one row: the first by document gives it, in any order.
    a = movement_list(date(2026, 1, 1), date(2026, 1, 31), spent(date(2026, 1, 9), 700))
    b = movement_list(date(2026, 1, 5), date(2026, 1, 31), spent(date(2026, 1, 9), 700))
    for arrived in ([("shaA", a), ("shaB", b)], [("shaB", b), ("shaA", a)]):
        docs = [(Document(f"{sha}.xls", "test", b"", sha), r, None) for sha, r in arrived]
        ds = build(docs, categorizer, {"ad_soyad": "ÖRNEK İSİM"})
        assert [t.document for t in ds.transactions if t.account == LIST_ACCOUNT.id] == ["shaA"]


def test_each_list_keeps_its_own_rows_and_checks(categorizer):
    may = movement_list(date(2026, 5, 1), date(2026, 5, 31), spent(date(2026, 5, 31), 200))
    june = movement_list(date(2026, 5, 31), date(2026, 6, 30), spent(date(2026, 5, 31), 200))
    ds = ledger(categorizer, may, june)
    assert [len(s.transactions) for s in ds.statements] == [1, 1]
    assert all(s.verified for s in ds.statements)


def test_a_row_keeps_its_fingerprint_whichever_list_brings_it(categorizer):
    alone = movement_list(date(2026, 5, 1), date(2026, 5, 31), spent(date(2026, 5, 31), 200))
    before = {t.fingerprint for t in ledger(categorizer, alone).transactions}
    may = movement_list(date(2026, 5, 1), date(2026, 5, 31), spent(date(2026, 5, 31), 200))
    june = movement_list(
        date(2026, 5, 31), date(2026, 6, 30), spent(date(2026, 5, 31), 200), spent(date(2026, 6, 2), 50)
    )
    after = {t.fingerprint for t in ledger(categorizer, may, june).transactions if t.date == date(2026, 5, 31)}
    assert after == before


def test_rows_alike_within_one_list_are_never_merged(categorizer):
    # Two coffees of the same price on one day are two rows; the other list, taken in between, shows one.
    both = movement_list(date(2026, 4, 1), date(2026, 4, 30), spent(date(2026, 4, 7), 90), spent(date(2026, 4, 7), 90))
    one = movement_list(date(2026, 4, 7), date(2026, 5, 31), spent(date(2026, 4, 7), 90))
    assert counted(ledger(categorizer, both, one)) == [(date(2026, 4, 7), Decimal("-0.9"))] * 2


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    days=st.lists(st.lists(st.integers(1, 999), max_size=3), min_size=30, max_size=30),
    ranges=st.lists(st.tuples(st.integers(0, 29), st.integers(0, 29)), min_size=1, max_size=4),
)
def test_lists_over_any_dates_count_every_day_s_rows_once(categorizer, days, ranges):
    """Lists that show every row of the days they cover, over any ranges: the ledger holds each covered day's rows
    exactly once."""
    first = date(2026, 3, 1)
    truth = {
        first + timedelta(days=n): [spent(first + timedelta(days=n), m) for m in minors]
        for n, minors in enumerate(days)
    }
    lists = []
    covered: set[date] = set()
    for a, b in ranges:
        start, end = first + timedelta(days=min(a, b)), first + timedelta(days=max(a, b))
        span = [start + timedelta(days=n) for n in range((end - start).days + 1)]
        covered.update(span)
        lists.append(movement_list(start, end, *[spent(t.date, -int(t.amount * 100)) for d in span for t in truth[d]]))
    expected = sorted((t.date, t.amount) for d in covered for t in truth[d])
    assert counted(ledger(categorizer, *lists)) == expected
