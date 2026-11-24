"""An income the user says comes every month (`_düzenli_gelir`, F08): a salary that just started counts from its first
payment, at the declared amount and day, in TL at today's rate when it comes in another currency. With it the forecast
counts a deposit's interest, tells the income expected into the accounts it leaves out, and names the income it does
not expect again (F09)."""

from datetime import date
from decimal import Decimal

from iplikci.analysis import Dataset
from iplikci.app import outlook
from iplikci.domain.codes import (
    AccountType,
    DetailLevel,
    EventKind,
    Necessity,
    PaymentKind,
    RateSource,
    TransactionKind,
)
from iplikci.domain.models import Account, DeclaredIncome, Statement, Transaction
from iplikci.feed import news
from iplikci.forecast import forecast
from iplikci.fx.book import Quote, RateBook
from iplikci.insights import brought, declared_anchor, interpret, row_currency
from iplikci.notify import content
from iplikci.upcoming import next_day, upcoming

INCOME = TransactionKind.INCOME
CHECKING = Account("garanti-1234567", "Garanti BBVA Vadesiz TL 1234567", "Garanti BBVA", AccountType.CURRENT)
EUROS = Account("garanti-7654321", "Garanti BBVA Vadesiz EUR 7654321", "Garanti BBVA", AccountType.FX, "EUR")
DEPOSIT = Account("teb-111222333", "TEB Vadeli TL 111222333", "TEB", AccountType.DEPOSIT)
ACCOUNTS = (CHECKING, EUROS, DEPOSIT)
PAYER = "Örnek Yazılım Ltd"
SALARY = DeclaredIncome(PAYER, Decimal(2000), "EUR", 1)
RATE = RateBook([Quote(date(2026, 11, 20), "EUR", Decimal("51.0000"), Decimal("51.2000"), RateSource.TCMB)])
TODAY = date(2026, 11, 23)


def row(d: date, merchant: str, amount: str, account: Account = CHECKING, original: str = "") -> Transaction:
    kind = INCOME if Decimal(amount) < 0 else TransactionKind.PURCHASE
    return Transaction(
        date=d,
        description=merchant.upper(),
        amount=Decimal(amount),
        kind=kind,
        account=account.id,
        merchant=merchant,
        category="Diğer Gelirler" if kind == INCOME else "Diğer Harcamalar",
        necessity=None if kind == INCOME else Necessity.REQUIRED,
        original=original,
    )


# The first month of a salary paid in two parts into the euro account, at that day's rate.
PAID = [
    row(date(2026, 10, 1), PAYER, "-75000.00", EUROS, "1.500,00 EUR × 50,0000"),
    row(date(2026, 10, 27), PAYER, "-25050.00", EUROS, "500,00 EUR × 50,1000"),
]
FRIEND = row(date(2026, 10, 15), "Örnek Kişi", "-2000.00")
INTEREST = [row(date(2026, 11, d), "net faiz geliri", "-20.00", DEPOSIT) for d in range(11, 21)]
SPENT = [row(date(2026, m, 10), "Örnek Market", "3000.00") for m in range(5, 11)]


def account_list(account: Account, start: date, cut: date, total: str) -> Statement:
    return Statement(account.id, cut, account.currency, "liste.xls", Decimal(0), Decimal(total), start=start)


def dataset(declared: dict[str, DeclaredIncome] | None = None) -> Dataset:
    rows = [*PAID, FRIEND, *INTEREST, *SPENT]
    return Dataset(
        accounts={a.id: a for a in ACCOUNTS},
        statements=[
            account_list(CHECKING, date(2026, 5, 1), date(2026, 10, 31), "40000"),
            account_list(EUROS, date(2026, 5, 1), date(2026, 10, 31), "2000"),
            account_list(DEPOSIT, date(2026, 11, 10), date(2026, 11, 20), "50200"),
        ],
        transactions=sorted(rows, key=lambda t: (t.date, t.account, t.description)),
        documents=[],
        groups=[],
        categories={},
        coverage={CHECKING.id: {f"2026-{m:02d}": 1.0 for m in range(5, 11)}},
        declared=declared or {},
        book=RATE,
    )


DECLARED = {"ORNEK YAZILIM LTD": SALARY}


# --- the series -------------------------------------------------------------------------------------------------------


def test_a_row_says_what_it_brought_in_its_own_currency():
    assert (row_currency(PAID[0]), brought(PAID[0], "EUR"), brought(PAID[0], "TRY")) == ("EUR", Decimal(1500), None)
    assert (row_currency(FRIEND), brought(FRIEND, "TRY"), brought(FRIEND, "EUR")) == ("TRY", Decimal(2000), None)


