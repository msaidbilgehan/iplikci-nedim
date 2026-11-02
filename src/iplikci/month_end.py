"""Month-end reports: how far each month is closed by its statements, and what happened in it.

    exports/ay-sonu/2026-10.html   one page per month: the last twelve and the current one
    exports/ay-sonu/index.html     every month with its status

A month closes ("kapandı") when every account with documents has statements for all of its days, they
check out (card totals, running balances) and every receipt of the month was found on them. Until then
the page says what it waits for: the card statement that comes by e-mail after the next cut date, or the
account movement list the user downloads from the bank. Receipts that came before their statement count
as provisional meanwhile (analysis.settle_receipts).

The pages carry no script: everything is rendered here with statement text escaped, under the report's
Content-Security-Policy without scripts.
"""

import calendar
import html
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from importlib import resources
from pathlib import Path
from statistics import median

from .analysis import (
    ACTIVE_DAYS,
    CONFIRMED,
    NOT_ON_STATEMENT,
    PROVISIONAL,
    Dataset,
    ReceiptLine,
    statement_periods,
    whole,
)
from .categorize import NECESSITY_SLOTS, group_slot
from .domain.codes import (
    CARD_TYPES,
    DEFAULT_EXPENSE_KINDS,
    AccountType,
    EvidenceStatus,
    MonthStatus,
    Necessity,
    TransactionKind,
)
from .domain.labels import ACCOUNT_MONTH_STATUS, KIND, MONTHS, NECESSITY, format_amount
from .domain.labels import MONTH_STATUS as _MONTH_LABELS
from .domain.models import TRY, Account, Statement, Transaction
from .domain.money import TOLERANCE, round_half_up
from .insights import (
    NOT_BANK_ACCOUNTS,
    Insights,
    Series,
    complete_months,
    debt_at,
    fresh_starts,
    month_name,
    month_of,
    receipt_amount,
    salary_timing,
    shift,
    span,
    tl,
)

FOLDER = "ay-sonu"
INDEX = "index.html"
MONTHS_KEPT = 12  # finished months that get a page, besides the current one
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"

CLOSED, WAITING, MISSING, CHECK, RUNNING = (
    MonthStatus.CLOSED,
    MonthStatus.WAITING,
    MonthStatus.MISSING,
    MonthStatus.CHECK,
    MonthStatus.RUNNING,
)
ACCOUNT_STATUS = ACCOUNT_MONTH_STATUS
MONTH_STATUS = _MONTH_LABELS
LATE_DAYS = 5  # a card statement this long past its expected cut date is late (the e-mail did not come)
INCOME_NOTE = "hesap dökümlerindeki gelen para"  # the income note when there is nothing to add
ZERO = Decimal(0)


# --- days ----------------------------------------------------------------------------------------


def first_day(month: str) -> date:
    return date(int(month[:4]), int(month[5:]), 1)


def last_day(month: str) -> date:
    year, mon = int(month[:4]), int(month[5:])
    return date(year, mon, calendar.monthrange(year, mon)[1])


def _days(lo: date, hi: date) -> list[date]:
    return [lo + timedelta(days=n) for n in range((hi - lo).days + 1)]


def _next_cut(cut: date) -> date:
    year, mon = (cut.year, cut.month + 1) if cut.month < 12 else (cut.year + 1, 1)
    return date(year, mon, min(cut.day, calendar.monthrange(year, mon)[1]))


def _ranges(days: list[date]) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    for d in sorted(days):
        if out and (d - out[-1][1]).days == 1:
            out[-1] = (out[-1][0], d)
        else:
            out.append((d, d))
    return out


def range_text(ranges: list[tuple[date, date]]) -> str:
    """[(25 Oct, 31 Oct)] -> '25–31 Ekim'."""
    return ", ".join(
        f"{a.day} {MONTHS[a.month - 1]}" if a == b else f"{a.day}–{b.day} {MONTHS[a.month - 1]}" for a, b in ranges
    )


def _fails(s: Statement) -> bool:
    """A statement whose own check failed. One with nothing to check (a list without movements, a
    statement without a printed total) does not hold a month open."""
    if s.is_account:
        return s.checks_ok < s.checks_total
    return s.difference is not None and abs(s.difference) > TOLERANCE


def statement_check(s: Statement) -> tuple[str, str, str]:
    """(style, mark, word) of a statement's own check: it checked out, failed, or had nothing to check."""
    if _fails(s):
        return "fail", "✗", "tutmuyor"
    return ("ok", "✓", "tutarlı") if s.verified else ("", "–", "denetlenecek satır yok")


def _day(d: date) -> str:
    return f"{d:%d.%m.%Y}"


def _short_day(d: date) -> str:
    return f"{d:%d.%m}"


def period_text(lo: date, hi: date) -> str:
    """'01.10–31.10' within a year, '30.10.2025–02.11.2026' across years."""
    return f"{lo:%d.%m}–{hi:%d.%m}" if lo.year == hi.year else f"{lo:%d.%m.%Y}–{hi:%d.%m.%Y}"


# --- one account in one month -------------------------------------------------------------------


