"""The balances ahead (F09; docs/domain/interpretation.md, "Nakit akışı öngörüsü"): day by day, per bank account in
TL, for the next 60 days. An estimate (tahmin), always labelled as one.

* The start is today's balance as far as the documents tell: the newest balance a document prints (an account list's
  closing balance, or a bank notice's balance after its row) moved by the receipts and notices that came after it.
* On top of it come the calendar's items the account pays or receives: the regular and periodic payments last paid
  from it, the income last paid into it, the loans' installments and the cards' due dates it pays (in full or in part,
  as the user paid the card's statements before).
* The account's other money out is spread evenly over each month's days: the median month of its last six complete
  months, card payments apart. What came in outside the series is not counted on: irregular income is never projected.
* The days between the balance a document printed and today count too, up to as many days as the forecast looks
  ahead: what was expected on them (a salary paid on the 1st, read on the 2nd from the list of the 31st) is in
  today's balance unless a document says otherwise, so the items and the spread of those days are counted before
  today's, and a note says so.
"""

from calendar import monthrange
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise
from statistics import median

from .analysis import Dataset, Start, start_of, whole
from .domain.codes import CARD_TYPES, AccountType, PaymentKind, TransactionKind
from .domain.labels import format_amount
from .domain.models import TRY
from .domain.money import round_half_up
from .domain.text import fold
from .insights import FULL, Insights, Series, month_name, month_of, pct
from .upcoming import HORIZON, Due, horizon_end

ESTIMATE = "tahmin"  # what every forecast is labelled (F09)
ZERO = Decimal(0)
# The accounts with a balance from day to day; foreign currency and gold move with their rates and are left out.
BANK_TYPES = (AccountType.CURRENT, AccountType.OVERDRAFT, AccountType.DEPOSIT)
CARD_PAYMENTS = (TransactionKind.CARD_PAYMENT, TransactionKind.CARD_PAYMENT_NO_STATEMENT)
# A balance this much older than the newest document says nothing about today (interpretation.md, "Eski belge").
STALE_DAYS = 180
GAP_DAYS = HORIZON  # the days before today a forecast fills in at most, as many as it looks ahead
_BASE_MONTHS = 6  # the complete months the money spread over the days is the median month of
_STATEMENTS = 6  # the card statements whose payments tell how the user pays the card
IN_FULL = Decimal("0.99")  # a statement paid this much of before the next cut was paid in full


@dataclass(frozen=True)
class Spread:
    """Money out the documents tie to no day: the median month, spread evenly over each month's days."""

    monthly: Decimal
    months: tuple[str, ...]  # the complete months it is the median of
    after: date | None = None  # only on the days after this one (card payments after the last due date known)

    def on(self, day: date) -> Decimal:
        if self.after is not None and day <= self.after:
            return ZERO
        return self.monthly / monthrange(day.year, day.month)[1]


@dataclass(frozen=True)
class PaidShare:
    """How the user paid a card's statements before the next cut."""

    share: Decimal  # the median share of a statement's balance paid, 1 in full
    full: int  # statements paid in full
    of: int  # statements looked at


@dataclass
class AccountForecast:
    account: str
    label: str
    start: Start
    days: list[tuple[date, Decimal]]  # the balance at each day's end, from today
    items: list[Due]  # the calendar's items it pays or receives, as counted (a card due at the share the user pays)
    spend: Spread | None  # money out outside the series, card payments apart
    cards: Spread | None  # card payments beyond the due dates known
    notes: list[str]  # what the forecast assumes, in Turkish, each with its window and numbers
    interest: Decimal | None = None  # overdraft interest on the days below zero, only at a rate a document prints
    overdraft: bool = False  # an overdraft account (KMH): below zero is its credit in use
    funded: bool = False  # topped up from the user's own accounts for what it pays (funded_by_own)

    @property
    def negative(self) -> tuple[date, Decimal] | None:
        """The first day the balance is below zero, and the balance that day."""
        return next(((day, balance) for day, balance in self.days if balance < 0), None)

    @property
    def warning(self) -> tuple[date, Decimal] | None:
        """The first day below zero as a warning: none for an overdraft account, whose balance below zero is the
        credit in use, nor for one the user tops up from their own accounts, which goes as low as the transfers the
        forecast does not project (the accounts' total still counts both: Forecast.total_negative)."""
        return None if self.overdraft or self.funded else self.negative

    @property
    def lowest(self) -> tuple[date, Decimal]:
        return min(self.days, key=lambda point: point[1])

    @property
    def end(self) -> Decimal:
        return self.days[-1][1]


