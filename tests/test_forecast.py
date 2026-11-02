"""The cash-flow forecast (F09): where each account starts, what it pays and receives, and where it goes below zero."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from iplikci.analysis import CONFIRMED, NO_STATEMENT, PROVISIONAL, Dataset, ReceiptLine
from iplikci.domain.codes import AccountType, EvidenceStatus, Necessity, PaymentKind, TransactionKind
from iplikci.domain.models import Account, Statement, Transaction
from iplikci.forecast import (
    ESTIMATE,
    Spread,
    Start,
    counted_from,
    forecast,
    paid_share,
    paying_account,
    spreads,
    start_of,
)
from iplikci.insights import interpret
from iplikci.upcoming import Due, add_months, upcoming

CASH = Account("cash", "Örnek Vadesiz TL", "TEB", AccountType.CURRENT, number="111222333")
CARD = Account("card", "Örnek Kart •1234", "TEB", AccountType.CREDIT_CARD, number="1234")
VAKIF = Account("vakif", "Vakıfbank Vadesiz TL …4321", "Vakıfbank", AccountType.CURRENT, number="****4321")
USD = Account("usd", "Örnek Dolar", "TEB", AccountType.FX, currency="USD", number="555")
OLD = Account("old", "Örnek Vadeli TL", "İş Bankası", AccountType.DEPOSIT, number="1234-0765432")
GARANTI = Account("garanti", "Garanti Vadesiz TL 1234567", "Garanti BBVA", AccountType.CURRENT, number="1234567")
LOAN = Account("qnb-kredi-5678", "QNB İhtiyaç Kredisi …5678", "QNB", AccountType.LOAN, number="5678")
QNB = Account("qnb-cash", "QNB Vadesiz TL", "QNB", AccountType.CURRENT, number="444555666")
QNB_OTHER = Account("qnb-other", "QNB Ek Hesap", "QNB", AccountType.OVERDRAFT, number="444555777")
MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]


def tx(
    d: date,
    merchant: str,
    amount: Decimal | int | str,
    kind: TransactionKind = TransactionKind.PURCHASE,
    account: str = "cash",
    category: str = "Diğer Harcamalar",
    description: str = "",
    balance: Decimal | int | None = None,
) -> Transaction:
    return Transaction(
        date=d,
        description=description or merchant.upper(),
        amount=Decimal(amount),
        kind=kind,
        account=account,
        merchant=merchant,
        category=category,
        necessity=Necessity.REQUIRED,
        balance=None if balance is None else Decimal(balance),
    )


def receipt(
    d: date,
    amount: int,
    status: EvidenceStatus,
    account: str = "cash",
    balance: int | None = None,
    query: int = 0,
) -> ReceiptLine:
    """A receipt's or a notice's row; a notice's receipt key ends in its query number, as Vakıfbank's do."""
    t = tx(d, "Gelen ya da giden FAST", amount, TransactionKind.P2P_TRANSFER, account, balance=balance)
    return ReceiptLine(t, f"{account}-{d:%Y%m%d}-{query or amount}", status, Decimal(amount))


def account_list(account: str, start: date, cut: date, total: int) -> Statement:
    return Statement(
        account=account,
        cut_date=cut,
        currency="USD" if account == "usd" else "TRY",
        source="liste.xls",
        previous=Decimal(0),
        total=Decimal(total),
        start=start,
    )


def card_statement(cut: date, total: int, paid: int = 0) -> Statement:
    rows = [tx(cut, "Ödemeniz için teşekkürler", -paid, TransactionKind.CARD_PAYMENT, "card")] if paid else []
    return Statement(
        account="card",
        cut_date=cut,
        currency="TRY",
        source="k.pdf",
        previous=None,
        total=Decimal(total),
        transactions=rows,
    )


def dataset(
    txns: list[Transaction] | None = None,
    statements: list[Statement] | None = None,
    accounts: tuple[Account, ...] = (CASH, CARD, VAKIF),
    **extra,
) -> Dataset:
    return Dataset(
        accounts={a.id: a for a in accounts},
        statements=statements or [],
        transactions=sorted(txns or [], key=lambda t: (t.date, t.account, t.description)),
        documents=[],
        groups=[],
        categories={},
        regular={"Kira"},
        **extra,
    )


def due(day: date, title: str, account: str, amount: int | str, kind: PaymentKind = PaymentKind.REGULAR) -> Due:
    return Due(day, kind, title, account, Decimal(amount), "beklenen")


# --- the start ----------------------------------------------------------------------------------------------


def test_the_start_is_the_newest_list_balance_moved_by_the_receipts_after_it():
    rows = [
        receipt(date(2026, 10, 30), 2000, CONFIRMED),  # the list shows it: in its closing balance
        receipt(date(2026, 11, 1), 1000, CONFIRMED),  # the list booked it a day early: in the balance too
        receipt(date(2026, 11, 3), 15000, PROVISIONAL),
        receipt(date(2026, 11, 4), -500, PROVISIONAL),  # money in
    ]
    ds = dataset(statements=[account_list("cash", date(2026, 5, 1), date(2026, 10, 31), 50000)], receipts=rows)
    assert start_of(ds, "cash") == Start(
        Decimal(35500), Decimal(50000), date(2026, 10, 31), False, 2, date(2026, 11, 4)
    )


def test_an_account_known_from_notices_starts_from_the_newest_balance_a_notice_prints():
    rows = [
        receipt(date(2026, 10, 20), -2000, NO_STATEMENT, "vakif", balance=8000),
        receipt(date(2026, 10, 25), 3000, NO_STATEMENT, "vakif", balance=5000),
        receipt(date(2026, 10, 28), 1000, NO_STATEMENT, "vakif"),  # an outflow notice prints no balance
    ]
    assert start_of(dataset(receipts=rows), "vakif") == Start(
        Decimal(4000), Decimal(5000), date(2026, 10, 25), True, 1, date(2026, 10, 28)
    )


def test_of_two_notices_on_one_day_the_later_one_is_the_one_no_other_row_goes_on_from():
    first = receipt(date(2026, 11, 2), 1000, NO_STATEMENT, "vakif", balance=9000, query=9)
    second = receipt(date(2026, 11, 2), 500, NO_STATEMENT, "vakif", balance=8500, query=1)  # query numbers out of order
    for rows in ([first, second], [second, first]):
        start = start_of(dataset(receipts=rows), "vakif")
        assert start is not None and (start.stated, start.balance, start.moves) == (Decimal(8500), Decimal(8500), 0)


def test_a_list_closes_its_whole_day_but_a_later_notice_is_newer():
    statements = [account_list("vakif", date(2026, 10, 1), date(2026, 10, 31), 7000)]
    same_day = receipt(date(2026, 10, 31), 100, CONFIRMED, "vakif", balance=7100)
    later = receipt(date(2026, 11, 5), 200, PROVISIONAL, "vakif", balance=6800)
    start = start_of(dataset(statements=statements, receipts=[same_day]), "vakif")
    assert start is not None and (start.on, start.stated, start.notice) == (date(2026, 10, 31), Decimal(7000), False)
    start = start_of(dataset(statements=statements, receipts=[same_day, later]), "vakif")
    assert start is not None and (start.on, start.stated, start.notice) == (date(2026, 11, 5), Decimal(6800), True)
    assert start_of(dataset(receipts=[receipt(date(2026, 10, 1), 100, NO_STATEMENT, "vakif")]), "vakif") is None


# --- money out spread over the days -------------------------------------------------------------------------


def test_money_out_outside_the_series_is_the_median_month_of_the_last_complete_months():
    txns = [tx(add_months(date(2026, 4, 3), i), "Ev kirası", 15000, category="Kira") for i in range(7)]  # a series
    for i, month in enumerate(MONTHS):
        day = date(int(month[:4]), int(month[5:]), 10)
        txns += [
            tx(day, "TEB ücretleri", 10, TransactionKind.INTEREST_FEE),
            tx(day, "Kendi hesabım", 5000, TransactionKind.OWN_TRANSFER),  # its other side is not projected
            tx(day, "Eski Spor", [500, 900, 300, 700, 400, 800][i]),  # listed as ended
            tx(day, "Kart ödemesi", 8000, TransactionKind.CARD_PAYMENT),
        ]
    txns += [tx(date(2026, m, 20), "Ayşe Örnek", 1000, TransactionKind.P2P_TRANSFER) for m in (4, 5, 6)]
    txns.append(tx(date(2026, 7, 20), "Ayşe Örnek", 3000, TransactionKind.P2P_TRANSFER))
    coverage = {"cash": dict.fromkeys(MONTHS, 1.0) | {"2026-10": 0.5}}
    statements = [account_list("cash", date(2026, 4, 1), date(2026, 10, 15), 20000)]
    ds = dataset(txns, statements, coverage=coverage, ended={"ESKI SPOR": "2026-09"})
    spend, cards = spreads(ds, interpret(ds), "cash")
    assert spend == Spread(Decimal(1010), tuple(MONTHS))  # 10 in fees each month, 1000 to a person in four of them
    assert cards == Spread(Decimal(8000), tuple(MONTHS))
    assert spreads(ds, interpret(ds), "vakif") == (None, None)  # no complete month: nothing to spread


def test_a_spread_covers_each_months_days_and_only_after_its_day():
    spread = Spread(Decimal(3000), ("2026-09",), after=date(2026, 11, 25))
    assert spread.on(date(2026, 11, 25)) == 0 and spread.on(date(2026, 11, 26)) == 100
    assert sum(Spread(Decimal(3100), ("2026-09",)).on(date(2026, 12, d)) for d in range(1, 32)) == 3100


# --- cards ----------------------------------------------------------------------------------------------------


def card_dataset(paid: tuple[int, int, int]) -> Dataset:
    statements = [
        card_statement(date(2026, 7, 15), 10000),
        card_statement(date(2026, 8, 15), 8000, paid[0]),
        card_statement(date(2026, 9, 15), 6000, paid[1]),
        card_statement(date(2026, 10, 15), 9000, paid[2]),
        account_list("cash", date(2026, 7, 1), date(2026, 10, 31), 30000),
    ]
    payments = [
        tx(d, "Kart ödemesi", a, TransactionKind.CARD_PAYMENT, description="5555 66** **** 1234 NO.LU KARTA ÖDEME")
        for d, a in zip((date(2026, 8, 1), date(2026, 9, 1), date(2026, 10, 1)), paid, strict=True)
    ]
    return dataset(payments, statements)


def test_a_card_is_paid_from_the_account_that_paid_it_last_at_the_share_the_user_pays():
    ds = card_dataset((10000, 8000, 3000))
    assert paying_account(ds, "card") == "cash"
    share = paid_share(ds, "card")
    assert share is not None and (share.share, share.full, share.of) == (Decimal(1), 2, 3)
    item = Due(
        date(2026, 11, 25),
        PaymentKind.CARD_DUE,
        CARD.label,
        "card",
        Decimal(9000),
        "dönem borcu",
        minimum=Decimal(1800),
    )
    (cash,) = forecast(ds, interpret(ds), date(2026, 11, 15), [item]).accounts
    (counted,) = cash.items
    assert (counted.account, counted.amount) == ("cash", Decimal(9000))
    assert counted.basis.endswith("son 3 ekstreden 2 tanesinin tamamı ödendi, tamamı sayıldı")
    # Partly paid statements: the median share, never below the minimum payment.
    partial = card_dataset((4000, 4000, 3600))  # 40%, 50% and 60% of the statements before
    (cash,) = forecast(partial, interpret(partial), date(2026, 11, 15), [item]).accounts
    assert cash.items[0].amount == Decimal(4500) and cash.items[0].basis.endswith("ekstrenin %50'si")


def test_a_card_nobody_is_seen_paying_stays_out_of_the_accounts():
    ds = dataset(statements=[account_list("cash", date(2026, 7, 1), date(2026, 10, 31), 30000)])
    item = Due(date(2026, 11, 25), PaymentKind.CARD_DUE, CARD.label, "card", Decimal(9000), "dönem borcu")
    result = forecast(ds, interpret(ds), date(2026, 11, 15), [item])
    assert result.elsewhere == [item] and result.accounts[0].items == []


# --- the forecast ---------------------------------------------------------------------------------------------


def test_the_forecast_runs_day_by_day_and_says_where_an_account_goes_below_zero():
    ds = dataset(statements=[account_list("cash", date(2026, 7, 1), date(2026, 10, 31), 1000)])
    items = [
        due(date(2026, 11, 3), "Ev kirası", "cash", 15000),
        due(date(2026, 11, 9), "Örnek Müzik", "card", "99.99"),  # on the card: it reaches the account as a card payment
        due(date(2026, 12, 1), "Örnek İşveren", "cash", -40000, PaymentKind.INCOME),
    ]
    result = forecast(ds, interpret(ds), date(2026, 11, 1), items)
    assert (result.label, result.today, result.end) == (ESTIMATE, date(2026, 11, 1), date(2026, 12, 30))
    (cash,) = result.accounts
    assert len(cash.days) == 60 and cash.days[0] == (date(2026, 11, 1), Decimal(1000))
    assert cash.negative == (date(2026, 11, 3), Decimal(-14000)) == cash.lowest
    assert cash.end == Decimal(26000)
    assert [item.title for item in cash.items] == ["Ev kirası", "Örnek İşveren"]
    assert result.elsewhere == [items[1]]
    assert "Kartla ödenen 1 kalem kartın ekstresine girer; hesaptan kart ödemesiyle çıkar." in result.notes
    assert cash.notes[0] == (
        "Başlangıç: 31.10.2026 tarihli hesap dökümünün kapanış bakiyesi 1.000,00 TL; 31.10.2026 sonrasının "
        "hareketleri belgelerde yok."
    )
    assert cash.notes[1].startswith("Seri dışı çıkışlar tahmin edilmedi")
    # No overdraft rate in the documents: no interest estimate.
    assert cash.interest is None and cash.notes[-1] == "KMH faiz oranı belgelerde yazmadığı için faiz tahmin edilmedi."
    (rated,) = forecast(ds, interpret(ds), date(2026, 11, 1), items, overdraft_rates={"cash": Decimal("0.05")}).accounts
    assert rated.interest == Decimal("644.38")  # 14.000 TL for the 28 days to 30 November at 5% a month
    assert rated.notes[-1] == "KMH faizi: belgedeki aylık %5,00 oranıyla, eksi günler için yaklaşık 644,38 TL."


def test_the_spread_lowers_the_balance_every_day_by_its_months_share():
    coverage = {"cash": dict.fromkeys(MONTHS, 1.0) | {"2026-10": 0.5}}
    txns = [tx(date(int(m[:4]), int(m[5:]), 10), "Ayşe Örnek", 3000, TransactionKind.P2P_TRANSFER) for m in MONTHS]
    ds = dataset(txns, [account_list("cash", date(2026, 4, 1), date(2026, 10, 15), 10000)], coverage=coverage)
    (cash,) = forecast(ds, interpret(ds), date(2026, 11, 1), []).accounts
    # The list ends on 15 October: the 16 days after it spend their share too (16 × 3.000 / 31 = 1.548,39 TL).
    assert cash.days[0] == (date(2026, 11, 1), Decimal("8351.61"))
    assert cash.days[29] == (date(2026, 11, 30), Decimal("5451.61"))
    assert cash.notes[1] == (
        "16.10.2026–31.10.2026 arası için belgelerin henüz göstermediği beklenenler de sayıldı: seri dışı "
        "çıkışlardan 1.548,39 TL."
    )
    assert cash.notes[2] == (
        "Seri dışı çıkışlar: Nisan 2026 – Eylül 2026 arasındaki 6 tam ayın medyanı, ayda 3.000,00 TL, günlere yayıldı."
    )


def test_what_was_expected_on_the_days_the_documents_do_not_reach_yet_is_in_todays_balance():
    # The list ends on 31 October and today is 2 November: the salary due on the 1st is expected, not lost.
    ds = dataset(statements=[account_list("cash", date(2026, 7, 1), date(2026, 10, 31), 1000)])
    today = date(2026, 11, 2)
    assert counted_from(ds, today) == date(2026, 11, 1)
    items = [
        due(date(2026, 10, 31), "Eski kalem", "cash", 500),  # the list's own day: its balance knows of it
        due(date(2026, 11, 1), "Örnek İşveren", "cash", -40000, PaymentKind.INCOME),
        due(date(2026, 11, 1), "Örnek Müzik", "card", "99.99"),  # nobody's balance: not listed before today
        due(date(2026, 11, 3), "Ev kirası", "cash", 15000),
    ]
    result = forecast(ds, interpret(ds), today, items)
    (cash,) = result.accounts
    assert cash.days[0] == (today, Decimal(41000)) and cash.days[1] == (date(2026, 11, 3), Decimal(26000))
    assert cash.lowest == (date(2026, 11, 3), Decimal(26000)) and cash.negative is None
    assert [item.title for item in cash.items] == ["Örnek İşveren", "Ev kirası"]
    assert result.elsewhere == []
    assert cash.notes[1] == (
        "01.11.2026 günü için belgelerin henüz göstermediği beklenenler de sayıldı: 1 kalem (+40.000,00 TL)."
    )
    # A balance that knows of today needs nothing before it.
    assert counted_from(ds, date(2026, 11, 1)) == date(2026, 11, 1)


def test_a_balance_older_than_the_days_ahead_is_not_carried_over_that_many_days_of_guesses():
    ds = dataset(statements=[account_list("cash", date(2026, 1, 1), date(2026, 1, 31), 1000)])
    today = date(2026, 11, 2)  # 275 days after the list: what came between is anyone's guess
    assert counted_from(ds, today) == today
    items = [due(date(2026, 3, 3), "Ev kirası", "cash", 15000), due(date(2026, 11, 3), "Ev kirası", "cash", 15000)]
    (cash,) = forecast(ds, interpret(ds), today, items).accounts
    assert cash.days[0] == (today, Decimal(1000)) and [item.day for item in cash.items] == [date(2026, 11, 3)]
    assert cash.notes[1] == "Son bakiye 275 gün önceki: aradaki günler tahmin edilmedi, öngörü o bakiyeden başlıyor."


def test_the_calendar_brings_the_forecast_the_days_before_today_its_documents_do_not_reach():
    salary = [
        tx(d, "Örnek İşveren", -40000, TransactionKind.INCOME, category="Maaş")
        for d in (date(2026, m, 1) for m in range(5, 11))
    ]
    ds = dataset(salary, [account_list("cash", date(2026, 5, 1), date(2026, 10, 31), 1000)])
    ins, today = interpret(ds), date(2026, 11, 2)
    assert [item.day for item in upcoming(ds, ins, today)] == [date(2026, 12, 1)]  # the calendar looks ahead
    items = upcoming(ds, ins, today, since=counted_from(ds, today))
    assert [item.day for item in items] == [date(2026, 11, 1), date(2026, 12, 1)]
    (cash,) = forecast(ds, ins, today, items).accounts
    assert cash.days[0] == (today, Decimal(41000))


def test_accounts_without_a_balance_known_today_are_left_out_and_say_why():
    statements = [
        account_list("cash", date(2026, 7, 1), date(2026, 10, 31), 1000),
        account_list("usd", date(2026, 7, 1), date(2026, 10, 31), 500),
        account_list("old", date(2024, 1, 17), date(2024, 1, 17), 7500),  # only the passbook sent when it opened
    ]
    rows = [receipt(date(2026, 9, 10), 1250, NO_STATEMENT, "garanti")]  # receipts print no balance
    ds = dataset(statements=statements, receipts=rows, accounts=(CASH, USD, OLD, GARANTI))
    result = forecast(ds, interpret(ds), date(2026, 11, 1), [])
    assert [a.account for a in result.accounts] == ["cash"]
    assert result.skipped == [  # by the accounts' labels
        ("garanti", "bakiyesi hiçbir belgede yazmıyor"),
        ("usd", "döviz ya da altın hesabı: değeri kurla değişir, öngörü TL hesapları içindir"),
        ("old", "son bakiye 17.01.2024 tarihli; bugünkü bakiyesi belgelerde yok"),
    ]


def test_a_loan_installment_leaves_its_banks_only_tl_account():
    statements = [account_list("qnb-cash", date(2026, 7, 1), date(2026, 10, 31), 5000)]
    item = due(date(2026, 11, 5), LOAN.label, LOAN.id, "2512.40", PaymentKind.LOAN)
    ds = dataset(statements=statements, accounts=(QNB, LOAN))
    (qnb,) = forecast(ds, interpret(ds), date(2026, 11, 1), [item]).accounts
    assert qnb.items[0].account == "qnb-cash" and qnb.end == Decimal("2487.60")
    assert qnb.items[0].basis.endswith("ödeyen hesap QNB Vadesiz TL sayıldı (bankanın tek TL hesabı)")
    two = statements + [account_list("qnb-other", date(2026, 7, 1), date(2026, 10, 31), 100)]
    ds = dataset(statements=two, accounts=(QNB, QNB_OTHER, LOAN))
    result = forecast(ds, interpret(ds), date(2026, 11, 1), [item])
    assert result.elsewhere == [item] and all(not a.items for a in result.accounts)


@pytest.mark.parametrize("days", [1, 14, 60])
def test_the_forecast_has_one_balance_a_day(days):
    ds = dataset(statements=[account_list("cash", date(2026, 7, 1), date(2026, 10, 31), 1000)])
    (cash,) = forecast(ds, interpret(ds), date(2026, 11, 1), [], days=days).accounts
    assert len(cash.days) == days and cash.days[-1][0] == date(2026, 10, 31) + timedelta(days=days)


# --- which days below zero warn ----------------------------------------------------------------------------------


def test_an_overdraft_account_below_zero_warns_of_nothing_its_credit_in_use_is_no_news():
    ds = dataset(
        statements=[account_list("qnb-other", date(2026, 7, 1), date(2026, 10, 31), -24000)], accounts=(QNB_OTHER,)
    )
    (overdraft,) = forecast(ds, interpret(ds), date(2026, 11, 1), []).accounts
    assert overdraft.negative == (date(2026, 11, 1), Decimal(-24000))  # the chart still shows where it stands
    assert overdraft.warning is None
    assert "Ek hesap (KMH): eksi bakiye kullanılan krediyi gösterir; eksiye düşmesi uyarı sayılmaz." in overdraft.notes


def test_an_account_the_user_tops_up_for_what_it_pays_warns_of_nothing_and_says_why():
    # Each month 5.000 TL comes in from another own account and pays the card: the balance stays near zero, and the
    # card payments the forecast spreads take it below it without the transfers that would come.
    coverage = {"cash": dict.fromkeys(MONTHS, 1.0)}
    txns = []
    for m in MONTHS:
        year, month = int(m[:4]), int(m[5:])
        txns.append(tx(date(year, month, 5), "Kendi hesabınızdan", -5000, TransactionKind.OWN_TRANSFER))
        txns.append(tx(date(year, month, 6), "Kart ödemesi", 5000, TransactionKind.CARD_PAYMENT))
    ds = dataset(txns, [account_list("cash", date(2026, 4, 1), date(2026, 10, 31), 0)], coverage=coverage)
    (cash,) = forecast(ds, interpret(ds), date(2026, 11, 1), []).accounts
    assert cash.negative is not None and cash.warning is None
    assert cash.notes[-1] == (
        "Bu hesaba kendi hesaplarınızdan düzenli para aktarılıyor: Nisan 2026 – Eylül 2026 arasında 30.000,00 TL geldi, "
        "hesaptan 30.000,00 TL çıktı. Öngörü bu aktarmaları saymaz; bu hesabın eksi günleri uyarı sayılmaz."
    )


def test_the_accounts_total_warns_when_it_goes_below_zero_and_says_more_than_one_account():
    # The rent takes the TL account below zero; the overdraft account says nothing of itself, but the total does.
    statements = [
        account_list("cash", date(2026, 7, 1), date(2026, 10, 31), 6000),
        account_list("qnb-other", date(2026, 7, 1), date(2026, 10, 31), -2000),
    ]
    ds = dataset(statements=statements, accounts=(CASH, QNB_OTHER))
    result = forecast(ds, interpret(ds), date(2026, 11, 1), [due(date(2026, 11, 3), "Ev kirası", "cash", 5000)])
    assert result.total_negative == (date(2026, 11, 3), Decimal(-1000))
    assert result.warnings == [("", (date(2026, 11, 3), Decimal(-1000)))]  # the cash account stays at 1.000 TL


def test_one_account_below_zero_is_told_once_not_again_as_the_total():
    ds = dataset(statements=[account_list("cash", date(2026, 7, 1), date(2026, 10, 31), 1000)])
    result = forecast(ds, interpret(ds), date(2026, 11, 1), [due(date(2026, 11, 3), "Ev kirası", "cash", 15000)])
    assert result.warnings == [("cash", (date(2026, 11, 3), Decimal(-14000)))]


def test_a_total_below_zero_already_today_is_no_forecast_and_warns_of_nothing():
    ds = dataset(
        statements=[account_list("qnb-other", date(2026, 7, 1), date(2026, 10, 31), -500)], accounts=(QNB_OTHER,)
    )
    assert forecast(ds, interpret(ds), date(2026, 11, 1), []).warnings == []
