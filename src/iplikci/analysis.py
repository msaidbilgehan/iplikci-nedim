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
"""

import calendar
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from .categorize import Categorizer, clean_description
from .domain.codes import CARD_TYPES, AccountType, DocumentKind, EvidenceStatus, TransactionKind
from .domain.fingerprint import Fingerprints
from .domain.labels import EVIDENCE_STATUS, format_amount
from .domain.models import TRY, Account, Invoice, ParseResult, Statement, Transaction
from .domain.money import CENT, round_half_up
from .domain.text import fold
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
    regular: set[str] = field(default_factory=set)  # commitment categories (the rules' `_düzenli`)
    receipts: list[ReceiptLine] = field(default_factory=list)  # every receipt row, counted or not
    invoices: list[InvoiceMatch] = field(default_factory=list)  # non-bank bills and receipts, never counted (F14)


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


def _bank_only(t: Transaction) -> bool:
    """TEB prints only the receiver's bank ("TÜRKIYE GARANTI BANKASI A.Ş.") for outgoing transfers."""
    return bool(re.fullmatch(r"[A-ZÇĞİÖŞÜ .]+(?:A\.Ş\.|T\.A\.O\.?)", t.description.strip()))


def _receiver_bank(t: Transaction) -> str:
    """Bank of the receiver: the whole description on TEB, the part before the name elsewhere."""
    m = re.search(r"hesabından\s+(.+?(?:A\.Ş\.|T\.A\.O\.?))\s+.+?\s+hesabına", t.description)
    if m:
        return _bank_key(m[1])
    return _bank_key(t.description) if _bank_only(t) else ""


def _free_card_payments(card_txns: list[Transaction], account_txns: list[Transaction]) -> list[Transaction]:
    """Card payments seen on a card statement but not as a card-payment row of any account:
    paid by a transfer from another bank, so they can pair with that transfer."""
    from_accounts = [t for t in account_txns if t.kind == TransactionKind.CARD_PAYMENT]
    free = []
    for p in (t for t in card_txns if t.kind == TransactionKind.CARD_PAYMENT):
        if not any(abs(a.amount + p.amount) <= CENT and -1 <= (p.date - a.date).days <= 4 for a in from_accounts):
            free.append(p)
    return free


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
    open_: list[Transaction] = []
    for t in candidates:
        if own.is_self(t.counterparty) or own.mentions_own_account(t.description):
            t.kind = TransactionKind.OWN_TRANSFER
            found_by_name.append(t)
        elif categorizer.resolve_kind(t):
            pass  # a rule named the receiver/sender: rent, family, salary, ...
        else:
            open_.append(t)

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
        bank = _receiver_bank(t) if t.amount > 0 and not t.counterparty else ""
        like = known.get((bank, round(t.amount))) if bank else None
        if like:
            t.kind, t.category, t.merchant, t.counterparty = like.kind, like.category, like.merchant, like.counterparty
            t.description += f" (→ {like.counterparty})"
        else:
            still_open.append(t)

    # A row matched by an opposite row of the same amount in another own account.
    paired: set[int] = set()
    pool = still_open + found_by_name + card_payments
    for t in sorted(still_open, key=lambda x: x.date):
        if t.kind != TransactionKind.TRANSFER_CANDIDATE or id(t) in paired:
            continue
        best, best_gap = None, None
        for other in pool:
            if other is t or id(other) in paired or other.account == t.account or abs(other.amount + t.amount) > CENT:
                continue
            out, inc = (t, other) if t.amount > 0 else (other, t)
            gap = (inc.date - out.date).days
            if -1 <= gap <= 4 and (best is None or abs(gap) < best_gap):
                best, best_gap = other, abs(gap)
        if best:
            t.kind = best.kind = TransactionKind.OWN_TRANSFER
            paired.update((id(t), id(best)))

    # A bank-only payment to a bank where the user has an account, on a date none of
    # that bank's statements cover, most likely went to that own account.
    covered: dict[str, list] = defaultdict(list)
    for s in statements:
        if s.is_account and s.account in accounts:
            covered[accounts[s.account].bank].append((s.start, s.cut_date))
    for t in still_open:
        if t.kind != TransactionKind.TRANSFER_CANDIDATE or t.amount <= 0 or not _bank_only(t):
            continue
        bank = next((name for key, name in _BANK_NAMES if key in fold(t.description)), "")
        if bank in covered and not any(a <= t.date <= b for a, b in covered[bank]):
            t.kind = TransactionKind.OWN_TRANSFER
            t.description += " (muhtemelen kendi hesabınıza)"

    for t in still_open:
        if t.kind == TransactionKind.TRANSFER_CANDIDATE:
            t.kind = TransactionKind.INCOME if t.amount < 0 else TransactionKind.P2P_TRANSFER


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


