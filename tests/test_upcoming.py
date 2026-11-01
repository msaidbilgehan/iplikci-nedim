"""The calendar (F09): the series' next payments, the salary, card installments, loan installments and card dues."""

from datetime import date, timedelta
from decimal import Decimal

from iplikci.analysis import NO_STATEMENT, Dataset, ReceiptLine
from iplikci.domain.codes import AccountType, Necessity, PaymentKind, SeriesPeriod, TransactionKind
from iplikci.domain.models import Account, Statement, Transaction
from iplikci.insights import PeriodicSeries, find_series, interpret, settle, timeline
from iplikci.upcoming import (
    HORIZON,
    CardDue,
    add_months,
    card_due_items,
    expected_amount,
    horizon_end,
    income_items,
    installment_items,
    installments_left,
    loan_items,
    monthly_days,
    next_day,
    periodic_items,
    series_id,
    series_items,
    upcoming,
)

CARD = Account("card", "Örnek Kart •1234", "TEB", AccountType.CREDIT_CARD, number="1234")
CASH = Account("cash", "Örnek Vadesiz TL", "TEB", AccountType.CURRENT, number="111222333")
LOAN = Account("qnb-kredi-5678", "QNB İhtiyaç Kredisi …5678", "QNB", AccountType.LOAN, number="5678")
QNB = Account("qnb-cash", "QNB Vadesiz TL", "QNB", AccountType.CURRENT, number="444555666")
REGULAR = {"Kira", "Dijital Abonelikler", "Elektrik, Su & Doğalgaz"}


def tx(
    d: date,
    merchant: str,
    amount: Decimal | int,
    category: str = "Kira",
    kind: TransactionKind = TransactionKind.PURCHASE,
    account: str = "cash",
    installment: str = "",
) -> Transaction:
    return Transaction(
        date=d,
        description=merchant.upper(),
        amount=Decimal(amount),
        kind=kind,
        account=account,
        installment=installment,
        merchant=merchant,
        category=category,
        necessity=Necessity.REQUIRED,
        fingerprint=f"fp-{merchant[:4]}-{d.isoformat()}",
    )


def monthly(first: date, count: int) -> list[date]:
    out = [first]
    for _ in range(count - 1):
        out.append(add_months(out[-1], 1))
    return out


def dataset(txns: list[Transaction], statements: list[Statement] | None = None, **extra) -> Dataset:
    return Dataset(
        accounts={a.id: a for a in (CARD, CASH, LOAN, QNB)},
        statements=statements or [],
        transactions=sorted(txns, key=lambda t: t.date),
        documents=[],
        groups=[],
        categories={},
        regular=REGULAR,
        **extra,
    )


def running(series):
    for s in series:
        s.status = "devam"
    return series


# --- days ---------------------------------------------------------------------------------------------


def test_a_monthly_payment_comes_on_its_usual_day_from_the_month_after_its_last():
    rent = [tx(d, "Ev kirası", 15000) for d in monthly(date(2026, 5, 3), 6)]  # last on 03.10.2026
    assert monthly_days(rent, date(2026, 11, 15), date(2027, 1, 13)) == [date(2026, 12, 3), date(2027, 1, 3)]
    assert monthly_days(rent, date(2026, 10, 1), date(2026, 11, 30)) == [date(2026, 11, 3)]  # not October's again


def test_a_salary_paid_around_the_turn_of_the_month_keeps_to_the_first_and_is_not_paid_twice():
    days = [date(2026, 7, 1), date(2026, 7, 31), date(2026, 9, 1), date(2026, 10, 1), date(2026, 10, 30)]
    salary = [tx(d, "Örnek İşveren", -40000, kind=TransactionKind.INCOME) for d in days]
    # The 30th and the 31st are a day or two before the 1st, not the 30th of the next month; November's salary
    # came on 30 October, so the next one is December's.
    assert monthly_days(salary, date(2026, 11, 5), date(2027, 1, 3)) == [date(2026, 12, 1), date(2027, 1, 1)]


