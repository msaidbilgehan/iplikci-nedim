"""The API's answers (pydantic at the boundary). Amounts, when they come, are minor units with their currency."""

from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints

from ..app.invoices import InvoiceKind, InvoiceStatus
from ..app.notify import Channel, DeliveryStatus, DetailLevel, EventKind


class LoginLink(BaseModel):
    url: str


class MoneyOut(BaseModel):
    """An amount in its currency's smallest unit: {"minor": 123456, "currency": "TRY"} is 1.234,56 TL. The interface
    formats it (architecture §16)."""

    minor: int
    currency: str


class AccountRefOut(BaseModel):
    id: str
    label: str


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


class SystemOut(BaseModel):
    service: ServiceOut
    documents: dict[str, int]
    readers: list[ReaderHealthOut]
    disk: DiskOut
    queue: QueueOut
    mail: MailOut
    backup: BackupHealthOut


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
    note: str  # what it is, or what it still needs


QuietHours = Annotated[str, StringConstraints(pattern=r"^$|^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")]


class NotifySettingsOut(BaseModel):
    quiet_hours: str  # "23:00-08:00"; "" for none
    detail: dict[Channel, DetailLevel]  # desktop, telegram, email
    channels: list[ChannelStateOut]
    counts: dict[DeliveryStatus, int]
    unread: int


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


class NotifyTestIn(BaseModel):
    channel: Channel
