"""The Değerlendirme screen's interpretation (F10), which no filter changes: the highlights, the steps with their
monthly effect, the monthly budget, the habits, money in and out over the window, what changed and the large one-off
purchases, the regular income, and the unusual movements worth a look. Every part says its window and numbers
(docs/domain/interpretation.md); the averages use complete months only."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from ..analysis import Dataset, payments
from ..categorize import FEE_CATEGORIES
from ..domain.codes import Certainty, HabitStatus, Necessity, SeriesStatus, Tone, TransactionKind, UnusualKind
from ..domain.labels import format_amount
from ..domain.models import Transaction
from ..domain.text import fold
from ..insights import V1_STATUS, Habit, Insights, large_purchase_threshold
from .analysis import Analysis
from .links import Link, Screen, finding_link
from .rows import RowView, view

__all__ = [
    "Assessment",
    "HabitStatus",
    "Necessity",
    "SeriesStatus",
    "Tone",
    "UnusualKind",
    "assess",
]

ZERO = Decimal(0)
_TONES = {"dikkat": Tone.ATTENTION, "bilgi": Tone.INFO, "iyi": Tone.GOOD}
_HABITS = {
    "duzenli": HabitStatus.MONTHLY,
    "yeni": HabitStatus.NEW,
    "ara_sira": HabitStatus.OCCASIONAL,
    "durdu": HabitStatus.STOPPED,
    "tek": HabitStatus.ONE_OFF,
}
# The rules of docs/domain/interpretation.md, "Olağan dışı hareketler".
UNUSUAL_DAYS = 90  # the unusual movements of the last three months: older ones are history
USUAL_COUNT = 3  # earlier purchases a merchant needs before an amount can be unusual for it
UNUSUAL_TIMES = Decimal(3)  # an amount more than this many times the merchant's median of earlier purchases …
UNUSUAL_GAP = Decimal(500)  # … and this many TL above it: a few liras more at a café are no news
HISTORY_DAYS = 90  # rows going back this far before a movement, so "never seen before" means something
FEE_QUIET_DAYS = 365  # a fee of a kind the account charged none of in the last twelve months is unexpected …
FEE_MINIMUM = Decimal(50)  # … when it is this many TL at least: a few liras of a transfer fee are no news


@dataclass(frozen=True, slots=True)
class Window:
    months: tuple[str, ...]  # the complete months the interpretation uses, oldest first (up to twelve)
    as_of: date  # the newest statement's end
    last_complete: str  # the newest month every account covers in full


@dataclass(frozen=True, slots=True)
class Finding:
    tone: Tone
    title: str
    text: str  # with its window and numbers
    link: Link  # the rows it rests on, when it names them


@dataclass(frozen=True, slots=True)
class Step:
    title: str
    text: str
    monthly: Decimal | None  # money freed per month; None when it depends on a choice the data cannot price


@dataclass(frozen=True, slots=True)
class BudgetLine:
    label: str
    now: Decimal  # the typical month today
    plan: Decimal  # the month the steps lead to
    note: str


@dataclass(frozen=True, slots=True)
class HabitLine:
    name: str  # the merchant, or the category of an avoidable cost
    category: str
    necessity: Necessity | None
    by_category: bool
    status: HabitStatus
    pattern: str  # how often, in words
    count: int  # purchases in the window
    months: int  # months of the window with one
    span: int  # months in the window
    total: Decimal  # spent in the window
    recent: Decimal  # monthly average of the last three complete months
    monthly: Decimal  # what it costs per month from now on, as far as the data tells
    last: date
    link: Link


@dataclass(frozen=True, slots=True)
class Flow:
    """Money in and out, each a monthly average over the window's months; only with an account list among the
    documents, as income is known only there."""

    months: tuple[str, ...]
    income: Decimal
    expense: Decimal
    people: Decimal  # sent to other people
    unnamed_people: Decimal  # of it, sent to people the statement does not name (the bank's name only)
    debt: Decimal  # debt principal repaid
    saving: Decimal  # pension and other investments
    fx: Decimal  # foreign currency and gold bought (above zero) or sold with TL
    left: Decimal  # income less all of the above but foreign currency
    debt_start: Decimal  # card balances and overdraft use before the window …
    debt_end: Decimal  # … and at its end
    other_typical: Decimal  # median month of money to people and debt repaid, last six months


@dataclass(frozen=True, slots=True)
class Change:
    category: str
    before: Decimal  # monthly average of the earlier months
    recent: Decimal  # of the recent months


@dataclass(frozen=True, slots=True)
class Trend:
    before: tuple[str, ...]
    recent: tuple[str, ...]
    before_average: Decimal
    recent_average: Decimal
    usual_before: Decimal  # without the large one-off purchases
    usual_recent: Decimal
    changes: list[Change]  # the largest movers first
    large: list[RowView]  # the large one-off purchases of the window, largest first: kept apart from the averages
    threshold: Decimal  # from this amount on a single purchase is large


@dataclass(frozen=True, slots=True)
class Income:
    name: str
    monthly: Decimal
    last: date
    status: SeriesStatus


@dataclass(frozen=True, slots=True)
class Unusual:
    kind: UnusualKind
    row: RowView
    text: str  # why it stands out, with its numbers
    link: Link


@dataclass(frozen=True, slots=True)
class Assessment:
    window: Window
    findings: list[Finding]
    steps: list[Step]
    budget: list[BudgetLine]
    habits: list[HabitLine]
    flow: Flow | None  # None without an account list in the window
    trend: Trend | None  # None with fewer than four complete months
    income: list[Income]  # the regular income still coming
    unusual: list[Unusual]  # newest first


def _tl(value: Decimal) -> str:
    return f"{format_amount(value)} TL"


def _habit(h: Habit) -> HabitLine:
    query = (("category", h.category),) if h.by_category else (("merchant", h.name),)
    return HabitLine(
        name=h.name,
        category=h.category,
        necessity=h.necessity,
        by_category=h.by_category,
        status=_HABITS[h.status],
        pattern=h.pattern,
        count=h.count,
        months=h.months,
        span=h.span,
        total=h.total,
        recent=h.recent,
        monthly=h.monthly,
        last=h.last,
        link=Link(Screen.TRANSACTIONS, query=query),
    )


def _flow(ins: Insights) -> Flow | None:
    f = ins.flow
    if f is None:
        return None
    return Flow(
        tuple(f.months),
        f.income,
        f.expense,
        f.people,
        f.unnamed_people,
        f.debt,
        f.saving,
        f.fx,
        f.left,
        f.debt_start,
        f.debt_end,
        f.other_typical,
    )


def _trend(ds: Dataset, ins: Insights) -> Trend | None:
    t = ins.trend
    if t is None:
        return None
    return Trend(
        tuple(t.before),
        tuple(t.recent),
        t.before_avg,
        t.recent_avg,
        t.usual_before,
        t.usual_recent,
        [Change(c.category, c.before, c.recent) for c in t.changes],
        [_row(r) for r in t.big],
        large_purchase_threshold(ds, ins.timeline.window),
    )


def _row(t: Transaction) -> RowView:
    return view(t, Certainty.PROVISIONAL if t.provisional else Certainty.CONFIRMED)


def assess(a: Analysis, today: date) -> Assessment:
    ds, ins = a.dataset, a.insights
    tl_ = ins.timeline
    return Assessment(
        window=Window(tuple(tl_.window), tl_.as_of, tl_.last_complete),
        findings=[
            Finding(_TONES.get(f.tone, Tone.INFO), f.title, f.text, finding_link(f.filter)) for f in ins.findings
        ],
        steps=[Step(s.title, s.text, s.monthly if s.monthly >= 1 else None) for s in ins.steps],
        budget=[BudgetLine(b.label, b.now, b.plan, b.note) for b in ins.budget],
        habits=[_habit(h) for h in ins.habits],
        flow=_flow(ins),
        trend=_trend(ds, ins),
        income=[Income(s.merchant, s.monthly, s.last.date, V1_STATUS[s.status]) for s in ins.income if s.running],
        unusual=unusual(ds, ins, today),
    )


# --- the unusual movements ----------------------------------------------------------------------------------------


def unusual(ds: Dataset, ins: Insights, today: date) -> list[Unusual]:
    """The movements of the last UNUSUAL_DAYS worth a look: an amount far above what the merchant usually takes, the
    same amount at the same merchant on the same day again, a large amount at a merchant never seen before, a fee or
    a due the account did not charge in the months before. Only flagged: every row still counts as it is."""
    since = today - timedelta(days=UNUSUAL_DAYS)
    # Payments as made: a split row's parts would look like the same merchant charging twice on one day.
    rows = sorted((t for t in payments(ds) if t.fingerprint), key=lambda t: (t.date, t.account, t.fingerprint))
    found = [
        *_amounts(rows, since),
        *_twice(rows, since),
        *_new_large(rows, since, large_purchase_threshold(ds, ins.timeline.window)),
        *_fees(rows, since),
    ]
    return sorted(found, key=lambda u: (u.row.day, u.row.fingerprint), reverse=True)


def _flag(kind: UnusualKind, t: Transaction, text: str) -> Unusual:
    return Unusual(kind, _row(t), text, Link(Screen.TRANSACTION, t.fingerprint))


def _purchases(rows: list[Transaction]) -> list[Transaction]:
    return [t for t in rows if t.kind is TransactionKind.PURCHASE and t.amount > 0]


def _amounts(rows: list[Transaction], since: date) -> list[Unusual]:
    earlier: dict[str, list[Decimal]] = defaultdict(list)
    found: list[Unusual] = []
    for t in _purchases(rows):
        key = fold(t.merchant)
        seen = earlier[key]
        if t.date >= since and len(seen) >= USUAL_COUNT and not t.installment:
            usual = Decimal(median(seen))
            if t.amount > UNUSUAL_TIMES * usual and t.amount - usual >= UNUSUAL_GAP:
                text = f"{_tl(t.amount)}; bu işyerinde önceki {len(seen)} alışverişin ortası {_tl(usual)}."
                found.append(_flag(UnusualKind.UNUSUAL_AMOUNT, t, text))
        seen.append(t.amount)
    return found


def _twice(rows: list[Transaction], since: date) -> list[Unusual]:
    """The same amount at the same merchant on the same day of one account: the second and later ones."""
    seen: dict[tuple[str, date, Decimal, str], int] = defaultdict(int)
    found: list[Unusual] = []
    for t in _purchases(rows):
        key = (t.account, t.date, t.amount, fold(t.merchant))
        seen[key] += 1
        if seen[key] > 1 and t.date >= since:
            text = f"Aynı gün aynı işyerinde {_tl(t.amount)} tutarında {seen[key]}. çekim; biri iade edilmediyse bakın."
            found.append(_flag(UnusualKind.POSSIBLE_DUPLICATE, t, text))
    return found


def _new_large(rows: list[Transaction], since: date, threshold: Decimal) -> list[Unusual]:
    """A large purchase at a merchant never seen before, once the rows go back far enough to tell."""
    known: set[str] = set()
    found: list[Unusual] = []
    first = min((t.date for t in rows), default=None)
    for t in _purchases(rows):
        key = fold(t.merchant)
        history = first is not None and (t.date - first).days >= HISTORY_DAYS
        if key not in known and t.date >= since and history and t.amount >= threshold:
            text = f"{_tl(t.amount)}; bu işyerinde ilk alışveriş (büyük tutar sınırı {_tl(threshold)})."
            found.append(_flag(UnusualKind.NEW_LARGE, t, text))
        known.add(key)
    return found


def _fees(rows: list[Transaction], since: date) -> list[Unusual]:
    first_seen: dict[str, date] = {}
    last_fee: dict[tuple[str, str], date] = {}
    found: list[Unusual] = []
    for t in rows:
        first_seen.setdefault(t.account, t.date)
        if t.kind is not TransactionKind.INTEREST_FEE or t.amount <= 0:
            continue
        key = (t.account, t.category)
        before = last_fee.get(key)
        history = (t.date - first_seen[t.account]).days >= HISTORY_DAYS
        quiet = before is None or (t.date - before).days > FEE_QUIET_DAYS
        if t.date >= since and history and quiet and t.amount >= FEE_MINIMUM:
            text = f"{_tl(t.amount)} ({t.category}); hesap son 12 ayda bu tür bir ücret almamıştı."
            if t.category == FEE_CATEGORIES["card_fee"]:
                text += " Kart aidatıysa bankanızdan iadesini isteyebilirsiniz."
            found.append(_flag(UnusualKind.UNEXPECTED_FEE, t, text))
        last_fee[key] = t.date
    return found
