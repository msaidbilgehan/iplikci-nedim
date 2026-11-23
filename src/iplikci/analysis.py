"""Combine parse results into one categorized dataset.

Account movement lists bring the hard part: a transfer row only says "money
went to X" or "came from Y". Each candidate is resolved in this order:
own name or own account number -> the category rules -> the same
receiver bank and amount as an earlier, named payment (rent paid from another
account) -> a matching opposite row in another own account -> money from or
to another person.

Receipts (dekont, mostly e-mailed by the bank right after a transfer) bring the
news before the statement does: a receipt's row counts as provisional until a
statement of its account covers its day, then the statement's own row takes
its place (the receipt is confirmed) or, when the statement does not show it,
the receipt is flagged for a look.

Movement lists the user downloads cover any dates, so two lists of one account
may cover the same days: each such day's rows are counted from one list only.
"""

import calendar
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from .categorize import Categorizer, clean_description
from .domain.codes import (
    CARD_TYPES,
    AccountType,
    DocumentKind,
    EvidenceStatus,
    RateSource,
    TransactionKind,
    TransferStep,
)
from .domain.dates import add_months
from .domain.fingerprint import Fingerprints
from .domain.labels import EVIDENCE_STATUS, format_amount, format_rate
from .domain.models import TRY, Account, DeclaredIncome, Invoice, ParseResult, Statement, Transaction
from .domain.money import CENT, round_half_up
from .domain.text import fold
from .fx.book import EMPTY, RateBook, to_tl
from .invoices import InvoiceMatch, one_copy, settled_until
from .invoices import match as match_invoices
from .parsers.registry import document_type, label

# What the statements say about a receipt's row.
PROVISIONAL = EvidenceStatus.PROVISIONAL  # after the account's newest statement: counts now, the next one confirms it
CONFIRMED = EvidenceStatus.MATCHED  # a statement shows the same transaction: the statement's row counts
NOT_ON_STATEMENT = EvidenceStatus.UNMATCHED  # a statement covers its days but does not show it: left out, a look
NO_STATEMENT = EvidenceStatus.NO_STATEMENT  # a period no statement of the account covers (older, or a loan)
RECEIPT_STATUS = EVIDENCE_STATUS
# A statement books a receipt's transaction from the day before (a late-evening transfer) to three days
# after it (a weekend or holiday in between).
POSTING_DAYS = (-1, 3)
# A transfer's receiving side is booked from the day before its sending side (a late-evening transfer) to four days
# after it; a card payment's card side likewise after the paying account's.
TRANSFER_DAYS = (-1, 4)
# An account whose statements stopped this long before the newest statement is closed or no longer
# followed: no statement is expected for it any more.
ACTIVE_DAYS = 180


@dataclass
class DocumentStatus:
    name: str
    origin: str
    status: str  # "ekstre", "hesap", "dekont", "bildirim", "fatura", "atlandi", "is", "hata"
    detail: str = ""


@dataclass
class ReceiptLine:
    """One row of a receipt and what the statements say about it."""

    txn: Transaction
    key: str  # the receipt it came from
    status: EvidenceStatus
    native: Decimal  # amount in the account's currency (txn.amount is turned into TRY for a foreign-currency account)
    match: Transaction | None = None  # the statement's row that confirmed it


