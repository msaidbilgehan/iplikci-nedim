"""The API's answers (pydantic at the boundary). Amounts, when they come, are minor units with their currency."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from ..app import invoices
from ..app.fx import RateSource
from ..app.invoices import InvoiceKind, InvoiceStatus
from ..app.links import Link, Screen
from ..app.notify import Channel, ChannelStage, DeliveryStatus, DetailLevel, EventKind
from ..app.now import Pace, Untold
from ..app.rows import Certainty, Direction, Necessity, RowView, TransactionKind
from ..app.sayings import Mood, Saying, Situation
from ..app.transactions import SavingPart, SavingShown


class LoginLink(BaseModel):
    url: str


class MoneyOut(BaseModel):
    """An amount in its currency's smallest unit: {"minor": 123456, "currency": "TRY"} is 1.234,56 TL. The interface
    formats it (architecture §16)."""

    minor: int
    currency: str


def money(value: Decimal, currency: str = "TRY") -> MoneyOut:
    """An exact amount as the API carries it: minor units of its currency, rounded half up to them (ADR-0006). Grams
    of gold ("GR") count in hundredths, as the documents print them."""
    return MoneyOut(minor=invoices.minor(value, currency), currency=currency)


class AccountRefOut(BaseModel):
    id: str
    label: str


def account_ref(account: str, labels: dict[str, str]) -> AccountRefOut:
    return AccountRefOut(id=account, label=labels.get(account, account))


class UntoldOut(BaseModel):
    """Money that came into an account which no document tells yet: the account paid out more than its documents show
    it held, so the money came in first, from where the documents most likely still count it (another own account).
    The totals take it off, so it is not counted twice; the account's balance is zero for it."""

    account: AccountRefOut
    value: MoneyOut  # in TL, above zero
    day: date  # the newest day the account's balance knows of


def untold_out(found: Untold, labels: dict[str, str]) -> UntoldOut:
    return UntoldOut(account=account_ref(found.account, labels), value=money(found.value), day=found.day)


class LinkOut(BaseModel):
    """Where an item leads in the interface: a screen and what to open there (Screen names what id holds for each)."""

    screen: Screen
    id: str
    # The filters a list screen opens with, in the API's names: one value as a string, a filter given many values
    # (kind=purchase&kind=refund) as their list. A document opens at a row with {"satir": fp}.
    query: dict[str, str | list[str]]


def link_out(link: Link | None) -> LinkOut | None:
    if link is None:
        return None
    query: dict[str, str | list[str]] = {}
    for name, value in link.query:
        was = query.get(name)
        query[name] = value if was is None else [*([was] if isinstance(was, str) else was), value]
    return LinkOut(screen=link.screen, id=link.id, query=query)


class SavingPartOut(BaseModel):
    """A part of a month's saving: an investment category (BES, a fund) or a kind of savings account (currency, gold,
    deposits, investment accounts)."""

    part: SavingPart
    category: str  # the investment rows' category; "" for a kind of savings account
    label: str  # how the screens name it: the category, else the kind of savings
    amount: MoneyOut  # above zero set aside, below zero taken out of the savings
    link: LinkOut  # its rows of the month; their totals' saving is the amount


def saving_part_out(found: SavingShown) -> SavingPartOut:
    link = link_out(found.link)
    assert link is not None  # a part always leads to its rows
    return SavingPartOut(
        part=found.part, category=found.category, label=found.label, amount=money(found.amount), link=link
    )


class RowOut(BaseModel):
    """A row of the ledger as the screens list it."""

    fingerprint: str  # its identity: notes and corrections are bound to it (architecture §8)
    day: date
    account: AccountRefOut
    title: str  # the merchant or the person as the rules name them, else what the bank printed
    description: str  # as the bank printed it
    merchant: str
    counterparty: str  # the other party of a transfer; "" for none
    # Above zero; direction says which way. In TL as the ledger counts it; an excluded row of a foreign account,
    # which no rate ever valued, in the account's currency.
    amount: MoneyOut
    direction: Direction
    kind: TransactionKind
    category: str
    group: str
    necessity: Necessity | None  # only spending and money sent to people have one
    # In the ledger's totals. Not: an excluded row, or a receipt's row a statement confirmed in its own words (a fee
    # the statement prints with the transfer).
    counted: bool
    expense: bool  # counted as spending: a purchase, a refund, interest or a fee
    certainty: Certainty  # confirmed; provisional (only a receipt or a notice shows it); excluded (never counted)
    original: str  # the foreign amount as printed, with the rate it was valued at; "" for a TL row
    installment: str  # "8/12"; "" for none
    note: str
    tags: list[str]
    invoice: str  # the non-bank bill or receipt it paid, "<sha256>:<position>"; "" for none
    document: str  # the sha256 of the document it is printed in (the viewer: /belgeler/<sha256>?satir=<fingerprint>)
    # A part of a row the user split (F04): the row's fingerprint, which its detail, its corrections and the viewer
    # go by; the part's own is the row's with its number after it. "" for any other row.
    split_of: str
    split_parts: int  # a part of a split row: how many parts the row has; 0 for any other row
    # What a counted row adds to the money set aside, above zero, or takes out of the savings, below zero, and where
    # it went (BES and investments, currency, gold, a deposit, an investment account); null for a row that moves no
    # money into or out of the savings. The rows of a month's saving add up to it.
    saving: MoneyOut | None = None
    saving_part: SavingPart | None = None


