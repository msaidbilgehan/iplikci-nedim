"""The providers' rates in the ledger and on the screens (architecture §15; docs/domain/ledger.md, "Kur çevirisi";
docs/domain/interpretation.md, "Varlıklar ve borçlar"): a foreign account's row takes its own printed rate, else the
providers' rate of its day at the buying side, else the documents' nearest, else it is left out; a foreign balance is
an asset at the buying rate and a debt at the selling rate, and the net worth is told in a currency at its selling
rate. Without the providers' rates everything is as the documents alone make it."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from iplikci.analysis import Dataset, DatedRate, PrintedRate, _to_tl, nearest, printed_rate
from iplikci.app import account_pages, holdings, now, outlook
from iplikci.app.analysis import analyze
from iplikci.app.workspace import Workspace
from iplikci.domain.codes import AccountType, RateSource, TransactionKind
from iplikci.domain.models import Account, Transaction
from iplikci.domain.money import round_half_up
from iplikci.fakes import Move, garanti, teb
from iplikci.fx.book import Quote, RateBook
from iplikci.insights import balance_rate
from iplikci.storage import fx_rates

from conftest import add

EURO = Account("garanti-9000001", "Garanti BBVA Vadesiz EUR 9000001", "Garanti BBVA", AccountType.FX, "EUR", "9000001")
DOLLAR = Account(
    "garanti-9000003", "Garanti BBVA Vadesiz USD 9000003", "Garanti BBVA", AccountType.FX, "USD", "9000003"
)
ACCOUNTS = {a.id: a for a in (EURO, DOLLAR)}
FRIDAY = date(2026, 10, 30)
TODAY = date(2026, 11, 5)
OCTOBER = (date(2026, 10, 1), date(2026, 10, 31))


def quote(day: date, buying: str, selling: str, currency: str = "EUR", source: RateSource = RateSource.TCMB) -> Quote:
    return Quote(day, currency, Decimal(buying), Decimal(selling), source)


def row(day: date, description: str = "ORNEK MUSTERI LTD", amount: str = "-100.00", account: str = EURO.id):
    """A row of a foreign account as its reader leaves it: the amount still in the account's currency."""
    currency = ACCOUNTS[account].currency
    return Transaction(day, description, Decimal(amount), TransactionKind.INCOME, account, f"100,00 {currency}")


# --- a row's rate ----------------------------------------------------------------------------------------------------


def test_a_row_takes_its_own_rate_then_the_days_provider_rate_then_the_documents_nearest_else_it_is_left_out():
    book = RateBook([quote(FRIDAY, "36.4521", "36.5178")])
    printed = {"EUR": [(date(2026, 9, 1), Decimal("35.10"))]}
    own = row(FRIDAY, "SWIFT GELEN EUR: 36,80")
    provider = row(FRIDAY, amount="20.00")  # money going out takes the buying rate too: what the euros were worth
    document = row(date(2026, 9, 3))  # no bulletin within a week before it
    nothing = row(FRIDAY, account=DOLLAR.id)  # no dollar rate anywhere
    warnings: list[str] = []
    out = _to_tl([own, provider, document, nothing], ACCOUNTS, printed, warnings, book)
    assert out == [own, provider, document] and "kur bulunamadı, işlem dışarıda bırakıldı" in warnings[0]
    assert [(t.reason.rate, t.reason.rate_day, t.reason.rate_source) for t in out] == [
        (Decimal("36.80"), FRIDAY, RateSource.DOCUMENT),
        (Decimal("36.4521"), FRIDAY, RateSource.TCMB),
        (Decimal("35.10"), date(2026, 9, 1), RateSource.DOCUMENT),
    ]
    assert (provider.amount, provider.reason.native) == (Decimal("729.04"), Decimal("20.00"))
    assert provider.original == "100,00 EUR × 36,4521"  # a provider's rate as TCMB prints it, to four decimals
    assert document.original == "100,00 EUR × 35,10"  # a document's as the documents always showed it


def test_a_weekend_row_takes_fridays_bulletin_and_names_its_day():
    book = RateBook([quote(FRIDAY, "36.4521", "36.5178")])
    [saturday] = _to_tl([row(FRIDAY + timedelta(days=1))], ACCOUNTS, {}, [], book)
    assert (saturday.reason.rate, saturday.reason.rate_day) == (Decimal("36.4521"), FRIDAY)
    [late] = _to_tl([row(FRIDAY + timedelta(days=8))], ACCOUNTS, {"EUR": [(FRIDAY, Decimal(37))]}, [], book)
    assert late.reason.rate_source is RateSource.DOCUMENT  # a bulletin over a week old says nothing of the day