def _to_tl(
    txns: list[Transaction], accounts: dict[str, Account], rates: dict, warnings: list[str]
) -> list[Transaction]:
    """Value foreign-currency account rows in TL with the nearest rate found in the documents."""
    out = []
    for t in txns:
        currency = accounts[t.account].currency if t.account in accounts else TRY
        if currency == TRY:
            out.append(t)
            continue
        if t.kind == TransactionKind.OWN_TRANSFER:
            continue  # moving foreign currency between own accounts changes nothing
        known = rates.get(currency)
        if not known:
            warnings.append(f"{t.date} {currency} {t.amount}: kur bulunamadı, işlem dışarıda bırakıldı")
            continue
        rate = min(known, key=lambda r: abs((r[0] - t.date).days))[1]
        t.amount = round_half_up(t.amount * rate)
        t.original = f"{t.original} × {format_amount(rate)}"
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
) -> Dataset:
    """results: (document, its reading or None, (status, detail) when there is no reading) tuples; a document has
    a name, an origin and a sha256."""
    accounts: dict[str, Account] = {}
    told: dict[str, Account] = {}  # accounts as only bank notices name them
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
        # account): the account as they name it stands.
        named = told if document_type(result.parser) is DocumentKind.NOTICE else accounts
        for a in result.accounts:
            named.setdefault(a.id, a)
        if result.holder:
            holders.add(result.holder)
        for s in result.statements:
            key = (s.account, s.cut_date, s.currency, s.start)
            # The same statement can arrive as different files (re-sent e-mail, archive copy).
            if key not in statements or len(s.transactions) > len(statements[key].transactions):
                statements[key] = s
        if result.transactions:
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
    _fingerprint(stmts, receipts, accounts)
    _link_foreign_currency(stmts)
    days = covered_days(stmts)
    coverage = _coverage(days)

    card_txns = [t for s in stmts if not s.is_account and s.currency == TRY for t in s.transactions]
    account_txns = [t for s in stmts if s.is_account for t in s.transactions]
    # Receipts add what no statement shows yet (a transfer made today) or ever will (a 2022 card payment,
    # old loan installments); a statement's own row stands for what it shows.
    lines = settle_receipts(receipts, stmts, accounts, days)
    receipt_txns = [line.txn for line in lines if line.status in (PROVISIONAL, NO_STATEMENT)]
    for line in lines:
        line.txn.provisional = line.status == PROVISIONAL

    names = settings.get("ad_soyad") or sorted(holders)
    own = Own([names] if isinstance(names, str) else list(names), accounts)
    warnings: list[str] = []
    # A receipt's transfer (a FAST to the landlord, a payment between own accounts) resolves like a list row.
    _resolve_transfers(
        account_txns + receipt_txns, own, categorizer, stmts, accounts, _free_card_payments(card_txns, account_txns)
    )
    rates = _rates(account_txns)
    account_txns = _to_tl(account_txns, accounts, rates, warnings)
    receipt_txns = _to_tl(receipt_txns, accounts, rates, warnings)

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
        regular=categorizer.regular,
        receipts=lines,
        invoices=invoices,
    )
