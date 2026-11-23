"""İplikçi Nedim's word on the money (F06, and the browser extension's window): one of his lines from the series,
chosen by what the documents show of the user's money today, with his face coloured by it.

Every situation the dashboard tells has lines that fit it: a forecast that goes below zero, a month that ended in the
red or with little left, debts larger than the money, more or less spent than in a typical month, a price rise, fees,
a foreign income, money set aside, an income that came. A line may fit more than one situation, and every situation
but "nothing known yet" has at least two, so the line shown is not the same day after day while the money stands the
same. Each comes with its
situation in a sentence of its own, in words and shares only, never an amount, an account or a name: the extension
shows it too (ADR-0020).

The situations are listed most pressing first. The first one's line is the one shown, and it changes with the day
among that situation's lines; the rest follow in order, for "Başka bir söz", each line once. A month's verdict is the
Pano's own: the newest ended month whose income is known, closed or still waiting for its documents, what was left of
its money in once what went out (spending, money sent to people, loan principal) and what was saved are taken off, as
the month-end page says; "little left" below a tenth of it (web dashboard/Overview). A month still open says "for now"
("şimdilik"), and only a closed one is compared with the closed months before it. This month against the typical one is
the dashboard's comparison, with its conditions.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum

from .. import exchange
from ..domain.codes import MonthStatus
from ..feed.news import NEWS_DAYS, REPRICED_DAYS, repriced
from ..insights import month_name, month_of, pct, year_suffix
from .analysis import Analysis
from .dashboard import COMPARABLE, NEAR, AlertKind, AlertLevel, Closing, Dashboard

THIN = Decimal("0.1")  # less than this share of the income left: little (the Pano's verdict, dashboard/Overview)
BEST_OF = 3  # a month is the best only among at least this many closed months
ZERO = Decimal(0)


class Situation(StrEnum):
    """What a line is said about; listed most pressing first."""

    GOING_NEGATIVE = "going_negative"  # the forecast goes below zero
    OVERSPENT = "overspent"  # more went out of the month (with what was saved) than came in
    IN_DEBT = "in_debt"  # the debts are more than the money in the accounts
    SPENDING_MORE = "spending_more"  # this month so far, more than the typical month's same days
    THIN = "thin"  # little of the month's income was left
    BEST_MONTH = "best_month"  # the month left the most money of the closed months
    FOREIGN_INCOME = "foreign_income"  # income came into a foreign-currency account in the month
    SPENDING_LESS = "spending_less"  # this month so far, less than the typical month's same days
    SAVING = "saving"  # money went to savings or investments in the month
    INCOME_ARRIVED = "income_arrived"  # a regular income came within the last week
    GOOD = "good"  # a part of the month's income was left
    PRICE_RISE = "price_rise"  # a regular payment's price rose
    FEES = "fees"  # interest and fees were paid in the month
    QUIET = "quiet"  # no income came and nothing was spent in the month
    NO_DATA = "no_data"  # nothing to say yet


class Mood(StrEnum):
    """How the situation stands, as the Pano's verdicts colour it; the face takes its colour."""

    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class Quote:
    """A line of İplikçi Nedim's; a dialogue's lines in turn, his first."""

    id: str
    lines: tuple[str, ...]