@dataclass
class Forecast:
    today: date
    end: date
    accounts: list[AccountForecast]
    elsewhere: list[Due]  # items no forecast account takes: paid by card, or from an account whose balance is unknown
    skipped: list[tuple[str, str]]  # (account, why it has no forecast), by the accounts' labels
    notes: list[str]  # what every account's forecast assumes, in Turkish
    label: str = ESTIMATE

    @property
    def total_negative(self) -> tuple[date, Decimal] | None:
        """The first day the accounts' summed balance is below zero, when it starts at zero or above today: the
        transfers between own accounts cancel out in it, an overdraft's credit in use counts as owed."""
        total: dict[date, Decimal] = defaultdict(Decimal)
        for account in self.accounts:
            for day, balance in account.days:
                total[day] += balance
        days = sorted(total)
        if not days or total[days[0]] < 0:
            return None
        return next(((day, total[day]) for day in days if total[day] < 0), None)

    @property
    def warnings(self) -> list[tuple[str, tuple[date, Decimal]]]:
        """(account, its first day below zero) for each account that warns of one (AccountForecast.warning), then
        ("", the total's) when the total goes below zero and says more than an account does: with one account, or
        one alone below zero, the total is that account's balance."""
        found = [(account.account, first) for account in self.accounts if (first := account.warning) is not None]
        total = self.total_negative
        if total is not None and all(first != total for _, first in found):
            found.append(("", total))
        return found


def _tl(value: Decimal) -> str:
    return f"{format_amount(value)} TL"


def _signed(value: Decimal) -> str:
    return ("+" if value > 0 else "−" if value < 0 else "") + _tl(abs(value))


def _day(d: date) -> str:
    return f"{d:%d.%m.%Y}"


def _window(months: Sequence[str]) -> str:
    return month_name(months[0]) if len(months) == 1 else f"{month_name(months[0])} – {month_name(months[-1])}"


# --- the start ---------------------------------------------------------------------------------------------------


def _newest_document(ds: Dataset) -> date | None:
    days = [s.cut_date for s in ds.statements] + [line.txn.date for line in ds.receipts]
    return max(days, default=None)


def starts(ds: Dataset) -> tuple[dict[str, Start], list[tuple[str, str]]]:
    """Where each TL bank account's forecast starts, and the accounts that have none with why, by their labels."""
    newest = _newest_document(ds)
    found: dict[str, Start] = {}
    skipped: list[tuple[str, str]] = []
    for account in sorted(ds.accounts.values(), key=lambda a: a.label):
        if account.type in (AccountType.FX, AccountType.GOLD) or (
            account.type in BANK_TYPES and account.currency != TRY
        ):
            skipped.append((account.id, "döviz ya da altın hesabı: değeri kurla değişir, öngörü TL hesapları içindir"))
            continue
        if account.type not in BANK_TYPES:
            continue
        start = start_of(ds, account.id)
        if start is None:
            skipped.append((account.id, "bakiyesi hiçbir belgede yazmıyor"))
        elif newest is not None and (newest - start.on).days > STALE_DAYS:
            skipped.append((account.id, f"son bakiye {_day(start.on)} tarihli; bugünkü bakiyesi belgelerde yok"))
        else:
            found[account.id] = start
    return found, skipped


def _begin(start: Start, today: date) -> date:
    """The first day an account's forecast counts: the day after the balance a document printed, today at the latest.
    The days before today the documents do not reach yet count as expected: the receipts and notices after the
    balance tell some of those days' moves, and a series' payment they tell already moves the series' next day on.
    A balance older than GAP_DAYS is not carried over that many days of guesses: the forecast starts from it today."""
    if (today - start.on).days > GAP_DAYS:
        return today
    return min(today, start.on + timedelta(days=1))


def counted_from(ds: Dataset, today: date) -> date:
    """The first day the forecast needs the calendar's items from: the earliest day an account's balance does not
    know of yet, today at the latest (forecast's items start there)."""
    return min([today, *(_begin(start, today) for start in starts(ds)[0].values())])


