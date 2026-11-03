"""İplikçi Nedim's lines (app.sayings): every line belongs to a situation the documents show, the most pressing
situation's line comes first and the day turns it, and the sentence that says the situation carries no amount."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from iplikci.app.sayings import LINES, QUOTES, Facts, MonthFacts, Mood, Negative, Situation, choose

TODAY = date(2026, 11, 15)


def month(
    income: str = "40000",
    expense: str = "20400",
    *,
    fees: str = "0",
    saving: str = "0",
    foreign: bool = False,
    best: int = 0,
) -> MonthFacts:
    return MonthFacts("2026-10", Decimal(income), Decimal(expense), Decimal(fees), Decimal(saving), foreign, best)


def facts(
    *,
    documents: bool = True,
    story: MonthFacts | None = None,
    negative: Negative | None = None,
    net_worth: str | None = None,
    pace: str | None = None,
    repriced: int = 0,
    income_days: int | None = None,
) -> Facts:
    return Facts(
        documents=documents,
        month=story,
        negative=negative,
        net_worth=None if net_worth is None else Decimal(net_worth),
        pace=None if pace is None else Decimal(pace),
        repriced=repriced,
        income_days=income_days,
    )


def said(f: Facts, today: date = TODAY) -> list[tuple[Situation, Mood, str]]:
    """Each situation once, in the order the lines come, with its mood and its sentence."""
    out: list[tuple[Situation, Mood, str]] = []
    for s in choose(f, today):
        if not out or out[-1][0] is not s.situation:
            out.append((s.situation, s.mood, s.reason))
    return out


# --- the lines -------------------------------------------------------------------------------------------------------


def test_every_line_belongs_to_one_situation_and_every_situation_has_lines():
    owned = [id for ids in LINES.values() for id in ids]
    assert sorted(owned) == sorted(QUOTES)  # each line once
    assert set(LINES) == set(Situation)
    assert len(QUOTES) == 21  # the user's list, the twice-written one once


def test_the_lines_keep_turkish_letters_and_the_dialogue_its_turns():
    words = {word.strip(".,;:!?…") for q in QUOTES.values() for line in q.lines for word in line.split()}
    assert not words & {"canim", "kizim", "evladim", "Çakir", "ihlamur", "karanlik", "kapisini", "adami"}
    assert QUOTES["who_is_bigger"].lines == (
        "Ortadoğu mu büyük? Ben mi büyüğüm? Çabuk söyle.",
        "Siz efendim.",
        "Hıh. Tamam canım.",
    )
    assert QUOTES["safe_door"].lines == (
        "Evladım, para alacağın zaman kapısını aç kasanın! Kerhane kapısı mıdır bu? Kasa kapısıdır!",
    )


# --- nothing known ----------------------------------------------------------------------------------------------------


def test_without_documents_he_does_not_know():
    [only] = choose(facts(documents=False), TODAY)
    assert (only.situation, only.mood, only.quote.id) == (Situation.NO_DATA, Mood.NEUTRAL, "dont_know")
    assert only.reason == "Henüz belge yok; paranın nasıl gittiği bilinmiyor."


def test_with_documents_but_no_closed_month_he_still_does_not_know():
    assert said(facts()) == [
        (Situation.NO_DATA, Mood.NEUTRAL, "Henüz kapanan bir ayın geleni ve gideni bilinmiyor."),
    ]


# --- the month's verdict, as the Pano's ------------------------------------------------------------------------------


def test_a_month_that_closed_in_the_red_is_a_dark_future():
    [first] = choose(facts(story=month(expense="45000")), TODAY)
    assert (first.situation, first.mood, first.quote.id) == (Situation.OVERSPENT, Mood.CRITICAL, "dark_future")
    assert first.reason == "Ekim 2026'da harcanan, gelen paradan fazlaydı."


def test_little_left_is_a_car_without_an_engine():
    assert said(facts(story=month(expense="37600"))) == [
        (Situation.THIN, Mood.WARNING, "Ekim 2026'da gelen paranın yalnızca %6'sı elde kaldı."),
    ]
    assert said(facts(story=month(expense="40000"))) == [
        (Situation.THIN, Mood.WARNING, "Ekim 2026'da gelen paranın hepsi harcandı."),
    ]


def test_a_good_month_says_the_share_left_as_the_pano_does():
    assert said(facts(story=month())) == [(Situation.GOOD, Mood.GOOD, "Ekim 2026'da gelen paranın %49'u elde kaldı.")]
    assert said(facts(story=month(expense="36000"))) == [
        (Situation.GOOD, Mood.GOOD, "Ekim 2026'da gelen paranın %10'u elde kaldı."),  # a tenth is not little
    ]


def test_a_month_with_no_income_and_no_spending_is_quiet():
    for expense in ("0", "-50"):  # a refund alone is no spending
        assert said(facts(story=month(income="0", expense=expense))) == [
            (Situation.QUIET, Mood.NEUTRAL, "Ekim 2026'da ne gelir geldi ne harcama yapıldı."),
        ]
    assert said(facts(story=month(income="0", expense="10")))[0][0] is Situation.OVERSPENT


def test_the_best_of_the_closed_months_comes_before_its_verdict():
    assert said(facts(story=month(best=6))) == [
        (Situation.BEST_MONTH, Mood.GOOD, "Ekim 2026, kapanan son 6 ay içinde en çok paranın kaldığı ay oldu."),
        (Situation.GOOD, Mood.GOOD, "Ekim 2026'da gelen paranın %49'u elde kaldı."),
    ]
    assert QUOTES[LINES[Situation.BEST_MONTH][0]].id == "who_is_bigger"


# --- what else stands -------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("negative", "mood", "reason"),
    [
        (Negative(0, False, True), Mood.CRITICAL, "Öngörüye göre hesaplarınızdan biri bugün eksiye düşecek."),
        (Negative(1, True, True), Mood.CRITICAL, "Öngörüye göre hesaplarınızın toplamı yarın eksiye düşecek."),
        (Negative(40, False, False), Mood.WARNING, "Öngörüye göre hesaplarınızdan biri 40 gün sonra eksiye düşecek."),
    ],
)
def test_a_forecast_below_zero_comes_before_everything(negative, mood, reason):
    found = said(facts(story=month(expense="45000"), negative=negative, net_worth="-5"))
    assert found[0] == (Situation.GOING_NEGATIVE, mood, reason)
    assert [s for s, _, _ in found] == [Situation.GOING_NEGATIVE, Situation.OVERSPENT, Situation.IN_DEBT]
    assert {s.quote.id for s in choose(facts(negative=negative), TODAY)} == {"linden_tree", "two_lindens"}


def test_debts_larger_than_the_money_are_a_wedding_on_borrowed_means():
    assert said(facts(net_worth="-0.01")) == [
        (Situation.IN_DEBT, Mood.WARNING, "Borçlarınız hesaplarınızdaki paradan fazla."),
    ]
    assert said(facts(net_worth="0"))[0][0] is Situation.NO_DATA


def test_this_month_against_the_typical_month_from_a_tenth_on():
    assert said(facts(pace="0.12")) == [
        (Situation.SPENDING_MORE, Mood.WARNING, "Bu ay bugüne kadar tipik ayın aynı günlerinden %12 fazla harcandı."),
    ]
    assert said(facts(pace="-0.25")) == [
        (Situation.SPENDING_LESS, Mood.GOOD, "Bu ay bugüne kadar tipik ayın aynı günlerinden %25 az harcandı."),
    ]
    assert said(facts(pace="0.09"))[0][0] is Situation.NO_DATA  # near the typical month


def test_a_foreign_income_savings_an_income_a_price_rise_and_fees_follow_the_verdict():
    story = month(foreign=True, saving="1000", fees="50")
    assert said(facts(story=story, income_days=2, repriced=2)) == [
        (Situation.FOREIGN_INCOME, Mood.GOOD, "Ekim 2026'da döviz hesabınıza gelir girdi."),
        (Situation.SAVING, Mood.GOOD, "Ekim 2026'da birikime ya da yatırıma para ayrıldı."),
        (Situation.INCOME_ARRIVED, Mood.GOOD, "2 gün önce geliriniz hesaba geçti."),
        (Situation.GOOD, Mood.GOOD, "Ekim 2026'da gelen paranın %49'u elde kaldı."),
        (Situation.PRICE_RISE, Mood.WARNING, "Son 45 günde 2 düzenli ödemenizin tutarı arttı."),
        (Situation.FEES, Mood.WARNING, "Ekim 2026'da bankalara faiz ve ücret ödendi."),
    ]
    assert said(facts(repriced=1)) == [
        (Situation.PRICE_RISE, Mood.WARNING, "Son 45 günde bir düzenli ödemenizin tutarı arttı."),
    ]
    assert [r for _, _, r in said(facts(income_days=0)) + said(facts(income_days=1))] == [
        "Bugün geliriniz hesaba geçti.",
        "Dün geliriniz hesaba geçti.",
    ]


def test_the_day_turns_a_situations_lines_and_keeps_them_through_the_day():
    good = facts(story=month())
    days = [TODAY + timedelta(days=n) for n in range(4)]
    firsts = [choose(good, d)[0].quote.id for d in days]
    assert firsts[0] != firsts[1] and firsts[0] == firsts[2] and firsts[1] == firsts[3]  # two lines, in turn
    assert {s.quote.id for s in choose(good, TODAY)} == set(LINES[Situation.GOOD])  # the other follows
    assert [s.quote.id for s in choose(good, TODAY)] == [s.quote.id for s in choose(good, TODAY)]


# --- whatever the facts -----------------------------------------------------------------------------------------------

money = st.decimals(min_value=-1000, max_value=10**6, places=2, allow_nan=False, allow_infinity=False)
months = st.builds(
    MonthFacts,
    month=st.sampled_from(["2025-12", "2026-01", "2026-10"]),
    income=st.decimals(min_value=0, max_value=10**6, places=2, allow_nan=False, allow_infinity=False),
    expense=money,
    fees=money,
    saving=money,
    foreign_income=st.booleans(),
    best=st.sampled_from([0, 3, 7]),
)
every_facts = st.builds(
    Facts,
    documents=st.booleans(),
    month=st.none() | months,
    negative=st.none() | st.builds(Negative, days=st.integers(0, 60), total=st.booleans(), critical=st.booleans()),
    net_worth=st.none() | money,
    pace=st.none() | st.decimals(min_value=-1, max_value=5, places=3, allow_nan=False, allow_infinity=False),
    repriced=st.integers(0, 5),
    income_days=st.none() | st.integers(0, 7),
)


@given(every_facts, st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 12, 31)))
def test_every_situations_lines_come_once_in_order_and_no_sentence_names_an_amount(f, today):
    found = choose(f, today)
    assert found
    order = list(Situation)
    positions = [order.index(s.situation) for s in found]
    assert positions == sorted(positions)  # the most pressing first
    for situation in {s.situation for s in found}:
        assert sorted(s.quote.id for s in found if s.situation is situation) == sorted(LINES[situation])
    assert all("TL" not in s.reason and "₺" not in s.reason for s in found)
    if f.negative is not None:
        assert found[0].situation is Situation.GOING_NEGATIVE