def test_one_month_of_a_salary_makes_no_series_until_the_user_declares_it():
    assert interpret(dataset()).income == []
    [salary] = interpret(dataset(DECLARED)).income
    assert (salary.merchant, salary.declared, salary.status) == (PAYER, SALARY, "devam")
    assert salary.monthly == salary.declared_tl == Decimal(102000)  # 2.000 EUR at today's buying rate
    # The part that brought at least half of it sets the schedule: the 27th's 500 EUR does not make it November's.
    assert declared_anchor(salary) == date(2026, 10, 1)
    assert salary.expected == next_day(salary) == date(2026, 11, 1)


def test_a_declared_salary_comes_on_its_day_into_the_account_it_came_to_at_the_declared_amount():
    ds = dataset(DECLARED)
    items = [item for item in upcoming(ds, interpret(ds), TODAY) if item.kind == PaymentKind.INCOME]
    assert [(item.day, item.account, item.amount) for item in items] == [
        (date(2026, 12, 1), EUROS.id, Decimal(-102000)),
        (date(2027, 1, 1), EUROS.id, Decimal(-102000)),
    ]
    assert items[0].basis == "kurallarınızda her ay 2.000,00 EUR, ayın 1'i; bugünkü kurla 102.000,00 TL"


def test_the_payers_that_could_be_declared_are_the_recent_income_without_a_series():
    ds = dataset()
    found = outlook.income_candidates(ds, interpret(ds).income, TODAY)
    assert [(c.payee, c.account, c.currency, c.month, c.parts, c.day) for c in found] == [
        (PAYER, EUROS.id, "EUR", "2026-10", (Decimal(1500), Decimal(500)), 1),  # the most it brought first
        ("Örnek Kişi", CHECKING.id, "TRY", "2026-10", (Decimal(2000),), 15),
    ]  # a deposit's interest is no salary to declare
    declared = dataset(DECLARED)
    assert [c.payee for c in outlook.income_candidates(declared, interpret(declared).income, TODAY)] == ["Örnek Kişi"]


# --- the forecast -----------------------------------------------------------------------------------------------------


def test_the_forecast_adds_a_deposits_interest_at_the_rate_its_rows_tell_on_the_balance_that_earned_it():
    # 20 TL a day on about 50.000 TL: the rate is the interest over the balances that earned it, each day's for the
    # day before, so a balance that moves later (money taken out) earns at the same rate, not the same amount.
    ds = dataset()
    fc = forecast(ds, interpret(ds), TODAY, [])
    deposit = next(a for a in fc.accounts if a.account == DEPOSIT.id)
    assert deposit.earned is not None and deposit.earned.rate == Decimal(200) / Decimal(500900)
    assert deposit.days[0] == (TODAY, Decimal("50260.16"))  # three days after the list's 20 November, compounded
    assert deposit.notes[-1] == (
        "Faiz geliri: 11.11.2026–20.11.2026 arasında işlenen net faiz 200,00 TL; bakiyenin yıllık net getirisi "
        "yaklaşık %14,6. Öngörü her gün bakiyeye bu oranla faiz ekler: bugünkü bakiyeyle günde 20,04 TL."
    )
    assert fc.earns_interest


def test_a_deposit_emptied_for_a_card_earns_on_what_is_left():
    ds = dataset()
    ds.transactions.append(
        Transaction(date(2026, 11, 20), "KART ÖDEMESİ", Decimal(40000), TransactionKind.CARD_PAYMENT, DEPOSIT.id)
    )
    ds.statements[2] = account_list(DEPOSIT, date(2026, 11, 10), date(2026, 11, 20), "10200")
    deposit = next(a for a in forecast(ds, interpret(ds), TODAY, []).accounts if a.account == DEPOSIT.id)
    assert deposit.earned is not None and deposit.earned.rate == Decimal(200) / Decimal(500900)  # as before it
    assert round(deposit.earned.daily, 2) == Decimal("4.07")  # on 10.200 TL, not the 20 TL a day of 50.000


def test_the_forecast_carries_on_the_rate_the_newest_interest_rows_tell_once_the_bank_changed_it():
    # A new customer's rate ended: 60 TL a day on about 50.000 TL until 17 November, 20 TL since. The forecast adds the
    # new rate, not the mean of the month's rows, and says when the rate changed.
    ds = dataset()
    ds.transactions = [t for t in ds.transactions if t.account != DEPOSIT.id] + [
        row(date(2026, 11, d), "net faiz geliri", "-60.00" if d < 18 else "-20.00", DEPOSIT) for d in range(11, 21)
    ]
    deposit = next(a for a in forecast(ds, interpret(ds), TODAY, []).accounts if a.account == DEPOSIT.id)
    assert deposit.earned is not None
    assert deposit.earned.rate == Decimal(60) / Decimal(150480)  # over the balances of 17, 18 and 19 November
    assert deposit.days[0] == (TODAY, Decimal("50260.07"))
    assert deposit.notes[-1] == (
        "Faiz geliri: 18.11.2026–20.11.2026 arasında işlenen net faiz 60,00 TL; bakiyenin yıllık net getirisi "
        "yaklaşık %14,6. Oran 18.11.2026 tarihinde değişti: önceki günlerde işlenen faiz yıllık net yaklaşık %43,9 "
        "ediyordu. Öngörü her gün bakiyeye bu oranla faiz ekler: bugünkü bakiyeyle günde 20,02 TL."
    )