def test_a_reference_rate_stands_in_when_no_tcmb_bulletin_came():
    book = RateBook([quote(FRIDAY, "36.40", "36.40", source=RateSource.ECB)])
    [valued] = _to_tl([row(FRIDAY)], ACCOUNTS, {}, [], book)
    assert (valued.reason.rate, valued.reason.rate_source) == (Decimal("36.40"), RateSource.ECB)


def test_vakifbanks_printed_rate_comes_with_its_foreign_amount():
    t = Transaction(
        FRIDAY,
        "Döviz Alış (100,00 EUR karşılığı)) (İşlem Kuru : 36,5000)",
        Decimal(3650),
        TransactionKind.OWN_TRANSFER,
        "x",
    )
    found = printed_rate(t)
    assert found is not None and (found.currency, found.rate, found.amount) == ("EUR", Decimal("36.5000"), Decimal(100))
    garanti_row = Transaction(FRIDAY, "Döviz satış EUR:54.44500", Decimal(-544), TransactionKind.OWN_TRANSFER, "x")
    assert printed_rate(garanti_row) == PrintedRate("EUR", Decimal("54.44500"), None)


_DAYS = st.dates(min_value=date(2025, 1, 1), max_value=date(2026, 12, 31))


@given(
    st.lists(st.tuples(_DAYS, st.decimals(min_value=Decimal(1), max_value=Decimal(99), places=4)), max_size=5),
    st.lists(st.tuples(_DAYS, st.decimals(min_value=Decimal(-99999), max_value=Decimal(99999), places=2)), max_size=8),
)
def test_without_the_providers_rates_every_row_is_valued_as_the_documents_alone_value_it(printed, moves):
    rates = {"EUR": printed} if printed else {}
    rows = [row(day, amount=str(amount)) for day, amount in moves]  # no row prints a rate of its own
    expected = [
        (round_half_up(t.amount * found[1]), found[1], found[0])
        for t in rows
        if (found := nearest(rates, "EUR", t.date)) is not None
    ]
    warnings: list[str] = []
    out = _to_tl(rows, ACCOUNTS, rates, warnings)  # no book: as before the providers came
    assert [(t.amount, t.reason.rate, t.reason.rate_day) for t in out] == expected
    assert len(warnings) == len(rows) - len(expected)


@given(
    st.decimals(min_value=Decimal(-1000000), max_value=Decimal(1000000), places=2),
    st.decimals(min_value=Decimal("0.0001"), max_value=Decimal(100), places=4),
)
def test_a_valued_row_keeps_what_it_was_worth_in_its_currency(amount, rate):
    book = RateBook([quote(FRIDAY, str(rate), str(rate))])
    [t] = _to_tl([row(FRIDAY, amount=str(amount))], ACCOUNTS, {}, [], book)
    assert t.reason.native == amount and abs(t.amount - amount * rate) <= Decimal("0.005")


# --- a balance's rate ------------------------------------------------------------------------------------------------


def ledger(**extra) -> Dataset:
    return Dataset(accounts={}, statements=[], transactions=[], documents=[], groups=[], categories={}, **extra)


def test_a_foreign_asset_is_valued_at_the_buying_rate_and_a_debt_at_the_selling_rate():
    printed = {"EUR": [(date(2026, 10, 20), Decimal("37.00"))]}
    ds = ledger(
        rates=printed,
        book=RateBook([quote(FRIDAY - timedelta(days=3), "36", "36.1"), quote(FRIDAY, "36.4521", "36.5178")]),
    )
    assert balance_rate(ds, "EUR", Decimal(100)) == DatedRate(Decimal("36.4521"), FRIDAY, RateSource.TCMB)
    assert balance_rate(ds, "EUR", Decimal(-100)) == DatedRate(Decimal("36.5178"), FRIDAY, RateSource.TCMB)
    # Without the providers the documents' newest rate stands for both, its day written.
    offline = ledger(rates=printed)
    assert balance_rate(offline, "EUR", Decimal(-100)) == DatedRate(
        Decimal("37.00"), date(2026, 10, 20), RateSource.DOCUMENT
    )
    assert balance_rate(offline, "USD", Decimal(1)) is None