def row_out(row: RowView, labels: dict[str, str]) -> RowOut:
    return RowOut(
        fingerprint=row.fingerprint,
        day=row.day,
        account=account_ref(row.account, labels),
        title=row.title,
        description=row.description,
        merchant=row.merchant,
        counterparty=row.counterparty,
        amount=money(row.amount, row.currency),
        direction=row.direction,
        kind=row.kind,
        category=row.category,
        group=row.group,
        necessity=row.necessity,
        counted=row.counted,
        expense=row.expense,
        certainty=row.certainty,
        original=row.original,
        installment=row.installment,
        note=row.note,
        tags=list(row.tags),
        invoice=row.invoice,
        document=row.document,
        split_of=row.split_of,
        split_parts=row.split_parts,
        saving=None if row.saving_part is None else money(row.saving),
        saving_part=row.saving_part,
    )


class PaceOut(BaseModel):
    """The month's spending so far (purchases, refunds, interest and fees) against the typical month. The month is
    partial: card spending comes with the statements after their cut dates; the typical month comes from complete
    months only."""

    month: str  # the current month, YYYY-MM
    partial: bool  # always true: the current month is not over
    day: int  # today's day of the month
    days: int  # the month's days
    spent: MoneyOut  # spending dated in the month up to today, as far as the documents tell
    provisional: MoneyOut  # of that, what only receipts and notices show yet
    typical: MoneyOut | None  # the median month of up to six complete months before it; null with fewer than three
    by_day: MoneyOut | None  # the median of the same months' spending up to the same day of the month
    months: list[str]  # those complete months
    covered: float  # the share of the month's days so far the accounts' documents cover, 0..1
    note: str  # what the numbers rest on, in Turkish


def pace_out(found: Pace) -> PaceOut:
    return PaceOut(
        month=found.month,
        partial=True,
        day=found.day,
        days=found.days,
        spent=money(found.spent),
        provisional=money(found.provisional),
        typical=None if found.typical is None else money(found.typical),
        by_day=None if found.by_day is None else money(found.by_day),
        months=list(found.months),
        covered=found.covered,
        note=found.note,
    )


class QuoteOut(BaseModel):
    """A line of İplikçi Nedim's; a dialogue's lines in turn, his first."""

    id: str
    lines: list[str]


class SayingOut(BaseModel):
    """İplikçi Nedim's word on the money (F06): a line of his, the situation it is said about and how that stands.
    The browser extension shows it too, so it carries no amount, account or name (ADR-0020)."""

    situation: Situation
    mood: Mood  # good, warning, critical or neutral: the colour of his face
    reason: str  # the situation in a Turkish sentence: words and shares only
    quote: QuoteOut


def saying_out(found: Saying) -> SayingOut:
    return SayingOut(
        situation=found.situation,
        mood=found.mood,
        reason=found.reason,
        quote=QuoteOut(id=found.quote.id, lines=list(found.quote.lines)),
    )


class ReaderHealthOut(BaseModel):
    parser: str
    name: str
    version: str
    documents: int
    statements: int
    verified: int
    last_read: str
    alarms: int


class DiskOut(BaseModel):
    vault: int
    database: int
    free: int


class ServiceOut(BaseModel):
    version: str
    started_at: str
    pid: int
    home: str


class FailedJobOut(BaseModel):
    id: int
    kind: str
    attempts: int
    finished_at: str
    error: str


class QueueOut(BaseModel):
    counts: dict[str, int]
    next_run: str
    failures: list[FailedJobOut]


class RefusedMailOut(BaseModel):
    taken: Literal["unlisted", "unverified", "business"]
    reason: str  # what the trust rule saw: no-dmarc, dmarc:fail, header-from:…
    domain: str  # the sender's domain; "" for a sender on no list
    count: int
    label: str  # why, in Turkish


class UnknownMailOut(BaseModel):
    domain: str
    template: str  # the subject with numbers and month names masked
    count: int


