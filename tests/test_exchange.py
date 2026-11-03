"""What the banks' rates cost and what a foreign income is worth (F12; docs/domain/interpretation.md, "Kur makası"
and "Döviz geliri"): a trade against TCMB's rate of its day in its direction, a card purchase abroad at the rate it
was charged, the last 12 months only; the foreign income at the current rate, its sales for TL, and the sensitivity of
the monthly income over complete months only."""

from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from iplikci.analysis import Dataset
from iplikci.domain.codes import AccountType, RateSource, TradeSide, TransactionKind
from iplikci.domain.models import Account, Reason, Transaction
from iplikci.domain.money import round_half_up
from iplikci.exchange import foreign_income, spread, window_of
from iplikci.fx.book import Quote, RateBook

LIRA = Account("tl", "Örnek Vadesiz TL", "Garanti BBVA", AccountType.CURRENT, number="1234567")
EURO = Account("eur", "Örnek Vadesiz EUR", "Garanti BBVA", AccountType.FX, "EUR", "9000001")
CARD = Account("card", "Örnek Kart •1234", "Garanti BBVA", AccountType.CREDIT_CARD, number="1234")
ACCOUNTS = {a.id: a for a in (LIRA, EURO, CARD)}
WEDNESDAY = date(2026, 10, 28)
FRIDAY = date(2026, 10, 30)
TODAY = date(2026, 11, 5)


def quote(day: date, buying: str, selling: str, currency: str = "EUR", source: RateSource = RateSource.TCMB) -> Quote:
    return Quote(day, currency, Decimal(buying), Decimal(selling), source)


BOOK = RateBook(
    [
        quote(WEDNESDAY, "36.4000", "36.5000"),
        quote(FRIDAY, "36.4521", "36.5178"),
        quote(WEDNESDAY, "34.0000", "34.1600", "USD"),
    ]
)


def trade(day: date, text: str, tl: str, fingerprint: str = "") -> Transaction:
    """The TL account's row of a currency bought (TL out, above zero) or sold (TL in, below zero)."""
    return Transaction(day, text, Decimal(tl), TransactionKind.OWN_TRANSFER, LIRA.id, fingerprint=fingerprint or text)


def purchase(day: date, merchant: str, tl: str, original: str, installment: str = "") -> Transaction:
    return Transaction(
        day,
        merchant.upper(),
        Decimal(tl),
        TransactionKind.PURCHASE,
        CARD.id,
        original=original,
        installment=installment,
        merchant=merchant,
        fingerprint=f"{merchant}:{day}",
    )


def ledger(rows: list[Transaction], book: RateBook = BOOK, **extra) -> Dataset:
    return Dataset(
        accounts=ACCOUNTS,
        statements=[],
        transactions=sorted(rows, key=lambda t: (t.date, t.account, t.description)),
        documents=[],
        groups=[],
        categories={},
        book=book,
        **extra,
    )


# --- the spread ------------------------------------------------------------------------------------------------------


def test_a_currency_bought_is_compared_with_tcmbs_selling_rate_and_one_sold_with_its_buying_rate():
    bought = trade(WEDNESDAY, "DÖVİZ ALIŞ EUR: 36,80", "3680")  # 100 EUR, the TL over the printed rate
    sold = trade(WEDNESDAY, "DÖVİZ SATIŞ EUR: 36,10", "-1805")  # 50 EUR
    found = spread(ledger([bought, sold]), TODAY)
    buy, sale = found.trades
    assert (buy.side, buy.amount, buy.rate, buy.tcmb, buy.cost) == (
        TradeSide.BUY,
        Decimal("100.00"),
        Decimal("36.80"),
        Decimal("36.5000"),
        Decimal("30.00"),  # (36,80 − 36,50) × 100
    )
    assert (sale.side, sale.amount, sale.tl, sale.tcmb, sale.cost) == (
        TradeSide.SELL,
        Decimal("50.00"),
        Decimal(1805),
        Decimal("36.4000"),
        Decimal("15.00"),  # (36,40 − 36,10) × 50
    )
    assert (found.trades_cost, found.total, found.purchases) == (Decimal("45.00"), Decimal("45.00"), [])
    assert found.note.startswith("06.11.2025 – 05.11.2026 arasındaki 2 işlemde") and "45,00 TL" in found.note


def test_vakifbanks_printed_foreign_amount_is_taken_as_printed():
    row = trade(WEDNESDAY, "Döviz Alış (99,50 EUR karşılığı)) (İşlem Kuru : 36,9000)", "3671.55")
    [found] = spread(ledger([row]), TODAY).trades
    assert (found.amount, found.rate, found.cost) == (Decimal("99.50"), Decimal("36.9000"), Decimal("39.80"))