def test_a_payment_on_the_months_last_day_stays_there_and_another_day_is_its_day_of_the_month():
    gym = [tx(d, "Spor Salonu", 900) for d in (date(2026, 7, 31), date(2026, 8, 31), date(2026, 9, 30))]
    expected = [date(2026, 10, 31), date(2026, 11, 30), date(2026, 12, 31)]
    assert monthly_days(gym, date(2026, 10, 1), date(2026, 12, 31)) == expected
    dues = [tx(d, "Site aidatı", 1250) for d in monthly(date(2026, 6, 15), 4)]
    assert monthly_days(dues, date(2026, 10, 1), date(2026, 11, 30)) == [date(2026, 10, 15), date(2026, 11, 15)]
    late = [tx(d, "Örnek Dergi", 50) for d in (date(2026, 10, 29), date(2026, 11, 29), date(2026, 12, 29))]
    assert monthly_days(late, date(2027, 1, 1), date(2027, 3, 1)) == [date(2027, 1, 29), date(2027, 2, 28)]


def test_the_next_day_of_a_series_may_be_past_and_a_periodic_one_is_a_period_after_the_last():
    (rent,) = find_series([tx(d, "Ev kirası", 15000) for d in monthly(date(2026, 5, 3), 6)], REGULAR)
    assert next_day(rent) == date(2026, 11, 3)
    yearly = PeriodicSeries("Örnek Sigorta", [tx(date(2025, 3, 10), "Örnek Sigorta", 4000)], period=SeriesPeriod.YEAR)
    yearly.payments.append(tx(date(2026, 3, 12), "Örnek Sigorta", 4400))
    assert next_day(yearly) == date(2027, 3, 14)  # 367 days, like the last gap
    assert expected_amount(yearly) == Decimal(4400)
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28) and add_months(date(2026, 1, 31), 13) == date(
        2027, 2, 28
    )


# --- items --------------------------------------------------------------------------------------------


def test_running_series_bring_their_next_payments_from_the_account_last_paid_from():
    rent = [tx(d, "Ev kirası", 15000) for d in monthly(date(2026, 5, 3), 5)]
    rent.append(tx(date(2026, 10, 3), "Ev kirası", 15000, account="card"))  # paid from the card the last time
    gas = [
        tx(d, "Doğalgaz", a, category="Elektrik, Su & Doğalgaz")
        for d, a in zip(monthly(date(2026, 5, 6), 6), [500, 250, 150, 120, 200, 600])
    ]
    ended = [tx(d, "Eski Dergi", 50, category="Dijital Abonelikler") for d in monthly(date(2025, 1, 9), 5)]
    series = find_series(rent + gas + ended, REGULAR)
    for s in series:
        s.status = "bitti" if s.merchant == "Eski Dergi" else "devam"
    found = series_items(dataset([]), series, date(2026, 11, 15), date(2027, 1, 13))
    assert [(d.day, d.title, d.account, d.amount) for d in found] == [
        (date(2026, 12, 3), "Ev kirası", "card", Decimal(15000)),
        (date(2027, 1, 3), "Ev kirası", "card", Decimal(15000)),
        (date(2026, 12, 6), "Doğalgaz", "cash", Decimal(200)),
        (date(2027, 1, 6), "Doğalgaz", "cash", Decimal(200)),
    ]
    rent_item, _, gas_item, _ = found
    assert rent_item.kind == PaymentKind.REGULAR and rent_item.basis == "son ödeme 03.10.2026: 15.000,00 TL"
    assert gas_item.basis == "son üç ödemenin medyanı (Ağustos 2026 – Ekim 2026)"  # the amounts move: a median
    assert rent_item.series == series_id(series[0]) == "fp-Ev k-2026-05-03"
    assert rent_item.rows == ("fp-Ev k-2026-08-03", "fp-Ev k-2026-09-03", "fp-Ev k-2026-10-03")


def test_a_series_paid_after_its_cancellation_is_still_expected_with_a_word_about_it():
    (s,) = running(
        find_series(
            [tx(d, "Örnek Dergi", 50, category="Dijital Abonelikler") for d in monthly(date(2026, 6, 9), 5)], REGULAR
        )
    )
    s.status = "iptal_sonrasi"
    (first, *_) = series_items(dataset([]), [s], date(2026, 11, 1), date(2026, 12, 30))
    assert first.day == date(2026, 11, 9) and first.basis.endswith("iptal edildi ama ödeme sürüyor")


