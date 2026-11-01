"""Interpretation: regular payments and their status, habits, balances and the findings."""

from datetime import date, timedelta

import pytest

from iplikci.analysis import Dataset
from iplikci.domain.models import Account, Security, Statement, Transaction
from iplikci.insights import (
    complete_months,
    debt_at,
    find_series,
    flow,
    habits,
    holdings,
    interpret,
    months_in,
    pct,
    regular_payments,
    since,
    timeline,
)

CARD = Account("card", "Test Kart •1234", "TEB", "Kredi kartı", number="1234")
OTHER_CARD = Account("old", "Eski Kart •9999", "QNB", "Kredi kartı", number="9999")
CASH = Account("cash", "Test Vadesiz TL", "TEB", "Vadesiz hesap", number="111222333")
USD = Account("usd", "Test Dolar", "TEB", "Döviz hesabı", currency="USD", number="555")
STOCKS = Account("hisse", "Test Yatırım 1-101", "Garanti BBVA", "Yatırım hesabı", number="1-101")
TERM = Account("vadeli", "Test Vadeli TL", "İş Bankası", "Vadeli hesap", number="1234-0765432")
REGULAR = {"Dijital Abonelikler", "Elektrik, Su & Doğalgaz", "İnternet & Telefon", "Kira"}


