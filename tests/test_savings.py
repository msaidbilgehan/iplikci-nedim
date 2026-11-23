"""What a month sets aside (docs/domain/interpretation.md, "Birikim"): BES and investments, currency and gold bought
with TL, and what comes into or leaves an account that holds savings; money moved within the savings adds nothing."""

from datetime import date
from decimal import Decimal

import pytest

from iplikci import month_end
from iplikci.analysis import build
from iplikci.app import sayings
from iplikci.app.dashboard import Closing
from iplikci.app.links import Link, Screen
from iplikci.categorize import FX_CATEGORY, Categorizer
from iplikci.domain.codes import AccountType, MonthStatus, SavingPart, TransactionKind
from iplikci.domain.models import Account, ParseResult, Statement, Transaction
from iplikci.insights import SavingLine, interpret, saving_of, savings
from iplikci.parsers.contract import Document

from conftest import PEOPLE_RULES

K = TransactionKind
HOLDER = "ÖRNEK KULLANICI"
CHECKING = Account("garanti-1234567", "Garanti BBVA Vadesiz TL 1234567", "Garanti BBVA", AccountType.CURRENT)
EUROS = Account("garanti-7654321", "Garanti BBVA Vadesiz EUR 7654321", "Garanti BBVA", AccountType.FX, "EUR")
DEPOSIT = Account("teb-111222333", "TEB Vadeli TL 111222333", "TEB", AccountType.DEPOSIT)
STOCKS = Account("garanti-yatirim-1-101", "Garanti BBVA Yatırım 1-101", "Garanti BBVA", AccountType.BROKERAGE)
GOLD = Account("teb-444555666", "TEB Altın 444555666", "TEB", AccountType.GOLD, "GR")
CARD = Account("teb-4321", "TEB Bonus •4321", "TEB", AccountType.CREDIT_CARD)
ACCOUNTS = {a.id: a for a in (CHECKING, EUROS, DEPOSIT, STOCKS, GOLD, CARD)}
DAY = date(2026, 10, 7)


def row(amount: str, kind: TransactionKind, account: Account = CHECKING, desc: str = "", category: str = ""):
    return Transaction(DAY, desc, Decimal(amount), kind, account.id, category=category)


# --- one row ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "t, found",
    [
        # A pension paid by card, a fund bought from a current account: set aside.
        (row("5000", K.INVESTMENT, CARD, "ANADOLU HAYAT"), (SavingPart.INVESTMENT, Decimal(5000))),
        (row("-2500", K.INVESTMENT, CHECKING, "FON SATIŞ"), (SavingPart.INVESTMENT, Decimal(-2500))),
        # A currency or gold trade, of which the ledger has the TL side only: TL paid in, a sale's TL taken out.
        (row("10000", K.OWN_TRANSFER, desc="DÖVİZ ALIŞ", category=FX_CATEGORY), (SavingPart.FX, Decimal(10000))),
        (row("-8000", K.OWN_TRANSFER, desc="DÖVİZ SATIŞ", category=FX_CATEGORY), (SavingPart.FX, Decimal(-8000))),
        (row("3000", K.OWN_TRANSFER, desc="ALTIN ALIŞ", category=FX_CATEGORY), (SavingPart.GOLD, Decimal(3000))),
        # What comes into a savings account is set aside, what leaves it comes out of the savings.
        (row("-50000", K.INCOME, EUROS, "ÖRNEK LTD Havale"), (SavingPart.FX, Decimal(50000))),
        (row("-30000", K.OWN_TRANSFER, DEPOSIT, "vadeli para yatırma"), (SavingPart.DEPOSIT, Decimal(30000))),
        (row("-25.00", K.INCOME, DEPOSIT, "net faiz geliri"), (SavingPart.DEPOSIT, Decimal("25.00"))),
        (row("12000", K.CARD_PAYMENT, DEPOSIT, "Kredi Kartına Ödenen"), (SavingPart.DEPOSIT, Decimal(-12000))),
        (row("-10.50", K.INCOME, STOCKS, "temettü"), (SavingPart.BROKERAGE, Decimal("10.50"))),
        # Money moved within the savings: a fund bought with a deposit's money, currency bought with a deposit's.
        (row("2000", K.INVESTMENT, DEPOSIT, "PARA PİYASASI FONU alış"), None),
        (row("2000", K.OWN_TRANSFER, DEPOSIT, "DÖVİZ ALIŞ", FX_CATEGORY), None),
        # Spending and transfers between the accounts the month is spent from move nothing into the savings.
        (row("400", K.PURCHASE, CARD, "MARKET"), None),
        (row("15000", K.OWN_TRANSFER, CHECKING, "KK BORÇ KAPAMA", "Hesaplar Arası Transfer"), None),
        (row("-40000", K.INCOME, CHECKING, "MAAŞ ÖDEMESİ"), None),
    ],
)
def test_a_row_sets_money_aside_where_it_goes_into_the_savings(t, found):
    assert saving_of(t, ACCOUNTS) == found


