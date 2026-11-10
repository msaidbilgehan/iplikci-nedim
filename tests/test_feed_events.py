"""The feed's news (architecture §13): payments due soon, balances going below zero, payments and income that did
not come, new prices, payments after a cancellation, income received, large purchases and receipt rows no statement
shows. Each is told once; more than BULK of a kind at once are one event; an old snapshot still loads."""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

from iplikci.analysis import CONFIRMED, NOT_ON_STATEMENT, PROVISIONAL, Dataset, ReceiptLine
from iplikci.app import background
from iplikci.domain.codes import AccountType, EvidenceStatus, Necessity, RateSource, TransactionKind
from iplikci.domain.models import Account, Statement, Transaction
from iplikci.domain.text import fold
from iplikci.fakes import teb
from iplikci.feed import news
from iplikci.feed.news import Found
from iplikci.feed.snapshot import BULK, Change, Snapshot, diff, take
from iplikci.fx.book import Quote, RateBook
from iplikci.insights import interpret
from iplikci.storage import events
from iplikci.upcoming import CardDue, add_months

from conftest import add

CARD = Account("card", "Örnek Kart •1234", "TEB", AccountType.CREDIT_CARD, number="1234")
CASH = Account("cash", "Örnek Vadesiz TL", "TEB", AccountType.CURRENT, number="111222333")
EURO = Account("euro", "Örnek Euro Hesabı", "TEB", AccountType.FX, currency="EUR", number="444555666")
REGULAR = {"Kira", "Dijital Abonelikler"}
INCOME, P2P = TransactionKind.INCOME, TransactionKind.P2P_TRANSFER


def tx(
    d: date,
    merchant: str,
    amount: Decimal | int | str,
    category: str = "Kira",
    kind: TransactionKind = TransactionKind.PURCHASE,
    account: str = "cash",
    fingerprint: str = "",
    counterparty: str = "",
) -> Transaction:
    return Transaction(
        date=d,
        description=(merchant or counterparty).upper(),
        amount=Decimal(amount),
        kind=kind,
        account=account,
        counterparty=counterparty,
        merchant=merchant,
        category=category,
        necessity=Necessity.REQUIRED,
        fingerprint=fingerprint or f"{account}:{merchant or counterparty}:{d.isoformat()}",
    )


def monthly(first: date, count: int) -> list[date]:
    return [add_months(first, n) for n in range(count)]


RENT = [tx(d, "Ev kirası", 15000) for d in monthly(date(2026, 5, 3), 6)]  # the last on 3 October, from the account
SALARY = [tx(d, "Örnek İşveren", -40000, "Maaş", INCOME) for d in monthly(date(2026, 5, 1), 6)]  # the last 1 October


def notice(d: date, amount: int, account: str = "cash", status: EvidenceStatus = PROVISIONAL) -> ReceiptLine:
    """A bank notice's transfer row, after the account's newest list unless status says otherwise."""
    t = tx(d, "", amount, "Kişilere Giden", P2P, account, counterparty="VELİ ÖRNEKSOY")
    return ReceiptLine(t, f"bildirim:{t.fingerprint}", status, Decimal(amount))


def account_list(cut: date, total: int = 100000, start: date = date(2026, 5, 1)) -> Statement:
    return Statement("cash", cut, "TRY", "liste.xls", Decimal(0), Decimal(total), start=start)


def card_statement(cut: date) -> Statement:
    return Statement("card", cut, "TRY", "ekstre.pdf", Decimal(0), Decimal(0))


def dataset(
    txns: Sequence[Transaction] = (),
    statements: Sequence[Statement] = (),
    receipts: Sequence[ReceiptLine] = (),
    **extra,
) -> Dataset:
    """The ledger of txns; a receipt row counts when it is provisional, as analysis.build counts it."""
    counted = [line.txn for line in receipts if line.status == PROVISIONAL and line.txn not in txns]
    return Dataset(
        accounts={a.id: a for a in (CARD, CASH, EURO)},
        statements=list(statements),
        transactions=sorted([*txns, *counted], key=lambda t: (t.date, t.account, t.description)),
        documents=[],
        groups=[],
        categories={},
        regular=REGULAR,
        receipts=list(receipts),
        **extra,
    )