def test_a_posting_for_a_weekend_is_no_change_of_rate():
    # Monday's interest pays for Friday, Saturday and Sunday: three times a weekday's, at the same rate.
    ds = dataset()
    weekdays = [d for d in range(11, 21) if date(2026, 11, d).weekday() < 5]
    ds.transactions = [t for t in ds.transactions if t.account != DEPOSIT.id] + [
        row(date(2026, 11, d), "net faiz geliri", "-60.00" if date(2026, 11, d).weekday() == 0 else "-20.00", DEPOSIT)
        for d in weekdays
    ]
    deposit = next(a for a in forecast(ds, interpret(ds), TODAY, []).accounts if a.account == DEPOSIT.id)
    assert deposit.earned is not None and deposit.earned.before is None
    assert deposit.earned.first == date(2026, 11, 11)


def test_the_forecast_names_the_income_it_does_not_expect_again():
    ds = dataset()
    fc = forecast(ds, interpret(ds), TODAY, [])
    assert fc.notes[-1] == (
        "Son 90 günde (26.08.2026–23.11.2026) gelen ama öngörünün yeniden beklemediği gelirler: Örnek Yazılım Ltd "
        "100.050,00 TL, Örnek Kişi 2.000,00 TL. Her ay düzenli gelmedikleri ya da bittikleri için sayılmadılar; her ay "
        "geleceğini bildiğiniz bir geliri Düzenli ödemeler ekranında ekleyebilirsiniz."
    )


def test_a_salary_into_a_currency_account_is_told_beside_the_tl_lines_and_covers_their_shortfall():
    ds = dataset(DECLARED)
    ins = interpret(ds)
    fc = forecast(ds, ins, TODAY, upcoming(ds, ins, TODAY))
    assert [(item.day, item.amount) for item in fc.outside_income] == [
        (date(2026, 12, 1), Decimal(-102000)),
        (date(2027, 1, 1), Decimal(-102000)),
    ]
    assert fc.coming(date(2026, 12, 31)) == Decimal(102000) and fc.coming(date(2027, 1, 18)) == Decimal(204000)
    assert (
        "Döviz ve yatırım hesaplarına 2 gelir bekleniyor, bugünkü kurla toplam 204.000,00 TL: TL hesaplarına "
        "bozdurdukça geçer, bu yüzden TL çizgisinde yok."
    ) in fc.notes
    assert not any("Örnek Yazılım Ltd" in note for note in fc.notes if note.startswith("Son 90 günde"))


def test_the_totals_warning_counts_the_salary_coming_before_its_lowest_day():
    total = {
        "account": "",
        "title": news.TOTAL,
        "day": "2026-12-20",
        "days": 27,
        "balance": "-500.00",
        "income": False,
        "interest": True,
        "lowest": "-20000.00",
        "lowest_day": "2027-01-18",
        "cover": "5000.00",
        "coming": "102000.00",
    }
    full = content.render(EventKind.BALANCE_FORECAST_NEGATIVE, "k", total, DetailLevel.FULL).body
    assert full.endswith(
        "olacak. Öngörü TL hesaplarınıza vadeli hesap faizi dışında düzenli bir gelir beklemiyor. 18.01.2027 gününe "
        "kadar en çok 20.000,00 TL eksik kalıyor; döviz ve yatırımlarınız bugünkü değeriyle 5.000,00 TL, o güne kadar "
        "döviz hesaplarınıza bugünkü kurla 102.000,00 TL daha gelmesi bekleniyor: eksiye düşmeden önce bir kısmını "
        "TL'ye çevirmeniz yeter."
    )
    summary = content.render(EventKind.BALANCE_FORECAST_NEGATIVE, "k", total, DetailLevel.SUMMARY).body
    assert summary.endswith("Döviz ve yatırımlarınız ile oraya gelecek gelir bunu karşılıyor.")
    only_coming = {**total, "cover": "0"}
    assert content.render(EventKind.BALANCE_FORECAST_NEGATIVE, "k", only_coming, DetailLevel.SUMMARY).body.endswith(
        "Döviz hesaplarınıza gelecek gelir bunu karşılıyor."
    )
