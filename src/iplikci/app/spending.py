"""The Değerlendirme screen's spending (F10, the MVP report's cards), narrowed by the Transactions screen's filters:
the summary tiles, the months by group and by necessity, the categories, the merchants, money in and out by month,
and the three-month forecast, which every filter but the period narrows (features.md, "Süzgeçlerin kapsamı").

Without a kind filter the spending kinds count (purchases, refunds, interest and fees), as the MVP's "Giderler"; the
rows the ledger never counts stay out. Averages use complete months only; irregular spending is never annualized."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from statistics import median

from ..categorize import NECESSITY_SLOTS, group_slot
from ..domain.codes import DEFAULT_EXPENSE_KINDS, ForecastPart, Necessity, TransactionKind
from ..domain.labels import NECESSITY, format_amount
from ..domain.text import fold
from ..insights import NOT_BANK_ACCOUNTS, Series, complete_months, month_of, shift, span
from .analysis import Analysis
from .links import Link, Screen
from .rows import Direction, RowView
from .transactions import Filter, every_row, labels, select

__all__ = ["ForecastPart", "Necessity", "Spending", "spending"]

ZERO = Decimal(0)
LEVELS = (Necessity.REQUIRED, Necessity.OPTIONAL, Necessity.UNNECESSARY, Necessity.UNKNOWN)
DEFAULT_MONTHS = 12  # without a period: the last twelve months of the data, as the MVP report opened
TOP_MERCHANTS = 100
AHEAD = 3  # months the forecast looks ahead
BASE_MONTHS = 6  # complete months the forecast's typical month is taken from
INCOME_COVER = 0.5  # share of a month an account list must cover for its income to be known
_RUNNING = ("devam", "iptal_sonrasi")


@dataclass(frozen=True, slots=True)
class Period:
    start: str  # first month, YYYY-MM
    end: str  # last month
    first: str  # the data's first and last month in the accounts the filters keep: the presets' bounds
    last: str


@dataclass(frozen=True, slots=True)
class Tiles:
    total: Decimal  # spending the filters keep over the period
    count: int
    average: Decimal | None  # monthly, over the complete months with spending
    average_months: int
    partial_months: int  # months with spending some account covers only partly: not in the average
    income_average: Decimal | None  # monthly, over the period's months account lists cover
    income_months: int
    income_share: Decimal | None  # the spending of those months as a share of their income
    unnecessary: Decimal  # spent on what the rules call unnecessary: interest, late fees, bank charges
    last_month: str | None  # the newest month with spending
    last_total: Decimal
    last_partial: bool  # not complete: a card statement of it still to come, or a gap in the documents
    last_change: Decimal | None  # against the average of the up to three months before it with spending


@dataclass(frozen=True, slots=True)
class Slice:
    """A slice of the stacked monthly bars: a group, or a necessity level."""

    key: str  # a group's name, or a necessity's code
    slot: int  # the fixed colour slot: groups 1–8 by the rule file's order, "Diğer" 0


@dataclass(frozen=True, slots=True)
class MonthRow:
    month: str
    values: tuple[Decimal, ...]  # one per slice
    partial: bool  # some account covers it only partly: drawn lighter, never in an average


@dataclass(frozen=True, slots=True)
class MonthTable:
    slices: list[Slice]
    months: list[MonthRow]


@dataclass(frozen=True, slots=True)
class CategoryLine:
    category: str
    group: str
    slot: int
    total: Decimal
    share: Decimal | None  # of the total spending; None when that is not above zero
    average: Decimal  # per month with spending in the period
    count: int
    link: Link


@dataclass(frozen=True, slots=True)
class MerchantLine:
    merchant: str
    category: str  # of its newest row
    group: str
    slot: int
    count: int
    total: Decimal
    per_row: Decimal
    last: date
    link: Link


@dataclass(frozen=True, slots=True)
class FlowMonth:
    month: str
    income: Decimal
    expense: Decimal
    net: Decimal  # income − expense
    people: Decimal  # sent to other people
    debt: Decimal  # debt principal repaid
    saving: Decimal  # pension and other investments
    left: Decimal  # what is left after all of them


@dataclass(frozen=True, slots=True)
class ForecastLine:
    part: ForecastPart
    label: str
    note: str
    necessity: Necessity
    group: str  # "" for a necessity level's variable spending
    slot: int
    amounts: tuple[Decimal, ...]  # one per month ahead
    link: Link | None


@dataclass(frozen=True, slots=True)
class Forecast:
    base: tuple[str, ...]  # the complete months the typical month is taken from
    months: tuple[str, ...]  # the months ahead
    lines: list[ForecastLine]
    totals: tuple[Decimal, ...]
    by_level: MonthTable  # the months ahead by necessity
    actual: MonthTable  # the six months before them by necessity, beside the forecast
    income: Decimal  # monthly, from the regular income still coming
    income_names: tuple[str, ...]
    saving: Decimal  # monthly, from the regular savings still paid
    saving_names: tuple[str, ...]
    other: Decimal  # money to people and debt repaid: the median month of the last six; irregular
    left: Decimal | None  # income − the first month's spending − saving − other; None without a regular income


@dataclass(frozen=True, slots=True)
class Spending:
    period: Period | None  # None when no row is in the accounts the filters keep
    tiles: Tiles
    by_group: MonthTable
    by_level: MonthTable
    categories: list[CategoryLine]
    merchants: list[MerchantLine]
    flow: list[FlowMonth]  # the period's months account lists cover
    forecast: Forecast | None  # None without complete months or anything to forecast


def _signed(r: RowView) -> Decimal:
    return r.amount if r.direction is Direction.OUT else -r.amount


def _counted(a: Analysis, f: Filter) -> list[RowView]:
    return [r for r in select(a, f) if r.counted]


def _expenses(f: Filter) -> Filter:
    return f if f.kinds else replace(f, kinds=frozenset(DEFAULT_EXPENSE_KINDS))


def _kinds(f: Filter, *kinds: TransactionKind) -> Filter:
    """The same filters for other kinds of rows, every category and necessity (the MVP's cash-flow card)."""
    return replace(f, kinds=frozenset(kinds), categories=frozenset(), groups=frozenset(), necessities=frozenset())


def _period(a: Analysis, f: Filter) -> Period | None:
    months = sorted(
        {month_of(r.day) for r in every_row(a) if r.counted and (not f.accounts or r.account in f.accounts)}
    )
    if not months:
        return None
    first, last = months[0], months[-1]
    if f.start is None and f.end is None:
        return Period(max(first, shift(last, 1 - DEFAULT_MONTHS)), last, first, last)
    start = month_of(f.start) if f.start else first
    end = month_of(f.end) if f.end else last
    return Period(start, end, first, last)


def _within(f: Filter, period: Period) -> Filter:
    """The filters with the period as whole months."""
    start = date(int(period.start[:4]), int(period.start[5:]), 1)
    end_month = shift(period.end, 1)
    end = date.fromordinal(date(int(end_month[:4]), int(end_month[5:]), 1).toordinal() - 1)
    return replace(f, start=start, end=end)


def spending(a: Analysis, f: Filter) -> Spending:
    period = _period(a, f)
    complete = complete_months(a.dataset)
    if period is None:
        empty = MonthTable([], [])
        return Spending(None, _tiles(a, f, [], [], complete), empty, empty, [], [], [], None)
    narrowed = _within(_expenses(f), period)
    rows = _counted(a, narrowed)
    months = span(period.start, period.end)
    income_months = _income_months(a, months, f)
    return Spending(
        period=period,
        tiles=_tiles(a, narrowed, rows, income_months, complete),
        by_group=_by_group(a, rows, months, complete),
        by_level=_level_table(rows, months, complete),
        categories=_categories(a, rows),
        merchants=_merchants(a, rows),
        flow=_flow(a, narrowed, rows, income_months),
        forecast=_forecast(a, _expenses(f), period),
    )


def _income_months(a: Analysis, months: Sequence[str], f: Filter) -> list[str]:
    """The months an account list covers: income is known only there (cards, loans and brokerage say nothing)."""
    ds = a.dataset
    known: set[str] = set()
    for account, cover in ds.coverage.items():
        acc = ds.accounts.get(account)
        if acc is None or acc.type in NOT_BANK_ACCOUNTS or (f.accounts and account not in f.accounts):
            continue
        known |= {m for m, share in cover.items() if share >= INCOME_COVER}
    return [m for m in months if m in known]


def _by_month(rows: Iterable[RowView]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for r in rows:
        totals[month_of(r.day)] += _signed(r)
    return totals


def _tiles(a: Analysis, f: Filter, rows: list[RowView], income_months: list[str], complete: set[str]) -> Tiles:
    total = sum((_signed(r) for r in rows), ZERO)
    by_month = _by_month(rows)
    with_rows = sorted(by_month)
    full = [m for m in with_rows if m in complete]
    average = sum((by_month[m] for m in full), ZERO) / len(full) if full else None
    came = _counted(a, _kinds(f, TransactionKind.INCOME)) if income_months else []
    income = -sum((_signed(r) for r in came if month_of(r.day) in income_months), ZERO)
    spent_then = sum((by_month.get(m, ZERO) for m in income_months), ZERO)
    last = with_rows[-1] if with_rows else None
    before = with_rows[-4:-1]
    base = sum((by_month[m] for m in before), ZERO) / len(before) if before else ZERO
    return Tiles(
        total=total,
        count=len(rows),
        average=average,
        average_months=len(full),
        partial_months=len(with_rows) - len(full),
        income_average=income / len(income_months) if income_months else None,
        income_months=len(income_months),
        income_share=spent_then / income if income > 0 else None,
        unnecessary=sum((_signed(r) for r in rows if r.necessity is Necessity.UNNECESSARY), ZERO),
        last_month=last,
        last_total=by_month[last] if last else ZERO,
        last_partial=bool(last and last not in complete),
        last_change=(by_month[last] - base) / base if last and base > 0 else None,
    )


def _table(
    slices: list[Slice], months: Sequence[str], values: dict[tuple[str, str], Decimal], complete: set[str]
) -> MonthTable:
    present = [s for s in slices if any(values.get((m, s.key), ZERO) for m in months)]
    return MonthTable(
        present,
        [MonthRow(m, tuple(values.get((m, s.key), ZERO) for s in present), m not in complete) for m in months],
    )


def _by_group(a: Analysis, rows: list[RowView], months: Sequence[str], complete: set[str]) -> MonthTable:
    groups = a.dataset.groups
    values: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for r in rows:
        values[(month_of(r.day), r.group)] += _signed(r)
    known = [*groups, *sorted({r.group for r in rows} - set(groups))]
    return _table([Slice(g, group_slot(groups, g)) for g in known], months, values, complete)


def _level_table(rows: Iterable[RowView], months: Sequence[str], complete: set[str]) -> MonthTable:
    values: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for r in rows:
        if r.necessity is not None:
            values[(month_of(r.day), r.necessity.value)] += _signed(r)
    return _table([Slice(n.value, NECESSITY_SLOTS[n]) for n in LEVELS], months, values, complete)


def _categories(a: Analysis, rows: list[RowView]) -> list[CategoryLine]:
    total = sum((_signed(r) for r in rows), ZERO)
    months = len({month_of(r.day) for r in rows}) or 1
    sums: dict[str, Decimal] = defaultdict(Decimal)
    counts: dict[str, int] = defaultdict(int)
    group: dict[str, str] = {}
    for r in rows:
        sums[r.category] += _signed(r)
        counts[r.category] += 1
        group[r.category] = r.group
    groups = a.dataset.groups
    return [
        CategoryLine(
            category=c,
            group=group[c],
            slot=group_slot(groups, group[c]),
            total=v,
            share=v / total if total > 0 else None,
            average=v / months,
            count=counts[c],
            link=Link(Screen.TRANSACTIONS, query=(("category", c),)),
        )
        for c, v in sorted(sums.items(), key=lambda item: -item[1])
    ]


def _merchants(a: Analysis, rows: list[RowView]) -> list[MerchantLine]:
    by: dict[str, list[RowView]] = defaultdict(list)
    for r in rows:
        by[r.merchant or r.title].append(r)
    groups = a.dataset.groups
    lines: list[MerchantLine] = []
    for name, items in by.items():
        newest = max(items, key=lambda r: r.day)
        total = sum((_signed(r) for r in items), ZERO)
        lines.append(
            MerchantLine(
                merchant=name,
                category=newest.category,
                group=newest.group,
                slot=group_slot(groups, newest.group),
                count=len(items),
                total=total,
                per_row=total / len(items),
                last=newest.day,
                link=Link(Screen.TRANSACTIONS, query=(("merchant", name),)),
            )
        )
    return sorted(lines, key=lambda m: -m.total)[:TOP_MERCHANTS]


def _flow(a: Analysis, f: Filter, rows: list[RowView], income_months: list[str]) -> list[FlowMonth]:
    if not income_months:
        return []
    spent = _by_month(rows)

    def by_kind(kind: TransactionKind) -> dict[str, Decimal]:
        return _by_month(_counted(a, _kinds(f, kind)))

    income, people = by_kind(TransactionKind.INCOME), by_kind(TransactionKind.P2P_TRANSFER)
    debt, saving = by_kind(TransactionKind.LOAN_PRINCIPAL), by_kind(TransactionKind.INVESTMENT)
    out: list[FlowMonth] = []
    for m in income_months:
        came, went = -income.get(m, ZERO), spent.get(m, ZERO)
        p, d, s = people.get(m, ZERO), debt.get(m, ZERO), saving.get(m, ZERO)
        out.append(FlowMonth(m, came, went, came - went, p, d, s, came - went - p - d - s))
    return out


# --- the forecast ---------------------------------------------------------------------------------------------


def _series_kept(s: Series, f: Filter) -> bool:
    """A regular payment the filters keep, as the MVP report's recurring card kept it: every filter but the period."""
    last = s.last
    return (
        (not f.accounts or any(t.account in f.accounts for t in s.payments))
        and (last.kind is not TransactionKind.PURCHASE or not f.kinds or TransactionKind.PURCHASE in f.kinds)
        and (not f.categories or last.category in f.categories)
        and (not f.groups or last.group in f.groups)
        and (not f.necessities or (last.necessity or Necessity.UNKNOWN) in f.necessities)
        and (not f.merchant or fold(s.merchant) == fold(f.merchant))
        and (not f.text or all(w in fold(s.merchant) for w in fold(f.text).split()))
    )


def _day(d: date) -> str:
    return f"{d:%d.%m.%Y}"


def _months_between(a: str, b: str) -> int:
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[5:]) - int(a[5:])


def _forecast(a: Analysis, f: Filter, period: Period) -> Forecast | None:
    ins, ds = a.insights, a.dataset
    hi = period.last
    base = tuple(m for m in ins.timeline.window[-BASE_MONTHS:] if m >= period.first)
    if not base:
        return None
    ahead = tuple(shift(hi, k) for k in range(1, AHEAD + 1))
    rows = _counted(a, replace(f, start=None, end=None))
    groups = ds.groups
    lines = [
        *_regular(ins.series, f, groups, ahead),
        *_installments(rows, hi, ahead, labels(a), groups),
        *_variable(a, rows, base, ahead),
    ]
    if not lines:
        return None
    totals = tuple(sum((line.amounts[i] for line in lines), ZERO) for i in range(AHEAD))
    level_values: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for line in lines:
        for i, m in enumerate(ahead):
            level_values[(m, line.necessity.value)] += line.amounts[i]
    levels = [Slice(n.value, NECESSITY_SLOTS[n]) for n in LEVELS]
    income = [s for s in ins.income if s.status in _RUNNING]
    saving = [s for s in ins.series if s.status in _RUNNING and s.last.kind is TransactionKind.INVESTMENT]
    monthly_income = sum((s.monthly for s in income), ZERO)
    monthly_saving = sum((s.monthly for s in saving), ZERO)
    other = ins.flow.other_typical if ins.flow is not None else ZERO
    actual = span(shift(hi, 1 - BASE_MONTHS), hi)
    return Forecast(
        base=base,
        months=ahead,
        lines=lines,
        totals=totals,
        by_level=_table(levels, ahead, level_values, set(ahead)),  # the months ahead are no partial ones
        actual=_level_table([r for r in rows if month_of(r.day) in set(actual)], actual, complete_months(ds)),
        income=monthly_income,
        income_names=tuple(s.merchant for s in income),
        saving=monthly_saving,
        saving_names=tuple(s.merchant for s in saving),
        other=other,
        left=monthly_income - totals[0] - monthly_saving - other if monthly_income > 0 else None,
    )


def _regular(series: Sequence[Series], f: Filter, groups: list[str], ahead: tuple[str, ...]) -> list[ForecastLine]:
    out: list[ForecastLine] = []
    for s in series:
        if s.status not in _RUNNING or s.last.kind is not TransactionKind.PURCHASE or not _series_kept(s, f):
            continue
        note = f"{s.last.category} · son ödeme {_day(s.last.date)}"
        if s.status == "iptal_sonrasi":
            note += " · iptalden sonra da çekildi"
        out.append(
            ForecastLine(
                ForecastPart.REGULAR,
                s.merchant,
                note,
                s.last.necessity or Necessity.UNKNOWN,
                s.last.group,
                group_slot(groups, s.last.group),
                tuple(s.monthly for _ in ahead),
                Link(Screen.TRANSACTIONS, query=(("merchant", s.merchant),)),
            )
        )
    return sorted(out, key=lambda line: -line.amounts[0])


def _installments(
    rows: list[RowView], hi: str, ahead: tuple[str, ...], names: dict[str, str], groups: list[str]
) -> list[ForecastLine]:
    """The installments still due: the newest seen of each purchase paid in installments."""
    newest: dict[tuple[str, str, int, int], tuple[RowView, int, int]] = {}
    for r in rows:
        if month_of(r.day) < shift(hi, -2) or r.direction is not Direction.OUT or "/" not in r.installment:
            continue
        k_text, _, n_text = r.installment.partition("/")
        if not (k_text.isdigit() and n_text.isdigit()):
            continue
        k, n = int(k_text), int(n_text)
        key = (r.account, r.merchant, n, round(r.amount))
        if key not in newest or k > newest[key][1]:
            newest[key] = (r, k, n)
    out: list[ForecastLine] = []
    for r, k, n in newest.values():
        amounts = tuple(r.amount if k + _months_between(month_of(r.day), m) <= n else ZERO for m in ahead)
        if not any(amounts):
            continue
        out.append(
            ForecastLine(
                ForecastPart.INSTALLMENTS,
                r.merchant or r.title,
                f"{names.get(r.account, r.account)} · {n} taksit, son görülen {k}.",
                r.necessity or Necessity.UNKNOWN,
                r.group,
                group_slot(groups, r.group),
                amounts,
                Link(Screen.TRANSACTION, r.fingerprint),
            )
        )
    return sorted(out, key=lambda line: -line.amounts[0])


def _variable(a: Analysis, rows: list[RowView], base: tuple[str, ...], ahead: tuple[str, ...]) -> list[ForecastLine]:
    """Everything else a necessity level at a time: the median of the base months, without regular payments,
    installments and the merchants the rules list as ended. A level, not each merchant: an irregular shop never turns
    into a fixed monthly cost, and the median keeps one big purchase from inflating the month."""
    in_series = {t.fingerprint for s in a.insights.series for t in s.payments}
    ended = a.dataset.ended
    inside = set(base)
    variable = [
        r
        for r in rows
        if month_of(r.day) in inside
        and (r.split_of or r.fingerprint) not in in_series  # a split payment's parts are in its series too
        and not r.installment
        and fold(r.merchant) not in ended
        and r.necessity is not None
    ]
    out: list[ForecastLine] = []
    for level in LEVELS:
        mine = [r for r in variable if r.necessity is level]
        months = [sum((_signed(r) for r in mine if month_of(r.day) == m), ZERO) for m in base]
        typical = Decimal(median(months))
        if typical < 1:
            continue
        seen: dict[str, tuple[Decimal, set[str]]] = {}
        for r in mine:
            total, where = seen.get(r.merchant, (ZERO, set[str]()))
            seen[r.merchant] = (total + _signed(r), where | {month_of(r.day)})
        top = [m for m, (_, where) in sorted(seen.items(), key=lambda item: -item[1][0]) if len(where) >= 2][:4]
        note = f"aylık {format_amount(min(months))} TL ile {format_amount(max(months))} TL arasında"
        if top:
            note += f" · en çok: {', '.join(top)}"
        out.append(
            ForecastLine(
                ForecastPart.VARIABLE,
                NECESSITY[level],
                note,
                level,
                "",
                NECESSITY_SLOTS[level],
                tuple(typical for _ in ahead),
                Link(Screen.TRANSACTIONS, query=(("necessity", level.value),)),
            )
        )
    return out