def finds(kind: str, ds: Dataset, today: date, dues: Sequence[CardDue] = ()) -> list[Found]:
    """What the analysis of ds finds of a kind on today."""
    return [f for f in news.find(ds, interpret(ds), today, dues) if f.kind == kind]


def feed(*steps: tuple[Dataset, date], dues: Sequence[CardDue] = ()) -> list[list[Change]]:
    """The events of a refresh on each step's day against the snapshot the one before saved, saved as the service
    saves it; the first only takes note."""
    saved: Snapshot | None = None
    told: list[list[Change]] = []
    for ds, today in steps:
        after = take(ds, interpret(ds), [], today, dues)
        told.append(diff(saved, after))
        saved = Snapshot.load(after.keeping(saved).dump())
    return told


def of(kind: str, told: list[list[Change]]) -> list[list[Change]]:
    return [[c for c in changes if c.kind == kind] for changes in told]


def snapshot(
    day: str = "2026-11-15",
    rows: dict[str, tuple[str, str]] | None = None,
    receipts: dict[str, str] | None = None,
    told: dict[str, dict[str, str]] | None = None,
    negative: dict[str, str] | None = None,
    found: tuple[Found, ...] = (),
) -> Snapshot:
    """A snapshot as take makes one: it remembers every occurrence it found, as found on its day."""
    if told is None:
        told = {kind: {f.key: day for f in found if f.kind == kind} for kind in news.OCCURRENCES}
    return Snapshot(day[:7], rows or {}, receipts or {}, {}, {}, day, told, negative or {}, found)


# --- payments due soon -------------------------------------------------------------------------------------------

DUE = CardDue("card", date(2026, 11, 25), Decimal("12500.75"), Decimal("2500.15"))
SHOPPING = dataset([tx(date(2026, 11, 1), "Örnek Market", 300, "Market", account="card")])


def test_a_payment_is_told_a_week_three_days_and_a_day_before_and_on_its_day_once_each():
    days = [15, 18, 19, 22, 23, 24, 25, 25, 26]
    told = of(news.DUE_SOON, feed(*[(SHOPPING, date(2026, 11, d)) for d in days], dues=[DUE]))
    assert [[c.detail["days"] for c in changes] for changes in told] == [[], [7], [], [3], [], [1], [0], [], []]
    assert told[1] == [
        Change(
            news.DUE_SOON,
            "card_due|card|Örnek Kart •1234|2026-11-25",
            {
                "payment": "card_due",
                "title": "Örnek Kart •1234",
                "account": "card",
                "due": "2026-11-25",
                "days": 7,
                "amount": "12500.75",
                "minimum": "2500.15",
                "about": "TEB",  # a card's due date is about its bank: its digits are the full level's
            },
        )
    ]


def test_a_service_that_was_down_tells_only_the_tightest_threshold_it_finds():
    steps = [(SHOPPING, date(2026, 11, d)) for d in (15, 24, 25)]
    told = of(news.DUE_SOON, feed(*steps, dues=[DUE]))
    assert [[c.detail["days"] for c in changes] for changes in told] == [[], [1], [0]]  # not the week's or 3 days'


def test_a_regular_payment_is_due_soon_without_a_minimum_and_income_never():
    ds = dataset([*RENT, *SALARY], [account_list(date(2026, 10, 31))])
    # The salary is expected on 1 December, five days ahead: money in is no payment due.
    (rent,) = finds(news.DUE_SOON, ds, date(2026, 11, 26))
    assert (rent.target, rent.key) == ("regular|cash|Ev kirası|2026-12-03", "regular|cash|Ev kirası|2026-12-03|7")
    assert rent.detail == {
        "payment": "regular",
        "title": "Ev kirası",
        "account": "cash",
        "due": "2026-12-03",
        "days": 7,
        "amount": "15000.00",
        "about": "Kira",  # a payment is about its category: its payee is the full level's
    }


def test_what_a_card_is_charged_on_its_own_and_its_installments_are_not_due_soon():
    netflix = [tx(d, "Örnekflix", 199, "Dijital Abonelikler", account="card") for d in monthly(date(2026, 5, 3), 6)]
    ds = dataset([*RENT, *netflix], [account_list(date(2026, 10, 31)), card_statement(date(2026, 10, 31))])
    found = finds(news.DUE_SOON, ds, date(2026, 11, 26))
    assert [f.detail["title"] for f in found] == ["Ev kirası"]  # the rent goes from the account; the card pays Netflix