# --- the screens, on documents and stored rates ------------------------------------------------------------------


def store(ws: Workspace, *quotes: Quote) -> None:
    """The providers' answers as the rate job would keep them, a day and a source at a time."""
    days = sorted({(q.day, q.source) for q in quotes})
    with ws.db() as db:
        for day, source in days:
            fx_rates.put(db, day, source, [q for q in quotes if (q.day, q.source) == (day, source)])


@pytest.fixture
def foreign_ws(ws: Workspace) -> Workspace:
    """A TL account that bought euros once, a euro account with an income and a balance of 2.000 EUR, and a euro
    account overdrawn by 300 EUR after a fee."""
    tl_moves = [
        Move(date(2026, 10, 1), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(40000)),
        Move(date(2026, 10, 20), "DÖVİZ ALIŞ EUR: 37,00", Decimal(-3700)),
    ]
    add(ws, "teb.xls", teb.account_export(teb.running_rows(tl_moves), period="01/10/2026 - 31/10/2026"))
    income = [Move(date(2026, 10, 5), "ORNEK MUSTERI LTD GELEN EFT", Decimal(1500))]
    add(ws, "eur.xls", garanti.account_xls(income, Decimal(500), "9000001", period=OCTOBER, currency="EUR"))
    fee = [Move(date(2026, 10, 8), "HESAP İŞLETİM MASRAFI", Decimal(-300))]
    add(ws, "eksi.xls", garanti.account_xls(fee, Decimal(0), "9000002", period=OCTOBER, currency="EUR"))
    return ws


PROVIDED = (
    quote(date(2026, 7, 1), "34.0000", "34.0600"),  # more than 90 days before the newest: not in the history
    quote(date(2026, 10, 5), "36.1000", "36.1650"),
    quote(date(2026, 10, 8), "36.2000", "36.2650"),
    quote(FRIDAY, "36.4521", "36.5178"),
    quote(FRIDAY, "34.1000", "34.1600", currency="USD"),
    quote(FRIDAY, "44.0000", "44.2000", currency="GBP"),  # held nowhere, billed nowhere: not listed
)


def test_the_rows_of_a_foreign_account_are_valued_at_the_days_tcmb_buying_rate(foreign_ws):
    store(foreign_ws, *PROVIDED)
    ds = analyze(foreign_ws, today=TODAY).dataset
    [income] = [t for t in ds.transactions if t.account == EURO.id]
    assert (income.amount, income.reason.rate, income.reason.rate_source) == (
        Decimal("-54150.00"),
        Decimal("36.1000"),
        RateSource.TCMB,
    )
    [fee] = [t for t in ds.transactions if t.account == "garanti-9000002"]
    assert (fee.amount, fee.reason.rate_day) == (Decimal("10860.00"), date(2026, 10, 8))


def test_a_balance_is_valued_at_the_newest_rate_on_its_side_with_its_day_and_source(foreign_ws):
    store(foreign_ws, *PROVIDED)
    a = analyze(foreign_ws, today=TODAY)
    found = {b.account: b for b in now.balances(a)[0]}
    euro, overdrawn = found[EURO.id], found["garanti-9000002"]
    assert (euro.balance, euro.value, euro.rate, euro.rate_day, euro.rate_source) == (
        Decimal(2000),
        Decimal("72904.20"),
        Decimal("36.4521"),
        FRIDAY,
        RateSource.TCMB,
    )
    assert euro.note.endswith("; kur 36,4521 (TCMB 30.10.2026 döviz alış kuru)")
    assert (overdrawn.balance, overdrawn.value, overdrawn.rate) == (
        Decimal(-300),
        Decimal("-10955.34"),
        Decimal("36.5178"),
    )
    assert overdrawn.note.endswith("(TCMB 30.10.2026 döviz satış kuru)")
    # The asset and the debt as Döviz lists them, and the account page.
    listed = {h.account: h for h in holdings.holdings(a, TODAY).holdings}
    assert (listed[EURO.id].rate, listed[EURO.id].rate_source) == (Decimal("36.4521"), RateSource.TCMB)
    assert listed["garanti-9000002"].value == Decimal("-10955.34")
    page = account_pages.holding_page(a.dataset, EURO.id, euro)
    assert (page.rate_source, page.value) == (RateSource.TCMB, Decimal("72904.20"))
    assert "döviz alış" in page.note
    # The MVP's report and findings value the euros the same way.
    [mvp] = [h for h in a.insights.holdings if h.label == EURO.label]
    assert (mvp.value, mvp.note) == (Decimal("72904.20"), "kur 36,4521 (TCMB 30.10.2026 döviz alış kuru)")


