"""The models the readers fill and the ledger combines: accounts, statements, rows, securities, and the bills and
receipts of non-bank senders."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .codes import AccountType, InvoiceKind, Necessity, TransactionKind
from .money import TOLERANCE, round_half_up

# The lira as the models carry it (ADR-0006); labels.currency_label writes it as "TL".
TRY = "TRY"


@dataclass
class Account:
    id: str
    label: str
    bank: str
    type: AccountType
    currency: str = TRY
    number: str = ""  # card last digits or account number, for file names and own-account detection
    note: str = ""


@dataclass(frozen=True)
class SourceRef:
    """Where a row is printed in its document (architecture §10): a PDF page with the line's box or its line number
    in the page's text, a spreadsheet's sheet and row, or a span of an HTML document's text."""

    page: int | None = None  # 1-based
    box: tuple[float, float, float, float] | None = None  # x0, top, x1, bottom in points from the page's top left
    line: int | None = None  # 1-based line of the page's text, where the reader reads text rather than boxes
    sheet: str | None = None  # the sheet's name; "" for an HTML table
    row: int | None = None  # 1-based row of the sheet or table
    span: tuple[int, int] | None = None  # start and end in the document's text, its whitespace collapsed


@dataclass
class Transaction:
    """A row. For every kind an amount above zero is money leaving the user, below zero money coming in."""

    date: date
    description: str
    amount: Decimal  # in the account's (the statement's) currency until the ledger turns it into TRY
    kind: TransactionKind
    account: str
    original: str = ""  # foreign amount, e.g. "19,99 USD"
    installment: str = ""  # e.g. "8/12"
    bank_category: str = ""  # category heading printed by the bank, if any
    counterparty: str = ""  # sender/receiver of a bank transfer
    source: str = ""
    ref: SourceRef | None = None  # where the row is printed in the document
    balance: Decimal | None = None  # the account's balance after the row, where only the row prints it (a notice)
    # Filled in by categorize.py; necessity only for spending (purchases, refunds, fees, money sent to people).
    merchant: str = ""
    category: str = ""
    group: str = ""
    necessity: Necessity | None = None
    # Set by analysis.py: a receipt's row that no statement shows yet (it waits for the next one).
    provisional: bool = False
    # Set by analysis.py from the row as read (domain.fingerprint), and the user's note and tags bound to it.
    fingerprint: str = ""
    note: str = ""
    tags: tuple[str, ...] = ()
    # Set by analysis.py: the non-bank bill or receipt matched to the row (F14), as "<sha256>:<position>".
    invoice: str = ""
    # Set by analysis.py: the sha256 of the document the row is printed in. `source` is the file's name as its reader
    # saw it, and many documents share one ("HesapOzeti.pdf"); this names the very one.
    document: str = ""


@dataclass
class Security:
    """A security held in an investment account, valued at the market price its statement prints."""

    code: str  # exchange ticker, e.g. "ORNEK"
    name: str
    quantity: Decimal
    value: Decimal  # market value in TRY on as_of
    as_of: date


@dataclass
class Statement:
    """A card statement (hesap özeti) or an account movement list (hesap hareketleri)."""

    account: str
    cut_date: date  # statement cut date, or the last day of an account movement list
    currency: str
    source: str
    previous: Decimal | None  # previous balance printed on the statement
    total: Decimal | None  # statement balance printed on the statement
    transactions: list[Transaction] = field(default_factory=list[Transaction])
    # Debit-card statements only print the sum of purchases, not a balance.
    total_is_sum: bool = False
    # Account movement lists: covered period and running-balance checks.
    # previous / total then hold the opening and closing balance.
    start: date | None = None
    checks_ok: int = 0
    checks_total: int = 0
    balances: dict[str, Decimal] = field(default_factory=dict[str, Decimal])  # "YYYY-MM" -> month-end balance
    # Investment accounts: the securities held at the end of the statement (previous / total are the cash).
    securities: list[Security] = field(default_factory=list[Security])
    # A passbook (e-cüzdan): the account as the bank sent it once, when it opened. Banks mail no monthly list after
    # it, so the month-end does not wait for the account's later days.
    one_off: bool = False
    # Card statements: what the bank prints for paying the statement, in its currency; None where it prints none.
    due_date: date | None = None  # this statement's "Son Ödeme Tarihi", never the next statement's
    minimum_payment: Decimal | None = None  # the minimum due by due_date
    credit_limit: Decimal | None = None  # the card's total limit

    @property
    def is_account(self) -> bool:
        return self.start is not None

    @property
    def computed_total(self) -> Decimal:
        lines = round_half_up(sum((t.amount for t in self.transactions), Decimal(0)))
        return lines if self.total_is_sum else round_half_up((self.previous or Decimal(0)) + lines)

    @property
    def difference(self) -> Decimal | None:
        """A card statement: its lines against the total it prints. An account list: how many running-balance
        checks failed."""
        if self.is_account:
            return Decimal(self.checks_total - self.checks_ok)
        if self.total is None:
            return None
        return round_half_up(self.computed_total - self.total)

    @property
    def verified(self) -> bool:
        if self.is_account:
            return self.checks_total > 0 and self.checks_ok == self.checks_total
        return self.difference is not None and abs(self.difference) <= TOLERANCE


@dataclass(frozen=True)
class InvoiceLine:
    """An item of a bill or a receipt, as it prints it."""

    description: str
    amount: Decimal  # the item's total, its taxes included
    quantity: Decimal | None = None


@dataclass
class Invoice:
    """A bill or a receipt a non-bank sender mails (F14). It is never counted: the ledger only matches it to a bank
    row (docs/domain/ledger.md, "Banka dışı faturalar")."""

    kind: InvoiceKind
    seller: str  # as printed
    issued: date
    total: Decimal  # what is to pay, or was paid, taxes included; below zero for a refund
    currency: str = TRY
    number: str = ""  # the invoice's or the order's number
    due: date | None = None  # a bill's last day to pay
    seller_id: str = ""  # the seller's tax number (VKN), when printed
    lines: list[InvoiceLine] = field(default_factory=list[InvoiceLine])
    ref: SourceRef | None = None  # where the total is printed


@dataclass
class ParseResult:
    """What a parser extracted from one document."""

    parser: str
    accounts: list[Account] = field(default_factory=list[Account])
    statements: list[Statement] = field(default_factory=list[Statement])
    # Transactions that don't belong to a statement (bank receipts / dekont).
    transactions: list[Transaction] = field(default_factory=list[Transaction])
    # Unique id of a receipt so the same receipt in PDF and HTML is counted once.
    receipt_key: str = ""
    # Account holder printed on the document; used to recognise own transfers.
    holder: str = ""
    # Short title for the document, used when filing it ("Kredi Taksiti 5678").
    title: str = ""
    # Bills and receipts of non-bank senders (F14).
    invoices: list[Invoice] = field(default_factory=list[Invoice])