@dataclass
class AccountClose:
    """One account in one month: how far its statements cover the month and whether they check out."""

    account: Account
    status: MonthStatus
    blocking: bool  # the month waits for it (a brokerage account does not: no bill or salary passes through it)
    needed: int  # days of the month its statements should cover (up to today in the current month)
    covered: int
    open: list[tuple[date, date]]  # days not covered: missing before its newest statement, waiting after it
    statements: list[tuple[Statement, date, date]]  # overlapping the month, with the days each one covers
    receipts: list[ReceiptLine]
    balance: Decimal | None  # month-end balance as the list prints it (account lists only)
    last: date  # newest day its statements cover
    next_cut: date | None = None  # cards: the cut date of the statement that will cover the open days
    late: bool = False  # that cut date passed days ago and the statement did not come
    untracked: bool = False  # known only from a passbook: its days after it are not awaited

    @property
    def is_card(self) -> bool:
        return self.account.type in CARD_TYPES

    @property
    def mailed(self) -> bool:
        """Its statements come by e-mail every month (cards, the brokerage account); account movement lists
        are downloaded from the bank."""
        return self.is_card or self.account.type == AccountType.BROKERAGE

    def count(self, status: EvidenceStatus) -> int:
        return sum(line.status == status for line in self.receipts)

    @property
    def problems(self) -> list[str]:
        out = []
        for s, a, b in self.statements:
            if _fails(s):
                out.append(
                    f"{period_text(a, b)} ekstresi bankanın toplamıyla tutmuyor"
                    if self.is_card
                    else f"{period_text(a, b)} dökümünde bakiye {s.checks_ok}/{s.checks_total} satır tutarlı"
                )
        missing = self.count(NOT_ON_STATEMENT)
        if missing:
            out.append(f"{missing} dekont satırı ekstrede yok")
        return out

    @property
    def waiting_for(self) -> str:
        """The document that closes the account's month, in a few words."""
        if self.status == MISSING:
            return f"{range_text(self.open)} {'ekstresi' if self.mailed else 'hesap dökümü'} eksik"
        if self.status == WAITING and self.mailed:
            cut = f", kesim ~{_short_day(self.next_cut)}" if self.is_card and self.next_cut else ""
            return f"{range_text(self.open)} ekstresi{cut}{' (gecikti)' if self.late else ''}"
        if self.status == WAITING:
            return f"{range_text(self.open)} hesap dökümü"
        return "; ".join(self.problems)

    @property
    def note(self) -> str:
        """What there is to know about the account this month, in one line."""
        if self.status == MISSING:
            parts = [
                (
                    f"{range_text(self.open)} için {'ekstre' if self.mailed else 'hesap dökümü'} yok: bankadan "
                    "indirip Belgeler ekranından yükleyin"
                )
            ]
        elif self.status == WAITING and self.mailed:
            when = (
                f" (sonraki kesim ~{_day(self.next_cut)})" if self.is_card and self.next_cut else " (ay sonu ekstresi)"
            )
            parts = [f"{range_text(self.open)} ekstresi e-postayla bekleniyor{when}"]
            if self.late:
                parts.append("beklenen tarih geçti: e-posta gelmediyse ekstreyi bankadan indirin")
        elif self.status == WAITING:
            parts = [
                (f"{range_text(self.open)}: son döküm {_day(self.last)} tarihli; sonrasını bankadan indirip ekleyin")
            ]
        elif self.status == CHECK:
            parts = []
        elif self.untracked:
            parts = [f"{_day(self.last)} tarihli e-cüzdandan sonrası için banka e-postayla döküm göndermiyor"]
        else:
            parts = ["ayın tamamı belgelerle kapsandı ve tutarlı"]
        parts += self.problems
        receipts = [
            f"{n} {label}"
            for status, label in ((CONFIRMED, "dekont eşleşti"), (PROVISIONAL, "dekont geçici"))
            if (n := self.count(status))
        ]
        return "; ".join(parts + receipts)


# --- the month ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Totals:
    income: Decimal | None  # None when no account movement list covers the month
    expense: Decimal  # purchases, refunds, interest and fees
    people: Decimal
    debt: Decimal  # loan principal repaid
    saving: Decimal
    fees: Decimal  # interest and fees, part of expense

    @property
    def left(self) -> Decimal | None:
        if self.income is None:
            return None
        return self.income - self.expense - self.people - self.debt - self.saving


