"""Money, quantities, the domain's codes and their labels, and the rule that the domain imports nothing else."""

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from iplikci.domain import labels
from iplikci.domain.codes import DEFAULT_EXPENSE_KINDS, MonthStatus, Necessity, TransactionKind
from iplikci.domain.dates import Cut, add_months
from iplikci.domain.models import Statement
from iplikci.domain.money import TOLERANCE, Money, Quantity, Unit, round_half_up, to_decimal

PACKAGE = Path(__file__).parent.parent / "src" / "iplikci"

# Amounts as banks print them: two decimals, up to a billion either way.
kurus = st.integers(min_value=-(10**11), max_value=10**11)
amounts = kurus.map(lambda n: Decimal(n).scaleb(-2))
currencies = st.sampled_from(["TRY", "EUR", "USD"])


def try_(value: str) -> Money:
    return Money(Decimal(value), "TRY")


# --- money ------------------------------------------------------------------------------------------


@given(kurus, currencies)
def test_an_amount_survives_the_trip_through_the_database(units, currency):
    money = Money.from_minor(units, currency)
    assert money.to_minor() == units
    assert Money.from_minor(money.to_minor(), currency) == money


@given(st.lists(amounts, max_size=40))
def test_sums_are_exact_whatever_the_order(values):
    moneys = [Money(v, "TRY") for v in values]
    total = Money.total(moneys, "TRY")
    assert total == Money.total(reversed(moneys), "TRY")
    assert total.amount == sum(values, Decimal(0))
    assert total.to_minor() == sum(m.to_minor() for m in moneys)


@given(amounts, amounts)
def test_subtraction_undoes_addition(a, b):
    x, y = Money(a, "EUR"), Money(b, "EUR")
    assert x + y - y == x
    negated = -x
    assert -negated == x
    assert abs(x) == abs(-x)


@given(st.decimals(min_value=-(10**9), max_value=10**9, allow_nan=False, allow_infinity=False, places=6))
def test_rounding_half_up_moves_an_amount_by_at_most_half_a_kurus(value):
    rounded = round_half_up(value)
    assert abs(rounded - value) <= Decimal("0.005")
    assert rounded == rounded.quantize(Decimal("0.01"))


def test_halves_round_away_from_zero_as_banks_round():
    assert round_half_up(Decimal("2.675")) == Decimal("2.68")
    assert round_half_up(Decimal("-2.675")) == Decimal("-2.68")
    assert round_half_up(Decimal("2.665")) == Decimal("2.67")  # banker's rounding would give 2.66
    assert try_("10.005").rounded() == try_("10.01")


def test_a_float_is_read_through_its_shortest_form():
    assert to_decimal(0.1) == Decimal("0.1")
    assert to_decimal(1234.56) == Decimal("1234.56")
    with pytest.raises(ValueError):
        to_decimal(float("nan"))


def test_two_currencies_never_mix():
    with pytest.raises(ValueError, match="farklı para birimleri"):
        try_("1") + Money(Decimal(1), "EUR")
    with pytest.raises(ValueError):
        assert try_("1") < Money(Decimal(2), "USD")


def test_floats_are_refused_at_the_door():
    with pytest.raises(TypeError):
        Money(1.5, "TRY")  # type: ignore[arg-type] - the point of the test
    with pytest.raises(TypeError):
        try_("1") * 1.5  # type: ignore[operator] - the point of the test


def test_an_unknown_currency_is_refused():
    with pytest.raises(ValueError, match="bilinmeyen para birimi"):
        Money(Decimal(1), "XYZ")


def test_an_unrounded_amount_cannot_be_stored():
    with pytest.raises(ValueError, match="yuvarlanmalı"):
        try_("1.005").to_minor()
    assert try_("1.005").rounded().to_minor() == 101


def test_sum_starts_from_zero():
    assert sum([try_("1.10"), try_("2.20")]) == try_("3.30")


def test_conversion_rounds_to_the_target_currency():
    assert Money(Decimal("19.99"), "USD").convert(Decimal("34.5678"), "TRY") == try_("691.01")