def test_the_salary_is_expected_on_its_day_at_the_median_of_its_last_three_amounts():
    amounts = [40000, 40000, 41000, 45000, 41500]
    salary = [
        tx(d, "Örnek İşveren", -a, category="Maaş", kind=TransactionKind.INCOME)
        for d, a in zip(monthly(date(2026, 6, 1), 5), amounts)
    ]
    series = running(find_series(salary, set()))
    found = income_items(series, date(2026, 11, 1), date(2026, 12, 30))
    assert [(d.day, d.kind, d.amount) for d in found] == [
        (date(2026, 11, 1), PaymentKind.INCOME, Decimal(-41500)),  # money in: below zero, as a Transaction's
        (date(2026, 12, 1), PaymentKind.INCOME, Decimal(-41500)),
    ]
    assert found[0].basis == "son üç tutarın medyanı (Ağustos 2026 – Ekim 2026)"


def test_a_periodic_payment_is_expected_a_period_after_the_last():
    s = PeriodicSeries(
        "Örnek Sigorta",
        [tx(date(2025, 1, 12), "Örnek Sigorta", 4000), tx(date(2026, 1, 10), "Örnek Sigorta", 4800)],
        status="devam",
        period=SeriesPeriod.YEAR,
    )
    (found,) = periodic_items([s], date(2026, 11, 20), horizon_end(date(2026, 11, 20)))
    assert (found.day, found.kind, found.amount) == (date(2027, 1, 8), PaymentKind.PERIODIC, Decimal(4800))
    assert found.basis == "yılda bir; son ödeme 10.01.2026: 4.800,00 TL"
    s.status = "bitti"
    assert periodic_items([s], date(2026, 11, 20), horizon_end(date(2026, 11, 20))) == []


def card_statement(cut: date, rows: list[Transaction]) -> Statement:
    return Statement(
        account="card",
        cut_date=cut,
        currency="TRY",
        source="k.pdf",
        previous=Decimal(0),
        total=Decimal(0),
        transactions=rows,
    )


def test_installments_left_come_from_the_cards_newest_statement_one_on_each_later_cut():
    older = card_statement(
        date(2026, 9, 15), [tx(date(2026, 1, 20), "Örnek Elektronik", 500, account="card", installment="7/12")]
    )
    newest = card_statement(
        date(2026, 10, 15),
        [
            tx(date(2026, 1, 20), "Örnek Elektronik", 500, account="card", installment="8/12"),
            tx(date(2026, 7, 2), "Örnek Mobilya", 1000, account="card", installment="3/3"),  # the last one: none left
            tx(date(2026, 10, 1), "Örnek Market", 300, account="card"),
        ],
    )
    ds = dataset([], [older, newest])
    (left,) = installments_left(ds)
    assert (left.title, left.left, left.remaining, left.last) == (
        "Örnek Elektronik",
        4,
        Decimal(2000),
        date(2027, 2, 15),
    )
    found = installment_items(ds, date(2026, 11, 1), horizon_end(date(2026, 11, 1)))
    assert [(d.day, d.title, d.account, d.amount) for d in found] == [
        (date(2026, 11, 15), "Örnek Elektronik (9/12)", "card", Decimal(500)),
        (date(2026, 12, 15), "Örnek Elektronik (10/12)", "card", Decimal(500)),
    ]
    assert found[0].kind == PaymentKind.INSTALLMENT and found[0].basis.startswith("8/12. taksit 15.10.2026 ekstresinde")


def loan_receipts(days: list[date]) -> tuple[list[Transaction], list[ReceiptLine]]:
    txns, lines = [], []
    for d in days:
        principal = tx(d, "QNB ihtiyaç kredisi", 2000, kind=TransactionKind.LOAN_PRINCIPAL, account=LOAN.id)
        cost = tx(d, "QNB ihtiyaç kredisi", Decimal("512.40"), kind=TransactionKind.INTEREST_FEE, account=LOAN.id)
        txns += [principal, cost]
        lines += [ReceiptLine(t, f"qnb-{d:%Y%m%d}", NO_STATEMENT, t.amount) for t in (principal, cost)]
    return txns, lines