@dataclass
class MonthEnd:
    month: str
    status: MonthStatus
    accounts: list[AccountClose]
    totals: Totals
    previous: Totals | None
    typical: Decimal | None  # median expense of up to six complete months before this one
    typical_months: int
    groups: list[tuple[str, int, Decimal]]  # (group, colour slot, expense)
    levels: list[tuple[str, int, Decimal]]  # (necessity level, colour slot, expense)
    categories: list[tuple[str, int, Decimal, int]]  # (category, its group's slot, expense, count)
    merchants: list[tuple[str, int, Decimal, int]]
    regular: list[tuple[Series, list[Transaction], date | None]]  # payee, payments this month, expected day
    big: list[Transaction]
    provisional: list[Transaction]
    unmatched: list[ReceiptLine]
    count: int  # expense transactions
    trend: list[tuple[str, Decimal]]  # expense of the twelve months up to this one
    income_note: str
    debt_end: Decimal | None  # card statement balances and overdraft use at the month's end
    level_codes: list[Necessity] = field(default_factory=list)  # the levels' codes, in their order (İşlemler's filter)

    @property
    def label(self) -> str:
        return MONTH_STATUS[self.status]

    @property
    def name(self) -> str:
        return month_name(self.month)

    @property
    def file(self) -> str:
        return f"{self.month}.html"

    @property
    def open(self) -> list[AccountClose]:
        return [a for a in self.accounts if a.blocking and a.status != CLOSED]

    @property
    def summary(self) -> str:
        """The month's closing in one sentence, to go after its status label."""
        if self.status == CLOSED:
            matched = sum(a.count(CONFIRMED) for a in self.accounts)
            return "Bütün hesapların belgeleri ayın tamamını kapsıyor ve tutarlı" + (
                f"; {matched} dekont ekstrelerle eşleşti." if matched else "."
            )
        if self.status == RUNNING:
            provisional = len(self.provisional)
            return "Rakamlar şimdiye kadar gelen ekstre ve dökümlerden" + (
                f"; ekstresi henüz gelmemiş {provisional} işlem dekontlardan geçici olarak işlendi."
                if provisional
                else "."
            )
        if not self.accounts:
            return "Bu ay için hiçbir hesabın belgesi yok."
        lead = {
            WAITING: "Kapanması için bekleniyor",
            MISSING: "Kapanması için eksik belge var",
            CHECK: "Kapanmadan önce kontrol edin",
        }[self.status]
        return f"{lead}: " + "; ".join(f"{a.account.label} ({a.waiting_for})" for a in self.open) + "."