def test_a_transfer_between_two_savings_accounts_adds_nothing_to_the_month():
    # Its two sides cancel in the total; the parts still show where the money went.
    moved = [row("50000", K.OWN_TRANSFER, DEPOSIT), row("-50000", K.OWN_TRANSFER, STOCKS)]
    assert savings(moved, ACCOUNTS) == (
        Decimal(0),
        (
            SavingLine(SavingPart.DEPOSIT, "", Decimal(-50000)),
            SavingLine(SavingPart.BROKERAGE, "", Decimal(50000)),
        ),
    )


def test_a_months_parts_are_the_investment_categories_and_the_kinds_of_savings_the_largest_first():
    rows = [
        row("1000", K.INVESTMENT, CARD, category="Bireysel Emeklilik (BES)"),
        row("-50000", K.INCOME, EUROS),
        row("-50000", K.INCOME, EUROS),
        row("-98500", K.OWN_TRANSFER, CHECKING, "DÖVİZ SATIŞ", FX_CATEGORY),  # most of it sold: 1.500 kept
        row("500", K.INVESTMENT, CHECKING, category="Yatırım Fonu"),
        row("-1000", K.INCOME, DEPOSIT),
        row("1000", K.OWN_TRANSFER, DEPOSIT),  # what came in left again: no part
    ]
    total, parts = savings(rows, ACCOUNTS)
    assert total == Decimal(3000)
    assert parts == (
        SavingLine(SavingPart.FX, "", Decimal(1500)),
        SavingLine(SavingPart.INVESTMENT, "Bireysel Emeklilik (BES)", Decimal(1000)),
        SavingLine(SavingPart.INVESTMENT, "Yatırım Fonu", Decimal(500)),
    )
    assert [line.label for line in parts] == ["Döviz", "Bireysel Emeklilik (BES)", "Yatırım Fonu"]


# --- a month ------------------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cat(tmp_path_factory):
    rules = tmp_path_factory.mktemp("kurallar") / "kategoriler.yaml"
    rules.write_text(PEOPLE_RULES, encoding="utf-8")
    return Categorizer(rules)


def listing(account: Account, *rows: Transaction, opening: Decimal = Decimal(0)) -> ParseResult:
    closing = round(opening - sum(r.amount for r in rows), 2)
    s = Statement(
        account.id,
        date(2026, 10, 31),
        account.currency,
        f"{account.id}.xls",
        opening,
        closing,
        list(rows),
        start=date(2026, 10, 1),
        checks_ok=1,
        checks_total=1,
    )
    return ParseResult("liste", accounts=[account], statements=[s], holder=HOLDER)


def card(*rows: Transaction) -> ParseResult:
    total = sum((r.amount for r in rows), Decimal(0))
    s = Statement(CARD.id, date(2026, 11, 3), "TRY", "ekstre.pdf", Decimal(0), total, list(rows))
    return ParseResult("ekstre", accounts=[CARD], statements=[s], holder=HOLDER)


def on(d: int, desc: str, amount: str, kind: TransactionKind, account: Account) -> Transaction:
    return Transaction(date(2026, 10, d), desc, Decimal(amount), kind, account.id, source="belge")


def october(cat, *results: ParseResult) -> month_end.MonthEnd:
    docs = [(Document(f"{i}.xls", "test", b"", f"sha{i}"), r, None) for i, r in enumerate(results)]
    ds = build(docs, cat, {"ad_soyad": HOLDER})
    [me] = month_end.build(ds, interpret(ds), today=date(2026, 11, 20), months=["2026-10"])
    return me