class MailCoverageOut(BaseModel):
    """F01's measure: the kept bank messages read or knowingly classified as moving no money."""

    total: int
    read: int  # a reader read the body
    attached: int  # read through the documents it carries
    no_money: int  # a campaign, an announcement, a security or a card notice
    business: int  # a company's: gone to the Trash
    unknown: int
    share: float  # what is not unknown, of the total; 1.0 when there is nothing yet
    left: list[UnknownMailOut]  # the unknown ones by kind, most first


class MailOut(BaseModel):
    connector: Literal["imap", "browser_bridge"]
    configured: bool
    last_run: str
    last_error: str
    stopped: bool
    start_day: str  # where the history begins
    history_due: bool  # the extension has not scanned Gmail for this start day and these senders yet
    refused: list[RefusedMailOut]  # messages the extension delivered that were not kept, by why; most first
    coverage: MailCoverageOut


class BackupHealthOut(BaseModel):
    last: str
    next: str
    count: int
    size: int
    rehearsal: str
    rehearsal_ok: bool | None


class RateDaysOut(BaseModel):
    source: RateSource
    newest: date  # the newest day of its rates
    days: int  # days of its rates kept


class RatesOut(BaseModel):
    """Where the exchange rates stand (architecture §15)."""

    providers: list[RateSource]  # the providers the settings let the program ask, in that order; empty: none
    sources: list[RateDaysOut]  # those whose rates are kept, TCMB first
    days: int  # days with any provider's rates
    start: date | None  # the history's first day: the oldest the data covers; null without documents
    missing: int  # business days of the history the first provider was not asked for yet
    last_run: str  # the last fetch that asked anything; "" if none yet
    last_error: str  # what went wrong in it, in Turkish
    summary: str  # all of it in a line, in Turkish


class SystemOut(BaseModel):
    service: ServiceOut
    documents: dict[str, int]
    readers: list[ReaderHealthOut]
    disk: DiskOut
    queue: QueueOut
    mail: MailOut
    backup: BackupHealthOut
    rates: RatesOut | None = None  # the service always gives it; null only from one older than Phase 8


class BackupOut(BaseModel):
    name: str
    created_at: str
    reason: str
    app: str
    documents: int
    annotations: int
    size: int  # bytes of its own files; the originals live in the shared store
    damaged: int  # originals left out because their bytes no longer matched their names


class EventOut(BaseModel):
    id: int
    at: str
    kind: str
    target: str
    detail: dict[str, Any]


# --- non-bank bills and receipts, and their senders (F14) -----------------------------------------------------------


class InvoiceLineOut(BaseModel):
    """An item of a bill or a receipt, as it prints it."""

    description: str
    amount: MoneyOut  # its total, taxes included, in the document's currency
    quantity: str | None  # a decimal number as text ("2", "1.5"); null when the document prints none


class WindowOut(BaseModel):
    """The days a document's bank row is looked for in."""

    start: date
    end: date


class BankRowOut(BaseModel):
    """The bank row that paid a bill or a receipt."""

    fingerprint: str
    day: date
    account: AccountRefOut
    amount: MoneyOut  # in TL, as the ledger counts it: money out above zero, a refund below
    description: str


class InvoiceOut(BaseModel):
    """A non-bank sender's bill or receipt and what the bank's rows say of it. None changes a total: the bank row
    that paid it is what counts."""

    key: str  # "<sha256>:<position>": the document and the bill's place in it
    kind: InvoiceKind
    status: InvoiceStatus
    seller: str
    number: str  # "" when the document prints none
    issued: date
    due: date | None  # a bill's last day to pay, when it prints one
    total: MoneyOut  # in the document's currency, taxes included; below zero for a refund
    lines: list[InvoiceLineOut]
    window: WindowOut
    document: str  # the name of the document it is read from
    sha256: str
    row: BankRowOut | None  # matched: the bank row that paid it
    reasons: list[str]  # unmatched: what may explain it


class InvoiceCountsOut(BaseModel):
    pending: int
    unmatched: int
    matched: int


class InvoicesOut(BaseModel):
    items: list[InvoiceOut]  # pending first by due date; then unmatched, then matched, newest first
    counts: InvoiceCountsOut


SenderDomain = Annotated[str, StringConstraints(max_length=253)]  # checked as settings.toml checks it


class OtherSendersIn(BaseModel):
    domains: list[SenderDomain] = Field(max_length=200)


class OtherSendersOut(BaseModel):
    """The domains whose bills and receipts are taken in beside the banks' messages (settings: mail.other_senders)."""

    domains: list[str]


# --- notifications (F13, ADR-0010) -----------------------------------------------------------------------------------