class _Shared:
    """What every month's report reads: computed once for all of them."""

    def __init__(self, ds: Dataset, ins: Insights, today: date):
        self.ds, self.ins, self.today = ds, ins, today
        self.periods = statement_periods(ds.statements)
        self.days: dict[str, set[date]] = defaultdict(set)
        tracked: set[str] = set()
        for s, a, b in self.periods:
            self.days[s.account].update(_days(a, b))
            if not s.one_off:
                tracked.add(s.account)
        # Accounts known only from passbooks: the bank sent them once, and no monthly list follows by e-mail.
        self.untracked = set(self.days) - tracked
        self.newest = max((s.cut_date for s in ds.statements), default=today)
        self.fresh = fresh_starts(ds)
        self.full = sorted(complete_months(ds))
        self.by_month: dict[str, list[Transaction]] = defaultdict(list)
        for t in ds.transactions:
            self.by_month[month_of(t.date)].append(t)
        self.receipts: dict[str, list[ReceiptLine]] = defaultdict(list)
        for line in ds.receipts:
            self.receipts[line.txn.account].append(line)

    # -- money ---------------------------------------------------------------------------------
    def expense(self, month: str) -> Decimal:
        return sum((t.amount for t in self.by_month.get(month, []) if t.kind in DEFAULT_EXPENSE_KINDS), ZERO)

    def income_known(self, month: str) -> bool:
        """Like the report: a bank account's movement list covers at least half of the month (of its days so
        far, in the current month)."""
        days = set(_days(first_day(month), min(last_day(month), self.today)))
        return bool(days) and any(
            self.ds.accounts[a].type not in NOT_BANK_ACCOUNTS and len(days & covered) >= 0.5 * len(days)
            for a, covered in self.days.items()
        )

    def totals(self, month: str) -> Totals:
        sums: dict[str, Decimal] = defaultdict(Decimal)
        for t in self.by_month.get(month, []):
            sums["expense" if t.kind in DEFAULT_EXPENSE_KINDS else t.kind] += t.amount
            if t.kind == TransactionKind.INTEREST_FEE:
                sums["fees"] += t.amount
        income = -sums[TransactionKind.INCOME] if self.income_known(month) else None
        return Totals(
            income,
            sums["expense"],
            sums[TransactionKind.P2P_TRANSFER],
            sums[TransactionKind.LOAN_PRINCIPAL],
            sums[TransactionKind.INVESTMENT],
            sums["fees"],
        )

    # -- closing --------------------------------------------------------------------------------
    def closing(self, month: str) -> list[AccountClose]:
        lo, hi = first_day(month), last_day(month)
        end = min(hi, self.today)
        out = []
        for account, covered in self.days.items():
            acc = self.ds.accounts[account]
            first, last = min(covered), max(covered)
            untracked = account in self.untracked
            # Its later days are awaited only while documents keep coming for it, never after a passbook alone.
            active = (self.newest - last).days <= ACTIVE_DAYS and not untracked
            if first > hi or (last < lo and not active):
                continue  # not open yet, or its documents stopped long before (closed)
            opened = month_of(first) == month and account in self.fresh  # opened this month: nothing before
            needed = [d for d in _days(lo, end) if not (d < first and opened) and not (d > last and not active)]
            holes = [d for d in needed if d not in covered]
            missing, waiting = [d for d in holes if d < last], [d for d in holes if d > last]
            stmts = [(s, a, b) for s, a, b in self.periods if s.account == account and a <= hi and b >= lo]
            lines = [line for line in self.receipts.get(account, []) if lo <= line.txn.date <= hi]
            if missing:
                status = MISSING
            elif waiting:
                status = WAITING
            elif any(_fails(s) for s, _, _ in stmts) or any(line.status == NOT_ON_STATEMENT for line in lines):
                status = CHECK
            else:
                status = CLOSED
            ac = AccountClose(
                acc,
                status,
                acc.type != AccountType.BROKERAGE,
                len(needed),
                len(needed) - len(holes),
                _ranges(missing or waiting),
                stmts,
                lines,
                None,
                last,
                untracked=untracked,
            )
            if not ac.is_card:
                covering = next((s for s, a, b in self.periods if s.account == account and a <= hi <= b), None)
                if covering is not None and acc.type == AccountType.BROKERAGE:
                    # Cash plus the securities at the market value the month's statement prints.
                    ac.balance = round_half_up(
                        (covering.total or ZERO) + sum((x.value for x in covering.securities), ZERO)
                    )
                elif covering is not None:
                    known = [m for m in covering.balances if m <= month]
                    ac.balance = covering.balances[max(known)] if known else covering.previous
            elif status == WAITING:
                cuts = [s.cut_date for s, _, _ in self.periods if s.account == account]
                ac.next_cut = _next_cut(max(cuts))
                while ac.next_cut < waiting[-1]:
                    ac.next_cut = _next_cut(ac.next_cut)
                ac.late = (self.today - ac.next_cut).days > LATE_DAYS
            if acc.type == AccountType.BROKERAGE and status == WAITING:
                # The brokerage statement covers a calendar month and comes in the first days of the next.
                ac.late = (self.today - last_day(month_of(waiting[-1]))).days > 2 * LATE_DAYS
            out.append(ac)
        order = {CHECK: 0, MISSING: 1, WAITING: 2, CLOSED: 3}
        return sorted(out, key=lambda a: (not a.blocking, order[a.status], a.account.bank, a.account.label))

    def status(self, month: str, accounts: list[AccountClose]) -> str:
        if month >= month_of(self.today):
            return RUNNING
        blocking = [a for a in accounts if a.blocking]
        if not blocking:
            return MISSING
        for status in (MISSING, CHECK, WAITING):
            if any(a.status == status for a in blocking):
                return status
        return CLOSED

    # -- the report -------------------------------------------------------------------------------
    def month_end(self, month: str) -> MonthEnd:
        ds, ins = self.ds, self.ins
        accounts = self.closing(month)
        status = self.status(month, accounts)
        txns = self.by_month.get(month, [])
        spent = [t for t in txns if t.kind in DEFAULT_EXPENSE_KINDS]
        prior = [m for m in self.full if m < month][-6:]
        typical = median(self.expense(m) for m in prior) if len(prior) >= 3 else None

        def ranked(key) -> list[tuple[str, Decimal, int]]:
            sums: dict[str, Decimal] = defaultdict(Decimal)
            paid: dict[str, set[object]] = defaultdict(set)  # the payments behind each: a split row's parts are one
            for t in spent:
                k = key(t)
                sums[k] += t.amount
                paid[k].add(t.split_of or id(t))
            return sorted(((k, v, len(paid[k])) for k, v in sums.items() if v >= 1), key=lambda x: -x[1])

        groups = [(g, group_slot(ds.groups, g), v) for g, v, _ in ranked(lambda t: t.group)]
        by_level = {level: v for level, v, _ in ranked(lambda t: t.necessity or Necessity.UNKNOWN)}
        levels = [(NECESSITY[code], NECESSITY_SLOTS[code], by_level[code]) for code in Necessity if code in by_level]
        group_of = {t.category: t.group for t in spent}
        categories = [(c, group_slot(ds.groups, group_of[c]), v, n) for c, v, n in ranked(lambda t: t.category)[:10]]
        merchant_group = {t.merchant: t.group for t in spent}
        merchants = [
            (m, group_slot(ds.groups, merchant_group[m]), v, n) for m, v, n in ranked(lambda t: t.merchant)[:10]
        ]

        regular = []
        for s in ins.series:
            paid = [t for t in s.payments if month_of(t.date) == month]
            if paid:
                regular.append((s, paid, None))
            elif s.running and s.expected and month_of(s.expected) == month:
                regular.append((s, [], s.expected))
        regular.sort(key=lambda r: (not r[1], -_regular_amount(r)))

        expense = self.expense(month)
        threshold = max(Decimal(5000), Decimal("0.1") * (typical or expense))
        # Payments as made: a split purchase is large or not as a whole, and is listed once.
        payments = list({id(w): w for w in (whole(ds, t) for t in spent)}.values())
        big = sorted(
            (t for t in payments if t.kind == TransactionKind.PURCHASE and t.amount >= threshold),
            key=lambda t: -t.amount,
        )[:8]
        waiting = {id(w): w for w in (whole(ds, t) for t in txns if t.provisional)}
        totals = self.totals(month)
        return MonthEnd(
            month=month,
            status=status,
            accounts=accounts,
            totals=totals,
            previous=self.totals(shift(month, -1)) if shift(month, -1) in self.by_month else None,
            typical=typical,
            typical_months=len(prior),
            groups=groups,
            levels=levels,
            level_codes=[code for code in Necessity if code in by_level],
            categories=categories,
            merchants=merchants,
            regular=regular,
            big=big,
            provisional=sorted(waiting.values(), key=lambda t: t.date),
            unmatched=sorted(
                (line for line in ds.receipts if line.status == NOT_ON_STATEMENT and month_of(line.txn.date) == month),
                key=lambda line: line.txn.date,
            ),
            count=len({t.split_of or id(t) for t in spent}),
            trend=[(m, self.expense(m)) for m in span(shift(month, -11), month)],
            income_note=self.income_note(month, totals, accounts, status),
            debt_end=debt_at(ds, last_day(month)) if status != RUNNING else None,
        )

    def income_note(self, month: str, totals: Totals, accounts: list[AccountClose], status: MonthStatus) -> str:
        if totals.income is None:
            return "bu ay için hesap dökümü yok: gelir bilinmiyor"
        partial = [a.account.label for a in accounts if a.blocking and not a.is_card and a.status in (WAITING, MISSING)]
        notes = []
        if partial and status != RUNNING:
            notes.append(f"gelir eksik olabilir: {', '.join(partial)} dökümü ayın tamamını kapsamıyor")
        if status != RUNNING:
            missing, double = salary_timing(self.ins.income, [month])
            if missing:
                notes.append("maaş bu ay görünmüyor: ödeme günü bir önceki ya da sonraki aya denk geldi")
            if double:
                notes.append("bu ay iki maaş var: ödeme günleri ayın başına ve sonuna denk geldi")
        return "; ".join(notes) or INCOME_NOTE


