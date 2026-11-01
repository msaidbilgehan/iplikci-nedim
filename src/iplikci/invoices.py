"""Non-bank bills and receipts against the bank's rows (F14; docs/domain/ledger.md, "Banka dışı faturalar").

A bill or a receipt is never counted: the bank's rows are what counts (K12). It is only matched to the row that paid
it: a row of its amount, in its days, from a merchant whose name is like its seller's. The matched row carries the
document (Transaction.invoice). A document whose days have not passed, or that the bank's documents do not reach yet,
waits. One whose days passed while the bank's documents covered them, with no row, stays information only, with what
may explain it; it changes no total.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from .domain.codes import InvoiceKind, InvoiceStatus, TransactionKind
from .domain.models import TRY, Invoice, Transaction
from .domain.money import CENT
from .domain.text import fold

RECEIPT_BEFORE, RECEIPT_AFTER = 1, 3  # a receipt's row: a day before it to three days after, like a bank receipt's
BILL_GRACE = 3  # days after a bill's due date its payment may still be booked
BILL_DAYS = 30  # a bill that prints no due date is looked for this many days after its date
ACTIVE_DAYS = 62  # an account whose documents end this much before the newest is no longer sent
# The rows a bill or a receipt can be paid by: a purchase (a refund for a refund), money sent to a person, or a
# transfer the ledger could not name.
_PAYING = (
    TransactionKind.PURCHASE,
    TransactionKind.REFUND,
    TransactionKind.P2P_TRANSFER,
    TransactionKind.TRANSFER_CANDIDATE,
)
# Words of a seller's name that do not tell who it is: legal forms, trades and places.
_GENERIC = frozenset(
    {
        "ANONIM",
        "SIRKETI",
        "LIMITED",
        "TICARET",
        "SANAYI",
        "HIZMET",
        "HIZMETLERI",
        "ILETISIM",
        "TELEKOMUNIKASYON",
        "ELEKTRIK",
        "DOGALGAZ",
        "ENERJI",
        "PERAKENDE",
        "SATIS",
        "DAGITIM",
        "TEKNOLOJI",
        "TEKNOLOJILERI",
        "BILISIM",
        "YAZILIM",
        "PAZARLAMA",
        "MAGAZACILIK",
        "TURKIYE",
        "ISTANBUL",
        "ANKARA",
        "IZMIR",
        "INTERNATIONAL",
        "DISTRIBUTION",
        "ONLINE",
        "SERVICES",
        "GROUP",
    }
)
_ORIGINAL = re.compile(r"(-?\d[\d.]*,\d{2})\s*([A-Z]{3})\b")  # a row's foreign amount as the readers write it
UNMATCHED_REASONS = (
    "Başkası ödemiş olabilir.",
    "Belgesi olmayan bir hesaptan ya da nakit ödenmiş olabilir.",
)
UNPAID_REASON = "Henüz ödenmemiş olabilir."  # only a bill may be left unpaid


@dataclass
class InvoiceMatch:
    """A bill or a receipt and what the bank's rows say of it."""

    key: str  # "<sha256>:<position>", as Transaction.invoice names it
    invoice: Invoice
    document: str  # the name of the document it is read from
    status: InvoiceStatus
    window: tuple[date, date]  # the days its bank row is looked for in
    row: Transaction | None = None  # the bank row that paid it, when matched
    reasons: tuple[str, ...] = ()  # what may explain an unmatched one, in Turkish


def window(invoice: Invoice) -> tuple[date, date]:
    """The days a document's bank row is looked for in: a bill's from its date to its due date and three days more, a
    receipt's from the day before it to three days after."""
    if invoice.kind is InvoiceKind.BILL:
        last = invoice.due or invoice.issued + timedelta(days=BILL_DAYS)
        return invoice.issued, last + timedelta(days=BILL_GRACE)
    return invoice.issued - timedelta(days=RECEIPT_BEFORE), invoice.issued + timedelta(days=RECEIPT_AFTER)


def seller_words(seller: str) -> list[str]:
    """The words of a seller's name that tell who it is: folded, of four characters or more, without its legal form,
    trade or place ("TURKCELL İLETİŞİM HİZMETLERİ A.Ş." → TURKCELL)."""
    return [w for w in re.findall(r"[A-Z0-9]+", fold(seller)) if len(w) >= 4 and w not in _GENERIC]


