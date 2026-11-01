"""The non-bank bills and receipts (F14): what /api/invoices answers and the MCP tool of the same name tells. They come
from the analysis the service keeps (analysis.Current), each with what the bank's rows say of it (invoices.py): a
matched one names the row that paid it, a pending one waits for its days or for the bank's documents to reach them,
and an unmatched one is information only, with what may explain it. None of them changes a total: the bank's rows
are what counts (K12)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ..domain.codes import InvoiceKind, InvoiceStatus
from ..domain.models import InvoiceLine
from ..domain.money import MINOR_DIGITS, round_half_up
from ..invoices import InvoiceMatch
from .analysis import Analysis

# What the API and the MCP tool name from here: the codes their answers carry and the records they are made from.
__all__ = ["BankRow", "InvoiceKind", "InvoiceLine", "InvoiceStatus", "InvoiceView", "Invoices", "minor", "overview"]


@dataclass(frozen=True, slots=True)
class BankRow:
    """The bank row that paid a bill or a receipt."""

    fingerprint: str
    day: date
    account: str
    amount: Decimal  # in TL, as the ledger counts it: money out above zero, a refund below
    description: str


@dataclass(frozen=True, slots=True)
class InvoiceView:
    """A bill or a receipt as the Bills screen shows it."""

    key: str  # "<sha256>:<position>", as the row that paid it names it (Transaction.invoice)
    sha256: str  # the document it is read from
    document: str  # that document's name
    kind: InvoiceKind
    status: InvoiceStatus
    seller: str
    number: str  # "" when the document prints none
    issued: date
    due: date | None  # a bill's last day to pay, when it prints one
    total: Decimal  # in currency, taxes included; below zero for a refund
    currency: str
    lines: tuple[InvoiceLine, ...]
    window: tuple[date, date]  # the days its bank row is looked for in
    row: BankRow | None  # matched: the row that paid it
    reasons: tuple[str, ...]  # unmatched: what may explain it, in Turkish


@dataclass(frozen=True, slots=True)
class Invoices:
    items: list[InvoiceView]  # pending first, the soonest due first; then unmatched, then matched, the newest first
    counts: dict[InvoiceStatus, int]  # every status, with how many documents have it
    labels: dict[str, str]  # the accounts' labels by id


def minor(value: Decimal, currency: str) -> int:
    """An amount in its currency's smallest unit, as the API carries it (ADR-0006), rounded half up to it. The
    readings keep two decimals in every currency (storage.readings), so a currency the ledger does not know is taken
    with two as well instead of refused: a bill in it is only shown, never counted."""
    digits = MINOR_DIGITS.get(currency, 2)
    return int(round_half_up(value, digits).scaleb(digits))


def _row(found: InvoiceMatch) -> BankRow | None:
    t = found.row
    return None if t is None else BankRow(t.fingerprint, t.date, t.account, t.amount, t.description)


def _view(found: InvoiceMatch) -> InvoiceView:
    invoice = found.invoice
    return InvoiceView(
        key=found.key,
        sha256=found.key.partition(":")[0],
        document=found.document,
        kind=invoice.kind,
        status=found.status,
        seller=invoice.seller,
        number=invoice.number,
        issued=invoice.issued,
        due=invoice.due,
        total=invoice.total,
        currency=invoice.currency,
        lines=tuple(invoice.lines),
        window=found.window,
        row=_row(found),
        reasons=found.reasons,
    )


def _ordered(views: list[InvoiceView]) -> list[InvoiceView]:
    """Pending first, by the last day their row is looked for: a bill's due date (and the days after it the payment
    may still be booked), a receipt's few days; then the unmatched and the matched, the newest first."""

    def having(status: InvoiceStatus) -> list[InvoiceView]:
        return [v for v in views if v.status == status]

    def newest(v: InvoiceView) -> tuple[date, str]:
        return v.issued, v.key

    pending = sorted(having(InvoiceStatus.PENDING), key=lambda v: (v.window[1], v.issued, v.key))
    unmatched = sorted(having(InvoiceStatus.UNMATCHED), key=newest, reverse=True)
    return pending + unmatched + sorted(having(InvoiceStatus.MATCHED), key=newest, reverse=True)


def overview(a: Analysis) -> Invoices:
    """Every bill and receipt non-bank senders mailed, with its status, in the order the screen lists them, and how
    many have each status."""
    ds = a.dataset
    views = _ordered([_view(found) for found in ds.invoices])
    counts = {status: sum(v.status == status for v in views) for status in InvoiceStatus}
    return Invoices(views, counts, {account.id: account.label for account in ds.accounts.values()})