def test_a_refresh_tells_a_cards_due_date_its_statement_prints(ws):
    add(ws, "teb-ekstre.pdf", teb.bonus_statement())  # cut on 5 October, due on 15 October
    assert background.refresh(ws, today=date(2026, 10, 7)) == []  # the first refresh only takes note
    assert background.refresh(ws, today=date(2026, 10, 8)) == [news.DUE_SOON]
    assert background.refresh(ws, today=date(2026, 10, 9)) == []
    with ws.db() as db:
        (due,) = events.entries(db, news.DUE_SOON)
    assert due.target.startswith("card_due|teb-1234|") and due.target.endswith("|2026-10-15")
    assert {k: due.detail[k] for k in ("payment", "account", "due", "days")} == {
        "payment": "card_due",
        "account": "teb-1234",
        "due": "2026-10-15",
        "days": 7,
    }


# --- balances below zero -----------------------------------------------------------------------------------------


def test_a_balance_below_zero_names_the_account_its_first_day_and_the_balance_then():
    # 16.000 TL on 31 October; the rent of 3 November is expected already, that of 3 December takes it below zero.
    ds = dataset(RENT, [account_list(date(2026, 10, 31), total=16000)])
    (negative,) = finds(news.NEGATIVE, ds, date(2026, 11, 15))
    assert (negative.target, negative.detail) == (
        "cash|2026-12-03",
        {
            "account": "cash",
            "title": "Örnek Vadesiz TL",
            "day": "2026-12-03",
            "days": 18,
            "balance": "-14000.00",
            "about": "TEB",
        },
    )


def test_a_balance_below_zero_is_told_once_and_again_when_it_comes_sooner_or_after_it_recovered():
    lists = [account_list(date(2026, 10, 31), total=20000)]  # 5.000 TL left after the rent of 3 November
    spent, received = notice(date(2026, 11, 17), 6000), notice(date(2026, 11, 19), -50000)
    spent_more = notice(date(2026, 11, 20), 60000)

    def on(day: int, *rows: ReceiptLine) -> tuple[Dataset, date]:
        return dataset(RENT, lists, rows), date(2026, 11, day)

    steps = [
        on(15),
        on(16),
        on(17, spent),
        on(18, spent),
        on(19, spent, received),
        on(20, spent, received, spent_more),
    ]
    told = of(news.NEGATIVE, feed(*steps))
    assert [[(c.target, c.detail["days"], c.detail["balance"]) for c in changes] for changes in told] == [
        [],  # the first refresh only takes note: below zero on 3 December, when the rent goes
        [],  # the same day again
        [("cash|2026-11-17", 0, "-1000.00")],  # sooner: a transfer takes it below zero today
        [],  # each day starts from the same balance: its day below zero only moves on
        [],  # money came in: above zero all along
        [("cash|2026-11-20", 0, "-11000.00")],  # below zero again
    ]


# --- payments and income that did not come -----------------------------------------------------------------------

LATER = notice(date(2026, 11, 14), 500)  # a transfer after the day the rent's grace ended (13 November)


def test_a_payment_is_missing_when_the_documents_go_past_its_day_and_grace_without_it():
    lists = [account_list(date(2026, 10, 31))]
    assert finds(news.MISSING, dataset(RENT, lists), date(2026, 11, 20)) == []  # the list ends on 31 October
    on_the_last_day = notice(date(2026, 11, 13), 500)  # the rent might still come later that day
    assert finds(news.MISSING, dataset(RENT, lists, [on_the_last_day]), date(2026, 11, 20)) == []
    (missing,) = finds(news.MISSING, dataset(RENT, lists, [LATER]), date(2026, 11, 20))
    assert (missing.target, missing.detail) == (
        f"{RENT[0].fingerprint}|2026-11-03",
        {"title": "Ev kirası", "expected": "2026-11-03", "amount": "15000.00", "period": "month", "about": "Kira"},
    )
    # A list that covers the grace's last day tells it too, though the series now reads as ended (insights.settle).
    november = dataset(RENT, [*lists, account_list(date(2026, 11, 13), start=date(2026, 11, 1))])
    assert interpret(november).series[0].status == "bitti"
    assert [f.target for f in finds(news.MISSING, november, date(2026, 11, 20))] == [missing.target]