def test_a_loans_next_installments_come_from_its_receipts_at_their_whole_amount():
    txns, lines = loan_receipts(monthly(date(2026, 7, 5), 4))  # last on 05.10.2026
    ds = dataset(txns, receipts=lines)
    found = loan_items(ds, timeline(ds), [], date(2026, 11, 1), date(2026, 12, 30))
    assert [(d.day, d.kind, d.account, d.amount) for d in found] == [
        (date(2026, 11, 5), PaymentKind.LOAN, LOAN.id, Decimal("2512.40")),
        (date(2026, 12, 5), PaymentKind.LOAN, LOAN.id, Decimal("2512.40")),
    ]
    assert found[0].title == LOAN.label and "kalan taksit sayısı belgelerde yok" in found[0].basis
    assert len(found[0].rows) == 2  # the last receipt's principal and interest rows


def test_a_loan_whose_receipts_stopped_or_that_its_bank_list_books_is_no_item():
    txns, lines = loan_receipts(monthly(date(2026, 1, 5), 3))  # last on 05.03.2026
    later = [tx(date(2026, 10, 1), "Örnek Market", 300)]
    ds = dataset(txns + later, receipts=lines)
    assert loan_items(ds, timeline(ds), [], date(2026, 11, 1), date(2026, 12, 30)) == []  # over 90 days late
    txns, lines = loan_receipts(monthly(date(2026, 7, 5), 4))
    booked = running(
        find_series(
            [
                tx(d, "QNB kredi taksidi", 2512, kind=TransactionKind.LOAN_PRINCIPAL, account=QNB.id)
                for d in monthly(date(2026, 7, 5), 4)
            ],
            REGULAR,
        )
    )
    ds = dataset(txns, receipts=lines)
    assert loan_items(ds, timeline(ds), booked, date(2026, 11, 1), date(2026, 12, 30)) == []


def test_card_dues_come_from_the_statements_the_caller_reads():
    dues = [
        CardDue("card", date(2026, 11, 25), Decimal("12500.75"), Decimal("2500.15")),
        CardDue("card", date(2026, 10, 25), Decimal(9000), Decimal(1800)),  # before today
        CardDue("card", date(2026, 12, 25), Decimal(0), Decimal(0)),  # nothing to pay
    ]
    (found,) = card_due_items(dataset([]), dues, date(2026, 11, 1), date(2026, 12, 30))
    assert (found.day, found.kind, found.title, found.account) == (
        date(2026, 11, 25),
        PaymentKind.CARD_DUE,
        CARD.label,
        "card",
    )
    assert (found.amount, found.minimum) == (Decimal("12500.75"), Decimal("2500.15"))
    assert found.basis == "ekstrenin dönem borcu 12.500,75 TL, asgari ödeme 2.500,15 TL"


def test_the_calendar_lists_every_kind_by_day_for_sixty_days():
    salary = [
        tx(d, "Örnek İşveren", -40000, category="Maaş", kind=TransactionKind.INCOME)
        for d in monthly(date(2026, 5, 1), 6)
    ]
    rent = [tx(d, "Ev kirası", 15000) for d in monthly(date(2026, 5, 3), 6)]
    statements = [
        Statement(
            account="cash",
            cut_date=date(2026, 10, 31),
            currency="TRY",
            source="v.xls",
            previous=Decimal(0),
            total=Decimal(50000),
            start=date(2026, 5, 1),
        )
    ]
    ds = dataset(salary + rent, statements)
    ins = interpret(ds)
    today = date(2026, 11, 15)
    found = upcoming(ds, ins, today, [CardDue("card", date(2026, 11, 25), Decimal(5000))])
    assert [(d.day, d.kind) for d in found] == [
        (date(2026, 11, 25), PaymentKind.CARD_DUE),
        (date(2026, 12, 1), PaymentKind.INCOME),
        (date(2026, 12, 3), PaymentKind.REGULAR),
        (date(2027, 1, 1), PaymentKind.INCOME),
        (date(2027, 1, 3), PaymentKind.REGULAR),
    ]
    assert horizon_end(today) == today + timedelta(days=HORIZON - 1) == date(2027, 1, 13)


def test_an_ended_series_and_settle_agree_on_what_runs():
    (s,) = find_series(
        [tx(d, "Eski Dergi", 50, category="Dijital Abonelikler") for d in monthly(date(2025, 1, 9), 5)], REGULAR
    )
    settle(s, {"cash": date(2026, 10, 31)}, {}, date(2026, 10, 31))
    assert s.status == "bitti" and series_items(dataset([]), [s], date(2026, 11, 1), date(2026, 12, 30)) == []