def test_the_card_statement_tolerance_is_one_kurus():
    assert TOLERANCE == Decimal("0.01")


@given(st.decimals(min_value=0, max_value=10**6, allow_nan=False, allow_infinity=False, places=4))
def test_a_quantity_survives_the_trip_through_its_text(value):
    q = Quantity(value, Unit.GRAM)
    assert Quantity.from_text(q.to_text(), Unit.GRAM) == q


def test_quantities_of_different_units_never_mix():
    with pytest.raises(ValueError):
        Quantity(Decimal(1), Unit.GRAM) + Quantity(Decimal(1), Unit.SHARE)


# --- codes and labels -------------------------------------------------------------------------------


def test_every_code_has_a_turkish_label():
    for code_type, table in labels.TABLES.items():
        assert set(table) == set(code_type), code_type.__name__
        assert len(set(table.values())) == len(table), f"{code_type.__name__}: two codes share a label"


def test_codes_read_as_their_english_value():
    assert TransactionKind.PURCHASE == "purchase"
    assert labels.label(TransactionKind.CARD_PAYMENT) == "Kredi kartı borç ödemesi"
    assert labels.label(Necessity.UNKNOWN) == "Belirsiz"
    assert labels.ACCOUNT_MONTH_STATUS[MonthStatus.CHECK] == "Kontrol edin"


def test_spending_kinds_are_purchases_refunds_and_costs():
    assert DEFAULT_EXPENSE_KINDS == (TransactionKind.PURCHASE, TransactionKind.REFUND, TransactionKind.INTEREST_FEE)


def test_money_reads_in_the_turkish_format():
    assert labels.format_money(try_("1234.5")) == "1.234,50 TL"
    assert labels.format_money(Money(Decimal("-0.5"), "EUR")) == "-0,50 EUR"
    assert labels.format_amount(Decimal(1000000)) == "1.000.000,00"
    assert labels.format_amount(Decimal("2.665")) == "2,67"


# --- a card's cuts ----------------------------------------------------------------------------------


def test_a_cards_next_cut_is_the_day_its_statement_prints_and_a_later_one_is_reckoned_from_it():
    # The bank moves the cut day: the statement cut on 5 October prints 4 November for the next one.
    s = Statement("kart", date(2026, 10, 5), "TRY", "ekstre.pdf", None, None, next_cut=date(2026, 11, 4))
    assert [s.cut_after(k) for k in (1, 2)] == [
        Cut(date(2026, 11, 4), printed=True),
        Cut(date(2026, 12, 4), printed=False),
    ]


def test_a_statement_that_prints_no_next_cut_has_it_reckoned_the_same_day_a_month_on():
    s = Statement("kart", date(2026, 1, 31), "TRY", "ekstre.pdf", None, None)
    assert [s.cut_after(k) for k in (1, 2)] == [
        Cut(date(2026, 2, 28), printed=False),  # a shorter month: its last day
        Cut(date(2026, 3, 31), printed=False),
    ]
    assert add_months(date(2026, 1, 31), 13) == date(2027, 2, 28)


# --- dependency rules (architecture §6) -------------------------------------------------------------


def _internal_imports(path: Path) -> set[str]:
    """The iplikci modules a file imports, relative imports resolved."""
    package = ".".join(path.relative_to(PACKAGE.parent).with_suffix("").parts[:-1])
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names if a.name.split(".")[0] == "iplikci"}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.rsplit(".", node.level - 1)[0] if node.level > 1 else package
                found.add(f"{base}.{node.module}" if node.module else base)
            elif node.module and node.module.split(".")[0] == "iplikci":
                found.add(node.module)
    return found


def test_the_domain_imports_no_other_module_of_the_package():
    for path in (PACKAGE / "domain").rglob("*.py"):
        outside = {m for m in _internal_imports(path) if not m.startswith("iplikci.domain")}
        assert not outside, f"{path.name} imports {sorted(outside)}"