# The lines, as the series has them (docs/İplikçi_Nedim_Sözler.md lists them with their situations).
QUOTES: dict[str, Quote] = {
    q.id: q
    for q in (
        Quote("bride", ("Elin şeyiyle gerdeğe giren, güvey değil gelin olur.",)),
        Quote("engineless_car", ("Parasız güç, motorsuz araba, bin gez canım.",)),
        Quote("hide_your_goods", ("Bak evladım; Türk'ten karını, Çeçen'den canını, Azeri'den malını saklayacaksın.",)),
        Quote("money_for_the_able", ("Para size ne lazım, para ehline lazım.",)),
        Quote("never_say_no", ("Bizim en güzel özelliğimiz; paraya asla hayır demek yok.",)),
        Quote("never_enough_currency", ("Türkiye dövize doymaz, para girsin de nasıl girerse girsin.",)),
        Quote(
            "moustached_foreigners", ("Dışarıdan gelen sıcak paranın sahipleri, bıyıklı yabancılardır. Yani biziz.",)
        ),
        Quote("loves_growth", ("Türkiye büyümeyi çok sever, bu nedenle sıcak paraya hayır demez.",)),
        Quote("generosity", ("Beni, hiçbir şey değil bu Türk milletinin bonkörlüğü öldürecek.",)),
        Quote(
            "toilet",
            ("Allah belasını versin büyük Ortadoğu'nun… Tuvalet mi canım bu? Küçük bin, büyük iki bin.",),
        ),
        Quote("dark_future", ("Kara bahtım, kör talihim benim; geleceğim çok karanlık.",)),
        Quote("no_mercy", ("İnsaf kalmamış ben-i âdemde, anamı ağlattılar Acıbadem'de.",)),
        Quote("cakir_dear", ("Çakır, kuzum…",)),
        Quote("dont_know", ("İsa Muhammed aşkına bilmiyorum.",)),
        Quote(
            "who_is_bigger", ("Ortadoğu mu büyük? Ben mi büyüğüm? Çabuk söyle.", "Siz efendim.", "Hıh. Tamam canım.")
        ),
        Quote("money_or_life", ("Ha param ha canım kuzum.",)),
        Quote("linden_tree", ("Değil ıhlamur içmek, ıhlamur ağacı yesem gevşemez sinirlerim.",)),
        Quote("no_to_money", ("Nerede görülmüş iplikçinin paraya hayır dediği canım.",)),
        Quote("two_lindens", ("Bize iki ıhlamur getir kızım.",)),
        Quote("tough_man", ("Çakır, nereden buldun bu sert adamı?",)),
        Quote(
            "safe_door", ("Evladım, para alacağın zaman kapısını aç kasanın! Kerhane kapısı mıdır bu? Kasa kapısıdır!",)
        ),
    )
}

# The lines that fit each situation, the closest first; a line may fit several, and every one fits at least one.
LINES: dict[Situation, tuple[str, ...]] = {
    # Nerves and a dark future; a debt on someone else's money is near.
    Situation.GOING_NEGATIVE: ("linden_tree", "two_lindens", "dark_future", "bride"),
    # A dark future; generosity that kills, power without money, nerves, someone else's money.
    Situation.OVERSPENT: ("dark_future", "generosity", "engineless_car", "linden_tree", "bride"),
    # Living on someone else's money; power without money; a dark future.
    Situation.IN_DEBT: ("bride", "engineless_car", "dark_future"),
    # Generosity that kills; nerves.
    Situation.SPENDING_MORE: ("generosity", "two_lindens", "linden_tree"),
    # Power without money; generosity that kills; money is life.
    Situation.THIN: ("engineless_car", "generosity", "money_or_life"),
    # Who is bigger; money is for the able; growth.
    Situation.BEST_MONTH: ("who_is_bigger", "money_for_the_able", "loves_growth"),
    # Foreign currency and hot money; never a no to money.
    Situation.FOREIGN_INCOME: (
        "never_enough_currency",
        "moustached_foreigners",
        "loves_growth",
        "no_to_money",
        "never_say_no",
    ),
    # The tough man who spends little; goods kept hidden.
    Situation.SPENDING_LESS: ("tough_man", "hide_your_goods"),
    # Goods kept hidden; money is life; the safe's door.
    Situation.SAVING: ("hide_your_goods", "money_or_life", "safe_door"),
    # The safe's door; never a no to money.
    Situation.INCOME_ARRIVED: ("safe_door", "no_to_money", "never_say_no"),
    # Money is for the able; never a no to money; goods kept hidden.
    Situation.GOOD: ("money_for_the_able", "never_say_no", "hide_your_goods"),
    # No mercy left; a price for nothing.
    Situation.PRICE_RISE: ("no_mercy", "toilet"),
    # Paying for nothing; no mercy left.
    Situation.FEES: ("toilet", "no_mercy"),
    # Nothing came in, nothing went out: a sigh, or a shrug.
    Situation.QUIET: ("cakir_dear", "dont_know"),
    # Nothing known yet: he says so, and only so.
    Situation.NO_DATA: ("dont_know",),
}