def tx(
    d: date,
    merchant: str,
    amount: float,
    category: str = "Dijital Abonelikler",
    necessity: str = "İsteğe bağlı",
    kind: str = "harcama",
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


def card_statements(first_cut: date, count: int, account: str = "card", total: float = 0.0) -> list[Statement]:
    return [
        Statement(account=account, cut_date=cut, currency="TL", source="e.pdf", previous=0.0, total=total)
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
    txns = [tx(d, "Örnek Müzik", 99.99) for d in monthly(date(2025, 6, 15), 7)]  # last 15.12.2025
    ds = dataset(txns, card_statements(date(2025, 6, 18), 16))  # statements until 18.09.2026
    assert series_status(ds) == {("Örnek Müzik", 99.99): "bitti"}


def test_subscription_runs_on_when_the_statements_stop_before_the_next_charge():
    txns = [tx(d, "Örnek Dergi", 49.90) for d in monthly(date(2025, 12, 12), 11)]  # last 12.10.2026
    ds = dataset(txns, card_statements(date(2025, 12, 13), 11))  # last statement cut 13.10.2026
    assert series_status(ds) == {("Örnek Dergi", 49.9): "devam"}


def test_listed_as_ended_is_cancelled_and_a_later_charge_is_reported():
    txns = [tx(d, "Örnek Dergi", 49.90) for d in monthly(date(2025, 12, 12), 11)]
    statements = card_statements(date(2025, 12, 13), 12)
    assert series_status(dataset(txns, statements, ended={"ORNEK DERGI": "2026-10"})) == {
        ("Örnek Dergi", 49.9): "iptal"
    }
    late = txns + [tx(date(2026, 11, 12), "Örnek Dergi", 49.90)]
    ds = dataset(late, statements, ended={"ORNEK DERGI": "2026-10"})
    assert series_status(ds) == {("Örnek Dergi", 49.9): "iptal_sonrasi"}
    finding = next(f for f in interpret(ds).findings if "iptalden sonra" in f.title)
    assert "12.11.2026" in finding.text


def test_two_subscriptions_with_one_payee_are_told_apart_by_amount():
    premium = [tx(d, "Örnek Video", 129.99) for d in monthly(date(2026, 1, 1), 8)]
    membership = [tx(d, "Örnek Video", 100.0, account="old") for d in monthly(date(2026, 1, 18), 8)]
    found = find_series(premium + membership, REGULAR)
    assert sorted(round(s.amount, 2) for s in found) == [100.0, 129.99]


def test_a_bill_moving_with_the_seasons_is_one_series_but_a_shop_is_none():
    amounts = [1500, 1200, 700, 320, 120, 80, 100, 150, 600]
    gas = [
        tx(d, "Doğalgaz (İGDAŞ)", a, category="Elektrik, Su & Doğalgaz", necessity="Gerekli")
        for d, a in zip(monthly(date(2026, 1, 20), 9), amounts)
    ]
    found = find_series(gas, REGULAR)
    assert len(found) == 1 and len(found[0].payments) == 9
    assert found[0].monthly == 150  # median of the last three: bills move from month to month
    market = [
        tx(d, "Örnek Market", a, category="Market & Gıda", necessity="Gerekli")
        for d, a in zip(monthly(date(2026, 1, 3), 9), amounts)
    ]
    assert find_series(market, REGULAR) == []


def test_an_unchanged_monthly_amount_is_regular_in_any_category():
    gym = [
        tx(d, "Spor Salonu", 900.0, category="Diğer Harcamalar", necessity="Belirsiz")
        for d in monthly(date(2026, 1, 5), 5)
    ]
    assert len(find_series(gym, REGULAR)) == 1


def test_old_series_on_an_account_without_statements_is_over():
    loan = [
        tx(d, "QNB ihtiyaç kredisi", 2500.0, kind="kredi_anapara", account="old") for d in monthly(date(2024, 1, 15), 5)
    ]
    recent = card_statements(date(2026, 1, 14), 9)
    assert series_status(dataset(loan, recent)) == {("QNB ihtiyaç kredisi", 2500.0): "bitti"}


def test_a_bill_paid_elsewhere_for_a_few_months_goes_on():
    # Paid from an account without documents in May and June: the two payments after the pause are too few
    # to be a series of their own and continue the bill. The same-day card fee keeps it out of the
    # once-a-month path, so the payments are chained by amount.
    bills = [
        (date(2026, 1, 9), 500.2),
        (date(2026, 1, 31), 540.0),
        (date(2026, 3, 10), 654.6),
        (date(2026, 4, 8), 654.6),
        (date(2026, 7, 30), 657.8),
        (date(2026, 9, 9), 657.8),
    ]
    fees = [(date(2026, 1, 9), 17.5), (date(2026, 9, 9), 23.02)]
    txns = [tx(d, "Türk Telekom", a, category="İnternet & Telefon", necessity="Gerekli") for d, a in bills + fees]
    ds = dataset(txns, card_statements(date(2026, 1, 10), 10))  # statements until 10.10.2026
    assert series_status(ds) == {("Türk Telekom", 657.8): "devam"}
    assert not any(f.title == "Görünmeyen faturalar" for f in interpret(ds).findings)


def test_a_once_a_month_bill_goes_on_after_a_pause_but_not_after_a_long_one():
    water = [
        tx(d, "Su (İSKİ)", a, category="Elektrik, Su & Doğalgaz", necessity="Gerekli")
        for d, a in zip(monthly(date(2026, 1, 20), 4), [200, 210, 170, 140])
    ]
    later = [
        tx(d, "Su (İSKİ)", a, category="Elektrik, Su & Doğalgaz", necessity="Gerekli")
        for d, a in zip(monthly(date(2026, 8, 25), 2), [85, 290])
    ]
    (s,) = find_series(water + later, REGULAR)
    assert s.last.date == date(2026, 9, 25) and len(s.payments) == 6
    years_later = [
        tx(d, "Su (İSKİ)", 280, category="Elektrik, Su & Doğalgaz", necessity="Gerekli")
        for d in monthly(date(2027, 1, 25), 2)
    ]
    (s,) = find_series(water + years_later, REGULAR)
    assert s.last.date == date(2026, 4, 20)


def test_price_change_needs_the_new_price_to_hold():
    rent = [
        tx(d, "Ev kirası", a, category="Kira", necessity="Gerekli", account="cash")
        for d, a in zip(monthly(date(2026, 1, 5), 10), [15000] * 6 + [16400] * 4)
    ]
    (s,) = find_series(rent, REGULAR)
    old, new, when = s.price_change()
    assert (old, new, when) == (15000, 16400, date(2026, 7, 5))
    s.payments = s.payments[:7]  # one payment at the new price is not a new price yet
    assert s.price_change() is None


# --- habits -----------------------------------------------------------------------------------


def test_habits_are_told_apart_and_only_habits_cost_from_now_on():
    window_cov = {"card": full_coverage("card", "2025-12", "2026-10", partial_last=0.4)}
    statements = card_statements(date(2025, 12, 14), 11)
    txns = []
    for i, d in enumerate(monthly(date(2025, 12, 3), 10)):  # every month, 2 orders of 500
        txns += [
            tx(d, "Getir", 500.0, category="Market & Gıda"),
            tx(d + timedelta(days=7), "Getir", 500.0, category="Market & Gıda"),
        ]
    txns += [tx(d, "Örnek Büfe", 1000.0, category="Tekel & Büfe") for d in monthly(date(2026, 5, 18), 5)]  # since May
    txns += [
        tx(date(2026, m, 10), "Hepsiburada", 1200.0, category="Online Alışveriş") for m in (1, 4, 8)
    ]  # now and then
    txns += [
        tx(date(2026, 1, 10), "Trendyol", 300.0, category="Online Alışveriş"),
        tx(date(2026, 3, 10), "Trendyol", 300.0, category="Online Alışveriş"),
    ]  # stopped in March
    txns.append(tx(date(2026, 8, 23), "sahibinden.com", 45000.0, category="Online Alışveriş"))  # once
    ds = dataset(txns, statements, coverage=window_cov)
    tl_ = timeline(ds)
    assert tl_.last_complete == "2026-09" and len(tl_.window) == 10
    found = {h.name: h for h in habits(ds, tl_, [])}
    assert (found["Getir"].status, found["Getir"].monthly) == ("duzenli", 1000.0)
    assert (found["Örnek Büfe"].status, found["Örnek Büfe"].since) == ("yeni", "2026-05")
    assert found["Örnek Büfe"].pattern.startswith("Mayıs 2026'dan beri")
    assert found["Hepsiburada"].status == "ara_sira"
    assert found["Hepsiburada"].monthly == pytest.approx(3600 / 10)  # spread over the window, not times twelve
    assert (found["Trendyol"].status, found["Trendyol"].monthly) == ("durdu", 0.0)
    assert (found["sahibinden.com"].status, found["sahibinden.com"].monthly) == ("tek", 0.0)


def test_a_habit_listed_as_ended_stopped():
    statements = card_statements(date(2025, 12, 14), 11)
    txns = [tx(d, "Örnek Büfe", 1000.0, category="Tekel & Büfe") for d in monthly(date(2026, 5, 18), 5)]
    ds = dataset(
        txns,
        statements,
        coverage={"card": full_coverage("card", "2025-12", "2026-10", 0.4)},
        ended={"ORNEK BUFE": "2026-09"},
    )
    (h,) = habits(ds, timeline(ds), [])
    assert (h.status, h.monthly) == ("durdu", 0.0)


# --- months, balances and debt ---------------------------------------------------------------


def test_complete_months_skip_a_partial_month_but_not_a_new_account():
    statements = card_statements(date(2026, 1, 14), 10) + [
        Statement(
            account="usd",
            cut_date=date(2026, 10, 31),
            currency="USD",
            source="u.xls",
            previous=0.0,
            total=590.0,
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
            account="card", cut_date=date(2026, 10, 13), currency="TL", source="k.pdf", previous=50.0, total=90000.5
        ),
        Statement(
            account="usd",
            cut_date=date(2026, 10, 31),
            currency="USD",
            source="u.xls",
            previous=0.0,
            total=500.0,
            start=date(2026, 4, 30),
            balances={"2026-10": 500.0},
        ),
        Statement(
            account="cash",
            cut_date=date(2026, 10, 31),
            currency="TL",
            source="v.xls",
            previous=0.0,
            total=-21000.75,
            start=date(2026, 1, 1),
            balances={"2026-09": -19000.0, "2026-10": -21000.75},
        ),
    ]
    paid = [
        tx(
            date(2026, 10, 14),
            "Kart ödemesi",
            40000.25,
            kind="kart_odemesi",
            account="cash",
            description="123456******1234 no.lu Kredi Kartına Ödenen Tutar",
        ),
        tx(
            date(2026, 10, 17),
            "Kart ödemesi",
            50000.25,
            kind="kart_odemesi",
            account="cash",
            description="123456******1234 no.lu Kredi Kartına Ödenen Tutar",
        ),
    ]
    ds = dataset(paid, statements)
    ds.rates = {"USD": [(date(2026, 5, 2), 46.4), (date(2026, 7, 1), 47.18)]}
    by_kind = {h.kind: h for h in holdings(ds)}
    assert by_kind["kart"].value == pytest.approx(0.0, abs=0.01)
    assert by_kind["doviz"].value == pytest.approx(500.0 * 47.18, abs=0.01)
    assert by_kind["kmh"].amount == pytest.approx(-21000.75)
    # Before its first statement a card counts with that statement's opening balance (50).
    assert debt_at(ds, date(2026, 9, 30)) == pytest.approx(19000.0 + 50.0)


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
            currency="TL",
            source="v.xls",
            previous=0.0,
            total=1000.0,
            start=date(2026, 10, 1),
        ),
        Statement(
            account="hisse",
            cut_date=date(2026, 9, 30),
            currency="TL",
            source="h.pdf",
            previous=0.0,
            total=5.0,
            start=date(2026, 9, 1),
            securities=[Security("ORNEK", "ÖRNEK A.Ş.", 20.0, 600.0, date(2026, 9, 30))],
        ),
        Statement(
            account="vadeli",
            cut_date=date(2024, 1, 17),
            currency="TL",
            source="c.pdf",
            previous=0.0,
            total=7500.0,
            start=date(2024, 1, 17),
        ),  # known only from the passbook sent when it was opened
    ]
    by_kind = {h.kind: h for h in holdings(dataset([], statements))}
    stocks, term = by_kind["yatirim"], by_kind["vadeli"]
    assert (stocks.value, stocks.as_of) == (605.0, date(2026, 9, 30))
    assert stocks.note.startswith("ORNEK 20 adet; 30.09.2026 piyasa değeriyle; nakit")
    assert (term.amount, term.value) == (7500.0, None) and term.note.startswith("son belge 17.01.2024")