def test_a_card_purchase_abroad_is_charged_its_tl_over_its_foreign_amount_against_tcmbs_selling_rate():
    abroad = purchase(WEDNESDAY, "Örnek Yayın", "701.00", "19,99 USD")
    at_home = purchase(WEDNESDAY, "Örnek Market", "250.00", "")
    in_parts = purchase(WEDNESDAY, "Örnek Mağaza", "500.00", "120,00 EUR", installment="2/6")  # a part tells no rate
    found = spread(ledger([abroad, at_home, in_parts]), TODAY)
    [row] = found.purchases
    assert (row.title, row.currency, row.amount, row.rate, row.tcmb) == (
        "Örnek Yayın",
        "USD",
        Decimal("19.99"),
        Decimal("35.0675"),  # 701,00 TL ÷ 19,99 USD
        Decimal("34.1600"),
    )
    assert row.cost == Decimal("18.14")  # 701,00 − 34,16 × 19,99
    assert (found.purchases_cost, found.trades, found.left_out) == (Decimal("18.14"), [], 0)


def test_a_weekend_trade_takes_fridays_bulletin():
    saturday = trade(FRIDAY + timedelta(days=1), "DÖVİZ ALIŞ EUR: 36,6000", "3660")
    [row] = spread(ledger([saturday]), TODAY).trades
    assert (row.tcmb_day, row.tcmb, row.cost) == (FRIDAY, Decimal("36.5178"), Decimal("8.22"))


def test_rows_without_a_tcmb_rate_are_left_out_and_counted():
    pounds = trade(WEDNESDAY, "DÖVİZ ALIŞ GBP: 44,00", "4400")  # no pound rate at all
    reference = trade(WEDNESDAY, "DÖVİZ ALIŞ EUR: 36,80", "3680")
    ecb_only = RateBook([quote(WEDNESDAY, "36.45", "36.45", source=RateSource.ECB)])  # a reference rate has no sides
    found = spread(ledger([pounds, reference], ecb_only), TODAY)
    assert (found.trades, found.left_out, found.total) == ([], 2, Decimal(0))
    assert "TCMB kuru bulunmayan 2 işlem toplama girmedi. TCMB kurları henüz alınmadı." in found.note
    offline = spread(ledger([reference], RateBook()), TODAY)
    assert offline.left_out == 1 and offline.trades == []


def test_only_the_last_12_months_count_and_the_window_is_stated():
    assert window_of(TODAY) == (date(2025, 11, 6), TODAY)
    assert window_of(date(2028, 2, 29)) == (date(2027, 3, 1), date(2028, 2, 29))
    old = trade(date(2025, 11, 5), "DÖVİZ ALIŞ EUR: 36,80", "3680")
    book = RateBook([quote(date(2025, 11, 5), "36", "36.1")])
    found = spread(ledger([old], book), TODAY)
    assert (found.start, found.end, found.trades, found.left_out) == (date(2025, 11, 6), TODAY, [], 0)
    assert "bankanın kurunu gösteren bir döviz alım-satımı ya da yurt dışı kart harcaması yok" in found.note


@given(
    st.decimals(min_value=Decimal("0.01"), max_value=Decimal(100000), places=2),
    st.decimals(min_value=Decimal(1), max_value=Decimal(99), places=4),
    st.decimals(min_value=Decimal(1), max_value=Decimal(99), places=4),
)
def test_a_purchases_cost_is_what_it_paid_over_tcmbs_price_of_the_same_amount(foreign, rate, tcmb):
    tl = round_half_up(foreign * rate)
    abroad = purchase(WEDNESDAY, "Örnek Yayın", str(tl), f"{foreign:.2f} USD".replace(".", ","))
    book = RateBook([quote(WEDNESDAY, str(tcmb), str(tcmb), "USD")])
    found = spread(ledger([abroad], book), TODAY)
    [row] = found.purchases
    assert row.cost == round_half_up(tl - tcmb * foreign) and found.total == row.cost
    assert (row.cost > 0) == (tl - tcmb * foreign >= Decimal("0.005"))  # paid more than TCMB's price: a cost


# --- the foreign income ----------------------------------------------------------------------------------------------


def income(day: date, euros: str, rate: str = "36.0000") -> Transaction:
    """An income row of the euro account as the ledger leaves it: in TL at its day's rate, its euros on its reason."""
    native = -Decimal(euros)
    reason = Reason(rate=Decimal(rate), rate_day=day, rate_source=RateSource.TCMB, native=native)
    return Transaction(
        day,
        "ORNEK MUSTERI LTD",
        round_half_up(native * Decimal(rate)),
        TransactionKind.INCOME,
        EURO.id,
        merchant="Örnek Müşteri",
        fingerprint=f"gelir:{day}",
        reason=reason,
    )