def _regular_amount(row: tuple[Series, list[Transaction], date | None]) -> Decimal:
    series, paid, _ = row
    return sum((abs(t.amount) for t in paid), ZERO) or series.monthly


def report_months(ds: Dataset, today: date) -> list[str]:
    """The current month and the twelve before it, from the first month with any data."""
    seen = [month_of(t.date) for t in ds.transactions] + [m for cov in ds.coverage.values() for m in cov]
    if not seen:
        return []
    last = month_of(today)
    first = max(min(seen), shift(last, -MONTHS_KEPT))
    return span(first, last)


def build(ds: Dataset, ins: Insights, today: date | None = None, months: list[str] | None = None) -> list[MonthEnd]:
    today = today or date.today()
    months = report_months(ds, today) if months is None else months
    shared = _Shared(ds, ins, today)
    return [shared.month_end(m) for m in months]


# --- rendering ----------------------------------------------------------------------------------------


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _template(name: str) -> str:
    return resources.files("iplikci").joinpath("templates", name).read_text(encoding="utf-8")


_PAGE = """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="viz-root month-end">
{body}
</div>
</body>
</html>
"""

_TONES = {
    CLOSED: ("iyi", "✓"),
    WAITING: ("bekle", "…"),
    RUNNING: ("bekle", "…"),
    MISSING: ("dikkat", "!"),
    CHECK: ("dikkat", "!"),
}


def _page(title: str, body: str) -> str:
    css = _template("rapor.css") + "\n" + _template("aysonu.css")
    return _PAGE.format(csp=_e(CSP), title=_e(title), css=css, body=body)


def _badge(status: MonthStatus, label: str) -> str:
    tone, icon = _TONES[status]
    return f'<span class="tone {tone}"><span class="icon" aria-hidden="true">{icon}</span>{_e(label)}</span>'


def _money(value: Decimal | None) -> str:
    return "–" if value is None else _e(tl(value))


def _amount(value: Decimal, currency: str) -> str:
    if currency == TRY:
        return _e(tl(value))
    return _e(("−" if value < 0 else "") + f"{format_amount(abs(value))} {currency}")


def _swatch(slot: int) -> str:
    color = f"var(--s{slot})" if slot else "var(--other)"
    return f'<span class="swatch" style="background:{color}" aria-hidden="true"></span>'


def _sparkline(points: list[tuple[str, Decimal]]) -> str:
    """The month's expense against the eleven before it: de-emphasis line, this month in the accent."""
    values = [float(v) for _, v in points]  # drawing coordinates, not money
    if len([v for v in values if v]) < 2:
        return ""
    width, height = 150, 36
    lo, hi = min(0.0, *values), max(values) or 1.0
    x = lambda i: 2 + i * (width - 8) / (len(values) - 1)
    y = lambda v: height - 4 - (v - lo) / ((hi - lo) or 1.0) * (height - 8)
    line = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
    spoken = ", ".join(f"{month_name(m)} {tl(v)}" for m, v in points)
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{_e("Son 12 ayın gideri: " + spoken)}"><title>{_e("Son 12 ay: " + spoken)}</title>'
        f'<polyline points="{line}" fill="none" style="stroke:var(--muted)" stroke-width="2" '
        'stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{x(len(values) - 1):.1f}" cy="{y(values[-1]):.1f}" r="4" '
        'style="fill:var(--accent);stroke:var(--surface)" stroke-width="2"/></svg>'
    )


def _delta(now: Decimal, before: Decimal | None, what: str) -> str:
    """Change against a named period; for spending, up is the bad direction."""
    if not before or before <= 0:
        return ""
    change = (now - before) / before
    direction, icon, word = ("up", "▲", "fazla") if change >= 0 else ("down", "▼", "az")
    text = f"{what} %{abs(change) * 100:.0f} {word}"
    return f'<div class="delta {direction}"><span class="icon" aria-hidden="true">{icon} </span>{_e(text)}</div>'