@dataclass(frozen=True, slots=True)
class MonthFacts:
    """The newest ended month whose income is known: the Pano's story month."""

    month: str  # YYYY-MM
    income: Decimal
    out: Decimal  # what went out and is gone: spending, money sent to people, loan principal (dashboard.Closing.out)
    # What the income left: the income less what went out and what was set aside, as the month-end page says. Money
    # taken out of the savings (currency sold, a deposit drawn) is no income of the month: it leaves this as it is.
    left: Decimal
    fees: Decimal  # interest and fees, part of the spending
    saving: Decimal  # what was set aside (month_end.Totals.saving); below zero taken out of the savings
    foreign_income: bool  # income came into a foreign-currency account in it
    best: int  # how many closed months it left the most money of; 0 when it is not the best of BEST_OF or more
    # Every document of it came and checks out; an open month's figures are the documents' so far: its card statements'
    # last days may still add spending.
    closed: bool = True


@dataclass(frozen=True, slots=True)
class Negative:
    """The forecast's first day below zero."""

    days: int  # from today
    total: bool  # it is the accounts' total, not one account
    critical: bool  # within the week the dashboard calls critical
    covered: bool = False  # the total, which the foreign currency and investments cover at today's value
    income: bool = True  # an income is expected into the TL accounts within the forecast's days


@dataclass(frozen=True, slots=True)
class Facts:
    """What the situations rest on, as of a day."""

    documents: bool  # an account has a document
    month: MonthFacts | None
    negative: Negative | None
    net_worth: Decimal | None  # the assets less the debts; None while an account has no TL value or none a balance
    pace: Decimal | None  # this month so far against the typical month's same days (0.12: 12 % more), if comparable
    repriced: int  # the regular and periodic payments whose price rose within REPRICED_DAYS
    income_days: int | None  # the days since the newest regular income within NEWS_DAYS; None for none


@dataclass(frozen=True, slots=True)
class Saying:
    situation: Situation
    mood: Mood
    reason: str  # the situation in a Turkish sentence: words and shares only, never an amount or a name
    quote: Quote


def _in(month: str) -> str:
    """ "2026-10" -> "Ekim 2026'da"."""
    return f"{month_name(month)}{year_suffix(month[:4], ablative=False)}"


def _share(m: MonthFacts) -> Decimal:
    return m.left / m.income


def _going_negative(n: Negative) -> tuple[Situation, Mood, str]:
    # Words only, never "TL" (the lines name no amount): the forecast counts the lira accounts alone. The total of
    # someone whose income comes in another currency falls though the money is there: it says why and what to do.
    whose = "Türk lirası hesaplarınızın toplamı" if n.total else "hesaplarınızdan biri"
    when = {0: "bugün", 1: "yarın"}.get(n.days, f"{n.days} gün sonra")
    said = f"Öngörüye göre {whose} {when} eksiye düşecek"
    if not n.covered:
        return Situation.GOING_NEGATIVE, Mood.CRITICAL if n.critical else Mood.WARNING, f"{said}."
    why = ", çünkü bu hesaplara düzenli gelir görünmüyor" if not n.income else ""
    cover = "Döviz ve yatırımlarınız bunu karşılıyor: o güne kadar bir kısmını Türk lirasına çevirmeniz yeter."
    return Situation.GOING_NEGATIVE, Mood.WARNING, f"{said}{why}. {cover}"


