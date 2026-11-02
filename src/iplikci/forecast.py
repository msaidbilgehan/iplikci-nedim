"""The balances ahead (F09; docs/domain/interpretation.md, "Nakit akışı öngörüsü"): day by day, per bank account in
TL, for the next 60 days. An estimate (tahmin), always labelled as one.

* The start is today's balance as far as the documents tell: the newest balance a document prints (an account list's
  closing balance, or a bank notice's balance after its row) moved by the receipts and notices that came after it.
* On top of it come the calendar's items the account pays or receives: the regular and periodic payments last paid
  from it, the income last paid into it, the loans' installments and the cards' due dates it pays (in full or in part,
  as the user paid the card's statements before).
* The account's other money out is spread evenly over each month's days: the median month of its last six complete
  months, card payments apart. What came in outside the series is not counted on: irregular income is never projected.
"""

from calendar import monthrange
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise
from statistics import median

from .analysis import NO_STATEMENT, PROVISIONAL, Dataset, ReceiptLine, whole
from .domain.codes import CARD_TYPES, AccountType, PaymentKind, TransactionKind
from .domain.labels import format_amount
from .domain.models import TRY
from .domain.money import CENT, round_half_up
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
_BASE_MONTHS = 6  # the complete months the money spread over the days is the median month of
_STATEMENTS = 6  # the card statements whose payments tell how the user pays the card
IN_FULL = Decimal("0.99")  # a statement paid this much of before the next cut was paid in full


@dataclass(frozen=True)
class Start:
    """Where an account's forecast starts."""

    balance: Decimal  # today's balance as far as the documents tell
    stated: Decimal  # the balance the document printed
    on: date  # the day of that balance
    notice: bool  # a bank notice's balance after its row, not an account list's closing balance
    moves: int  # receipt and notice rows after it, counted in the balance
    through: date  # the newest day the balance knows of


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

    @property
    def negative(self) -> tuple[date, Decimal] | None:
        """The first day the balance is below zero, and the balance that day."""
        return next(((day, balance) for day, balance in self.days if balance < 0), None)

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


def _tl(value: Decimal) -> str:
    return f"{format_amount(value)} TL"


def _signed(value: Decimal) -> str:
    return ("+" if value > 0 else "−" if value < 0 else "") + _tl(abs(value))


def _day(d: date) -> str:
    return f"{d:%d.%m.%Y}"


def _window(months: Sequence[str]) -> str:
    return month_name(months[0]) if len(months) == 1 else f"{month_name(months[0])} – {month_name(months[-1])}"


# --- the start ---------------------------------------------------------------------------------------------------


def last_of_day(found: list[tuple[ReceiptLine, Decimal]]) -> tuple[ReceiptLine, Decimal]:
    """Of the notices one day brought (row, balance after it), the one printed last: the one no other row goes on
    from (its balance less the other row's amount gives the other's balance). When the order cannot be told, the one
    with the largest receipt key (a Vakıfbank notice's key ends in its query number)."""
    last = [
        (line, balance)
        for line, balance in found
        if not any(abs(balance - other.native - after) <= CENT for other, after in found if other is not line)
    ]
    return last[0] if len(last) == 1 else max(found, key=lambda pair: pair[0].key)


def start_of(ds: Dataset, account: str) -> Start | None:
    """Today's balance of an account as far as the documents tell: the newest balance a document prints, an account
    list's closing balance before a notice's on the same day (it closes the whole day), moved by the counted receipt
    and notice rows dated after it. Rows of that same day are taken to be in a notice's balance already."""
    currency = ds.accounts[account].currency
    lists = [s for s in ds.statements if s.account == account and s.is_account and s.currency == currency]
    closing = max((s for s in lists if s.total is not None), key=lambda s: s.cut_date, default=None)
    lines = [line for line in ds.receipts if line.txn.account == account]
    printed = [(line, line.txn.balance) for line in lines if line.txn.balance is not None]
    newest = max((line.txn.date for line, _ in printed), default=None)
    if closing is not None and closing.total is not None and (newest is None or closing.cut_date >= newest):
        on, stated, notice = closing.cut_date, closing.total, False
    elif newest is not None:
        _, stated = last_of_day([(line, balance) for line, balance in printed if line.txn.date == newest])
        on, notice = newest, True
    else:
        return None
    after = [line for line in lines if line.status in (PROVISIONAL, NO_STATEMENT) and line.txn.date > on]
    moved = -sum((line.native for line in after), ZERO)
    through = max((line.txn.date for line in after), default=on)
    return Start(stated + moved, stated, on, notice, len(after), through)


def _newest_document(ds: Dataset) -> date | None:
    days = [s.cut_date for s in ds.statements] + [line.txn.date for line in ds.receipts]
    return max(days, default=None)


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
        first += f"; sonraki {start.moves} dekont ve bildirimle {_signed(start.balance - start.stated)}"
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
    """The balances of the bank accounts in TL from today on, for days days, with the calendar's items. Overdraft
    rates (monthly, by account) come from the documents; none prints one yet, so no interest is estimated."""
    end = horizon_end(today, days)
    newest = _newest_document(ds)
    starts: dict[str, Start] = {}
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
            starts[account.id] = start
    counted: dict[str, list[Due]] = defaultdict(list)
    elsewhere: list[Due] = []
    for item in items:
        taken = _assign(ds, item, starts)
        if taken is None:
            elsewhere.append(item)
        else:
            counted[taken.account].append(taken)
    accounts = [
        _account(ds, ins, account, start, counted[account], today, end, (overdraft_rates or {}).get(account))
        for account, start in starts.items()
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
    balance, day = start.balance, today
    points: list[tuple[date, Decimal]] = []
    while day <= end:
        balance -= by_day[day] + sum((s.on(day) for s in (spend, cards) if s is not None), ZERO)
        points.append((day, round_half_up(balance)))
        day += timedelta(days=1)
    found = AccountForecast(
        account,
        ds.accounts[account].label,
        start,
        points,
        sorted(items, key=lambda item: (item.day, item.kind, item.title)),
        spend,
        cards,
        _notes(start, spend, cards),
    )
    found.interest, note = _interest(found, rate)
    if note:
        found.notes.append(note)
    return found