# --- findings ---------------------------------------------------------------------------------


def test_interpretation_prices_the_steps_and_balances_the_budget():
    statements = card_statements(date(2025, 12, 14), 11, total=5000.0) + [
        Statement(
            account="cash",
            cut_date=date(2026, 10, 31),
            currency="TL",
            source="v.xls",
            previous=0.0,
            total=-20000.0,
            start=date(2025, 11, 30),
            balances={"2026-09": -20000.0, "2026-10": -20000.0},
        )
    ]
    coverage = {
        "card": full_coverage("card", "2025-12", "2026-10", 0.4),
        "cash": full_coverage("cash", "2025-12", "2026-10"),
    }
    txns = [
        tx(d, "Örnek (maaş)", -100000.0, kind="gelir", category="Maaş & İş Geliri", necessity="", account="cash")
        for d in monthly(date(2025, 12, 1), 11)
    ]
    txns += [
        tx(d, "Ev kirası", 20000.0, category="Kira", necessity="Gerekli", account="cash")
        for d in monthly(date(2025, 12, 5), 11)
    ]
    txns += [
        tx(d + timedelta(days=4 * k), "Getir", 1400.0, category="Market & Gıda")  # six orders a month: a shop
        for d in monthly(date(2025, 12, 2), 10)
        for k in range(6)
    ]
    txns += [
        tx(
            d,
            "TEB faiz & ücretleri",
            1000.0,
            kind="faiz_ucret",
            category="Ek Hesap (KMH) Faizi",
            necessity="Gereksiz",
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
    assert steps["Faiz ödemeyi bırakın"] == pytest.approx(1000.0)
    income, *spent, left = ins.budget
    assert income.now == 100000.0
    assert left.now == pytest.approx(income.now - sum(line.now for line in spent))
    assert left.plan - left.now == pytest.approx(sum(line.now - line.plan for line in spent))


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
    ],
)
def test_percent_takes_the_right_suffix(share, text):
    assert pct(share) == text


def test_years_take_the_right_suffix():
    assert since("2026-05") == "Mayıs 2026'dan beri"
    assert since("2025-12") == "Aralık 2025'ten beri"
    assert months_in(["2026-03", "2026-07", "2025-12"]) == "Mart ve Temmuz 2026'da, Aralık 2025'te"