def test_a_months_saving_holds_the_pension_the_currency_bought_and_kept_and_the_deposit(cat):
    """The salary comes in TL, a foreign income into the euro account (valued at the rate the trade prints); TL buys
    euros, fills a deposit and pays the card's pension: all of it is set aside, and what is left is what stayed in the
    current account and on the card."""
    me = october(
        cat,
        listing(
            CHECKING,
            on(1, "MAAŞ ÖDEMESİ ÖRNEK A.Ş.", "-40000", K.INCOME, CHECKING),
            on(3, "Mobil DÖVİZ ALIŞ 1234567 - 7654321 EUR:50.00000", "10000", K.OWN_TRANSFER, CHECKING),
            on(4, "VADELİ HESABA AKTARIM", "3000", K.OWN_TRANSFER, CHECKING),
            on(9, "MARKET ALIŞVERİŞ", "400", K.PURCHASE, CHECKING),
        ),
        listing(EUROS, on(2, "ÖRNEK LTD Havale Ödeme", "-1000", K.INCOME, EUROS)),
        listing(DEPOSIT, on(4, "vadeli para yatırma", "-3000", K.OWN_TRANSFER, DEPOSIT)),
        card(on(15, "ANADOLU HAYAT EMEKLILIK", "5000", K.PURCHASE, CARD)),
    )
    t = me.totals
    assert (t.income, t.expense, t.saving) == (Decimal(90000), Decimal(400), Decimal(68000))
    assert t.left == Decimal(21600)  # the current account kept 26.600, the card owes 5.000 for the pension
    assert [(line.label, line.amount) for line in t.saving_parts] == [
        ("Döviz", Decimal(60000)),  # 10.000 TL bought and 1.000 EUR earned at 50
        ("Bireysel Emeklilik (BES)", Decimal(5000)),
        ("Vadeli hesap", Decimal(3000)),
    ]


def test_currency_sold_to_spend_is_taken_out_of_the_savings(cat):
    """Euros earned before the month are sold for the month's spending: its saving is below zero, and what was left
    holds what the sale brought."""
    me = october(
        cat,
        listing(
            CHECKING,
            on(5, "Mobil DÖVİZ SATIŞ 7654321 - 1234567 EUR:50.00000", "-20000", K.OWN_TRANSFER, CHECKING),
            on(9, "MARKET ALIŞVERİŞ", "15000", K.PURCHASE, CHECKING),
            on(20, "MAAŞ ÖDEMESİ ÖRNEK A.Ş.", "-10000", K.INCOME, CHECKING),
        ),
        listing(EUROS, opening=Decimal(1000)),
    )
    t = me.totals
    assert (t.income, t.expense, t.saving, t.left) == (Decimal(10000), Decimal(15000), Decimal(-20000), Decimal(15000))
    assert [(line.part, line.amount) for line in t.saving_parts] == [(SavingPart.FX, Decimal(-20000))]


# --- what İplikçi Nedim says of it -----------------------------------------------------------------------------------


def told(expense: str, income: str, saving: str) -> Closing:
    """A closed October as the dashboard tells it: its left is the month-end page's."""
    left = Decimal(income) - Decimal(expense) - Decimal(saving)
    return Closing(
        "2026-10",
        MonthStatus.CLOSED,
        "",
        Decimal(expense),
        Decimal(income),
        left,
        "",
        0,
        0,
        [],
        Link(Screen.MONTH, "2026-10"),
        saving=Decimal(saving),
    )


def verdict(month: Closing) -> sayings.Saying:
    """İplikçi Nedim's verdict on the month: the first of what he says of it that is no saving's."""
    income = month.income or Decimal(0)
    facts = sayings.MonthFacts(
        month.month, income, month.out, sayings._kept(income, month), month.fees, month.saving, False, 0
    )
    found = sayings.choose(sayings.Facts(True, facts, None, None, None, 0, None), date(2026, 11, 20))
    return next(s for s in found if s.situation is not sayings.Situation.SAVING)


def test_money_taken_out_of_the_savings_is_not_what_the_income_left():
    # Euros sold for 20.000 to spend 15.000 out of an income of 10.000: the current account ended the month with more,
    # yet more went out than came in.
    drawn = told(expense="15000", income="10000", saving="-20000")
    assert drawn.left == Decimal(15000)
    assert sayings._kept(Decimal(10000), drawn) == Decimal(-5000)
    first = verdict(drawn)
    assert (first.situation, first.reason) == (
        sayings.Situation.OVERSPENT,
        "Ekim 2026'da giden para, gelen paradan fazlaydı.",
    )
    # More set aside than the income left is no overspending: what went out was covered, the accounts' money paid the
    # rest of the saving.
    beyond = told(expense="8000", income="10000", saving="5000")
    first = verdict(beyond)
    assert (first.situation, first.mood, first.reason) == (
        sayings.Situation.THIN,
        sayings.Mood.WARNING,
        "Ekim 2026'da gelen paranın hepsi harcandı ya da birikime ayrıldı; birikime hesaplardaki paradan da eklendi.",
    )
    # What was set aside is not left either.
    saved = told(expense="5000", income="10000", saving="3000")
    assert sayings._kept(Decimal(10000), saved) == saved.left == Decimal(2000)
    first = verdict(saved)
    assert (first.situation, first.reason) == (sayings.Situation.GOOD, "Ekim 2026'da gelen paranın %20'si elde kaldı.")