class NotificationOut(BaseModel):
    """A notification as it was sent on its channel."""

    id: int
    created_at: str
    rule: str  # the alert rule's name; a test the user asked for is "Deneme bildirimi"
    kind: str  # the event's kind (architecture §13), or "test"
    # What the event concerns (architecture §13): a document's sha256 (document.*), a row's fingerprint
    # (transaction.*, income.received, evidence.unmatched), a bill's "<sha256>:<n>" (invoice.*), a month (month.*);
    # "" for an event standing for many and for a test.
    target: str
    channel: Channel
    detail: DetailLevel
    title: str
    body: str
    status: DeliveryStatus
    attempts: int  # failed attempts
    sent_at: str
    error: str  # why the last attempt failed
    read: bool  # the interface's box: seen


class NotificationsOut(BaseModel):
    items: list[NotificationOut]  # newest first
    unread: int  # in the interface's box
    next: int | None = None  # the next page's `before`; null: this page was the last


class NotificationsReadIn(BaseModel):
    up_to: int | None = None  # the newest notification seen; null: all


class NotificationsReadOut(BaseModel):
    marked: int


class AlertConditionModel(BaseModel):
    days: int | None = Field(default=None, ge=0, le=60)  # at most so many days ahead
    amount: int | None = Field(default=None, ge=0)  # at least so many kuruş (minor units of TL)
    text: str = Field(default="", max_length=80)  # the event's title holds this text


class AlertRuleModel(BaseModel):
    """An alert rule (architecture §14); rules/alerts.yaml writes it with Turkish keys."""

    name: str = Field(min_length=1, max_length=80)
    event: EventKind
    condition: AlertConditionModel = AlertConditionModel()
    channels: list[Channel] = Field(max_length=4)  # besides the interface's box, which always gets it
    detail: DetailLevel | None = None  # null: each channel's own level
    enabled: bool = True
    quiet: bool = True  # keeps to the quiet hours; false: goes out at once even then
    # The user's own words, added to each notification the rule sends; one line ("" for none).
    note: str = Field(default="", max_length=200, pattern=r"^[^\n]*$")


class EventInfoOut(BaseModel):
    """An event a rule may watch, and the conditions it allows."""

    kind: EventKind
    label: str
    days: bool
    amount: bool
    text: bool


class AlertRulesOut(BaseModel):
    rules: list[AlertRuleModel]
    own: bool  # the user's rules/alerts.yaml; false: the rules shipped with the app
    problem: str  # the user's file could not be read: the shipped rules stand in, and this says why
    events: list[EventInfoOut]


class AlertRulesIn(BaseModel):
    rules: list[AlertRuleModel] = Field(max_length=200)


class NotifyMessageOut(BaseModel):
    title: str
    body: str


class AlertPreviewIn(BaseModel):
    rule: AlertRuleModel


class AlertPreviewOut(BaseModel):
    count: int  # how many notifications the rule would have given in the days
    days: int
    examples: list[NotifyMessageOut]  # the newest few


class ChannelStateOut(BaseModel):
    channel: Channel
    on: bool  # turned on (the interface's box always is)
    ready: bool  # can carry a notification now
    stage: ChannelStage  # what stands in its way besides being off; the interface names the next step by it
    note: str  # what it is, or what it still needs


QuietHours = Annotated[str, StringConstraints(pattern=r"^$|^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")]


class NotifySettingsOut(BaseModel):
    quiet_hours: str  # "23:00-08:00"; "" for none
    detail: dict[Channel, DetailLevel]  # desktop, telegram, email
    channels: list[ChannelStateOut]
    counts: dict[DeliveryStatus, int]
    unread: int
    telegram_documents: bool  # the documents the paired chat sends the bot are taken in (ADR-0021)


class NotifySettingsIn(BaseModel):
    quiet_hours: QuietHours
    detail: dict[Channel, DetailLevel]
    channels: list[Channel] = Field(max_length=4)  # the channels turned on


class TelegramTokenIn(BaseModel):
    token: str = Field(min_length=1, max_length=100)


class TelegramTokenOut(BaseModel):
    bot: str  # the bot's user name
    in_keyring: bool  # false: the system has no keyring, and IPLIKCI_TELEGRAM_TOKEN must carry it


class TelegramPairingOut(BaseModel):
    code: str  # sent to the bot as "/start <code>" within ten minutes
    expires: str
    bot: str
    link: str  # opens the chat with the bot, the code ready to send; "" when the bot's name is not known


class TelegramCheckOut(BaseModel):
    paired: bool


class TelegramDocumentsIn(BaseModel):
    on: bool  # take the documents the paired chat sends the bot


class NotifyTestIn(BaseModel):
    channel: Channel