def test_the_forecast_names_the_foreign_accounts_it_leaves_out_with_their_value_in_tl(foreign_ws):
    # The forecast counts TL accounts; what moves with a rate is named apart, valued as the balances are, so that a
    # view can say what it leaves out and count it too.
    store(foreign_ws, *PROVIDED)
    a = analyze(foreign_ws, today=TODAY)
    fc = outlook.cash_flow(a, TODAY).forecast
    held = {b.account: b.value for b in now.outside(a, fc)}
    assert held == {EURO.id: Decimal("72904.20"), "garanti-9000002": Decimal("-10955.34")}
    assert {account.account for account in fc.accounts}.isdisjoint(held)


def test_the_net_worth_is_told_in_euros_and_dollars_at_their_selling_rate(foreign_ws):
    store(foreign_ws, *PROVIDED)
    worth = holdings.holdings(analyze(foreign_ws, today=TODAY), TODAY).worth
    euro, dollar, gold = worth.currencies
    assert worth.total == Decimal("36300.00") + Decimal("72904.20") - Decimal("10955.34")
    assert (euro.rate, euro.rate_day, euro.rate_source) == (Decimal("36.5178"), FRIDAY, RateSource.TCMB)
    assert euro.amount == round_half_up(worth.total / Decimal("36.5178"))
    assert euro.note == "TCMB 30.10.2026 döviz satış kuruyla"
    assert (dollar.rate, dollar.amount) == (Decimal("34.1600"), round_half_up(worth.total / Decimal("34.1600")))
    assert (gold.amount, gold.rate_source) == (None, None)  # grams and cost only: no price is guessed


def test_the_rates_give_the_providers_newest_first_and_a_history_of_both_sources(foreign_ws):
    store(foreign_ws, *PROVIDED)
    found = holdings.rates(analyze(foreign_ws, today=TODAY))
    euro, dollar = found.currencies  # GBP comes from TCMB too, but nothing here is in pounds
    assert (euro.newest.rate, euro.newest.selling, euro.newest.source) == (
        Decimal("36.4521"),
        Decimal("36.5178"),
        RateSource.TCMB,
    )
    assert [(r.day, r.source) for r in euro.history] == [
        (date(2026, 10, 5), RateSource.TCMB),
        (date(2026, 10, 8), RateSource.TCMB),
        (date(2026, 10, 20), RateSource.DOCUMENT),  # the bank's rate for the euros bought, as the row printed it
        (FRIDAY, RateSource.TCMB),
    ]
    assert euro.history[2].buying is None and dollar.newest.source is RateSource.TCMB
    assert found.missing == [] and "TCMB" in found.note and "henüz" not in found.note


def test_without_stored_rates_the_documents_value_everything_as_before(foreign_ws):
    a = analyze(foreign_ws, today=TODAY)
    [income] = [t for t in a.dataset.transactions if t.account == EURO.id]
    # The documents' only rate, the euros bought on 20 October, values every euro row and balance.
    assert (income.reason.rate, income.reason.rate_day, income.reason.rate_source) == (
        Decimal("37.00"),
        date(2026, 10, 20),
        RateSource.DOCUMENT,
    )
    euro = {b.account: b for b in now.balances(a)[0]}[EURO.id]
    assert (euro.value, euro.note.rsplit("; ", 1)[-1]) == (Decimal("74000.00"), "kur 37,00 (20.10.2026 belgesinden)")
    overdrawn = {b.account: b for b in now.balances(a)[0]}["garanti-9000002"]
    assert overdrawn.rate == Decimal("37.00")  # the documents' one rate stands for both sides
    worth = holdings.holdings(a, TODAY).worth
    euro_worth, dollar, _ = worth.currencies
    assert (euro_worth.note, euro_worth.rate_source) == ("20.10.2026 belgesindeki kurla", RateSource.DOCUMENT)
    assert dollar.note == "belgelerde USD kuru yok"
    rates = holdings.rates(a)
    assert [c.currency for c in rates.currencies] == ["EUR"] and "henüz alınmadı" in rates.note
