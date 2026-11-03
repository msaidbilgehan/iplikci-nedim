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

# Kinds a row can be split into categories of (F04): spending, money sent to people and income. The others move
# money between the user's own pockets, where the kind alone says what the row is.
SPLITTABLE_KINDS: tuple[TransactionKind, ...] = (
    *DEFAULT_EXPENSE_KINDS,
    TransactionKind.P2P_TRANSFER,
    TransactionKind.INCOME,
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
    SPLIT_DROPPED = "split_dropped"  # a row the user split that counts whole again: its kind or amount changed
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
    SPLIT = "split"  # a part of a row the user split, under the category they gave the part


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


class HabitStatus(StrEnum):
    """How a discretionary merchant or an avoidable cost goes over the window (docs/domain/interpretation.md)."""

    MONTHLY = "monthly"  # in most months of the window: costs its last three months' average from now on
    NEW = "new"  # started inside the window and kept up
    OCCASIONAL = "occasional"  # now and then: its total spread over the window
    STOPPED = "stopped"  # nothing for longer than its usual gap: costs nothing from now on
    ONE_OFF = "one_off"  # once or twice in a month: never projected


class UnusualKind(StrEnum):
    """A movement worth a look (F10). It is only flagged: no row is ever dropped for it."""

    UNUSUAL_AMOUNT = "unusual_amount"  # far above what this merchant usually takes
    POSSIBLE_DUPLICATE = "possible_duplicate"  # the same amount at the same merchant on the same day, again
    NEW_LARGE = "new_large"  # a large amount at a merchant never seen before
    UNEXPECTED_FEE = "unexpected_fee"  # a fee or a due the account did not charge in the months before


class NecessityReason(StrEnum):
    """Where a spending row's necessity comes from (docs/domain/categorization.md, "Gereklilik")."""

    USER = "user"  # the user's correction on this row
    MERCHANT = "merchant"  # the rules' `_gereklilik_işyeri`: this merchant's own level
    CATEGORY = "category"  # the rules' `_gereklilik`: the category's level
    DEFAULT = "default"  # no rule gives one: "Belirsiz"


class ForecastPart(StrEnum):
    """The parts of the three-month spending forecast (docs/domain/interpretation.md, "Tahmin")."""

    REGULAR = "regular"  # regular payments still running, at their monthly amount
    INSTALLMENTS = "installments"  # installments still due
    VARIABLE = "variable"  # everything else, a necessity level at a time: the median of the base months


class AccountGroup(StrEnum):
    """The Accounts screen's groups (F07), in its order: a card of either kind is a card, every other account is
    grouped by its type."""

    CARDS = "cards"
    CURRENT = "current"
    DEPOSIT = "deposit"
    OVERDRAFT = "overdraft"
    FX = "fx"
    GOLD = "gold"
    BROKERAGE = "brokerage"
    LOAN = "loan"


class PaidStatus(StrEnum):
    """How a credit card statement was paid (F07's payment history): by the next statement's cut, or for the newest
    one, by today."""

    FULL = "full"  # its balance in full (99% or more)
    MINIMUM = "minimum"  # its minimum payment, or a little more
    PARTIAL = "partial"  # more than nothing, less than in full: above or below the minimum
    UNPAID = "unpaid"  # nothing paid
    OPEN = "open"  # the newest statement: its due date has not passed and it is not paid in full yet
    NOTHING_DUE = "nothing_due"  # no balance to pay


class FlowKind(StrEnum):
    """What a node of the flow between accounts is (F07's Sankey): one of the user's accounts, or where money came from
    or went."""

    ACCOUNT = "account"
    INCOME = "income"  # an income's payer
    SPENDING = "spending"  # a spending group: purchases less refunds, interest and fees
    PEOPLE = "people"  # money sent to or received from people
    SAVING = "saving"  # savings and investments: a pension fund, shares
    LOAN = "loan"  # a loan's principal paid, or a loan received
    CASH = "cash"  # cash taken with a card
    ELSEWHERE = "elsewhere"  # an own account or a card no document shows the other side of


class SetupStep(StrEnum):
    """The setup wizard's steps (F17), in its order."""

    DATA_FOLDER = "data_folder"  # where the data lives: information only
    NAMES = "names"  # the user's own names and their forms
    BUSINESS_NAMES = "business_names"  # company names, whose documents stay out (optional)
    MAIL = "mail"  # how e-mail comes in: the browser extension paired, or an IMAP account
    SENDERS = "senders"  # the banks the program reads, and the non-bank senders the user adds (optional)
    DOCUMENTS = "documents"  # older documents taken in from a folder, an mbox or a zip
    NOTIFICATIONS = "notifications"  # a channel besides the interface's box (optional)
    SERVICE = "service"  # the service registered to start with the computer (ADR-0017)
    REMOTE = "remote"  # remote access through Tailscale (optional)


class StatementCheck(StrEnum):
    """A statement's own check on the month-end page (docs/domain/interpretation.md, "Ay sonu kapanışı")."""

    VERIFIED = "verified"  # its rows add up to its total, its running balances agree
    FAILED = "failed"  # they do not: it holds the month open for a check
    NOTHING = "nothing"  # nothing to check: a list without movements, a statement printing no total


class RateSource(StrEnum):
    """Where a TL rate comes from (F12, architecture §15). A row's own rate always comes first; then TCMB's bulletin
    of the day; ECB's reference rate, or Frankfurter's copy of it, when TCMB could not be reached. Without the
    network the documents' own rates are used."""

    DOCUMENT = "document"  # a row of a bank's document prints it: a foreign currency bought or sold
    TCMB = "tcmb"  # the Central Bank of Turkey's daily bulletin: forex buying and selling
    ECB = "ecb"  # the European Central Bank's euro reference rates: one rate for both sides
    FRANKFURTER = "frankfurter"  # the same ECB rates, from frankfurter.dev
