"""The ledger's rows as the screens show them (F04, F05, F07), each with its certainty (architecture §8) and the
document it is printed in.

A receipt's or a bank notice's row that a statement showed left the ledger for the statement's row, which is the one
counted; one that no statement covering its days shows never counted (excluded). Both are still found by their
fingerprints: the first leads to the statement's row, the second is shown for what it is, never in a total. A row the
user split (F04) is counted as its parts, each a row of its own; its own fingerprint still finds it whole."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from ..analysis import CONFIRMED, NOT_ON_STATEMENT, PROVISIONAL, Dataset, ReceiptLine
from ..domain.codes import DEFAULT_EXPENSE_KINDS, Certainty, Necessity, TransactionKind
from ..domain.models import TRY, Transaction

# What the API names from here: the codes a row carries, and the records.
__all__ = [
    "Certainty",
    "Direction",
    "Found",
    "Necessity",
    "RowView",
    "Rows",
    "TransactionKind",
    "certainty_of",
    "direction",
    "view",
]


class Direction(StrEnum):
    """Which way a row's money goes: the screens say it in words, never by a sign (architecture §16)."""

    OUT = "out"
    IN = "in"


def direction(amount: Decimal) -> Direction:
    """Money out above zero, as the ledger counts every kind (docs/domain/ledger.md, "İşaret kuralı")."""
    return Direction.IN if amount < 0 else Direction.OUT


def certainty_of(t: Transaction) -> Certainty:
    """A counted row's certainty: provisional while only a receipt or a notice shows it."""
    return Certainty.PROVISIONAL if t.provisional else Certainty.CONFIRMED


@dataclass(frozen=True, slots=True)
class RowView:
    """A row as a screen lists it."""

    fingerprint: str
    day: date
    account: str  # the account's id
    title: str  # the merchant or the person as the rules name them, else what the bank printed
    description: str  # as the bank printed it (the ledger rewrites a few: a card's foreign spending)
    merchant: str
    counterparty: str  # the other party of a transfer
    amount: Decimal  # above zero; direction says which way
    currency: str  # TRY for every counted row; an excluded row of a foreign account is in the account's currency
    direction: Direction
    kind: TransactionKind
    category: str
    group: str
    necessity: Necessity | None  # only spending and money sent to people have one
    counted: bool  # in the ledger's totals; an excluded row, or a receipt's row a statement tells in its own words, not
    expense: bool  # counted as spending: a purchase, a refund, interest or a fee
    certainty: Certainty
    original: str  # the foreign amount as printed, with the rate it was valued at ("19,99 USD", "100,00 × 34,50")
    installment: str  # "8/12"
    note: str
    tags: tuple[str, ...]
    invoice: str  # the non-bank bill or receipt it paid, "<sha256>:<position>"; "" for none
    document: str  # the sha256 of the document it is printed in
    split_of: str  # a part of a split row: the row's fingerprint; "" for any other row


def view(t: Transaction, certainty: Certainty, currency: str = TRY, counted: bool = True) -> RowView:
    return RowView(
        fingerprint=t.fingerprint,
        day=t.date,
        account=t.account,
        title=t.merchant or t.counterparty or t.description,
        description=t.description,
        merchant=t.merchant,
        counterparty=t.counterparty,
        amount=abs(t.amount),
        currency=currency,
        direction=direction(t.amount),
        kind=t.kind,
        category=t.category,
        group=t.group,
        necessity=t.necessity,
        counted=counted,
        expense=counted and t.kind in DEFAULT_EXPENSE_KINDS,
        certainty=certainty,
        original=t.original,
        installment=t.installment,
        note=t.note,
        tags=t.tags,
        invoice=t.invoice,
        document=t.document,
        split_of=t.split_of,
    )


@dataclass(frozen=True, slots=True)
class Found:
    """What a fingerprint names in an analysis."""

    row: Transaction  # the row as the ledger counts it; else the receipt or notice row as it was read
    certainty: Certainty
    currency: str  # of row.amount: TRY, but an uncounted row of a foreign account keeps the account's currency
    told: ReceiptLine | None  # the receipt or notice row the fingerprint named, when it is not a counted row
    counted: bool = True  # row is in the ledger's totals

    @property
    def view(self) -> RowView:
        return view(self.row, self.certainty, self.currency, self.counted)


class Rows:
    """An analysis' rows by fingerprint: the counted ones, and the receipt and notice rows behind or beside them."""

    def __init__(self, ds: Dataset):
        self.ds = ds
        self.counted = {t.fingerprint: t for t in ds.transactions if t.fingerprint}
        self.evidence = {line.txn.fingerprint: line for line in ds.receipts if line.txn.fingerprint}

    def currency(self, account: str) -> str:
        found = self.ds.accounts.get(account)
        return found.currency if found is not None else TRY

    def find(self, fingerprint: str) -> Found | None:
        """The row a fingerprint names: a counted row; for a receipt's row a statement showed, the statement's row
        that counts in its place; a receipt's row no covering statement shows, excluded. None when no row has it (a
        reading changed the row, or it never was one)."""
        counted = self.counted.get(fingerprint) or self.ds.split.get(fingerprint)
        if counted is not None:
            return Found(counted, certainty_of(counted), TRY, None)
        line = self.evidence.get(fingerprint)
        if line is None:
            return None
        match = line.match
        if line.status == CONFIRMED and match is not None and self._kept(match.fingerprint):
            return Found(match, certainty_of(match), TRY, line)
        currency = self.currency(line.txn.account)
        if line.status == NOT_ON_STATEMENT:
            return Found(line.txn, Certainty.EXCLUDED, currency, line, counted=False)
        # Not counted on its own: a statement confirmed the receipt and tells this row in its own words (a fee printed
        # with the transfer, or on another day), or foreign currency moved between own accounts changes nothing in TL.
        certainty = Certainty.PROVISIONAL if line.status == PROVISIONAL else Certainty.CONFIRMED
        return Found(line.txn, certainty, currency, line, counted=False)

    def _kept(self, fingerprint: str) -> bool:
        """Whether the ledger counts the row: as it is, or split into parts."""
        return fingerprint in self.counted or fingerprint in self.ds.split

    def find_whole(self, fingerprint: str) -> Found | None:
        """As find, but a part of a split row stands for the row it makes up."""
        found = self.find(fingerprint)
        if found is not None and found.row.split_of:
            return self.find(found.row.split_of)
        return found

    def parts(self, fingerprint: str) -> list[Transaction]:
        """The parts of a split row, in order; none for any other row."""
        if fingerprint not in self.ds.split:
            return []
        return [t for t in self.ds.transactions if t.split_of == fingerprint]

    def excluded(self) -> list[ReceiptLine]:
        """The receipt and notice rows no statement covering their days shows: never in a total."""
        return [line for line in self.ds.receipts if line.status == NOT_ON_STATEMENT and line.txn.fingerprint]