def _tile(label: str, value: str, meta: str, extra: str = "", hero: bool = False) -> str:
    return (
        f'<div class="tile{" hero" if hero else ""}"><div class="label">{_e(label)}</div>'
        f'<div class="value">{value}</div><div class="meta">{_e(meta)}</div>{extra}</div>'
    )


def _table(head: list[tuple[str, bool]], rows: list[list[str]], foot: list[str] | None = None) -> str:
    """head: (label, numeric); cells are HTML already escaped."""
    th = "".join(f'<th class="num">{_e(h)}</th>' if num else f"<th>{_e(h)}</th>" for h, num in head)
    body = "".join(
        "<tr>"
        + "".join(f'<td class="num">{c}</td>' if head[i][1] else f"<td>{c}</td>" for i, c in enumerate(r))
        + "</tr>"
        for r in rows
    )
    tfoot = (
        (
            "<tfoot><tr>"
            + "".join(f'<td class="num">{c}</td>' if head[i][1] else f"<td>{c}</td>" for i, c in enumerate(foot))
            + "</tr></tfoot>"
        )
        if foot
        else ""
    )
    return f'<div class="table-wrap"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody>{tfoot}</table></div>'


def _bars(rows: list[tuple[str, int, Decimal]], total: Decimal, what: str) -> str:
    """A ranked bar list that is also its own table: name, bar, amount, share."""
    if not rows:
        return '<p class="empty">Bu ay gider yok.</p>'
    top = max(v for _, _, v in rows)
    out = []
    for name, slot, value in rows:
        share = value / total if total > 0 else 0
        color = f"var(--s{slot})" if slot else "var(--other)"
        out.append(
            f'<tr title="{_e(f"{name}: {tl(value)} (%{share * 100:.0f})")}"><td><span class="cat-cell">{_swatch(slot)}'
            f'{_e(name)}</span></td><td class="bar-cell"><span class="bar" style="width:{value / top * 100:.1f}%;'
            f'background:{color}"></span></td><td class="num">{_e(tl(value))}</td>'
            f'<td class="num">%{share * 100:.0f}</td></tr>'
        )
    return (
        f'<div class="table-wrap"><table class="bars"><thead><tr><th>{_e(what)}</th><th><span class="sr">Çubuk'
        '</span></th><th class="num">Tutar</th><th class="num">Pay</th></tr></thead><tbody>'
        + "".join(out)
        + "</tbody></table></div>"
    )


def _nav(months: list[str], month: str | None, home: str) -> str:
    links = []
    if month in months:
        i = months.index(month)
        if i > 0:
            links.append(f'<a href="{months[i - 1]}.html">‹ {_e(month_name(months[i - 1]))}</a>')
        links.append(f'<a href="{INDEX}">Bütün aylar</a>')
        if i + 1 < len(months):
            links.append(f'<a href="{months[i + 1]}.html">{_e(month_name(months[i + 1]))} ›</a>')
    links.append(f'<a href="{_e(home)}">Ana rapor</a>')
    return '<nav class="month-nav" aria-label="Aylar">' + "".join(links) + "</nav>"


def _closing_table(me: MonthEnd) -> str:
    rows = []
    for a in me.accounts:
        docs = []
        for s, lo, hi in a.statements:
            what = f"kesim {_short_day(s.cut_date)}" if not s.is_account else period_text(lo, hi)
            cls, mark, word = statement_check(s)
            docs.append(
                f'<span class="status {cls}" title="{_e(word)}"><span class="icon" aria-hidden="true">{mark}'
                f"</span>{_e(what)}</span>"
            )
        receipts = [
            f"{n} {label}"
            for status, label in ((CONFIRMED, "eşleşti"), (PROVISIONAL, "geçici"), (NOT_ON_STATEMENT, "ekstrede yok"))
            if (n := a.count(status))
        ]
        label = a.account.label + ("" if a.blocking else " (ayın kapanmasını beklemez)")
        rows.append(
            [
                _e(label),
                _badge(a.status, ACCOUNT_STATUS[a.status]),
                f"{a.covered}/{a.needed}",
                "<br>".join(docs) or "–",
                _e(", ".join(receipts) or "–"),
                "–" if a.balance is None else _amount(a.balance, a.account.currency),
                f'<span class="muted small">{_e(a.note)}</span>',
            ]
        )
    if not rows:
        return '<p class="empty">Bu ay için hiçbir hesabın belgesi yok.</p>'
    return _table(
        [
            ("Hesap", False),
            ("Durum", False),
            ("Kapsanan gün", True),
            ("Belgeler", False),
            ("Dekontlar", False),
            ("Ay sonu bakiyesi", True),
            ("Açıklama", False),
        ],
        rows,
    )


def _txn_table(rows: list[Transaction], ds: Dataset) -> str:
    return _table(
        [("Tarih", False), ("Hesap", False), ("Açıklama", False), ("Tür", False), ("Tutar", True)],
        [
            [
                _e(_day(t.date)),
                _e(ds.accounts[t.account].label),
                _e(t.merchant or t.description),
                _e(KIND.get(t.kind, t.kind)),
                f'<span class="{"neg" if t.amount < 0 else ""}">{_e(tl(t.amount))}</span>',
            ]
            for t in rows
        ],
    )


