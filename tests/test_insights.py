"""Interpretation: regular payments and their status, habits, balances and the findings."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from iplikci.analysis import Dataset
from iplikci.domain.codes import AccountType, Necessity, SeriesPeriod, TransactionKind
from iplikci.domain.models import Account, Security, Statement, Transaction
from iplikci.insights import (
    complete_months,
    debt_at,
    find_periodic,
    find_series,
    flow,
    habits,
    holdings,
    interpret,
    large_purchase_threshold,
    listed,
    months_in,
    pct,
    periodic_payments,
    regular_payments,
    since,
    timeline,
)

CARD = Account("card", "Test Kart •1234", "TEB", AccountType.CREDIT_CARD, number="1234")
OTHER_CARD = Account("old", "Eski Kart •9999", "QNB", AccountType.CREDIT_CARD, number="9999")
CASH = Account("cash", "Test Vadesiz TL", "TEB", AccountType.CURRENT, number="111222333")
USD = Account("usd", "Test Dolar", "TEB", AccountType.FX, currency="USD", number="555")
STOCKS = Account("hisse", "Test Yatırım 1-101", "Garanti BBVA", AccountType.BROKERAGE, number="1-101")
TERM = Account("vadeli", "Test Vadeli TL", "İş Bankası", AccountType.DEPOSIT, number="1234-0765432")
REGULAR = {"Dijital Abonelikler", "Elektrik, Su & Doğalgaz", "İnternet & Telefon", "Kira"}


def tx(
    d: date,
    merchant: str,
    amount: Decimal,
    category: str = "Dijital Abonelikler",
    necessity: Necessity | None = Necessity.OPTIONAL,
    kind: TransactionKind = TransactionKind.PURCHASE,
    account: str = "card",
    description: str = "",
) -> Transaction:
    return Transaction(
        date=d,
        description=description or merchant.upper(),
        amount=amount,
        kind=kind,
        account=account,
        merchant=merchant,
        category=category,
        group="",
        necessity=necessity,
    )


def monthly(first: date, count: int) -> list[date]:
    out, d = [], first
    for _ in range(count):
        out.append(d)
        d = (d.replace(day=1) + timedelta(days=32)).replace(day=min(first.day, 28))
    return out


def card_statements(first_cut: date, count: int, account: str = "card", total: Decimal = Decimal(0)) -> list[Statement]:
    return [
        Statement(account=account, cut_date=cut, currency="TRY", source="e.pdf", previous=Decimal(0), total=total)
        for cut in monthly(first_cut, count)
    ]


def full_coverage(account: str, first: str, last: str, partial_last: float | None = None) -> dict[str, float]:
    cov, m = {}, first
    while m <= last:
        cov[m] = 1.0
        y, mo = int(m[:4]), int(m[5:])
        m = f"{y + mo // 12}-{mo % 12 + 1:02d}"
    if partial_last is not None:
        cov[last] = partial_last
    return cov


def dataset(
    txns: list[Transaction], statements: list[Statement], coverage: dict | None = None, ended: dict | None = None
) -> Dataset:
    return Dataset(
        accounts={a.id: a for a in (CARD, OTHER_CARD, CASH, USD, STOCKS, TERM)},
        statements=statements,
        transactions=sorted(txns, key=lambda t: t.date),
        documents=[],
        groups=[],
        categories={},
        coverage=coverage or {},
        ended=ended or {},
        regular=REGULAR,
    )


def series_status(ds: Dataset) -> dict[tuple[str, float], str]:
    out, _ = regular_payments(ds, timeline(ds))
    return {(s.merchant, round(s.amount, 2)): s.status for s in out}


# --- regular payments -------------------------------------------------------------------------


def test_subscription_ends_when_the_card_statements_go_on_without_it():
    txns = [tx(d, "Örnek Müzik", Decimal("99.99")) for d in monthly(date(2025, 6, 15), 7)]  # last 15.12.2025
    ds = dataset(txns, card_statements(date(2025, 6, 18), 16))  # statements until 18.09.2026
    assert series_status(ds) == {("Örnek Müzik", Decimal("99.99")): "bitti"}


def test_subscription_runs_on_when_the_statements_stop_before_the_next_charge():
    txns = [tx(d, "Örnek Dergi", Decimal("49.90")) for d in monthly(date(2025, 12, 12), 11)]  # last 12.10.2026
    ds = dataset(txns, card_statements(date(2025, 12, 13), 11))  # last statement cut 13.10.2026
    assert series_status(ds) == {("Örnek Dergi", Decimal("49.9")): "devam"}


def test_listed_as_ended_is_cancelled_and_a_later_charge_is_reported():
    txns = [tx(d, "Örnek Dergi", Decimal("49.90")) for d in monthly(date(2025, 12, 12), 11)]
    statements = card_statements(date(2025, 12, 13), 12)
    assert series_status(dataset(txns, statements, ended={"ORNEK DERGI": "2026-10"})) == {
        ("Örnek Dergi", Decimal("49.9")): "iptal"
    }
    late = txns + [tx(date(2026, 11, 12), "Örnek Dergi", Decimal("49.90"))]
    ds = dataset(late, statements, ended={"ORNEK DERGI": "2026-10"})
    assert series_status(ds) == {("Örnek Dergi", Decimal("49.9")): "iptal_sonrasi"}
    finding = next(f for f in interpret(ds).findings if "iptalden sonra" in f.title)
    assert "12.11.2026" in finding.text


def test_two_subscriptions_with_one_payee_are_told_apart_by_amount():
    premium = [tx(d, "Örnek Video", Decimal("129.99")) for d in monthly(date(2026, 1, 1), 8)]
    membership = [tx(d, "Örnek Video", Decimal(100), account="old") for d in monthly(date(2026, 1, 18), 8)]
    found = find_series(premium + membership, REGULAR)
    assert sorted(round(s.amount, 2) for s in found) == [Decimal(100), Decimal("129.99")]


def test_a_bill_moving_with_the_seasons_is_one_series_but_a_shop_is_none():
    amounts = [1500, 1200, 700, 320, 120, 80, 100, 150, 600]
    gas = [
        tx(d, "Doğalgaz (İGDAŞ)", a, category="Elektrik, Su & Doğalgaz", necessity=Necessity.REQUIRED)
        for d, a in zip(monthly(date(2026, 1, 20), 9), amounts)
    ]
    found = find_series(gas, REGULAR)
    assert len(found) == 1 and len(found[0].payments) == 9
    assert found[0].monthly == 150  # median of the last three: bills move from month to month
    market = [
        tx(d, "Örnek Market", a, category="Market & Gıda", necessity=Necessity.REQUIRED)
        for d, a in zip(monthly(date(2026, 1, 3), 9), amounts)
    ]
    assert find_series(market, REGULAR) == []


def test_an_unchanged_monthly_amount_is_regular_in_any_category():
    gym = [
        tx(d, "Spor Salonu", Decimal(900), category="Diğer Harcamalar", necessity=Necessity.UNKNOWN)
        for d in monthly(date(2026, 1, 5), 5)
    ]
    assert len(find_series(gym, REGULAR)) == 1


def test_old_series_on_an_account_without_statements_is_over():
    loan = [
        tx(d, "QNB ihtiyaç kredisi", Decimal(2500), kind=TransactionKind.LOAN_PRINCIPAL, account="old")
        for d in monthly(date(2024, 1, 15), 5)
    ]
    recent = card_statements(date(2026, 1, 14), 9)
    assert series_status(dataset(loan, recent)) == {("QNB ihtiyaç kredisi", Decimal(2500)): "bitti"}


def test_a_bill_paid_elsewhere_for_a_few_months_goes_on():
    # Paid from an account without documents in May and June: the two payments after the pause are too few
    # to be a series of their own and continue the bill. The same-day card fee keeps it out of the
    # once-a-month path, so the payments are chained by amount.
    bills = [
        (date(2026, 1, 9), Decimal("500.2")),
        (date(2026, 1, 31), Decimal(540)),
        (date(2026, 3, 10), Decimal("654.6")),
        (date(2026, 4, 8), Decimal("654.6")),
        (date(2026, 7, 30), Decimal("657.8")),
        (date(2026, 9, 9), Decimal("657.8")),
    ]
    fees = [(date(2026, 1, 9), Decimal("17.5")), (date(2026, 9, 9), Decimal("23.02"))]
    txns = [
        tx(d, "Türk Telekom", a, category="İnternet & Telefon", necessity=Necessity.REQUIRED) for d, a in bills + fees
    ]
    ds = dataset(txns, card_statements(date(2026, 1, 10), 10))  # statements until 10.10.2026
    assert series_status(ds) == {("Türk Telekom", Decimal("657.8")): "devam"}
    assert not any(f.title == "Görünmeyen faturalar" for f in interpret(ds).findings)


def test_a_once_a_month_bill_goes_on_after_a_pause_but_not_after_a_long_one():
    water = [
        tx(d, "Su (İSKİ)", a, category="Elektrik, Su & Doğalgaz", necessity=Necessity.REQUIRED)
        for d, a in zip(monthly(date(2026, 1, 20), 4), [200, 210, 170, 140])
    ]
    later = [
        tx(d, "Su (İSKİ)", a, category="Elektrik, Su & Doğalgaz", necessity=Necessity.REQUIRED)
        for d, a in zip(monthly(date(2026, 8, 25), 2), [85, 290])
    ]
    (s,) = find_series(water + later, REGULAR)
    assert s.last.date == date(2026, 9, 25) and len(s.payments) == 6
    years_later = [
        tx(d, "Su (İSKİ)", 280, category="Elektrik, Su & Doğalgaz", necessity=Necessity.REQUIRED)
        for d in monthly(date(2027, 1, 25), 2)
    ]
    (s,) = find_series(water + years_later, REGULAR)
    assert s.last.date == date(2026, 4, 20)


def test_price_change_needs_the_new_price_to_hold():
    rent = [
        tx(d, "Ev kirası", a, category="Kira", necessity=Necessity.REQUIRED, account="cash")
        for d, a in zip(monthly(date(2026, 1, 5), 10), [15000] * 6 + [16400] * 4)
    ]
    (s,) = find_series(rent, REGULAR)
    old, new, when = s.price_change()
    assert (old, new, when) == (15000, 16400, date(2026, 7, 5))
    s.payments = s.payments[:7]  # one payment at the new price is not a new price yet
    assert s.price_change() is None


def test_only_running_series_and_commitments_that_ended_in_the_window_are_listed():
    window = ["2026-01", "2026-02", "2026-03"]
    ds = dataset([], [])
    shop = find_series(
        [tx(d, "Örnek Kahve", Decimal(180), category="Kafe & Kahve") for d in monthly(date(2025, 12, 5), 4)], REGULAR
    )[0]
    bill = find_series(
        [tx(d, "Su (İSKİ)", Decimal(200), category="Elektrik, Su & Doğalgaz") for d in monthly(date(2025, 11, 20), 4)],
        REGULAR,
    )[0]
    shop.status = bill.status = "bitti"
    assert not listed(shop, ds, window) and listed(bill, ds, window)  # an ended shop says nothing, a bill does
    bill.status = "iptal"
    assert listed(bill, ds, window)
    bill.payments = bill.payments[:1]  # cancelled before the window
    assert not listed(bill, ds, window)
    shop.status = "devam"
    assert listed(shop, ds, window)


# --- periodic payments ------------------------------------------------------------------------


def periodic_status(ds: Dataset) -> dict[str, tuple[SeriesPeriod, str]]:
    tl_ = timeline(ds)
    monthly_series, _ = regular_payments(ds, tl_)
    return {s.merchant: (s.period, s.status) for s in periodic_payments(ds, tl_, monthly_series)}


def test_a_yearly_payment_is_a_periodic_series_with_its_price_change_and_next_day():
    insurance = [
        tx(d, "Örnek Sigorta", a, category="Sigorta", necessity=Necessity.REQUIRED)
        for d, a in ((date(2024, 3, 10), 4000), (date(2025, 3, 12), 4400), (date(2026, 3, 9), 5200))
    ]
    ds = dataset(insurance, card_statements(date(2024, 3, 15), 32))  # statements until 15.10.2026
    tl_ = timeline(ds)
    (s,) = periodic_payments(ds, tl_, regular_payments(ds, tl_)[0])
    assert (s.period, s.status, s.per_period) == (SeriesPeriod.YEAR, "devam", Decimal(5200))
    assert s.expected == date(2026, 3, 9) + timedelta(days=364)  # the median of 367 and 362 days
    assert s.price_change() == (Decimal(4400), Decimal(5200), date(2026, 3, 9))


def test_a_half_yearly_tax_is_periodic_too():
    tax = [
        tx(d, "Motorlu Taşıtlar Vergisi", Decimal(3000), category="Vergi & Harç", necessity=Necessity.REQUIRED)
        for d in (date(2025, 7, 20), date(2026, 1, 15), date(2026, 7, 21))
    ]
    ds = dataset(tax, card_statements(date(2025, 7, 25), 15))
    assert periodic_status(ds) == {"Motorlu Taşıtlar Vergisi": (SeriesPeriod.HALF_YEAR, "devam")}


def test_a_commitments_amount_is_free_but_elsewhere_it_stays_within_half():
    def yearly(category: str) -> list[Transaction]:
        return [
            tx(date(2025, 1, 20), "Örnek Bulut", Decimal(500), category=category),
            tx(date(2026, 1, 22), "Örnek Bulut", Decimal(1200), category=category),  # more than doubled
        ]

    assert [s.period for s in find_periodic(yearly("Dijital Abonelikler"), REGULAR)] == [SeriesPeriod.YEAR]
    assert find_periodic(yearly("Diğer Harcamalar"), REGULAR) == []


def test_payments_a_period_apart_with_similar_ones_between_are_a_shop_not_a_periodic_payment():
    visits = [
        tx(d, "Örnek Restoran", a, category="Restoran & Yemek")
        for d, a in ((date(2026, 1, 10), 900), (date(2026, 3, 15), 950), (date(2026, 7, 12), 1000))
    ]
    assert find_periodic(visits, REGULAR) == []
    # A payment at another amount in between is another purchase: the yearly one stays a series.
    app = [
        tx(date(2025, 2, 1), "Örnek Uygulama", Decimal(1000), category="Diğer Harcamalar"),
        tx(date(2025, 6, 9), "Örnek Uygulama", Decimal(30), category="Diğer Harcamalar"),
        tx(date(2026, 2, 3), "Örnek Uygulama", Decimal(1100), category="Diğer Harcamalar"),
    ]
    (s,) = find_periodic(app, REGULAR)
    assert [t.amount for t in s.payments] == [Decimal(1000), Decimal(1100)]


@pytest.mark.parametrize("gap", [120, 208, 250, 420])
def test_payments_outside_both_periods_are_no_series(gap):
    payments = [
        tx(date(2025, 2, 14), "Örnek Site Yönetimi", Decimal(1250), category="Kira"),
        tx(date(2025, 2, 14) + timedelta(days=gap), "Örnek Site Yönetimi", Decimal(1250), category="Kira"),
    ]
    assert find_periodic(payments, REGULAR) == []


def test_a_periodic_payment_may_come_as_late_as_its_period_allows_before_it_ends():
    fee = [
        tx(d, "Örnek Dernek", Decimal(1000), category="Diğer Harcamalar") for d in (date(2024, 5, 5), date(2025, 5, 7))
    ]
    # Expected on 09.05.2026; a yearly payment may still come until 400 days after the last, 11.06.2026.
    waiting = dataset(fee, card_statements(date(2024, 5, 25), 25))  # statements until 25.05.2026
    assert periodic_status(waiting) == {"Örnek Dernek": (SeriesPeriod.YEAR, "devam")}
    over = dataset(fee, card_statements(date(2024, 5, 15), 26))  # statements until 15.06.2026
    assert periodic_status(over) == {"Örnek Dernek": (SeriesPeriod.YEAR, "bitti")}
    cancelled = dataset(fee, card_statements(date(2024, 5, 25), 25), ended={"ORNEK DERNEK": "2025-05"})
    assert periodic_status(cancelled) == {"Örnek Dernek": (SeriesPeriod.YEAR, "iptal")}


def test_monthly_series_keep_their_payments_and_periodic_series_stay_apart():
    music = [tx(d, "Örnek Müzik", Decimal("99.99")) for d in monthly(date(2025, 6, 15), 14)]
    yearly = [
        tx(d, "Örnek Sigorta", Decimal(4000), category="Sigorta", necessity=Necessity.REQUIRED)
        for d in (date(2025, 3, 10), date(2026, 3, 12))
    ]
    ins = interpret(dataset(music + yearly, card_statements(date(2025, 3, 15), 20)))
    assert [(s.merchant, len(s.payments)) for s in ins.series] == [("Örnek Müzik", 14)]
    assert [(s.merchant, s.period) for s in ins.periodic] == [("Örnek Sigorta", SeriesPeriod.YEAR)]


# --- habits -----------------------------------------------------------------------------------


def test_habits_are_told_apart_and_only_habits_cost_from_now_on():
    window_cov = {"card": full_coverage("card", "2025-12", "2026-10", partial_last=0.4)}
    statements = card_statements(date(2025, 12, 14), 11)
    txns = []
    for i, d in enumerate(monthly(date(2025, 12, 3), 10)):  # every month, 2 orders of 500
        txns += [
            tx(d, "Getir", Decimal(500), category="Market & Gıda"),
            tx(d + timedelta(days=7), "Getir", Decimal(500), category="Market & Gıda"),
        ]
    txns += [
        tx(d, "Örnek Büfe", Decimal(1000), category="Tekel & Büfe") for d in monthly(date(2026, 5, 18), 5)
    ]  # since May
    txns += [
        tx(date(2026, m, 10), "Hepsiburada", Decimal(1200), category="Online Alışveriş") for m in (1, 4, 8)
    ]  # now and then
    txns += [
        tx(date(2026, 1, 10), "Trendyol", Decimal(300), category="Online Alışveriş"),
        tx(date(2026, 3, 10), "Trendyol", Decimal(300), category="Online Alışveriş"),
    ]  # stopped in March
    txns.append(tx(date(2026, 8, 23), "sahibinden.com", Decimal(45000), category="Online Alışveriş"))  # once
    ds = dataset(txns, statements, coverage=window_cov)
    tl_ = timeline(ds)
    assert tl_.last_complete == "2026-09" and len(tl_.window) == 10
    found = {h.name: h for h in habits(ds, tl_, [])}
    assert (found["Getir"].status, found["Getir"].monthly) == ("duzenli", Decimal(1000))
    assert (found["Örnek Büfe"].status, found["Örnek Büfe"].since) == ("yeni", "2026-05")
    assert found["Örnek Büfe"].pattern.startswith("Mayıs 2026'dan beri")
    assert found["Hepsiburada"].status == "ara_sira"
    assert found["Hepsiburada"].monthly == pytest.approx(3600 / 10)  # spread over the window, not times twelve
    assert (found["Trendyol"].status, found["Trendyol"].monthly) == ("durdu", Decimal(0))
    assert (found["sahibinden.com"].status, found["sahibinden.com"].monthly) == ("tek", Decimal(0))


def test_a_habit_listed_as_ended_stopped():
    statements = card_statements(date(2025, 12, 14), 11)
    txns = [tx(d, "Örnek Büfe", Decimal(1000), category="Tekel & Büfe") for d in monthly(date(2026, 5, 18), 5)]
    ds = dataset(
        txns,
        statements,
        coverage={"card": full_coverage("card", "2025-12", "2026-10", 0.4)},
        ended={"ORNEK BUFE": "2026-09"},
    )
    (h,) = habits(ds, timeline(ds), [])
    assert (h.status, h.monthly) == ("durdu", Decimal(0))


def test_a_single_purchase_is_large_from_5000_tl_or_a_tenth_of_the_average_month_when_that_is_more():
    months = ["2026-01", "2026-02"]
    modest = [tx(date(2026, m, 10), "Örnek Market", Decimal(20000), category="Market & Gıda") for m in (1, 2)]
    assert large_purchase_threshold(dataset(modest, []), months) == Decimal(5000)  # a tenth of 20.000 is less
    lavish = [tx(date(2026, m, 10), "Örnek Market", Decimal(80000), category="Market & Gıda") for m in (1, 2)]
    assert large_purchase_threshold(dataset(lavish, []), months) == Decimal(8000)
    assert large_purchase_threshold(dataset(lavish, []), []) == Decimal(5000)


# --- months, balances and debt ---------------------------------------------------------------


def test_complete_months_skip_a_partial_month_but_not_a_new_account():
    statements = card_statements(date(2026, 1, 14), 10) + [
        Statement(
            account="usd",
            cut_date=date(2026, 10, 31),
            currency="USD",
            source="u.xls",
            previous=Decimal(0),
            total=Decimal(590),
            start=date(2026, 4, 30),
        )
    ]
    coverage = {
        "card": full_coverage("card", "2026-01", "2026-10", 0.45),
        "usd": full_coverage("usd", "2026-04", "2026-10"),
    }
    coverage["usd"]["2026-04"] = 0.03  # opened on 30 April from a zero balance
    ds = dataset([], statements, coverage=coverage)
    months = complete_months(ds)
    assert "2026-04" in months and "2026-09" in months and "2026-10" not in months


def test_holdings_value_foreign_currency_and_subtract_card_payments_after_the_cut():
    statements = [
        Statement(
            account="card",
            cut_date=date(2026, 10, 13),
            currency="TRY",
            source="k.pdf",
            previous=Decimal(50),
            total=Decimal("90000.5"),
        ),
        Statement(
            account="usd",
            cut_date=date(2026, 10, 31),
            currency="USD",
            source="u.xls",
            previous=Decimal(0),
            total=Decimal(500),
            start=date(2026, 4, 30),
            balances={"2026-10": Decimal(500)},
        ),
        Statement(
            account="cash",
            cut_date=date(2026, 10, 31),
            currency="TRY",
            source="v.xls",
            previous=Decimal(0),
            total=Decimal("-21000.75"),
            start=date(2026, 1, 1),
            balances={"2026-09": Decimal(-19000), "2026-10": Decimal("-21000.75")},
        ),
    ]
    paid = [
        tx(
            date(2026, 10, 14),
            "Kart ödemesi",
            Decimal("40000.25"),
            kind=TransactionKind.CARD_PAYMENT,
            account="cash",
            description="123456******1234 no.lu Kredi Kartına Ödenen Tutar",
        ),
        tx(
            date(2026, 10, 17),
            "Kart ödemesi",
            Decimal("50000.25"),
            kind=TransactionKind.CARD_PAYMENT,
            account="cash",
            description="123456******1234 no.lu Kredi Kartına Ödenen Tutar",
        ),
    ]
    ds = dataset(paid, statements)
    ds.rates = {"USD": [(date(2026, 5, 2), Decimal("46.4")), (date(2026, 7, 1), Decimal("47.18"))]}
    by_kind = {h.kind: h for h in holdings(ds)}
    assert by_kind["kart"].value == pytest.approx(Decimal(0), abs=Decimal("0.01"))
    assert by_kind["doviz"].value == pytest.approx(Decimal(500) * Decimal("47.18"), abs=Decimal("0.01"))
    assert by_kind["kmh"].amount == pytest.approx(Decimal("-21000.75"))
    # Before its first statement a card counts with that statement's opening balance (50).
    assert debt_at(ds, date(2026, 9, 30)) == pytest.approx(Decimal(19000) + Decimal(50))


def test_a_missing_brokerage_statement_leaves_the_month_complete():
    coverage = {
        "card": full_coverage("card", "2026-01", "2026-10", 0.45),
        "hisse": full_coverage("hisse", "2026-01", "2026-09"),
    }
    coverage["hisse"]["2026-05"] = 0.0  # that month's stock statement never arrived: no bill or income is missing
    ds = dataset([], card_statements(date(2026, 1, 14), 10), coverage=coverage)
    assert "2026-05" in complete_months(ds)
    assert flow(ds, timeline(ds)) is None  # nor does a brokerage statement make income known: no bank account list


def test_stocks_count_at_market_value_and_an_old_balance_is_shown_but_not_counted():
    statements = [
        Statement(
            account="cash",
            cut_date=date(2026, 10, 31),
            currency="TRY",
            source="v.xls",
            previous=Decimal(0),
            total=Decimal(1000),
            start=date(2026, 10, 1),
        ),
        Statement(
            account="hisse",
            cut_date=date(2026, 9, 30),
            currency="TRY",
            source="h.pdf",
            previous=Decimal(0),
            total=Decimal(5),
            start=date(2026, 9, 1),
            securities=[Security("ORNEK", "ÖRNEK A.Ş.", Decimal(20), Decimal(600), date(2026, 9, 30))],
        ),
        Statement(
            account="vadeli",
            cut_date=date(2024, 1, 17),
            currency="TRY",
            source="c.pdf",
            previous=Decimal(0),
            total=Decimal(7500),
            start=date(2024, 1, 17),
        ),  # known only from the passbook sent when it was opened
    ]
    by_kind = {h.kind: h for h in holdings(dataset([], statements))}
    stocks, term = by_kind["yatirim"], by_kind["vadeli"]
    assert (stocks.value, stocks.as_of) == (Decimal(605), date(2026, 9, 30))
    assert stocks.note.startswith("ORNEK 20 adet; 30.09.2026 piyasa değeriyle; nakit")
    assert (term.amount, term.value) == (Decimal(7500), None) and term.note.startswith("son belge 17.01.2024")


# --- findings ---------------------------------------------------------------------------------


def test_interpretation_prices_the_steps_and_balances_the_budget():
    statements = card_statements(date(2025, 12, 14), 11, total=Decimal(5000)) + [
        Statement(
            account="cash",
            cut_date=date(2026, 10, 31),
            currency="TRY",
            source="v.xls",
            previous=Decimal(0),
            total=Decimal(-20000),
            start=date(2025, 11, 30),
            balances={"2026-09": Decimal(-20000), "2026-10": Decimal(-20000)},
        )
    ]
    coverage = {
        "card": full_coverage("card", "2025-12", "2026-10", 0.4),
        "cash": full_coverage("cash", "2025-12", "2026-10"),
    }
    txns = [
        tx(
            d,
            "Örnek (maaş)",
            Decimal(-100000),
            kind=TransactionKind.INCOME,
            category="Maaş & İş Geliri",
            necessity=None,
            account="cash",
        )
        for d in monthly(date(2025, 12, 1), 11)
    ]
    txns += [
        tx(d, "Ev kirası", Decimal(20000), category="Kira", necessity=Necessity.REQUIRED, account="cash")
        for d in monthly(date(2025, 12, 5), 11)
    ]
    txns += [
        tx(d + timedelta(days=4 * k), "Getir", Decimal(1400), category="Market & Gıda")  # six orders a month: a shop
        for d in monthly(date(2025, 12, 2), 10)
        for k in range(6)
    ]
    txns += [
        tx(
            d,
            "TEB faiz & ücretleri",
            Decimal(1000),
            kind=TransactionKind.INTEREST_FEE,
            category="Ek Hesap (KMH) Faizi",
            necessity=Necessity.UNNECESSARY,
            account="cash",
        )
        for d in monthly(date(2025, 12, 28), 10)
    ]
    ins = interpret(dataset(txns, statements, coverage=coverage))
    titles = [f.title for f in ins.findings]
    assert (
        "Gelir ve gider dengesi" in titles and "En büyük alışkanlık" in titles and "Faiz ve banka ücretleri" in titles
    )
    steps = {s.title: s.monthly for s in ins.steps}
    assert steps["Faiz ödemeyi bırakın"] == pytest.approx(Decimal(1000))
    income, *spent, left = ins.budget
    assert income.now == Decimal(100000)
    assert left.now == pytest.approx(income.now - sum(line.now for line in spent))
    assert left.plan - left.now == pytest.approx(sum(line.now - line.plan for line in spent))


def _account_months(extra: list[Transaction]) -> Dataset:
    """A current account listed from January to June 2026 with a salary, and extra rows."""
    statements = [
        Statement(
            account="cash",
            cut_date=date(2026, 6, 30),
            currency="TRY",
            source="v.xls",
            previous=Decimal(0),
            total=Decimal(50000),
            start=date(2026, 1, 1),
        )
    ]
    salary = [
        tx(d, "Örnek İşveren", Decimal(-40000), "Maaş", None, TransactionKind.INCOME, "cash")
        for d in monthly(date(2026, 1, 1), 6)
    ]
    return dataset(salary + extra, statements, coverage={"cash": full_coverage("cash", "2026-01", "2026-06")})


def test_fees_are_advised_on_by_their_kind_and_a_purchase_from_an_account_is_no_card_debt():
    fee = (TransactionKind.INTEREST_FEE, "cash")
    fees = [
        tx(d, "TEB faiz & ücretleri", Decimal(8), "Transfer & İşlem Ücretleri", Necessity.UNNECESSARY, *fee)
        for d in monthly(date(2026, 1, 3), 6)
    ]
    laptop = tx(date(2026, 4, 25), "Örnek Elektronik", Decimal(8500), "Elektronik", account="cash")
    music = [tx(d, "Örnek Müzik", Decimal("99.99"), account="cash") for d in monthly(date(2026, 1, 9), 6)]
    ins = interpret(_account_months([*fees, laptop, *music]))
    step = next(s for s in ins.steps if s.title == "Abonelikleri gözden geçirin")
    assert step.text.endswith(
        "İptal ettiklerinizi Abonelikler ekranında “İptal ettim” ile işaretleyin; tahmin ona göre düşer."
    )
    found = next(f for f in ins.findings if f.title == "Faiz ve banka ücretleri")
    # A transfer's fee is not avoided by paying a debt on time.
    assert found.text == (
        "Ocak 2026 – Haziran 2026 arasındaki 6 tam ayda 48 TL, ayda 8 TL: Transfer & İşlem Ücretleri 48 TL. Transfer "
        "ücretleri, ücretsiz transfer hakkı olan bir hesap ya da kanalla önlenir."
    )
    fee_line = next(line for line in ins.budget if line.label == "Faiz ve banka ücretleri")
    assert (fee_line.now, fee_line.note) == (Decimal(8), "öneri: ücretsiz transfer kanalıyla sıfırlayın")
    step = next(s for s in ins.steps if s.title == "Büyük alışverişler için önceden biriktirin")
    assert step.text == (
        "6 ayda 1 büyük alışveriş (8.500 TL) tek seferde hesaptan ödendi. Bunlar için her ay 1.417 TL ayırmak o ayın "
        "bütçesinin bir anda açık vermesini önler."
    )
    # Card interest is: on a card, the same purchase is card debt.
    interest = tx(
        date(2026, 5, 14), "Kart faizi", Decimal(300), "Kredi Kartı Faizi", Necessity.UNNECESSARY, fee[0], "card"
    )
    on_card = tx(date(2026, 4, 25), "Örnek Elektronik", Decimal(8500), "Elektronik")
    statements = card_statements(date(2026, 1, 14), 6)
    ds = _account_months([*fees, interest, on_card])
    ds.statements += statements
    ds.coverage["card"] = full_coverage("card", "2026-01", "2026-06")
    ins = interpret(ds)
    found = next(f for f in ins.findings if f.title == "Faiz ve banka ücretleri")
    assert found.text.endswith(
        ": Kredi Kartı Faizi 300 TL, Transfer & İşlem Ücretleri 48 TL. Kart faizi, ekstre her ay tamamen ödenince "
        "önlenir; transfer ücretleri, ücretsiz transfer hakkı olan bir hesap ya da kanalla önlenir."
    )
    step = next(s for s in ins.steps if s.title == "Büyük alışverişler için önceden biriktirin")
    assert "tek seferde karttan ödendi" in step.text and step.text.endswith("kart borcunu ve faizi önler.")


# --- Turkish ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "share, text",
    [
        (0.64, "%64'ü"),
        (0.72, "%72'si"),
        (0.29, "%29'u"),
        (0.45, "%45'i"),
        (0.30, "%30'u"),
        (0.60, "%60'ı"),
        (0.06, "%6'sı"),
        (1.0, "%100'ü"),
        (11.0, "%1100'ü"),
        (10.1, "%1010'u"),
        (10.0, "%1000'i"),
        (20.0, "%2000'i"),
        (0.0, "%0'ı"),
        (0.004, "%1'den azı"),  # not nothing
        (Decimal("0.996"), "%99'dan fazlası"),  # not all
    ],
)
def test_percent_takes_the_right_suffix(share, text):
    assert pct(share) == text


def test_years_take_the_right_suffix():
    assert since("2026-05") == "Mayıs 2026'dan beri"
    assert since("2025-12") == "Aralık 2025'ten beri"
    assert months_in(["2026-03", "2026-07", "2025-12"]) == "Mart ve Temmuz 2026'da, Aralık 2025'te"
