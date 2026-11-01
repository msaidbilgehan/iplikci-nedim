"""The domain's codes (ADR-0006, docs/domain/ledger.md).

Codes are English and stable: they are what the database, the API and the exports carry. Their Turkish
labels live in one place, labels.py. The keys of the user's rule files stay Turkish (`_gereklilik`,
`_tür`) because the user edits them; the categorizer maps them to these codes.
"""

from enum import StrEnum


class TransactionKind(StrEnum):
    """What a row is. For every kind, an amount above zero is money leaving the user and below zero money
    coming in (a refund, income, a transfer in)."""

    PURCHASE = "purchase"
    REFUND = "refund"
    INTEREST_FEE = "interest_fee"
    P2P_TRANSFER = "p2p_transfer"
    LOAN_PRINCIPAL = "loan_principal"
    CASH_ADVANCE = "cash_advance"
    INVESTMENT = "investment"
    INCOME = "income"
    CARD_PAYMENT_NO_STATEMENT = "card_payment_no_statement"
    CARD_PAYMENT = "card_payment"
    OWN_TRANSFER = "own_transfer"
    # A row of an account list that moves money to or from someone the reader cannot name yet: the ledger
    # resolves it once every account is read (own transfer, a rule's kind, a person, income).
    TRANSFER_CANDIDATE = "transfer_candidate"


# Kinds counted as spending unless the user switches them on or off. Debt principal, cash advances, savings,
# card payments and transfers move money between the user's own pockets (or repay earlier spending) and would
# count purchases twice; money sent to other people is shown but kept apart.
DEFAULT_EXPENSE_KINDS: tuple[TransactionKind, ...] = (
    TransactionKind.PURCHASE,
    TransactionKind.REFUND,
    TransactionKind.INTEREST_FEE,
)


class Necessity(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    UNNECESSARY = "unnecessary"  # interest and fees by default
    UNKNOWN = "unknown"  # no rule decided


class AccountType(StrEnum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    CURRENT = "current"
    DEPOSIT = "deposit"
    OVERDRAFT = "overdraft"
    FX = "fx"
    GOLD = "gold"
    BROKERAGE = "brokerage"
    LOAN = "loan"


CARD_TYPES: tuple[AccountType, ...] = (AccountType.CREDIT_CARD, AccountType.DEBIT_CARD)


class EvidenceStatus(StrEnum):
    """What the statements say about a receipt's or a bank notice's row (docs/domain/ledger.md)."""

    MATCHED = "matched"  # a statement shows it: the statement's row counts
    PROVISIONAL = "provisional"  # after the account's newest statement: counts now, the next one confirms it
    UNMATCHED = "unmatched"  # statements cover its days but do not show it: left out, worth a look
    NO_STATEMENT = "no_statement"  # no statement covers its days (older, a gap, a loan): counts as it is


class Certainty(StrEnum):
    """How sure a row or a total is, and whether it counts (architecture §8)."""

    CONFIRMED = "confirmed"
    PROVISIONAL = "provisional"
    EXCLUDED = "excluded"
    INFO = "info"


class DocumentStatus(StrEnum):
    """Where a stored document stands (ADR-0003)."""

    PROCESSED = "processed"
    UNPROCESSED = "unprocessed"  # not recognised or carries no money movement; kept with the reason
    UNREADABLE = "unreadable"  # cannot be read as it is: an encrypted PDF, a broken zip, no OCR
    REMOVED = "removed"  # its file went to the system Trash


class DocumentKind(StrEnum):
    CARD_STATEMENT = "card_statement"
    ACCOUNT_STATEMENT = "account_statement"  # account movement lists, passbooks, brokerage statements
    RECEIPT = "receipt"
    NOTICE = "notice"  # a bank's e-mail about a movement (a transfer that came in or went out): evidence like a receipt


class SourceKind(StrEnum):
    """How a document reached the archive."""

    EMAIL = "email"
    UPLOAD = "upload"
    INBOX = "inbox"
    IMPORT = "import"


class MonthStatus(StrEnum):
    """Month-end closing: of a month, and of each account within it."""

    CLOSED = "closed"
    WAITING = "waiting"  # a statement is still due
    MISSING = "missing"  # a document that should exist is not in the archive
    CHECK = "check"  # the documents disagree: a receipt the statement does not show
    RUNNING = "running"  # the month is not over


class Tone(StrEnum):
    """How a finding reads."""

    ATTENTION = "attention"
    INFO = "info"
    GOOD = "good"


class Actor(StrEnum):
    """Who made a change, for the audit log."""

    USER = "user"
    MCP = "mcp"
    SYSTEM = "system"
    MIGRATION = "migration"


class BackupReason(StrEnum):
    """Why a backup was made (architecture §19)."""

    DAILY = "daily"
    MANUAL = "manual"  # asked for by the user
    BEFORE_RESTORE = "before_restore"  # what was there before a restore, so the restore can be undone


class SeriesStatus(StrEnum):
    """Whether a regular or periodic payment still runs (docs/domain/interpretation.md, "Düzenli ödemeler")."""

    ACTIVE = "active"
    ENDED = "ended"  # its accounts' statements went past the expected payment without it, or 90 days passed
    CANCELLED = "cancelled"  # the user's rules list it under `_biten`
    PAID_AFTER_CANCEL = "paid_after_cancel"  # a payment came after the month `_biten` names


class SeriesPeriod(StrEnum):
    """How far apart a series' payments are: about a month, half a year or a year."""

    MONTH = "month"
    HALF_YEAR = "half_year"
    YEAR = "year"