def _verdict(m: MonthFacts) -> tuple[Situation, Mood, str]:
    """The month's verdict, as the Pano's: more went out than came in, little left, a part of it left, or nothing
    moved. What is left is the month-end page's: the income less the spending, the money sent to people, the loan
    principal repaid and what was saved. A month still open says it for now: the documents still to come can only add
    to what went out, so what went out beyond the money in already did ("şimdiden"). More set aside than the income
    left is no overspending: the income covered what went out, the accounts' money the rest of the saving."""
    at = _in(m.month)
    now = "" if m.closed else "şimdilik "
    if m.left < 0 and m.out > m.income:
        saved = " ve birikime ayrılan" if m.saving > 0 else ""
        more = "gelen paradan fazlaydı" if m.closed else "şimdiden gelen paradan fazla"
        return Situation.OVERSPENT, Mood.CRITICAL, f"{at} giden{saved} para, {more}."
    if m.income == 0:  # nothing went out either, or refunds only
        return Situation.QUIET, Mood.NEUTRAL, f"{at} {now}ne gelir geldi ne harcama yapıldı."
    if m.left < 0:
        reason = (
            f"{at} gelen paranın {now}hepsi harcandı ya da birikime ayrıldı; birikime hesaplardaki paradan da eklendi."
        )
        return Situation.THIN, Mood.WARNING, reason
    if m.left == 0:
        return Situation.THIN, Mood.WARNING, f"{at} gelen paranın {now}hepsi harcandı ya da ayrıldı."
    if _share(m) < THIN:
        return Situation.THIN, Mood.WARNING, f"{at} gelen paranın {now}yalnızca {pct(_share(m))} elde kaldı."
    return Situation.GOOD, Mood.GOOD, f"{at} gelen paranın {now}{pct(_share(m))} elde kaldı."


def _month(m: MonthFacts) -> Iterator[tuple[Situation, Mood, str]]:
    """The month's verdict, whether it was the best one (a closed month only), and what else came in or went out in
    it."""
    at = _in(m.month)
    yield _verdict(m)
    if m.best and m.closed:
        reason = f"{month_name(m.month)}, kapanan son {m.best} ay içinde en çok paranın kaldığı ay oldu."
        yield Situation.BEST_MONTH, Mood.GOOD, reason
    if m.foreign_income:
        yield Situation.FOREIGN_INCOME, Mood.GOOD, f"{at} döviz hesabınıza gelir girdi."
    if m.saving > 0:
        yield Situation.SAVING, Mood.GOOD, f"{at} birikime ya da yatırıma para ayrıldı."
    if m.fees > 0:
        yield Situation.FEES, Mood.WARNING, f"{at} bankalara faiz ve ücret ödendi."


def _pace(pace: Decimal) -> tuple[Situation, Mood, str]:
    more = pace > 0
    by = f"%{round(abs(pace) * 100)} {'fazla' if more else 'az'}"
    said = f"Bu ay bugüne kadar tipik ayın aynı günlerinden {by} harcandı."
    return (Situation.SPENDING_MORE, Mood.WARNING, said) if more else (Situation.SPENDING_LESS, Mood.GOOD, said)


def _situations(f: Facts) -> Iterator[tuple[Situation, Mood, str]]:
    """Every situation the facts show, in no particular order."""
    if f.negative is not None:
        yield _going_negative(f.negative)
    if f.net_worth is not None and f.net_worth < 0:
        yield Situation.IN_DEBT, Mood.WARNING, "Borçlarınız hesaplarınızdaki paradan fazla."
    if f.pace is not None and abs(f.pace) >= NEAR:
        yield _pace(f.pace)
    if f.month is not None:
        yield from _month(f.month)
    if f.income_days is not None:
        when = {0: "Bugün", 1: "Dün"}.get(f.income_days, f"{f.income_days} gün önce")
        yield Situation.INCOME_ARRIVED, Mood.GOOD, f"{when} geliriniz hesaba geçti."
    if f.repriced:
        some = "bir" if f.repriced == 1 else str(f.repriced)
        yield Situation.PRICE_RISE, Mood.WARNING, f"Son {REPRICED_DAYS} günde {some} düzenli ödemenizin tutarı arttı."


