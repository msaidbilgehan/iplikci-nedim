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
    INVOICE = "invoice"  # a non-bank sender's bill or receipt (F14): matched to the bank's rows, never counted


class InvoiceKind(StrEnum):
    """What a non-bank document asks for (F14): it sets the days its bank row is looked for in."""

    BILL = "bill"  # a bill to pay by its due date: telephone, internet, energy
    RECEIPT = "receipt"  # a payment made at once: an app store, a subscription, a shop's order or e-archive invoice


class InvoiceStatus(StrEnum):
    """What the bank's rows say of a non-bank document (docs/domain/ledger.md, "Banka dışı faturalar")."""

    MATCHED = "matched"  # a bank row of its amount, in its days, from a merchant like its seller
    PENDING = "pending"  # its days have not passed, or the bank's documents do not reach them yet
    UNMATCHED = "unmatched"  # its days passed, the documents cover them, and no row is there


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


class PaymentKind(StrEnum):
    """What an item of the calendar is (F09)."""

    REGULAR = "regular"  # a monthly series' next payment
    PERIODIC = "periodic"  # a half-yearly or yearly series' next payment
    INCOME = "income"  # the salary or another regular income
    INSTALLMENT = "installment"  # a card purchase's installment still to come, on a later statement
    LOAN = "loan"  # a loan's next installment, from its receipts
    CARD_DUE = "card_due"  # a card statement's due date
    BILL = "bill"  # a non-bank bill not paid yet, on its due date (F14)


class EventKind(StrEnum):
    """What the event log records (architecture §13); the alert rules name these (architecture §14)."""

    DOCUMENT_RECEIVED = "document.received"
    DOCUMENT_PROCESSED = "document.processed"
    DOCUMENT_UNPROCESSED = "document.unprocessed"
    DOCUMENT_UNREADABLE = "document.unreadable"
    TRANSACTION_CREATED = "transaction.created"
    TRANSACTION_CONFIRMED = "transaction.confirmed"
    TRANSACTION_LARGE = "transaction.large"
    EVIDENCE_UNMATCHED = "evidence.unmatched"
    INVOICE_MATCHED = "invoice.matched"
    INVOICE_PENDING = "invoice.pending"
    INVOICE_UNMATCHED = "invoice.unmatched"
    PAYMENT_DUE_SOON = "payment.due_soon"
    EXPECTED_PAYMENT_MISSING = "expected_payment.missing"
    BALANCE_FORECAST_NEGATIVE = "balance.forecast_negative"
    SUBSCRIPTION_PRICE_CHANGED = "subscription.price_changed"
    SUBSCRIPTION_PAID_AFTER_CANCEL = "subscription.paid_after_cancel"
    INCOME_RECEIVED = "income.received"
    INCOME_LATE = "income.late"
    MONTH_ENDED = "month.ended"
    MONTH_CLOSED = "month.closed"
    MONTH_NEEDS_CHECK = "month.needs_check"
    PARSER_FORMAT_ALARM = "parser.format_alarm"
    MAIL_AUTH_FAILED = "mail.auth_failed"
    MAIL_BRIDGE_ALARM = "mail.bridge_alarm"
    MAIL_BRIDGE_SILENT = "mail.bridge_silent"
    BACKUP_FAILED = "backup.failed"
    BRIDGE_PAIRED = "bridge.paired"
    BRIDGE_REVOKED = "bridge.revoked"


class Channel(StrEnum):
    """Where a notification goes (ADR-0010)."""

    IN_APP = "in_app"  # the interface's notification box; always on
    DESKTOP = "desktop"
    EMAIL = "email"  # to the user's own address over SMTP; only accounts that allow app passwords
    TELEGRAM = "telegram"  # the user's own bot, to the paired chat


class DetailLevel(StrEnum):
    """How much a notification says (ADR-0010)."""

    FULL = "full"  # the event, the amount, the merchant or other party, the account's last digits
    SUMMARY = "summary"  # the event and the amount
    MINIMAL = "minimal"  # only the kind of event: the details are in the app


class DeliveryStatus(StrEnum):
    """Where a notification stands on its channel (ADR-0010)."""

    PENDING = "pending"  # to be sent; a failed attempt waits and is tried again
    SENT = "sent"
    HELD = "held"  # kept back by the quiet hours or the channel's rate: it goes out in the next digest
    DIGESTED = "digested"  # sent within a digest
    FAILED = "failed"  # every attempt failed: never tried again