@dataclass
class Dataset:
    accounts: dict[str, Account]
    statements: list[Statement]
    transactions: list[Transaction]
    documents: list[DocumentStatus]
    groups: list[str]  # in color-slot order, "Diğer" last
    categories: dict[str, str]  # category -> group, in rule-file order
    coverage: dict[str, dict[str, float]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    rates: dict[str, list[tuple[date, Decimal]]] = field(default_factory=dict)  # currency -> (date, TRY rate)
    ended: dict[str, str] = field(default_factory=dict)  # folded merchant -> last month (the rules' `_biten`)
    # Folded payer -> the income the user says comes every month (the rules' `_düzenli_gelir`).
    declared: dict[str, DeclaredIncome] = field(default_factory=dict)
    regular: set[str] = field(default_factory=set)  # commitment categories (the rules' `_düzenli`)
    receipts: list[ReceiptLine] = field(default_factory=list)  # every receipt row, counted or not
    invoices: list[InvoiceMatch] = field(default_factory=list)  # non-bank bills and receipts, never counted (F14)
    # The rows the user split (F04), whole, by fingerprint: `transactions` holds their parts in their place.
    split: dict[str, Transaction] = field(default_factory=dict)
    # The rates the providers published (architecture §15), as the analysis read them from the database: they value the
    # foreign rows no document gives a rate for and the balances, and the banks' rates are compared with them. Empty
    # without the network: the documents' own rates are used then.
    book: RateBook = EMPTY


def whole(ds: Dataset, t: Transaction) -> Transaction:
    """The row a part of a split row makes up; any other row is whole already."""
    return ds.split.get(t.split_of, t) if t.split_of else t


def payments(ds: Dataset) -> list[Transaction]:
    """The ledger's rows as payments: a split row whole, where its first part stands. The parts count the money by
    category; a payment's series, size and place in its document are the whole row's."""
    if not ds.split:
        return ds.transactions
    out: list[Transaction] = []
    seen: set[str] = set()
    for t in ds.transactions:
        if not t.split_of:
            out.append(t)
        elif t.split_of not in seen:
            seen.add(t.split_of)
            out.append(whole(ds, t))
    return out


def _one_month_before(d: date) -> date:
    year, month = (d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _link_foreign_currency(statements: list[Statement]) -> None:
    """Name the TL line that settles a card's USD/EUR balance after the purchases behind it."""
    foreign = {(s.account, s.cut_date): s for s in statements if s.currency != TRY and not s.is_account}
    for s in statements:
        if s.currency != TRY or s.is_account:
            continue
        for t in s.transactions:
            if "USD/EUR BORCUNUZUN" not in fold(t.description):
                continue
            fx = foreign.get((s.account, t.date))
            buys = [x for x in fx.transactions if x.kind == TransactionKind.PURCHASE] if fx else []
            if buys:
                names = list(dict.fromkeys(clean_description(x.description) for x in buys))
                t.description = "Yurt dışı harcama: " + ", ".join(names)
                t.original = f"{format_amount(sum((x.amount for x in buys), Decimal(0)))} {fx.currency}"
            else:
                t.description = "Yurt dışı harcamaların TL karşılığı"


def statement_periods(statements: list[Statement]) -> list[tuple[Statement, date, date]]:
    """(statement, first day, last day) of the period each statement covers. A card statement in a
    foreign currency is left out: its TL statement covers the same days.

    A gap between two card statements counts as covered when the later one
    starts from the earlier one's closing balance: the bank skipped the months
    without any activity.
    """
    by_account: dict[str, list[Statement]] = defaultdict(list)
    for s in statements:
        if s.currency == TRY or s.is_account:
            by_account[s.account].append(s)
    periods = []
    for stmts in by_account.values():
        stmts.sort(key=lambda s: s.cut_date)
        for i, s in enumerate(stmts):
            if s.is_account:
                start = s.start
            else:
                prev = stmts[i - 1] if i else None
                continuous = (
                    prev and prev.total is not None and s.previous is not None and abs(prev.total - s.previous) < CENT
                )
                if prev and ((s.cut_date - prev.cut_date).days <= 45 or continuous):
                    start = prev.cut_date + timedelta(days=1)
                else:
                    start = _one_month_before(s.cut_date) + timedelta(days=1)
            periods.append((s, start, s.cut_date))
    return periods


def one_list_per_day(statements: Sequence[Statement]) -> list[Statement]:
    """statements as the ledger counts them. Where movement lists of one account cover the same day, that day's rows
    come from one of them: the one with more rows that day (a list taken during the day lacks the day's later rows),
    else the one reaching further, else the first by document. A list's own rows are never deduplicated among
    themselves, and a statement given here is never changed: the one counted on fewer days is a copy without the rows
    of the days another list gives (the documents keep their checks and their own view)."""
    by_account: dict[tuple[str, str], list[Statement]] = defaultdict(list)
    for s in statements:
        if s.is_account:
            by_account[(s.account, s.currency)].append(s)
    elsewhere: dict[int, set[date]] = {}  # id of a list -> the days whose rows another list gives
    for lists in by_account.values():
        if len(lists) < 2:
            continue
        rows = [Counter(t.date for t in s.transactions) for s in lists]
        covering: dict[date, list[int]] = defaultdict(list)
        for i, s in enumerate(lists):
            start = s.start or s.cut_date
            for n in range((s.cut_date - start).days + 1):
                covering[start + timedelta(days=n)].append(i)
        for day, found in covering.items():
            if len(found) < 2:
                continue
            kept = min(found, key=lambda i: (-rows[i][day], -lists[i].cut_date.toordinal(), lists[i].document))
            for i in found:
                if i != kept and rows[i][day]:
                    elsewhere.setdefault(id(lists[i]), set()).add(day)
    return [
        replace(s, transactions=[t for t in s.transactions if t.date not in days])
        if (days := elsewhere.get(id(s)))
        else s
        for s in statements
    ]


_ADVANCE = "TAKSITLI NAKIT AVANS"
_CARD_DIGITS = re.compile(r"\*{4}\s?(\d{4})\b")  # a card as an account's line names it: "**** ****1234"
_INSTALLMENT = re.compile(r"(\d+)/(\d+)")
_ADVANCE_DAYS = 3  # an installment is booked on the advance's day of the month, a weekend or holiday later at most


def _lent(statements: Sequence[Statement]) -> list[tuple[str, date, Decimal]]:
    """(card's last digits, day, amount) of each installment cash advance a card paid into an own account, as the
    account's line tells it ("… ****1234 … Taksitli Nakit Avans İşlemi")."""
    found: list[tuple[str, date, Decimal]] = []
    for s in statements:
        if not s.is_account:
            continue
        for t in s.transactions:
            f = fold(t.description)
            if t.amount < 0 and _ADVANCE in f and (card := _CARD_DIGITS.search(f)):
                found.append((card[1], t.date, -t.amount))
    return found


def split_card_advances(statements: Sequence[Statement], accounts: Mapping[str, Account]) -> list[Statement]:
    """statements with a card's installment cash advance split into what repays the money it lent and its cost, where
    the card's statement prints the installment alone (Garanti's "Alo Taksitli Nakit Avans 740,00x3=2.220,00").
    The money lent is the account's line of the advance's day; each installment repays an equal share of it (the last
    what rounding left) as loan principal, and the rest is its interest and taxes, as İş Bankası's statements print
    them (parsers.common.split_interest). Without that line an installment stays a cash advance. A statement given
    here is never changed: one with a split row is a copy."""
    lent = _lent(statements)
    if not lent:
        return list(statements)
    out: list[Statement] = []
    for s in statements:
        account = accounts.get(s.account)
        digits = account.number[-4:] if account is not None and account.type in CARD_TYPES else ""
        rows = [part for t in s.transactions for part in _advance_parts(t, digits, lent)] if digits else s.transactions
        out.append(replace(s, transactions=rows) if len(rows) != len(s.transactions) else s)
    return out


def _advance_parts(t: Transaction, digits: str, lent: Sequence[tuple[str, date, Decimal]]) -> list[Transaction]:
    """An installment of a card's cash advance as its principal and its cost; any other row as it is."""
    shown = _INSTALLMENT.fullmatch(t.installment)
    if t.kind is not TransactionKind.CASH_ADVANCE or _ADVANCE not in fold(t.description) or shown is None:
        return [t]
    n, count = int(shown[1]), int(shown[2])
    if not 1 <= n <= count:
        return [t]
    # The advance this installment repays: the card's, taken n - 1 months before it, the nearest such day.
    near = [(abs((add_months(day, n - 1) - t.date).days), amount) for card, day, amount in lent if card == digits]
    taken = [found for found in near if found[0] <= _ADVANCE_DAYS]
    if not taken:
        return [t]
    principal = min(taken)[1]
    share = round_half_up(principal / count)
    if n == count:
        share = principal - share * (count - 1)  # the last installment repays what rounding left
    cost = t.amount - share
    if share <= 0 or cost <= 0:
        return [t]  # the installments do not add up to more than the money lent: not this advance's
    return [
        replace(t, amount=share, kind=TransactionKind.LOAN_PRINCIPAL),
        replace(t, amount=cost, kind=TransactionKind.INTEREST_FEE, description=f"{t.description} (faiz ve vergi payı)"),
    ]


def covered_days(statements: list[Statement]) -> dict[str, set[date]]:
    """The days an available statement covers, per account."""
    result: dict[str, set[date]] = defaultdict(set)
    for s, start, end in statement_periods(statements):
        day = start
        while day <= end:
            result[s.account].add(day)
            day += timedelta(days=1)
    return {account: days for account, days in result.items() if days}


def _coverage(days: dict[str, set[date]]) -> dict[str, dict[str, float]]:
    """Share of each calendar month covered by an available statement, per account."""
    result: dict[str, dict[str, float]] = {}
    for account, covered in days.items():
        months: dict[str, float] = {}
        first, last = min(covered), max(covered)
        y, m = first.year, first.month
        while (y, m) <= (last.year, last.month):
            length = calendar.monthrange(y, m)[1]
            n = sum(1 for d in range(1, length + 1) if date(y, m, d) in covered)
            months[f"{y:04d}-{m:02d}"] = round(n / length, 3)
            y, m = (y, m + 1) if m < 12 else (y + 1, 1)
        result[account] = months
    return result


# --- receipts and statements ------------------------------------------------------


def _is_card_payment(t: Transaction, account: Account | None) -> bool:
    """A receipt of a payment to a credit card is booked on the card (QNB, TEB)."""
    return (
        account is not None
        and account.type in CARD_TYPES
        and t.kind in (TransactionKind.CARD_PAYMENT_NO_STATEMENT, TransactionKind.CARD_PAYMENT)
    )


class _Rows:
    """Statement rows a receipt's row can be found among; each one confirms one receipt row only."""

    def __init__(self, statements: list[Statement], accounts: dict[str, Account]):
        self.accounts = accounts
        self.by_account: dict[str, list[Transaction]] = defaultdict(list)
        self.payments: list[Transaction] = []  # card payments as bank accounts book them
        for s in statements:
            self.by_account[s.account].extend(s.transactions)
            if s.is_account:
                self.payments += [t for t in s.transactions if t.kind == TransactionKind.CARD_PAYMENT and t.amount > 0]
        self.used: set[int] = set()

    def take(self, t: Transaction, card_payment: bool) -> Transaction | None:
        lo, hi = t.date + timedelta(days=POSTING_DAYS[0]), t.date + timedelta(days=POSTING_DAYS[1])

        def near(rows, amount, extra=lambda r: True):
            found = [
                r
                for r in rows
                if id(r) not in self.used and lo <= r.date <= hi and abs(r.amount - amount) <= CENT and extra(r)
            ]
            return min(found, key=lambda r: abs((r.date - t.date).days), default=None)

        # A card statement prints the payment as a credit; the paying account's list books it as money out.
        match = near(self.by_account.get(t.account, []), -t.amount if card_payment else t.amount)
        if match is None and card_payment:
            card = self.accounts[t.account]
            match = near(
                self.payments,
                t.amount,
                lambda r: card.number[-4:] in r.description or self.accounts[r.account].bank == card.bank,
            )
        if match is not None:
            self.used.add(id(match))
        return match


def settle_receipts(
    receipts: dict[str, list[Transaction]],
    statements: list[Statement],
    accounts: dict[str, Account],
    days: dict[str, set[date]],
) -> list[ReceiptLine]:
    """What the statements say about each receipt row (see the module docstring).

    A receipt keeps its status as a whole once one of its rows is found: a statement may print a
    transfer's fee and tax as one row, two rows or on another day."""
    rows = _Rows(statements, accounts)
    newest = max((s.cut_date for s in statements), default=None)
    lines = []
    for key, group in receipts.items():
        settled = []
        for t in group:
            account = accounts.get(t.account)
            covered = days.get(t.account, set())
            card_payment = _is_card_payment(t, account)
            if card_payment and covered and t.date >= min(covered):
                t.kind = TransactionKind.CARD_PAYMENT  # the card's statements show the purchases it pays for
            native = t.amount
            match = rows.take(t, card_payment)
            if match is not None:
                settled.append(ReceiptLine(t, key, CONFIRMED, native, match))
                continue
            window = [t.date + timedelta(days=n) for n in range(POSTING_DAYS[0], POSTING_DAYS[1] + 1)]
            if not covered or t.date < min(covered):
                status = NO_STATEMENT
            elif all(d in covered for d in window):
                status = NOT_ON_STATEMENT
            elif window[-1] > max(covered) and (newest - max(covered)).days <= ACTIVE_DAYS:
                status = PROVISIONAL  # the next statement may still show it
            else:
                status = NO_STATEMENT  # a gap between two statements: a document is missing
            settled.append(ReceiptLine(t, key, status, native))
        if any(line.status == CONFIRMED for line in settled):
            for line in settled:
                if line.status == NOT_ON_STATEMENT:
                    line.status = CONFIRMED
        lines += settled
    return lines


# --- balances -------------------------------------------------------------------

# The accounts whose balance below zero is a debt in use: an overdraft account's credit (KMH), a card's, a loan's.
_OWING = (AccountType.OVERDRAFT, AccountType.LOAN, *CARD_TYPES)


def _native(t: Transaction) -> Decimal:
    """A row's amount in its account's currency: the ledger turns a foreign account's rows into TL (_to_tl)."""
    return t.reason.native if t.reason.native is not None else t.amount


def _day_ends(s: Statement) -> Iterable[Decimal]:
    """A list's balance at the end of each day it has rows on, from its opening balance (as it prints it, else its
    closing balance before its rows): what its running balance column prints at the day's last row."""
    if s.previous is not None:
        balance = s.previous
    elif s.total is not None:
        balance = s.total + sum((_native(t) for t in s.transactions), Decimal(0))
    else:
        return
    by_day: dict[date, Decimal] = defaultdict(Decimal)
    for t in s.transactions:
        by_day[t.date] += _native(t)
    for day in sorted(by_day):
        balance -= by_day[day]
        yield balance


def shown_below_zero(ds: Dataset, account: str) -> bool:
    """Whether a document shows the account's balance below zero (a current account whose overdraft is in use): a
    list's opening, closing or month-end balance or its balance at a day's end, or a notice's balance after its row."""
    for s in ds.statements:
        if s.account != account:
            continue
        printed = [s.previous, s.total, *s.balances.values()]
        if any(value is not None and value < 0 for value in printed) or (
            s.is_account and any(balance < 0 for balance in _day_ends(s))
        ):
            return True
    return any(
        line.txn.account == account and line.txn.balance is not None and line.txn.balance < 0 for line in ds.receipts
    )


def untold_in(ds: Dataset, account: str, balance: Decimal) -> Decimal:
    """The money that came into an account before it paid out more than it held, which no document tells yet: how far
    below zero its balance is as the documents tell it (its newest printed balance moved by the receipts and notices
    after it), on an account that cannot go below zero. A bank pays out no more than an account holds, but the notices
    tell only some movements: Garanti's only the transfers out above an amount, none for an FX sale or a transfer in.
    Zero for an account whose balance below zero is a debt in use (an overdraft's credit, a card's, a loan's) and for
    one a document shows below zero (a current account whose overdraft is in use)."""
    if balance >= 0:
        return Decimal(0)
    found = ds.accounts.get(account)
    if found is None or found.type in _OWING or shown_below_zero(ds, account):
        return Decimal(0)
    return -balance


# --- own accounts and transfers -----------------------------------------------


def masked_as(masked: str, name: str) -> bool:
    """Whether a folded name masked but for the first letters of its words ("OR**** KU******", Vakıfbank's and
    Garanti's notices) can be the folded name: as many words, each starting with the letters shown. Another masked
    name agrees when every word shows the same start. One letter a word could be a relative's name: two are needed."""
    shown, words = [w.split("*", 1)[0] for w in masked.split()], name.split()
    if len(shown) < 2 or len(shown) != len(words) or any(len(s) < 2 for s in shown):
        return False
    if "*" in name:
        others = [w.split("*", 1)[0] for w in words]
        return all(a.startswith(b) or b.startswith(a) for a, b in zip(shown, others, strict=True))
    return all(w.startswith(s) for s, w in zip(shown, words, strict=True))


class Own:
    """The user's names and account numbers, to recognise transfers between own accounts."""

    def __init__(self, names: list[str], accounts: dict[str, Account]):
        variants = set()
        self.whole: list[list[str]] = []  # every name as given, word by word
        for name in names:
            parts = fold(name).split()
            if len(parts) >= 2:
                self.whole.append(parts)
                variants.add(" ".join(parts))
                variants.add(f"{parts[0]} {parts[-1]}")  # ORNEK SOYADOGLU
                variants.add(f"{parts[0][0]}.{parts[1]} {parts[-1]}" if len(parts) > 2 else "")
        self.names = {v for v in variants if v}
        self.numbers = {
            re.sub(r"\D", "", a.number)
            for a in accounts.values()
            if a.type not in (*CARD_TYPES, AccountType.LOAN) and len(re.sub(r"\D", "", a.number)) >= 6
        }

    def is_self(self, who: str) -> bool:
        f = fold(who)
        if "*" in f:
            # Banks mask the whole name as the account holds it, so the short variants are not tried: "Ör**** Ku****"
            # of a two-word name is somebody else's when the user's name has three words.
            return any(masked_as(f, " ".join(parts)) for parts in self.whole)
        return bool(f) and any(f == n or f.startswith(n + " ") or f.endswith(" " + n) for n in self.names)

    def mentions_own_account(self, text: str) -> bool:
        """TEB names the receiving account even on the receiving side
        ("222333444 no.lu hesaba gönderilmiştir"), so the row's own number counts too."""
        digits = {d.lstrip("0") for d in re.findall(r"\d{6,}", text)}
        own = {n.lstrip("0") for n in self.numbers}
        return any(d in own or any(d.endswith(n) for n in own) for d in digits)


_BANK_NOISE = {"TURKIYE", "TURK", "BANKASI", "BANK", "A.S.", "A.S", "T.A.O.", "T.A.O", "CUMHURIYETI", "VE"}
# Receiver bank as printed in a transfer row -> bank name used for accounts.
_BANK_NAMES = (
    ("GARANTI", "Garanti BBVA"),
    ("IS BANKASI", "İş Bankası"),
    ("QNB", "QNB"),
    ("FINANSBANK", "QNB"),
    ("EKONOMI", "TEB"),
    ("VAKIFLAR", "Vakıfbank"),
)


def _bank_key(text: str) -> str:
    return "".join(w for w in fold(text).split() if w not in _BANK_NOISE)


def _bank_named(printed: str) -> str:
    """The name accounts give the bank a transfer row prints ("TÜRKIYE GARANTI BANKASI A.Ş." → "Garanti BBVA"), or ""
    for a bank the table does not know."""
    folded = fold(printed)
    return next((name for key, name in _BANK_NAMES if key in folded), "")


def _bank_only(t: Transaction) -> bool:
    """TEB prints only the receiver's bank ("TÜRKIYE GARANTI BANKASI A.Ş.") for outgoing transfers."""
    return bool(re.fullmatch(r"[A-ZÇĞİÖŞÜ .]+(?:A\.Ş\.|T\.A\.O\.?)", t.description.strip()))


def _printed_receiver_bank(t: Transaction) -> str:
    """The receiver's bank as an outgoing row prints it: the whole description on TEB, the part before the name in
    "… hesabından <bank> <name> hesabına" elsewhere; "" when the row does not say."""
    m = re.search(r"hesabından\s+(.+?(?:A\.Ş\.|T\.A\.O\.?))\s+.+?\s+hesabına", t.description)
    if m:
        return m[1]
    return t.description if _bank_only(t) else ""


def _receiver_bank(t: Transaction) -> str:
    """Bank of the receiver, as a key to compare rows by."""
    return _bank_key(_printed_receiver_bank(t))


def _at_bank(printed: str, account: Account) -> bool:
    """Whether account is at the bank a transfer row prints: by the table's name, else by the words left of both names
    once "Türkiye", "Bankası", "A.Ş." and the like are taken off ("ZIRAAT" of "Ziraat Bankası")."""
    named = _bank_named(printed)
    if named:
        return account.bank == named
    key, own = _bank_key(printed), _bank_key(account.bank)
    return bool(key and own) and (key in own or own in key)


def _bank_fits(out: Transaction, inc: Transaction, accounts: dict[str, Account]) -> bool:
    """Whether the incoming side can be where the outgoing side says the money went: a row that names the receiver's
    bank pairs only with an account at that bank. TEB prints only the bank, so of two transfers of one amount on one
    day to two banks, the one to the first is not the one that reached an account at the second."""
    printed = _printed_receiver_bank(out)
    if not printed:
        return True
    account = accounts.get(inc.account)
    return account is not None and _at_bank(printed, account)


# TEB names the account a transfer went to: "12345678 no.lu hesaba gönderilmiştir".
_TO_ACCOUNT = re.compile(r"(\d{6,})\s+no\.?\s*lu\s+hesaba", re.IGNORECASE)


def sent_after(ds: Dataset, account: str, day: date) -> list[tuple[Transaction, bool]]:
    """Own transfers after day that another account's documents tell left for this account, or for an account at its
    bank, whose other side no document shows: a balance of day does not hold them. (row, True) when the row names this
    account ("<number> no.lu hesaba"), (row, False) when it names only the bank, which may hold other accounts."""
    target = ds.accounts[account]
    if target.type not in _BANK_ACCOUNTS:
        return []
    found: list[tuple[Transaction, bool]] = []
    for t in ds.transactions:
        if t.account == account or t.date <= day or t.amount <= 0:
            continue
        source = ds.accounts.get(t.account)
        if t.kind is not TransactionKind.OWN_TRANSFER or t.reason.pair or source is None:
            continue
        if source.currency != target.currency:
            continue
        named = _TO_ACCOUNT.search(t.description)
        if named:
            if named[1] == target.number:
                found.append((t, True))
            continue
        printed = _printed_receiver_bank(t)
        if printed and _at_bank(printed, target):
            found.append((t, False))
    return found


def _free_card_payments(card_txns: list[Transaction], account_txns: list[Transaction]) -> list[Transaction]:
    """Card payments seen on a card statement but not as a card-payment row of any account:
    paid by a transfer from another bank, so they can pair with that transfer."""
    from_accounts = [t for t in account_txns if t.kind == TransactionKind.CARD_PAYMENT]
    free = []
    for p in (t for t in card_txns if t.kind == TransactionKind.CARD_PAYMENT):
        if not any(abs(a.amount + p.amount) <= CENT and _in_transfer_days(a, p) for a in from_accounts):
            free.append(p)
    return free


def _in_transfer_days(out: Transaction, inc: Transaction) -> bool:
    return TRANSFER_DAYS[0] <= (inc.date - out.date).days <= TRANSFER_DAYS[1]


def _pair_open(
    rows: list[Transaction], pool: list[Transaction], paired: set[int], accounts: dict[str, Account]
) -> None:
    """Pair each open row with an opposite row of the same amount in another own account from pool, the closest in
    time within TRANSFER_DAYS and at the bank the outgoing side names, if it names one: both are an own transfer, each
    naming the other."""
    for t in sorted(rows, key=lambda x: x.date):
        if t.kind != TransactionKind.TRANSFER_CANDIDATE or id(t) in paired:
            continue
        best, best_gap = None, 0
        for other in pool:
            if other is t or id(other) in paired or other.account == t.account or abs(other.amount + t.amount) > CENT:
                continue
            out, inc = (t, other) if t.amount > 0 else (other, t)
            gap = abs((inc.date - out.date).days)
            if _in_transfer_days(out, inc) and _bank_fits(out, inc, accounts) and (best is None or gap < best_gap):
                best, best_gap = other, gap
        if best:
            t.kind = best.kind = TransactionKind.OWN_TRANSFER
            paired.update((id(t), id(best)))
            t.reason = replace(t.reason, transfer=TransferStep.PAIRED, pair=best.fingerprint)
            best.reason = replace(best.reason, transfer=best.reason.transfer or TransferStep.PAIRED, pair=t.fingerprint)


def _pair_own_sides(found: list[Transaction], paired: set[int], accounts: dict[str, Account]) -> None:
    """Pair the sides of transfers between own accounts that both name the user or an own account: they were found
    by name, so each knows it is an own transfer but not where the money went. An outgoing side takes the incoming
    one of the same amount in another account, the closest in time within TRANSFER_DAYS, at the bank it names if it
    names one."""
    incoming = sorted((t for t in found if t.amount < 0), key=lambda x: x.date)
    for out in sorted((t for t in found if t.amount > 0), key=lambda x: x.date):
        best, best_gap = None, 0
        for inc in incoming:
            if id(inc) in paired or inc.account == out.account or abs(inc.amount + out.amount) > CENT:
                continue
            gap = abs((inc.date - out.date).days)
            if _in_transfer_days(out, inc) and _bank_fits(out, inc, accounts) and (best is None or gap < best_gap):
                best, best_gap = inc, gap
        if best:
            paired.update((id(out), id(best)))
            out.reason = replace(out.reason, pair=best.fingerprint)
            best.reason = replace(best.reason, pair=out.fingerprint)


def _resolve_transfers(
    txns: list[Transaction],
    own: Own,
    categorizer: Categorizer,
    statements: list[Statement],
    accounts: dict[str, Account],
    card_payments: list[Transaction],
) -> None:
    candidates = [t for t in txns if t.kind == TransactionKind.TRANSFER_CANDIDATE]
    found_by_name: list[Transaction] = []  # own transfers whose other side may still be open
    open_: list[Transaction] = []  # rows that name nobody: the other side may be in another own account
    strangers: list[Transaction] = []  # rows that name someone else, whom no rule names
    for t in candidates:
        if own.is_self(t.counterparty) or own.mentions_own_account(t.description):
            t.kind = TransactionKind.OWN_TRANSFER
            step = TransferStep.OWN_NAME if own.is_self(t.counterparty) else TransferStep.OWN_ACCOUNT
            t.reason = replace(t.reason, transfer=step)
            found_by_name.append(t)
        elif categorizer.resolve_kind(t):
            t.reason = replace(t.reason, transfer=TransferStep.RULE)  # a rule named the receiver/sender: rent, ...
        elif t.counterparty:
            # "<name> den gelen havale": the money came from that person, or went to them. It is no side of a transfer
            # between own accounts, however well its amount and day fit one: otherwise someone's payment into an account
            # could take the place of an own FAST that reached another account at the same bank.
            strangers.append(t)
        else:
            open_.append(t)

    # The surer signs first. Two sides that both name the user pair with each other, and an open row with an opposite
    # one that names the user (in another own account, within days): a payment that only looks like a named one must
    # take neither, nor may a stranger's payment of the same amount.
    paired: set[int] = set()
    _pair_own_sides(found_by_name, paired, accounts)
    _pair_open(open_, found_by_name, paired, accounts)

    # Same receiver bank and amount as a named payment: "YAPI VE KREDI BANKASI A.Ş. -21.000"
    # on one account is the rent that another account pays to the landlord by name.
    known: dict[tuple, Transaction] = {}
    for t in candidates:
        if (
            t.kind not in (TransactionKind.TRANSFER_CANDIDATE, TransactionKind.OWN_TRANSFER)
            and t.amount > 0
            and t.counterparty
        ):
            bank = _receiver_bank(t)
            if bank:
                known[(bank, round(t.amount))] = t
    still_open = []
    for t in open_:
        if t.kind != TransactionKind.TRANSFER_CANDIDATE:
            continue  # paired above
        bank = _receiver_bank(t) if t.amount > 0 and not t.counterparty else ""
        like = known.get((bank, round(t.amount))) if bank else None
        if like:
            t.kind, t.category, t.merchant, t.counterparty = like.kind, like.category, like.merchant, like.counterparty
            t.description += f" (→ {like.counterparty})"
            t.reason = replace(like.reason, transfer=TransferStep.LIKE_NAMED, pair=like.fingerprint)
        else:
            still_open.append(t)

    # The rest: an open row matched by an opposite open row, or by a card's payment, in another own account.
    _pair_open(still_open, still_open + card_payments, paired, accounts)

    # A bank-only payment to a bank where the user has an account, on a date none of
    # that bank's statements cover, most likely went to that own account.
    covered: dict[str, list] = defaultdict(list)
    for s in statements:
        if s.is_account and s.account in accounts:
            covered[accounts[s.account].bank].append((s.start, s.cut_date))
    for t in still_open:
        if t.kind != TransactionKind.TRANSFER_CANDIDATE or t.amount <= 0 or not _bank_only(t):
            continue
        bank = _bank_named(t.description)
        if bank in covered and not any(a <= t.date <= b for a, b in covered[bank]):
            t.kind = TransactionKind.OWN_TRANSFER
            t.description += " (muhtemelen kendi hesabınıza)"
            t.reason = replace(t.reason, transfer=TransferStep.UNCOVERED_BANK)

    for t in [*still_open, *strangers]:
        if t.kind == TransactionKind.TRANSFER_CANDIDATE:
            income = t.amount < 0
            t.kind = TransactionKind.INCOME if income else TransactionKind.P2P_TRANSFER
            t.reason = replace(t.reason, transfer=TransferStep.INCOME if income else TransferStep.PERSON)


# --- foreign currency -------------------------------------------------------------

_RATE = re.compile(r"\b(USD|EUR|GBP)\s*:\s*(\d+(?:[.,]\d+)?)")
_RATE_VAKIF = re.compile(r"\(([\d.,]+)\s*(USD|EUR|GBP) karşılığı\)\)\s*\(İşlem Kuru\s*:\s*([\d.,]+)\)")


def _rates(txns: list[Transaction]) -> dict[str, list[tuple[date, Decimal]]]:
    rates: dict[str, list] = defaultdict(list)
    for t in txns:
        for cur, value in _RATE.findall(t.description):
            rates[cur].append((t.date, Decimal(value.replace(",", "."))))
        m = _RATE_VAKIF.search(t.description)
        if m:
            rates[m[2]].append((t.date, Decimal(m[3].replace(".", "").replace(",", "."))))
    return rates


def nearest(
    rates: Mapping[str, Sequence[tuple[date, Decimal]]], currency: str, day: date
) -> tuple[date, Decimal] | None:
    """The TL rate of currency the documents print nearest to day, with the day it was printed for; None when they
    print none."""
    known = rates.get(currency)
    return min(known, key=lambda r: abs((r[0] - day).days)) if known else None


def nearest_rate(rates: Mapping[str, Sequence[tuple[date, Decimal]]], currency: str, day: date) -> Decimal | None:
    """The TL rate of currency the documents print nearest to day; None when they print none."""
    found = nearest(rates, currency, day)
    return found[1] if found else None


@dataclass(frozen=True, slots=True)
class PrintedRate:
    """The rate a bank prints on a row of its own: a currency bought or sold for TL."""

    currency: str
    rate: Decimal  # TL for one unit
    amount: Decimal | None  # the foreign amount, where the row prints it beside the rate (Vakıfbank's "karşılığı")


def _turkish_number(text: str) -> Decimal:
    """A number as Vakıfbank prints it: "1.234,56" is Decimal("1234.56")."""
    return Decimal(text.replace(".", "").replace(",", "."))


def printed_rate(t: Transaction) -> PrintedRate | None:
    """The bank's rate t's description prints: Vakıfbank's "(100,00 EUR karşılığı)) (İşlem Kuru : 36,50)", with the
    foreign amount, or Garanti's "EUR:54.44500"; None where it prints none."""
    found = _RATE_VAKIF.search(t.description)
    if found:
        return PrintedRate(found[2], _turkish_number(found[3]), _turkish_number(found[1]))
    found = _RATE.search(t.description)
    return PrintedRate(found[1], Decimal(found[2].replace(",", ".")), None) if found else None


@dataclass(frozen=True, slots=True)
class DatedRate:
    """A TL rate as the ledger and the screens take it: TL for one unit, the day it is of, and where it comes from."""

    rate: Decimal
    day: date  # of the row that printed it, or of the providers' bulletin (Friday's for a Saturday)
    source: RateSource


def row_rate(
    rates: Mapping[str, Sequence[tuple[date, Decimal]]], book: RateBook, currency: str, t: Transaction
) -> DatedRate | None:
    """The TL rate a row of a foreign-currency account is valued at (docs/domain/ledger.md, "Kur çevirisi"):

    1. the bank's own rate for that very row, where its description prints one in the account's currency;
    2. else the providers' rate of its day (the book's: its own bulletin or the latest one within a week before it),
       at the buying side: what the currency was worth to its holder that day, as the account is an asset;
    3. else the rate the documents print nearest to its day: without the network only the documents' rates are known.

    None without any: the row is left out."""
    own = printed_rate(t)
    if own is not None and own.currency == currency:
        return DatedRate(own.rate, t.date, RateSource.DOCUMENT)
    quote = book.on(currency, t.date)
    if quote is not None:
        return DatedRate(quote.buying, quote.day, quote.source)
    found = nearest(rates, currency, t.date)
    return DatedRate(found[1], found[0], RateSource.DOCUMENT) if found else None


def _to_tl(
    txns: list[Transaction],
    accounts: dict[str, Account],
    rates: dict,
    warnings: list[str],
    book: RateBook = EMPTY,
) -> list[Transaction]:
    """Value foreign-currency account rows in TL at the rate row_rate picks; the rate, its day and its source, and the
    amount it turned into TL, stay on the row's reason."""
    out = []
    for t in txns:
        currency = accounts[t.account].currency if t.account in accounts else TRY
        if currency == TRY:
            out.append(t)
            continue
        if t.kind == TransactionKind.OWN_TRANSFER:
            continue  # moving foreign currency between own accounts changes nothing
        found = row_rate(rates, book, currency, t)
        if found is None:
            warnings.append(f"{t.date} {currency} {t.amount}: kur bulunamadı, işlem dışarıda bırakıldı")
            continue
        native = t.amount
        t.amount = to_tl(native, found.rate)
        # A bank prints its rate as it likes; a provider's is written as TCMB prints it, to four decimals.
        shown = format_amount(found.rate) if found.source is RateSource.DOCUMENT else format_rate(found.rate)
        t.original = f"{t.original} × {shown}"
        t.reason = replace(t.reason, rate=found.rate, rate_day=found.day, rate_source=found.source, native=native)
        out.append(t)
    return out


# --- build -------------------------------------------------------------------------


def _fingerprint(
    statements: list[Statement], receipts: dict[str, list[Transaction]], accounts: dict[str, Account]
) -> None:
    """Give every row its fingerprint from the row as its reader read it: before a description is rewritten or a
    foreign amount turned into TL. Statements come first, each in its place (account, cut, currency and first day
    are one statement's alone), then the receipts by key, so the order never depends on how documents arrived."""
    prints = Fingerprints()
    for s in sorted(statements, key=lambda s: (s.account, s.cut_date, s.currency, s.start or date.min)):
        for t in s.transactions:
            t.fingerprint = prints.next(t.account, t.date, round(t.amount * 100), s.currency, t.description)
    for key in sorted(receipts):
        for t in receipts[key]:
            currency = accounts[t.account].currency if t.account in accounts else TRY
            t.fingerprint = prints.next(t.account, t.date, round(t.amount * 100), currency, t.description)


_BANK_ACCOUNTS = (AccountType.CURRENT, AccountType.DEPOSIT, AccountType.OVERDRAFT)


def resolve_masked(results: Iterable[ParseResult]) -> None:
    """Receipts of incoming transfers print the account number masked ("1012/****321"): their rows
    move to the one account of that bank and currency whose number ends with the digits shown. A notice that shows
    no digit at all (QNB's FAST notices name only the branch) moves to the one bank account of that bank and
    currency, never to a card or a loan."""
    results = list(results)
    known = {a.id: a for r in results for a in r.accounts if "*" not in a.number}
    for r in results:
        for i, masked in enumerate(r.accounts):
            if "*" not in masked.number:
                continue
            shown = masked.number.rsplit("*", 1)[-1]
            same = [
                a
                for a in known.values()
                if a.bank == masked.bank
                and a.currency == masked.currency
                and (a.number.endswith(shown) if shown else a.type in _BANK_ACCOUNTS)
            ]
            if len(same) != 1:
                continue
            r.accounts[i] = same[0]
            for t in r.transactions:
                if t.account == masked.id:
                    t.account = same[0].id


def _same_movement(a: Transaction, b: Transaction) -> bool:
    """Whether two rows of two documents tell of one movement: the same account, day and amount, and names that can be
    one another's (a notice may mask the name a receipt prints whole)."""
    if a.account != b.account or a.date != b.date or abs(a.amount - b.amount) > CENT:
        return False
    x, y = fold(a.counterparty), fold(b.counterparty)
    if not x or not y:
        return True
    if "*" in x or "*" in y:
        return masked_as(x, y) if "*" in x else masked_as(y, x)
    return x == y


def _drop_told_twice(receipts: dict[str, list[Transaction]], notices: set[str]) -> None:
    """A bank's notice and a receipt can tell of the same movement: Garanti mails both for a transfer. The receipt's
    row stands, taking the balance the notice adds; the notice's row goes. Each receipt row stands for one notice row
    only, so two equal transfers of a day stay two; rows of two receipts, or of one document, are never merged."""
    told = [t for key in sorted(receipts.keys() - notices) for t in receipts[key]]
    used: set[int] = set()
    for key in sorted(notices & receipts.keys()):
        kept: list[Transaction] = []
        for t in receipts[key]:
            twin = next((r for r in told if id(r) not in used and _same_movement(r, t)), None)
            if twin is None:
                kept.append(t)
                continue
            used.add(id(twin))
            twin.balance = twin.balance if twin.balance is not None else t.balance
        if kept:
            receipts[key] = kept
        else:
            del receipts[key]


def _status(result: ParseResult) -> str:
    """What a read document is, as DocumentStatus says it: a statement or list, else a receipt, a bank's notice or a
    non-bank sender's bill or receipt."""
    if result.statements:
        return "hesap" if result.statements[0].is_account else "ekstre"
    kind = document_type(result.parser)
    return "bildirim" if kind is DocumentKind.NOTICE else "fatura" if kind is DocumentKind.INVOICE else "dekont"


def build(
    results: Sequence[tuple[Any, ParseResult | None, Sequence[str] | None]],
    categorizer: Categorizer,
    settings: Mapping[str, Any],
    book: RateBook = EMPTY,
) -> Dataset:
    """results: (document, its reading or None, (status, detail) when there is no reading) tuples; a document has
    a name, an origin and a sha256. book: the providers' rates; without them the documents' own rates value the
    foreign rows."""
    accounts: dict[str, Account] = {}
    told: dict[str, Account] = {}  # accounts as only bank notices name them
    listed: set[str] = set()  # the accounts a statement or list named
    statements: dict[tuple, Statement] = {}
    receipts: dict[str, list[Transaction]] = {}
    notices: set[str] = set()  # the keys of receipts that are bank notices
    documents: list[DocumentStatus] = []
    holders: set[str] = set()
    bills: list[tuple[str, Invoice, str]] = []  # (key, bill or receipt, document's name)

    resolve_masked(result for _, result, _ in results if isinstance(result, ParseResult))
    for doc, result, status in results:
        if not isinstance(result, ParseResult):
            documents.append(DocumentStatus(doc.name, doc.origin, status[0], status[1]))
            continue
        # A notice knows less of an account than a list or a receipt does (QNB's does not say whether it is an overdraft
        # account): the account as they name it stands. A receipt knows less than a list (TEB's does not say whether
        # the account earns interest): a list's account takes the place of one a receipt that came first named.
        named = told if document_type(result.parser) is DocumentKind.NOTICE else accounts
        for a in result.accounts:
            if result.statements and a.id not in listed:
                accounts[a.id] = a
                listed.add(a.id)
            else:
                named.setdefault(a.id, a)
        if result.holder:
            holders.add(result.holder)
        for s in result.statements:
            s.document = doc.sha256
            for t in s.transactions:
                t.document = doc.sha256
            key = (s.account, s.cut_date, s.currency, s.start)
            # The same statement can arrive as different files (re-sent e-mail, archive copy).
            if key not in statements or len(s.transactions) > len(statements[key].transactions):
                statements[key] = s
        if result.transactions:
            for t in result.transactions:
                t.document = doc.sha256
            key = result.receipt_key or doc.sha256
            receipts.setdefault(key, result.transactions)
            if document_type(result.parser) is DocumentKind.NOTICE:
                notices.add(key)
        bills += [(f"{doc.sha256}:{i}", invoice, doc.name) for i, invoice in enumerate(result.invoices)]
        documents.append(DocumentStatus(doc.name, doc.origin, _status(result), label(result.parser)))

    for a in told.values():
        accounts.setdefault(a.id, a)
    _drop_told_twice(receipts, notices)
    stmts = sorted(statements.values(), key=lambda s: (s.account, s.cut_date, s.currency))
    stmts = split_card_advances(stmts, accounts)
    # The rows the ledger counts: a day two lists of an account cover comes from one of them. Fingerprints are given
    # to those rows only, so a row keeps its fingerprint (and the user's notes) whichever list brings it.
    counted = one_list_per_day(stmts)
    _fingerprint(counted, receipts, accounts)
    _link_foreign_currency(counted)
    days = covered_days(stmts)
    coverage = _coverage(days)

    card_txns = [t for s in counted if not s.is_account and s.currency == TRY for t in s.transactions]
    account_txns = [t for s in counted if s.is_account for t in s.transactions]
    # Receipts add what no statement shows yet (a transfer made today) or ever will (a 2022 card payment,
    # old loan installments); a statement's own row stands for what it shows.
    lines = settle_receipts(receipts, counted, accounts, days)
    receipt_txns = [line.txn for line in lines if line.status in (PROVISIONAL, NO_STATEMENT)]
    for line in lines:
        line.txn.provisional = line.status == PROVISIONAL

    names = settings.get("ad_soyad") or sorted(holders)
    own = Own([names] if isinstance(names, str) else list(names), accounts)
    warnings: list[str] = []
    # A receipt's transfer (a FAST to the landlord, a payment between own accounts) resolves like a list row.
    _resolve_transfers(
        account_txns + receipt_txns, own, categorizer, counted, accounts, _free_card_payments(card_txns, account_txns)
    )
    rates = _rates(account_txns)
    account_txns = _to_tl(account_txns, accounts, rates, warnings, book)
    receipt_txns = _to_tl(receipt_txns, accounts, rates, warnings, book)

    txns = card_txns + account_txns + receipt_txns
    for t in txns:
        categorizer.apply(t, accounts.get(t.account))
    txns.sort(key=lambda t: (t.date, t.account, t.description))
    # Bills and receipts of non-bank senders only mark the rows that paid them, and may name what such a row bought;
    # they add no row (F14).
    invoices = match_invoices(one_copy(bills), txns, settled_until(days))
    for found in invoices:
        if found.row is not None:
            categorizer.name_by(found.row, found.invoice.seller)
    return Dataset(
        accounts=accounts,
        statements=stmts,
        transactions=txns,
        documents=documents,
        groups=categorizer.groups,
        categories=categorizer.categories,
        coverage=coverage,
        warnings=warnings,
        rates={cur: sorted(found) for cur, found in rates.items()},
        ended=categorizer.ended,
        declared=categorizer.income,
        regular=categorizer.regular,
        receipts=lines,
        invoices=invoices,
        book=book,
    )


# --- an account's balance today ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Start:
    """Where an account's forecast starts."""

    balance: Decimal  # today's balance as far as the documents tell
    stated: Decimal  # the balance the document printed
    on: date  # the day of that balance
    notice: bool  # a bank notice's balance after its row, not an account list's closing balance
    moves: int  # receipt and notice rows after it, counted in the balance
    through: date  # the newest day the balance knows of
    # Money that came in which no document tells yet (analysis.untold_in): the rows after the balance took an account
    # that cannot go below zero this far below it, so the balance is zero and this much came in first.
    untold: Decimal = Decimal(0)

    @property
    def told(self) -> Decimal:
        """The balance as the documents' rows add up, before the money in no document tells yet."""
        return self.balance - self.untold


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
    and notice rows dated after it. Rows of that same day are taken to be in a notice's balance already. A list's
    closing balance holds only the rows the list shows: a provisional row of its last days is one it does not show
    (settle_receipts: the bank may book it after the list ends), so it moves the balance too, as in the ledger. Rows
    that take an account which cannot go below zero below it tell money out only: the money that came in first is in
    no document yet (analysis.untold_in), so the balance is zero and Start.untold says how much came in."""
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
    after = [
        line
        for line in lines
        if (line.status in (PROVISIONAL, NO_STATEMENT) and line.txn.date > on)
        or (not notice and line.status == PROVISIONAL and line.txn.date <= on)
    ]
    told = stated - sum((line.native for line in after), Decimal(0))
    through = max([on, *(line.txn.date for line in after)])
    untold = untold_in(ds, account, told)
    return Start(told + untold, stated, on, notice, len(after), through, untold)