# July, August and September complete; October partial: its income counts in the rows, never in the average.
COVERAGE = {account: {"2026-07": 1.0, "2026-08": 1.0, "2026-09": 1.0, "2026-10": 0.5} for account in (LIRA.id, EURO.id)}
EARNED = [
    income(date(2026, 7, 3), "2000"),
    income(date(2026, 8, 3), "2000"),
    income(date(2026, 9, 3), "2500"),
    income(date(2026, 10, 3), "3000"),
]


def test_a_foreign_income_is_listed_at_the_current_buying_rate_beside_what_the_ledger_counted():
    found = foreign_income(ledger(EARNED, coverage=COVERAGE), TODAY)
    [euro] = found.currencies
    assert (euro.currency, euro.rate.rate, euro.rate.day) == ("EUR", Decimal("36.4521"), FRIDAY)
    first = euro.rows[0]
    assert (first.amount, first.counted, first.worth) == (Decimal(2000), Decimal(72000), Decimal("72904.20"))
    assert (euro.received, euro.worth) == (Decimal(9500), Decimal("346294.95"))
    assert euro.note.startswith("06.11.2025 – 05.11.2026 arasında 4 gelir: 9.500,00 EUR, bugünkü kurla 346.294,95 TL.")
    assert "TCMB 30.10.2026 döviz alış kuruyla (36,4521)" in euro.note


def test_the_sensitivity_averages_complete_months_only_and_says_which():
    [euro] = foreign_income(ledger(EARNED, coverage=COVERAGE), TODAY).currencies
    s = euro.sensitivity
    assert s is not None and s.months == ("2026-07", "2026-08", "2026-09")  # October is partial
    assert (s.received, s.monthly, s.monthly_tl, s.change) == (
        Decimal(6500),
        Decimal("2166.67"),
        Decimal("78979.67"),  # 2.166,67 EUR at 36,4521
        Decimal("3948.98"),
    )
    assert s.say == (
        "Aylık ortalama Temmuz 2026 – Eylül 2026 arasındaki 3 tam ay üzerinden: 2.166,67 EUR, bugünkü kurla "
        "78.979,67 TL. EUR/TRY %5 düşerse aylık gelir 3.948,98 TL azalır; %5 yükselirse o kadar artar."
    )


def test_a_single_complete_month_is_named_as_one():
    coverage = {account: {"2026-09": 1.0, "2026-10": 0.5} for account in (LIRA.id, EURO.id)}
    [euro] = foreign_income(ledger(EARNED[2:], coverage=coverage), TODAY).currencies
    assert euro.sensitivity is not None and euro.sensitivity.say.startswith(
        "Aylık ortalama Eylül 2026 (tek tam ay) üzerinden: 2.500,00 EUR"
    )


def test_the_sales_of_the_currency_for_tl_are_listed_with_their_day_amount_and_rate():
    sold = trade(date(2026, 10, 12), "DÖVİZ SATIŞ EUR: 36,10", "-3610", "satis")
    bought = trade(date(2026, 10, 14), "DÖVİZ ALIŞ EUR: 36,80", "3680", "alis")
    [euro] = foreign_income(ledger([*EARNED, sold, bought], coverage=COVERAGE), TODAY).currencies
    [sale] = euro.sold
    assert (sale.fingerprint, sale.day, sale.amount, sale.tl, sale.rate) == (
        "satis",
        date(2026, 10, 12),
        Decimal("100.00"),
        Decimal(3610),
        Decimal("36.10"),
    )
    assert "Bu dönemde 1 kez TL'ye çevrildi." in euro.note


def test_without_a_complete_month_or_a_rate_nothing_is_guessed():
    partial = {account: {"2026-10": 0.5} for account in (LIRA.id, EURO.id)}
    [euro] = foreign_income(ledger(EARNED[3:], coverage=partial), TODAY).currencies
    assert euro.sensitivity is None and "bu gelirin girdiği bir tam ay yok" in euro.note
    [unrated] = foreign_income(ledger(EARNED, RateBook(), coverage=COVERAGE), TODAY).currencies
    assert (unrated.rate, unrated.worth, unrated.rows[0].worth) == (None, None, None)
    assert unrated.sensitivity is not None and unrated.sensitivity.monthly_tl is None
    assert "EUR kuru olmadığından TL karşılığı ve kur duyarlılığı hesaplanamadı." in unrated.sensitivity.say


def test_without_a_foreign_income_there_is_nothing_and_the_note_says_so():
    lira_income = Transaction(date(2026, 9, 1), "MAAS", Decimal(-40000), TransactionKind.INCOME, LIRA.id)
    found = foreign_income(ledger([lira_income], coverage=COVERAGE), TODAY)
    assert found.currencies == [] and found.note.startswith("Döviz cinsinden gelen bir gelir yok")