def test_a_missing_payment_is_told_once():
    lists = [account_list(date(2026, 10, 31))]
    steps = [
        (dataset(RENT, lists), date(2026, 11, 12)),
        (dataset(RENT, lists, [LATER]), date(2026, 11, 20)),
        (dataset(RENT, lists, [LATER]), date(2026, 11, 21)),
    ]
    assert [[c.target for c in changes] for changes in of(news.MISSING, feed(*steps))] == [
        [],
        [f"{RENT[0].fingerprint}|2026-11-03"],
        [],
    ]


def test_a_cancelled_payment_is_not_expected_and_one_whose_grace_ended_long_ago_is_history():
    lists = [account_list(date(2026, 10, 31))]
    cancelled = dataset(RENT, lists, [LATER], ended={fold("Ev kirası"): "2026-10"})
    assert finds(news.MISSING, cancelled, date(2026, 11, 20)) == []
    stopped = [tx(d, "Ev kirası", 15000) for d in monthly(date(2026, 1, 3), 6)]  # the last on 3 June
    ds = dataset(stopped, [account_list(date(2026, 8, 31), start=date(2026, 1, 1))])
    # Expected on 3 July, waited for until 13 July: news for 60 days after that, then history.
    assert [f.detail["expected"] for f in finds(news.MISSING, ds, date(2026, 9, 11))] == ["2026-07-03"]
    assert finds(news.MISSING, ds, date(2026, 9, 12)) == []


def test_a_yearly_payment_that_did_not_come_names_its_period():
    insurance = [
        tx(date(2023, 11, 6), "Örnek Sigorta", 4000, "Sigorta"),
        tx(date(2024, 11, 5), "Örnek Sigorta", 4000, "Sigorta"),
        tx(date(2025, 11, 5), "Örnek Sigorta", 4400, "Sigorta"),
    ]
    # A year after the last, with as much grace as its period allows: until 10 December.
    ds = dataset(insurance, [account_list(date(2026, 10, 31))], [notice(date(2026, 12, 11), 500)])
    (missing,) = finds(news.MISSING, ds, date(2026, 12, 20))
    assert missing.detail == {
        "title": "Örnek Sigorta",
        "expected": "2026-11-05",
        "amount": "4400.00",
        "period": "year",
        "about": "Sigorta",
    }


def test_an_income_is_late_when_the_documents_go_past_its_day_and_grace_without_it():
    lists = [account_list(date(2026, 10, 31))]
    later = notice(date(2026, 11, 12), 500)  # after the salary's grace ended on 11 November
    (late,) = finds(news.LATE, dataset(SALARY, lists, [later]), date(2026, 11, 15))
    assert (late.target, late.detail) == (
        f"{SALARY[0].fingerprint}|2026-11-01",
        {"title": "Örnek İşveren", "expected": "2026-11-01", "amount": "40000.00", "about": "Maaş"},
    )
    paid = tx(date(2026, 11, 1), "Örnek İşveren", -40000, "Maaş", INCOME)
    assert finds(news.LATE, dataset([*SALARY, paid], lists, [later]), date(2026, 11, 15)) == []


# --- prices and cancellations ------------------------------------------------------------------------------------


def test_a_new_price_is_told_once_from_the_payment_that_shows_it_holds():
    amounts = [1500] * 6 + [1640] * 3
    gym = [
        tx(d, "Örnek Spor", a, "Dijital Abonelikler", account="card")
        for d, a in zip(monthly(date(2026, 1, 5), 9), amounts, strict=True)
    ]

    def on(paid: int, cut: date) -> tuple[Dataset, date]:  # the first payments, the card's statements through cut
        return dataset(gym[:paid], [card_statement(cut)]), cut + timedelta(days=1)

    told = of(news.REPRICED, feed(on(7, date(2026, 7, 20)), on(8, date(2026, 8, 20)), on(9, date(2026, 9, 20))))
    assert told == [
        [],  # one payment at 1.640 TL is no new price yet
        [
            Change(
                news.REPRICED,
                f"{gym[0].fingerprint}|2026-07-05",
                {
                    "title": "Örnek Spor",
                    "old": "1500.00",
                    "new": "1640.00",
                    "since": "2026-07-05",
                    "about": "Dijital Abonelikler",
                },
            )
        ],
        [],
    ]