# --- money out spread over the days ------------------------------------------------------------------------------


def spreads(ds: Dataset, ins: Insights, account: str) -> tuple[Spread | None, Spread | None]:
    """The account's money out outside the series per month, (spending, card payments): each the median month of the
    last six complete months its documents cover in full. Series payments come as items; a transfer between own
    accounts is left out, as its other side is not projected; so are payments to merchants the user listed as ended."""
    covered = ds.coverage.get(account, {})
    months = [m for m in ins.timeline.window[-_BASE_MONTHS:] if covered.get(m, 0) >= FULL]
    if not months:
        return None, None
    groups: tuple[Iterable[Series], ...] = (ins.series, ins.periodic, ins.income)
    in_series = {id(t) for group in groups for s in group for t in s.payments}
    spend, cards = dict.fromkeys(months, ZERO), dict.fromkeys(months, ZERO)
    for t in ds.transactions:
        month = month_of(t.date)
        if (
            t.account != account
            or month not in spend
            or t.amount <= 0
            or id(whole(ds, t)) in in_series  # a split payment's parts are in its series too
            or t.kind == TransactionKind.OWN_TRANSFER
            or fold(t.merchant) in ds.ended
        ):
            continue
        (cards if t.kind in CARD_PAYMENTS else spend)[month] += t.amount
    found = [Spread(median(totals.values()), tuple(months)) for totals in (spend, cards)]
    return found[0], (found[1] if found[1].monthly > 0 else None)


def funded_by_own(ds: Dataset, account: str, months: Sequence[str]) -> tuple[Decimal, Decimal] | None:
    """(money in from the user's own accounts, all money out) over months when the transfers in are at least half of
    what went out: the user tops the account up for what it pays (a card paid from an account the salary never reaches
    directly). None otherwise."""
    into = out = ZERO
    for t in ds.transactions:
        if t.account != account or month_of(t.date) not in months:
            continue
        if t.amount < 0 and t.kind == TransactionKind.OWN_TRANSFER:
            into -= t.amount
        elif t.amount > 0:
            out += t.amount
    return (into, out) if out > 0 and into * 2 >= out else None


# --- who pays what -----------------------------------------------------------------------------------------------


def paying_account(ds: Dataset, card: str) -> str | None:
    """The bank account that paid the card last: a card payment naming the card's last digits, else one made at the
    card's bank when the bank has no other card."""
    found = ds.accounts.get(card)
    if found is None:
        return None
    digits = found.number[-4:]
    alone = sum(1 for a in ds.accounts.values() if a.bank == found.bank and a.type in CARD_TYPES) == 1
    payer = None
    for t in ds.transactions:  # by day: the last match is the newest
        source = ds.accounts.get(t.account)
        if t.kind not in CARD_PAYMENTS or t.amount <= 0 or source is None or source.type in CARD_TYPES:
            continue
        if (digits and digits in t.description) or (alone and source.bank == found.bank):
            payer = t.account
    return payer


def paid_share(ds: Dataset, card: str) -> PaidShare | None:
    """How much of each of its last six statements the card was paid before the next cut, as the next statement
    shows the payments."""
    statements = sorted(
        (s for s in ds.statements if s.account == card and not s.is_account and s.currency == TRY),
        key=lambda s: s.cut_date,
    )
    shares: list[Decimal] = []
    for before, after in pairwise(statements):
        if before.total is None or before.total <= 0:
            continue
        paid = -sum((t.amount for t in after.transactions if t.kind in CARD_PAYMENTS and t.amount < 0), ZERO)
        shares.append(min(Decimal(1), max(ZERO, paid / before.total)))
    shares = shares[-_STATEMENTS:]
    if not shares:
        return None
    return PaidShare(median(shares), sum(1 for s in shares if s >= IN_FULL), len(shares))


def _card_due(ds: Dataset, item: Due, payer: str) -> Due:
    """A card's due date as its paying account pays it: in full, or at the share of its statements the user paid."""
    share = paid_share(ds, item.account)
    if share is None:
        return replace(item, account=payer, basis=f"{item.basis}; geçmiş ödemesi belgelerde yok, tamamı sayıldı")
    if share.share >= IN_FULL:
        basis = f"{item.basis}; son {share.of} ekstreden {share.full} tanesinin tamamı ödendi, tamamı sayıldı"
        return replace(item, account=payer, basis=basis)
    amount = max(item.minimum or ZERO, round_half_up(item.amount * share.share))
    basis = f"{item.basis}; son {share.of} ekstrede ödenen payın medyanı ekstrenin {pct(share.share)}"
    return replace(item, account=payer, amount=amount, basis=basis)