def render_month(me: MonthEnd, ds: Dataset, months: list[str], made: datetime, home: str) -> str:
    t, prev = me.totals, me.previous
    title = f"{me.name} ay sonu raporu"
    head = (
        f'<header class="top"><div><h1>{_e(title)}</h1><p class="sub">Oluşturulma {_e(f"{made:%d.%m.%Y %H:%M}")}'
        f" · kart ekstreleri, hesap dökümleri ve dekontlardan</p></div>{_nav(months, me.month, home)}</header>"
    )
    status = (
        f'<section class="card status-card" aria-label="Kapanış durumu">{_badge(me.status, me.label)}'
        f"<p>{_e(me.summary)}</p></section>"
    )

    # An open month lacks the days its statements have not reached yet: compared with whole months it only
    # looks cheaper.
    closed = me.status == CLOSED
    compare = (
        (
            _delta(t.expense, prev.expense if prev else None, "geçen aydan")
            + _delta(t.expense, me.typical, f"son {me.typical_months} tam ayın medyanından")
        )
        if closed
        else ""
    )
    spent_note = f"harcama, iade, faiz ve ücret · {me.count} işlem"
    if not closed:
        spent_note += " · ay kapanmadı: bekleyen ekstrelerle artabilir"
    tiles = [
        _tile("Gider", _e(tl(t.expense)), spent_note, compare + _sparkline(me.trend), hero=True),
        _tile("Gelir", _money(t.income), me.income_note),
        _tile(
            "Kişilere ve borca giden",
            _e(tl(t.people + t.debt)),
            f"kişilere {tl(t.people)} · kredi ve borç {tl(t.debt)}",
        ),
        _tile(
            "Şimdiye kadar kalan" if me.status == RUNNING else "Ay sonunda kalan",
            _money(t.left),
            "gelir − gider − kişilere − borç − birikim" if t.left is not None else "gelir bilinmediği için yok",
        ),
    ]
    kpis = f'<section class="kpis month" aria-label="Özet">{"".join(tiles)}</section>'

    debt = (
        f'<p class="hint">Ay sonunda kart ekstre borçları ve ek hesap kullanımı (belgelerin gösterdiği kadarıyla): '
        f"{_e(tl(me.debt_end))}.</p>"
        if me.debt_end is not None
        else ""
    )
    closing = (
        '<section class="card"><div class="card-head"><div><h2>Ekstre ile kapanış</h2><p class="hint">'
        "Her hesabın bu aydaki günlerini ekstre ya da hesap dökümü kapsıyor mu, belgeler tutarlı mı ve "
        "dekontlar ekstrelerde bulundu mu. Kart ekstreleri e-postayla gelir; hesap dökümlerini bankadan "
        f"indirip İplikçi Nedim'in Belgeler ekranından yükleyin.</p></div></div>{_closing_table(me)}{debt}</section>"
    )

    expense = [
        (
            '<section class="card"><div class="card-head"><div><h2>Giderler</h2><p class="hint">Harcama, iade, '
            "faiz ve ücretler; kişilere gönderilen para, kredi anaparası ve hesaplar arası transferler ayrı.</p>"
            '</div></div><div class="split">'
        ),
        f'<div><h3 class="subhead first">Ana gruplara göre</h3>{_bars(me.groups, t.expense, "Grup")}</div>',
        (
            f'<div><h3 class="subhead first">Gerekliliğe göre</h3>{_bars(me.levels, t.expense, "Gereklilik")}'
            "</div></div>"
        ),
    ]
    if me.categories:
        expense.append(
            '<div class="split"><div><h3 class="subhead">En çok harcanan kategoriler</h3>'
            + _table(
                [("Kategori", False), ("Tutar", True), ("İşlem", True)],
                [
                    [f'<span class="cat-cell">{_swatch(slot)}{_e(c)}</span>', _e(tl(v)), str(n)]
                    for c, slot, v, n in me.categories
                ],
            )
            + "</div>"
        )
        expense.append(
            '<div><h3 class="subhead">En çok harcama yapılan yerler</h3>'
            + _table(
                [("İşyeri", False), ("Tutar", True), ("İşlem", True)],
                [
                    [f'<span class="cat-cell">{_swatch(slot)}{_e(m)}</span>', _e(tl(v)), str(n)]
                    for m, slot, v, n in me.merchants
                ],
            )
            + "</div></div>"
        )
    if me.big:
        expense.append(
            '<h3 class="subhead">Büyük tek seferlik harcamalar</h3>'
            + _table(
                [("Tarih", False), ("İşyeri", False), ("Kategori", False), ("Tutar", True)],
                [[_e(_day(x.date)), _e(x.merchant), _e(x.category), _e(tl(x.amount))] for x in me.big],
            )
        )
    expense.append("</section>")

    sections = [head, "<main>", status, kpis, closing, "".join(expense)]
    if me.regular:
        rows = []
        for s, paid, expected in me.regular:
            when = (
                f"Ödendi {', '.join(_short_day(x.date) for x in paid)}"
                if paid
                else f"Bekleniyor ~{_short_day(expected)}"
            )
            rows.append(
                [
                    _e(s.merchant),
                    _e(s.last.category),
                    _e(when),
                    _e(tl(sum((abs(x.amount) for x in paid), ZERO))) if paid else "–",
                    _e(tl(s.monthly)),
                ]
            )
        sections.append(
            '<section class="card"><div class="card-head"><div><h2>Düzenli ödemeler</h2><p class="hint">'
            "Bu ay ödenenler ve beklenen günü bu aya düşüp henüz görünmeyenler.</p></div></div>"
            + _table(
                [("İşyeri / kişi", False), ("Kategori", False), ("Durum", False), ("Bu ay", True), ("Aylık", True)],
                rows,
            )
            + "</section>"
        )
    if me.provisional or me.unmatched:
        parts = ['<section class="card"><div class="card-head"><div><h2>Dekontlar</h2></div></div>']
        if me.provisional:
            parts.append(
                '<h3 class="subhead first">Geçici kayıtlar</h3><p class="hint">Ekstresi ya da dökümü henüz '
                "gelmemiş günlerden, bankanın e-postayla gönderdiği dekontlarla işlendi; belge gelince "
                "satırlarıyla eşleşip kesinleşecek.</p>" + _txn_table(me.provisional, ds)
            )
        if me.unmatched:
            parts.append(
                '<h3 class="subhead">Ekstrede görünmeyen dekontlar</h3><p class="hint">Aynı günleri kapsayan '
                "ekstre ya da döküm bu işlemi göstermiyor: iptal edilmiş, başka hesaptan yapılmış ya da "
                "dekont başka bir hesaba yazılmış olabilir. Toplamlara ekstredeki satırlar katıldı.</p>"
                + _table(
                    [("Tarih", False), ("Hesap", False), ("Açıklama", False), ("Tutar", True)],
                    [
                        [
                            _e(_day(line.txn.date)),
                            _e(ds.accounts[line.txn.account].label),
                            _e(line.txn.description),
                            _e(receipt_amount(ds, line)),
                        ]
                        for line in me.unmatched
                    ],
                )
            )
        parts.append("</section>")
        sections.append("".join(parts))
    sections.append("</main>")
    sections.append(
        '<footer class="foot">Bu sayfa bu bilgisayarda, belgelerinizden üretildi; hiçbir veri internete '
        "gönderilmez. Rakamlar ana raporla aynı kaynaktan; kategoriler kural dosyalarından."
        "</footer>"
    )
    return _page(f"{title} — İplikçi Nedim", "\n".join(sections))