def test_a_new_price_is_history_once_the_payment_that_made_it_certain_is_older_than_repriced_days():
    # 1.640 TL from 5 April, certain with the second payment at it on 5 May: an import that brings these
    # statements later tells it only within REPRICED_DAYS of 5 May.
    amounts = [1500] * 3 + [1640] * 3
    gym = [
        tx(d, "Örnek Spor", a, "Dijital Abonelikler", account="card")
        for d, a in zip(monthly(date(2026, 1, 5), 6), amounts, strict=True)
    ]
    ds = dataset(gym, [card_statement(date(2026, 6, 18))])
    last_day = date(2026, 5, 5) + timedelta(days=news.REPRICED_DAYS)
    assert [f.detail["since"] for f in finds(news.REPRICED, ds, last_day)] == ["2026-04-05"]
    assert finds(news.REPRICED, ds, last_day + timedelta(days=1)) == []


def test_a_yearly_payments_new_price_is_certain_on_its_one_payment_and_history_after_repriced_days():
    insurance = [
        tx(date(2023, 11, 6), "Örnek Sigorta", 4000, "Sigorta"),
        tx(date(2024, 11, 5), "Örnek Sigorta", 4000, "Sigorta"),
        tx(date(2025, 11, 5), "Örnek Sigorta", 4400, "Sigorta"),
    ]
    ds = dataset(insurance, [account_list(date(2025, 11, 30), start=date(2023, 11, 1))])
    last_day = date(2025, 11, 5) + timedelta(days=news.REPRICED_DAYS)
    assert [f.detail["new"] for f in finds(news.REPRICED, ds, last_day)] == ["4400.00"]
    assert finds(news.REPRICED, ds, last_day + timedelta(days=1)) == []


def test_a_payment_after_the_cancellation_month_is_told_once_at_the_latest_one():
    magazine = [tx(d, "Örnek Dergi", 50, "Dijital Abonelikler", account="card") for d in monthly(date(2026, 6, 9), 5)]
    ended = {fold("Örnek Dergi"): "2026-08"}

    def on(paid: int, cut: date) -> tuple[Dataset, date]:
        return dataset(magazine[:paid], [card_statement(cut)], ended=ended), cut + timedelta(days=1)

    steps = [on(4, date(2026, 9, 20)), on(5, date(2026, 10, 20)), on(5, date(2026, 10, 21))]
    assert of(news.PAID_AFTER_CANCEL, feed(*steps)) == [
        [],  # 9 September's payment, after August, only noted by the first refresh
        [
            Change(
                news.PAID_AFTER_CANCEL,
                f"{magazine[0].fingerprint}|2026-10-09",
                {
                    "title": "Örnek Dergi",
                    "amount": "50.00",
                    "date": "2026-10-09",
                    "cancelled": "2026-08",
                    "about": "Dijital Abonelikler",
                },
            )
        ],
        [],
    ]


# --- rows ----------------------------------------------------------------------------------------------------------


def test_a_new_row_of_a_regular_income_is_told_once_and_other_income_is_not():
    one_off = tx(date(2026, 10, 3), "Örnek Danışmanlık", -3000, "Diğer Gelirler", INCOME)
    steps = [
        (dataset(SALARY[:5]), date(2026, 9, 5)),
        (dataset([*SALARY, one_off]), date(2026, 10, 5)),
        (dataset([*SALARY, one_off]), date(2026, 10, 6)),
    ]
    assert of(news.INCOME, feed(*steps)) == [
        [],
        [
            Change(
                news.INCOME,
                SALARY[5].fingerprint,
                {
                    "title": "Örnek İşveren",
                    "amount": "40000.00",
                    "account": "cash",
                    "date": "2026-10-01",
                    "about": "Maaş",
                },
            )
        ],
        [],
    ]


def test_an_income_row_older_than_a_week_that_a_statement_brings_is_history():
    steps = [(dataset(SALARY[:5]), date(2026, 9, 5)), (dataset(SALARY), date(2026, 10, 20))]  # 1 October's salary
    assert of(news.INCOME, feed(*steps)) == [[], []]