def _assign(ds: Dataset, item: Due, accounts: Collection[str]) -> Due | None:
    """The item as the forecast counts it, on the account it leaves or enters; None when no forecast account takes it
    (a card's own items reach the bank account through the card's payments)."""
    if item.kind == PaymentKind.CARD_DUE:
        payer = paying_account(ds, item.account)
        return _card_due(ds, item, payer) if payer is not None and payer in accounts else None
    if item.kind == PaymentKind.LOAN:
        bank = ds.accounts[item.account].bank
        same = [a for a in accounts if ds.accounts[a].bank == bank]
        if len(same) != 1:
            return None
        payer = ds.accounts[same[0]].label
        return replace(
            item, account=same[0], basis=f"{item.basis}; ödeyen hesap {payer} sayıldı (bankanın tek TL hesabı)"
        )
    return item if item.account in accounts else None


# --- the forecast ------------------------------------------------------------------------------------------------


def _notes(start: Start, spend: Spread | None, cards: Spread | None) -> list[str]:
    where = "banka bildirimindeki bakiye" if start.notice else "hesap dökümünün kapanış bakiyesi"
    first = f"Başlangıç: {_day(start.on)} tarihli {where} {_tl(start.stated)}"
    if start.moves:
        first += f"; sonraki {start.moves} dekont ve bildirimle {_signed(start.told - start.stated)}"
    if start.untold:
        first += (
            f". Ek hesabı olmayan bir hesap eksiye düşmez: arada belgelerde olmayan en az {_tl(start.untold)} girmiş "
            f"olmalı; başlangıç {_tl(start.balance)} sayıldı"
        )
    notes = [f"{first}; {_day(start.through)} sonrasının hareketleri belgelerde yok."]
    if spend is None:
        notes.append("Seri dışı çıkışlar tahmin edilmedi: hesabın belgeleri son tam ayları tam kapsamıyor.")
    else:
        notes.append(
            f"Seri dışı çıkışlar: {_window(spend.months)} arasındaki {len(spend.months)} tam ayın medyanı, ayda "
            f"{_tl(spend.monthly)}, günlere yayıldı."
        )
    if cards is not None:
        text = f"Kart ödemeleri: aynı ayların medyanı, ayda {_tl(cards.monthly)}"
        if cards.after is not None:
            text += f"; bilinen son ödeme tarihinden ({_day(cards.after)}) sonrasına yayıldı"
        notes.append(text + ".")
    return notes


def _gap_note(start: Start, begin: date, today: date, items: Sequence[Due], spread: Decimal) -> str:
    """What the forecast counted for the days before today the documents do not reach yet; "" for nothing."""
    if (today - start.on).days > GAP_DAYS:
        return f"Son bakiye {(today - start.on).days} gün önceki: aradaki günler tahmin edilmedi, öngörü o bakiyeden başlıyor."
    if not items and not spread:
        return ""
    last = today - timedelta(days=1)
    days = f"{_day(begin)} günü" if begin == last else f"{_day(begin)}–{_day(last)} arası"
    parts = [f"{len(items)} kalem ({_signed(-sum((item.amount for item in items), ZERO))})"] if items else []
    if spread:
        parts.append(f"seri dışı çıkışlardan {_tl(spread)}")
    return f"{days} için belgelerin henüz göstermediği beklenenler de sayıldı: {' ve '.join(parts)}."


def _interest(account: AccountForecast, rate: Decimal | None) -> tuple[Decimal | None, str]:
    """Overdraft interest on the days below zero at a monthly rate a document prints; none without one."""
    below = [-balance for _, balance in account.days if balance < 0]
    if not below:
        return None, ""
    if rate is None:
        return None, "KMH faiz oranı belgelerde yazmadığı için faiz tahmin edilmedi."
    interest = round_half_up(sum(below, ZERO) * rate * 12 / 365)
    shown = f"{rate * 100:.2f}".replace(".", ",")
    return interest, f"KMH faizi: belgedeki aylık %{shown} oranıyla, eksi günler için yaklaşık {_tl(interest)}."