class TodoKind(StrEnum):
    """What keeps the data from being complete and right (F19): each a to-do with the step that settles it."""

    UNCATEGORIZED = "uncategorized"  # rows no rule names ("Belirsiz"), a merchant at a time
    UNMATCHED_EVIDENCE = "unmatched_evidence"  # a receipt's or notice's row its statement leaves out
    UNMATCHED_INVOICE = "unmatched_invoice"  # a non-bank bill no bank row paid
    UNVERIFIED_STATEMENT = "unverified_statement"  # a statement whose rows do not add up to what it prints
    MISSING_DOCUMENTS = "missing_documents"  # an account's statements stop early or skip a month
    UNPROCESSED_DOCUMENT = "unprocessed_document"  # a document no reader read, or could not read
    ORPHAN_ANNOTATION = "orphan_annotation"  # a correction no row carries any more
    FORMAT_ALARM = "format_alarm"  # a reader that may no longer know its bank's format


class TodoAction(StrEnum):
    """The steps a to-do offers (F19)."""

    ADD_RULE = "add_rule"  # a category rule for the merchant
    UPLOAD = "upload"  # the missing document, from the computer
    REPARSE = "reparse"  # read the document again
    OPEN = "open"  # the screen that shows it
    ASK_CLAUDE = "ask_claude"  # a request to paste into Claude, with the MCP server connected
    IGNORE = "ignore"  # take it off the list


class ChannelStage(StrEnum):
    """What stands between a notification channel and the next notification besides its being turned off: the
    interface names the user's next step by it (ADR-0010)."""

    READY = "ready"  # nothing: it carries the next notification
    STOPPED = "stopped"  # refused once (a login, a token, a blocked bot): it waits until the user turns it on again
    UNAVAILABLE = "unavailable"  # this computer or this account has no way: no notify-send, no app password
    NO_BOT = "no_bot"  # Telegram: no bot's token was entered
    TOKEN_LOST = "token_lost"  # Telegram: the keyring no longer holds the token
    NOT_PAIRED = "not_paired"  # Telegram: no chat sent the pairing code yet


class CategoryReason(StrEnum):
    """How a row got its category (docs/domain/categorization.md): the Transactions screen's "Neden?" (F04)."""

    RULE = "rule"  # a merchant or a keyword of the rules named it
    BANK_CATEGORY = "bank_category"  # no rule did: the category heading the bank printed, as the rules map it
    WEAK_RULE = "weak_rule"  # a weak keyword, tried after the bank's heading
    INVOICE = "invoice"  # the seller a matched bill or receipt names in full (F14)
    TRANSFER_RULE = "transfer_rule"  # a rule named the transfer's party or purpose: rent, family, salary
    KIND = "kind"  # its kind decides it: loan principal, a cash advance, a card payment, savings
    FEE = "fee"  # interest and fees, by what caused them
    OWN_TRANSFER = "own_transfer"  # between the user's own accounts, or foreign currency and gold bought or sold
    PERSON = "person"  # money sent to a person
    INCOME = "income"  # money that came in, no rule naming it
    UNCATEGORIZED = "uncategorized"  # nothing named it
    USER = "user"  # the user's correction on this very row


class TransferStep(StrEnum):
    """How the ledger resolved a row that moves money to or from someone its reader could not name
    (docs/domain/ledger.md, transfers), in the order the ledger tries them."""

    OWN_NAME = "own_name"  # the other party is the user
    OWN_ACCOUNT = "own_account"  # the description names one of the user's accounts
    RULE = "rule"  # a rule names the party or the purpose
    LIKE_NAMED = "like_named"  # the same receiving bank and amount as a payment a rule names
    PAIRED = "paired"  # an opposite row of the same amount in another own account, a few days apart
    UNCOVERED_BANK = "uncovered_bank"  # to a bank where the user has an account, on a day its statements leave out
    PERSON = "person"  # none of these, money out: sent to a person
    INCOME = "income"  # none of these, money in


class RuleLayer(StrEnum):
    """The rule file a category rule is in (docs/domain/categorization.md): the user's own goes above the shipped."""

    OWN = "own"
    SHIPPED = "shipped"