def render_index(items: list[MonthEnd], made: datetime, home: str) -> str:
    rows = []
    for me in reversed(items):
        t = me.totals
        # A month without the salary (or with two) explains its income and what was left.
        notes = [me.summary] + (
            [me.income_note[0].upper() + me.income_note[1:] + "."] if me.income_note != INCOME_NOTE else []
        )
        rows.append(
            [
                f'<a class="nowrap" href="{_e(me.file)}">{_e(me.name)}</a>',
                _badge(me.status, me.label),
                _e(tl(t.expense)),
                _money(t.income),
                _money(t.left),
                str(len(me.provisional)) if me.provisional else "–",
                "<br>".join(f'<span class="muted small">{_e(n)}</span>' for n in notes),
            ]
        )
    table = _table(
        [
            ("Ay", False),
            ("Durum", False),
            ("Gider", True),
            ("Gelir", True),
            ("Kalan", True),
            ("Geçici kayıt", True),
            ("Açıklama", False),
        ],
        rows,
    )
    body = (
        f'<header class="top"><div><h1>Ay sonu raporları</h1><p class="sub">Oluşturulma '
        f"{_e(f'{made:%d.%m.%Y %H:%M}')}</p></div>{_nav([], None, home)}</header><main>"
        '<section class="card"><p class="hint">Bir ay, bütün hesapların ekstreleri ve dökümleri ayın tamamını '
        "kapsayıp tutarlı çıkınca ve dekontlar ekstrelerde bulununca kapanır. Kapanmamış ayların rakamları "
        f"gelen belgelerle değişebilir.</p>{table}</section></main>"
    )
    return _page("Ay sonu raporları — İplikçi Nedim", body)


HOME = "../gider_raporu.html"  # the report, seen from a month-end page


def write_page(me: MonthEnd, ds: Dataset, folder: Path, months: list[str], made: datetime | None = None) -> Path:
    """One month's page; months are the ones its navigation links to."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / me.file
    path.write_text(render_month(me, ds, months, made or datetime.now(), HOME), encoding="utf-8")
    return path


def write_all(items: list[MonthEnd], ds: Dataset, folder: Path, made: datetime | None = None) -> list[Path]:
    """One page per month plus the index; returns the pages written."""
    made = made or datetime.now()
    folder.mkdir(parents=True, exist_ok=True)
    months = [me.month for me in items]
    written = [write_page(me, ds, folder, months, made) for me in items]
    index = folder / INDEX
    index.write_text(render_index(items, made, HOME), encoding="utf-8")
    return [*written, index]