def test_an_income_a_statement_confirms_after_its_notice_is_not_told_again():
    noticed = tx(date(2026, 11, 1), "Örnek İşveren", -40000, "Maaş", INCOME, fingerprint="bildirim-maas")
    listed = tx(date(2026, 11, 1), "Örnek İşveren", -40000, "Maaş", INCOME, fingerprint="liste-maas")
    steps = [
        (dataset(SALARY), date(2026, 10, 31)),
        (dataset(SALARY, receipts=[ReceiptLine(noticed, "b", PROVISIONAL, noticed.amount)]), date(2026, 11, 1)),
        (
            dataset([*SALARY, listed], receipts=[ReceiptLine(noticed, "b", CONFIRMED, noticed.amount, listed)]),
            date(2026, 11, 3),
        ),
    ]
    assert [[c.target for c in changes] for changes in of(news.INCOME, feed(*steps))] == [[], ["bildirim-maas"], []]


def test_a_large_single_purchase_of_the_last_week_is_told_once():
    rent = [tx(d, "Ev kirası", 15000) for d in monthly(date(2026, 5, 10), 7)]  # the last on 10 November: a series
    big = tx(date(2026, 11, 10), "Örnek Elektronik", 12000, "Elektronik", account="card")
    old = tx(date(2026, 11, 1), "Örnek Mobilya", 9000, "Mobilya", account="card")  # two weeks before: history
    small = tx(date(2026, 11, 12), "Örnek Market", 300, "Market", account="card")
    steps = [
        (dataset(rent[:6]), date(2026, 11, 9)),
        (dataset([*rent, big, old, small]), date(2026, 11, 15)),
        (dataset([*rent, big, old, small]), date(2026, 11, 16)),
    ]
    assert of(news.LARGE, feed(*steps)) == [
        [],
        [
            Change(
                news.LARGE,
                big.fingerprint,
                {
                    "title": "Örnek Elektronik",
                    "amount": "12000.00",
                    "account": "card",
                    "date": "2026-11-10",
                    "about": "Elektronik",
                },
            )
        ],
        [],
    ]


def test_a_large_purchase_its_statement_confirms_after_its_notice_is_not_told_again():
    noticed = tx(date(2026, 11, 10), "Örnek Elektronik", 12000, "Elektronik", account="card", fingerprint="bildirim")
    printed = tx(date(2026, 11, 10), "Örnek Elektronik", 12000, "Elektronik", account="card", fingerprint="ekstre")
    shopping = [tx(date(2026, 11, 1), "Örnek Market", 300, "Market", account="card")]
    steps = [
        (dataset(shopping), date(2026, 11, 9)),
        (dataset(shopping, receipts=[ReceiptLine(noticed, "b", PROVISIONAL, noticed.amount)]), date(2026, 11, 10)),
        (
            dataset(
                [*shopping, printed],
                [card_statement(date(2026, 11, 12))],
                [ReceiptLine(noticed, "b", CONFIRMED, noticed.amount, printed)],
            ),
            date(2026, 11, 13),
        ),
    ]
    assert [[c.target for c in changes] for changes in of(news.LARGE, feed(*steps))] == [[], ["bildirim"], []]


def test_a_receipt_row_is_told_once_when_the_statement_covering_its_days_does_not_show_it():
    steps = [
        (dataset(receipts=[notice(date(2026, 11, 5), 2500)]), date(2026, 11, 6)),
        (dataset(receipts=[notice(date(2026, 11, 5), 2500, status=NOT_ON_STATEMENT)]), date(2026, 11, 20)),
        (dataset(receipts=[notice(date(2026, 11, 5), 2500, status=NOT_ON_STATEMENT)]), date(2026, 11, 21)),
    ]
    assert of(news.UNMATCHED, feed(*steps)) == [
        [],
        [
            Change(
                news.UNMATCHED,
                "cash:VELİ ÖRNEKSOY:2026-11-05",
                # A receipt row is about its account's bank: the person it names is the full level's.
                {
                    "title": "VELİ ÖRNEKSOY",
                    "amount": "2500.00",
                    "account": "cash",
                    "date": "2026-11-05",
                    "about": "TEB",
                },
            )
        ],
        [],
    ]


def test_an_unmatched_row_of_a_foreign_currency_account_is_valued_at_the_nearest_rate_the_documents_print():
    line = notice(date(2026, 11, 6), 100, account="euro", status=NOT_ON_STATEMENT)
    rates = {"EUR": [(date(2026, 11, 1), Decimal("36.50")), (date(2026, 11, 20), Decimal("37.00"))]}
    (valued,) = news.unmatched(dataset(receipts=[line], rates=rates))
    assert valued.detail == {
        "title": "VELİ ÖRNEKSOY",
        "amount": "3650.00",
        "account": "euro",
        "date": "2026-11-06",
        "about": "TEB",
    }
    (unvalued,) = news.unmatched(dataset(receipts=[line]))  # no rate printed anywhere: the amount stays in euros
    assert (unvalued.detail["amount"], unvalued.detail["currency"]) == ("100.00", "EUR")