def similar(seller: str, row: Transaction) -> bool:
    """Whether a row's merchant is like the seller: a word that tells who the seller is is in the row's text, written
    together or apart ("APPLE.COM/BILL", "TURKCELLFATURA")."""
    text = re.sub(r"[^A-Z0-9]", "", fold(f"{row.description} {row.merchant} {row.counterparty}"))
    return any(word in text for word in seller_words(seller))


def _foreign(original: str) -> tuple[Decimal, str] | None:
    """A row's foreign amount ("19,99 USD") and its currency."""
    found = _ORIGINAL.search(original)
    if found is None:
        return None
    try:
        return Decimal(found[1].replace(".", "").replace(",", ".")), found[2]
    except InvalidOperation:
        return None


def _amount_fits(invoice: Invoice, row: Transaction) -> bool:
    """The row pays the document's total: in TL to the kuruş, in a foreign currency by the amount the row prints in
    it (the TL amount moves with the bank's rate)."""
    if invoice.currency == TRY:
        return abs(row.amount - invoice.total) < CENT
    foreign = _foreign(row.original)
    if foreign is None:
        return False
    amount, currency = foreign
    return (
        currency == invoice.currency
        and abs(abs(amount) - abs(invoice.total)) < CENT
        and (row.amount > 0) == (invoice.total > 0)
    )


def settled_until(covered: Mapping[str, set[date]]) -> date | None:
    """The newest day every account still sent covers: a document whose days end after it may yet find its row in a
    statement that has not come. An account whose documents stopped long before the others' is left out."""
    last = [max(days) for days in covered.values() if days]
    if not last:
        return None
    newest = max(last)
    return min(day for day in last if (newest - day).days <= ACTIVE_DAYS)


def _anchor(invoice: Invoice) -> date:
    """The day its row most likely falls on: a bill's due date, a receipt's date."""
    return (invoice.due or invoice.issued) if invoice.kind is InvoiceKind.BILL else invoice.issued


def match(
    found: Iterable[tuple[str, Invoice, str]], rows: Sequence[Transaction], until: date | None
) -> list[InvoiceMatch]:
    """Each document of found (key, invoice, document's name) and the bank row that paid it; a row pays one document
    at most, the older documents choosing first. until is settled_until's day: a document whose days end after it
    waits. A matched row is marked with the document's key."""
    used: set[int] = set()
    out: list[InvoiceMatch] = []
    for key, invoice, name in sorted(found, key=lambda f: (f[1].issued, f[0])):
        start, end = window(invoice)
        fits = [
            r
            for r in rows
            if id(r) not in used
            and r.kind in _PAYING
            and start <= r.date <= end
            and _amount_fits(invoice, r)
            and similar(invoice.seller, r)
        ]
        if fits:
            anchor = _anchor(invoice)
            row = min(fits, key=lambda r: (abs((r.date - anchor).days), r.date, r.fingerprint))
            used.add(id(row))
            row.invoice = key
            out.append(InvoiceMatch(key, invoice, name, InvoiceStatus.MATCHED, (start, end), row))
        elif until is None or end > until:
            out.append(InvoiceMatch(key, invoice, name, InvoiceStatus.PENDING, (start, end)))
        else:
            reasons = UNMATCHED_REASONS + ((UNPAID_REASON,) if invoice.kind is InvoiceKind.BILL else ())
            out.append(InvoiceMatch(key, invoice, name, InvoiceStatus.UNMATCHED, (start, end), reasons=reasons))
    return out


def one_copy(found: Iterable[tuple[str, Invoice, str]]) -> list[tuple[str, Invoice, str]]:
    """A document mailed twice, or read from two copies of one message, is one bill: the same seller, number, date
    and total keep the first copy."""
    seen: set[tuple[str, str, date, Decimal]] = set()
    kept: list[tuple[str, Invoice, str]] = []
    for key, invoice, name in found:
        who = invoice.seller_id or fold(invoice.seller)
        mark = (who, invoice.number, invoice.issued, invoice.total)
        if invoice.number and mark in seen:
            continue
        seen.add(mark)
        kept.append((key, invoice, name))
    return kept