def forecast(
    ds: Dataset,
    ins: Insights,
    today: date,
    items: Sequence[Due],
    days: int = HORIZON,
    overdraft_rates: Mapping[str, Decimal] | None = None,
) -> Forecast:
    """The balances of the bank accounts in TL from today on, for days days, with the calendar's items from
    counted_from(ds, today) on: an account counts those dated after the newest day its balance knows of, the days
    before today among them too. Overdraft rates (monthly, by account) come from the documents; none prints one yet,
    so no interest is estimated."""
    end = horizon_end(today, days)
    found, skipped = starts(ds)
    counted: dict[str, list[Due]] = defaultdict(list)
    elsewhere: list[Due] = []
    for item in items:
        taken = _assign(ds, item, found)
        if taken is None:
            if item.day >= today:  # what nobody's balance takes is listed as the calendar lists it: from today on
                elsewhere.append(item)
        elif _begin(found[taken.account], today) <= taken.day <= end:
            counted[taken.account].append(taken)
    accounts = [
        _account(ds, ins, account, start, counted[account], today, end, (overdraft_rates or {}).get(account))
        for account, start in found.items()
    ]
    notes = [
        "Bu bir tahmindir: belgelerdeki son bakiyeden ve geçmiş ödemelerden çıkarıldı.",
        "Düzenli ödemeler en son hangi hesaptan ödendiyse oradan, gelirler en son hangi hesaba geldiyse oraya sayıldı.",
        "Seri dışındaki düzensiz gelirler ve kendi hesaplarınız arasındaki transferler öngörüye girmez.",
    ]
    by_card = sum(
        1 for item in elsewhere if item.account in ds.accounts and ds.accounts[item.account].type in CARD_TYPES
    )
    if by_card:
        notes.append(f"Kartla ödenen {by_card} kalem kartın ekstresine girer; hesaptan kart ödemesiyle çıkar.")
    return Forecast(today, end, accounts, elsewhere, skipped, notes)


def _account(
    ds: Dataset,
    ins: Insights,
    account: str,
    start: Start,
    items: list[Due],
    today: date,
    end: date,
    rate: Decimal | None,
) -> AccountForecast:
    spend, cards = spreads(ds, ins, account)
    dues = [item.day for item in items if item.kind == PaymentKind.CARD_DUE]
    if cards is not None and dues:
        cards = replace(cards, after=max(dues))  # until then the due dates known stand for the card payments
    by_day: dict[date, Decimal] = defaultdict(Decimal)
    for item in items:
        by_day[item.day] += item.amount
    begin = _begin(start, today)
    balance, day, spread_before = start.balance, begin, ZERO
    points: list[tuple[date, Decimal]] = []
    while day <= end:
        spread = sum((s.on(day) for s in (spend, cards) if s is not None), ZERO)
        balance -= by_day[day] + spread
        if day >= today:
            points.append((day, round_half_up(balance)))
        else:
            spread_before += spread
        day += timedelta(days=1)
    notes = _notes(start, spend, cards)
    before = [item for item in items if item.day < today]
    if gap := _gap_note(start, begin, today, before, round_half_up(spread_before)):
        notes.insert(1, gap)
    found = AccountForecast(
        account,
        ds.accounts[account].label,
        start,
        points,
        sorted(items, key=lambda item: (item.day, item.kind, item.title)),
        spend,
        cards,
        notes,
    )
    found.interest, note = _interest(found, rate)
    if note:
        found.notes.append(note)
    found.overdraft = ds.accounts[account].type == AccountType.OVERDRAFT
    if found.overdraft:
        found.notes.append("Ek hesap (KMH): eksi bakiye kullanılan krediyi gösterir; eksiye düşmesi uyarı sayılmaz.")
    elif spend is not None and (topped := funded_by_own(ds, account, spend.months)) is not None:
        found.funded = True
        found.notes.append(
            f"Bu hesaba kendi hesaplarınızdan düzenli para aktarılıyor: {_window(spend.months)} arasında "
            f"{_tl(topped[0])} geldi, hesaptan {_tl(topped[1])} çıktı. Öngörü bu aktarmaları saymaz; bu hesabın eksi "
            "günleri uyarı sayılmaz."
        )
    return found