def test_an_unmatched_foreign_row_takes_the_providers_rate_of_its_day_before_the_documents():
    line = notice(date(2026, 11, 6), 100, account="euro", status=NOT_ON_STATEMENT)
    rates = {"EUR": [(date(2026, 11, 1), Decimal("36.50"))]}
    book = RateBook([Quote(date(2026, 11, 6), "EUR", Decimal("36.4521"), Decimal("36.5178"), RateSource.TCMB)])
    (valued,) = news.unmatched(dataset(receipts=[line], rates=rates, book=book))
    assert valued.detail["amount"] == "3645.21"  # at TCMB's buying rate of the day, as the ledger values the account


# --- the snapshot ------------------------------------------------------------------------------------------------


def test_more_than_bulk_of_a_kind_at_once_are_one_event_of_that_kind():
    soon = [Found(news.DUE_SOON, f"bill||Örnek Satıcı {i}|2026-11-20", {"days": 5}, 7) for i in range(BULK + 1)]
    paid = [Found(news.INCOME, f"fp{i}", {"date": "2026-11-01"}, rows=(f"fp{i}",)) for i in range(BULK + 1)]
    before = snapshot(day="2026-11-14", told={news.DUE_SOON: {}})
    assert diff(before, snapshot(found=(*soon, *paid))) == [
        Change(news.DUE_SOON, "", {"count": BULK + 1}),
        Change(news.INCOME, "", {"count": BULK + 1}),
    ]
    assert len(diff(before, snapshot(found=tuple(soon[:BULK])))) == BULK


def test_an_occurrence_is_remembered_for_a_year_after_it_was_last_found():
    before = snapshot(
        day="2026-11-14", told={news.REPRICED: {"a|2025-01-05": "2025-11-14", "b|2025-03-05": "2025-11-15"}}
    )
    after = snapshot(found=(Found(news.REPRICED, "c|2026-10-05", {}),))
    saved = after.keeping(before)
    assert saved.told[news.REPRICED] == {"b|2025-03-05": "2025-11-15", "c|2026-10-05": "2026-11-15"}
    assert saved.told[news.DUE_SOON] == {} and after.keeping(None) == after
    assert diff(saved, snapshot(day="2026-11-16", found=after.found)) == []  # found again: told already


def test_a_snapshot_keeps_what_it_told_through_its_dump_but_not_what_it_found():
    soon = Found(news.DUE_SOON, "bill||Örnek Elektrik|2026-11-20", {"days": 5}, 7)
    s = snapshot(rows={"a": ("cash", "2026-11-01")}, negative={"cash": "2026-12-03"}, found=(soon,))
    loaded = Snapshot.load(s.dump())
    assert loaded == s and loaded is not None and loaded.found == ()
    assert loaded.told[news.DUE_SOON] == {"bill||Örnek Elektrik|2026-11-20|7": "2026-11-15"}


def test_an_old_snapshot_loads_and_a_kind_it_did_not_keep_only_takes_note():
    old = {"month": "2026-11", "rows": {"a": ["cash", "2026-11-01"]}, "receipts": {}, "months": {}, "invoices": {}}
    before = Snapshot.load(old)  # saved before the occurrences were kept
    assert before == Snapshot("2026-11", {"a": ("cash", "2026-11-01")}, {}, {}, {})
    soon = Found(news.DUE_SOON, "bill||Örnek Elektrik|2026-11-20", {"days": 5}, 7)
    paid = Found(news.INCOME, "b", {"title": "Örnek İşveren"}, rows=("b",))
    after = snapshot(found=(soon, paid))
    assert diff(before, after) == [Change(news.INCOME, "b", {"title": "Örnek İşveren"})]  # the new row is news
    saved = Snapshot.load(after.keeping(before).dump())
    closer = Found(news.DUE_SOON, soon.target, {"days": 3}, 3)
    assert diff(saved, snapshot(day="2026-11-17", found=(closer,))) == [Change(news.DUE_SOON, soon.target, {"days": 3})]