def choose(facts: Facts, today: date) -> list[Saying]:
    """Every line the facts call for, the situations in Situation's order, most pressing first. Within a situation
    the day decides which line leads, so the line shown changes from one day to the next and stays through a day.

    A line that fits several situations comes once, with the most pressing of them; a situation whose every line came
    before keeps its day's line, so each situation is still told."""
    order = list(Situation)
    found = sorted(_situations(facts), key=lambda item: order.index(item[0]))
    if not found:
        reason = (
            "Henüz biten bir ayın geleni ve gideni bilinmiyor."
            if facts.documents
            else "Henüz belge yok; paranın nasıl gittiği bilinmiyor."
        )
        found = [(Situation.NO_DATA, Mood.NEUTRAL, reason)]
    out: list[Saying] = []
    said: set[str] = set()
    for situation, mood, reason in found:
        lines = LINES[situation]
        turn = today.toordinal() % len(lines)
        turned = lines[turn:] + lines[:turn]
        fresh = [id for id in turned if id not in said] or turned[:1]
        said.update(fresh)
        out += [Saying(situation, mood, reason, QUOTES[id]) for id in fresh]
    return out


# --- the facts, from the dashboard ------------------------------------------------------------------------------------


def _kept(income: Decimal, month: Closing) -> Decimal:
    """What a month's income left: Closing.left, but money taken out of the savings, which the month did not earn,
    is not counted as left."""
    return income - month.out - max(month.saving, ZERO)


def _story(a: Analysis, months: list[Closing], today: date) -> MonthFacts | None:
    """The Pano's story month: the newest ended month whose income is known, closed or still open, as the Pano tells
    it (web dashboard/Overview). A closed one is the best when it left the most money of the closed months; an open one
    is compared with none, as its last days may still add spending."""
    known = [(c, c.income) for c in months if c.status is not MonthStatus.RUNNING and c.income is not None]
    if not known:
        return None
    story, income = known[-1]
    left = _kept(income, story)
    closed = story.status is MonthStatus.CLOSED
    before = [_kept(i, c) for c, i in known[:-1] if c.status is MonthStatus.CLOSED]
    good = income > 0 and left / income >= THIN
    count = len(before) + 1
    best = count if closed and good and count >= BEST_OF and all(left > b for b in before) else 0
    rows = [row for c in exchange.foreign_income(a.dataset, today).currencies for row in c.rows]
    foreign = any(month_of(row.day) == story.month for row in rows)
    return MonthFacts(story.month, income, story.out, left, story.fees, story.saving, foreign, best, closed)


def _negative(board: Dashboard, today: date) -> Negative | None:
    found = [alert for alert in board.alerts.items if alert.kind is AlertKind.NEGATIVE and alert.day is not None]
    first = min(found, key=lambda alert: alert.day or today, default=None)
    if first is None or first.day is None:
        return None
    short = first.short
    covered, income = (short.covered, short.income) if short is not None else (False, True)
    return Negative((first.day - today).days, first.account == "", first.level is AlertLevel.CRITICAL, covered, income)


def _comparable(board: Dashboard) -> Decimal | None:
    """This month against the typical month's same days, under the dashboard's conditions: three complete months, and
    the month's days so far mostly covered by documents."""
    p = board.month.pace
    if p.by_day is None or not p.by_day or p.covered < COMPARABLE:
        return None
    return p.spent / p.by_day - 1


def _income_days(a: Analysis, today: date) -> int | None:
    since = today - timedelta(days=NEWS_DAYS)
    days = [t.date for s in a.insights.income for t in s.payments if t.fingerprint and since <= t.date <= today]
    return (today - max(days)).days if days else None


def facts(a: Analysis, board: Dashboard, today: date) -> Facts:
    worth = board.net_worth
    rises = [f for f in repriced(a.insights, today) if Decimal(f.detail["new"]) > Decimal(f.detail["old"])]
    return Facts(
        documents=bool(board.freshness.accounts or worth.parts),
        month=_story(a, board.closing.months, today),
        negative=_negative(board, today),
        # The money no document tells yet came from what the accounts hold: taken off, it can leave them empty, but
        # never more in debt than their debts.
        net_worth=max(worth.total, -worth.debts) if worth.parts and not worth.left_out else None,
        pace=_comparable(board),
        repriced=len(rises),
        income_days=_income_days(a, today),
    )


def sayings(a: Analysis, board: Dashboard, today: date) -> list[Saying]:
    """İplikçi Nedim's lines for the dashboard as of today, the one to show first."""
    return choose(facts(a, board, today), today)
