"""The notifications (ADR-0010, F13): the alert rules turned into notifications as the events come, sent on their
channels, kept back in the quiet hours or above a channel's rate and sent as one digest, tried again after a failed
attempt and never sent twice. The interface's box reads them from the database, and every one is kept as the
history.

The events are read in order from where the last run stopped; a first run starts at the newest, so the history
before it is no news. While the mailbox's history is read from the start (mail.first_read), the events go only to the
interface's box: told from a part of the history, a forecast or a missing payment may be gone once the rest has come.
A refused login (SMTP) or token (Telegram) stops its channel until the user sets it up anew:
trying again from a program may get an account locked.
"""

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from .. import egress, rulefile
from ..domain.codes import Actor, Channel, ChannelStage, DeliveryStatus, DetailLevel, EventKind
from ..domain.labels import EVENT_KIND
from ..ingest.mail.imap import clean_password
from ..notify import content, timing
from ..notify import rules as alert_rules
from ..notify.channels import Desktop, Email, Post, Sender, SendError, Telegram, bot_name
from ..notify.content import Message
from ..notify.rules import DEFAULTS, AlertRule, Condition, RulesError, Seen
from ..settings import config, secrets
from ..settings.config import SettingsError
from ..storage import audit, events, feed_state
from ..storage import notifications as stored
from ..storage.db import Database
from ..storage.events import Event
from ..storage.notifications import Notification
from . import mail
from .workspace import Workspace

log = logging.getLogger("iplikci.notify")

# What the API, the command line and the MCP server name from here: the codes and records their answers carry.
__all__ = [
    "Actor",
    "AlertRule",
    "Channel",
    "ChannelStage",
    "ChannelState",
    "Condition",
    "DeliveryStatus",
    "DetailLevel",
    "EventInfo",
    "EventKind",
    "Message",
    "Notification",
    "NotifyError",
    "Preview",
    "Rules",
    "RulesError",
    "Sent",
    "SettingsError",
    "Status",
    "TokenSet",
    "channel_states",
    "check_rules",
    "deliver",
    "event_catalog",
    "event_target",
    "history",
    "load_rules",
    "mark_read",
    "preview",
    "remove_telegram",
    "run",
    "save_rules",
    "send_test",
    "set_preferences",
    "set_telegram_token",
    "status",
    "take_events",
    "unread",
    "version",
]

CURSOR = "notify.cursor"  # the last event the notifications looked at
STOPPED = "notify.stopped"  # channel → why a refused login or token stopped it
BOT = "notify.telegram_bot"  # the bot's user name, as Telegram gave it when the token was entered
PAIRING = "notify.telegram_pairing"  # the open pairing: its code, when it ends, and whether it paired
OFFSET = "notify.telegram_offset"  # the first Telegram update not read yet
EVENTS_PER_RUN = 500
SMTP_PORT = 465
PUSH = (Channel.DESKTOP, Channel.TELEGRAM, Channel.EMAIL)  # the channels that leave the app
RULES_CHANGED = "rules.alerts_changed"
SETTINGS_CHANGED = "settings.changed"
TELEGRAM_SET, TELEGRAM_PAIRED, TELEGRAM_REMOVED = (
    "notify.telegram_set",
    "notify.telegram_paired",
    "notify.telegram_removed",
)
_TOKEN = re.compile(r"\d{5,15}:[A-Za-z0-9_-]{30,64}")  # what BotFather gives: the bot's number, a colon, the secret
_TEST = Message("Deneme bildirimi", "İplikçi Nedim bildirimleri bu kanala ulaşıyor.")
TEST_KIND = "test"  # a test the user asked for: no event behind it

type PostFor = Callable[[str], Post]  # a bot's token → its Bot API calls


class NotifyError(Exception):
    """A notification setting that cannot be done: the message says why and what to do, in Turkish."""


def _now() -> datetime:
    return datetime.now().astimezone()


def _iso(at: datetime) -> str:
    return at.astimezone(UTC).replace(microsecond=0).isoformat()


def _settings(ws: Workspace) -> config.Settings:
    return config.load(ws.layout.settings)


# --- the rules -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rules:
    rules: list[AlertRule]
    own: bool  # the user's rules/alerts.yaml; False: the rules shipped with the app
    problem: str = ""  # the user's file could not be read: the shipped rules stand in, and this says why


def load_rules(ws: Workspace) -> Rules:
    path = ws.layout.alert_rules
    if not path.exists():
        return Rules(list(DEFAULTS), own=False)
    try:
        return Rules(alert_rules.parse(path.read_text(encoding="utf-8"), path.name), own=True)
    except (RulesError, OSError, UnicodeDecodeError) as exc:
        return Rules(list(DEFAULTS), own=True, problem=str(exc))


def check_rules(ws: Workspace, found: Sequence[AlertRule]) -> str:
    """rules/alerts.yaml as it would hold the rules, nothing written: RulesError when the program would not read it
    (a name twice, a condition its event has not). The MCP server shows a change before the user approves it."""
    text = alert_rules.dump(found)
    alert_rules.parse(text, ws.layout.alert_rules.name)
    return text


def save_rules(ws: Workspace, found: Sequence[AlertRule], actor: Actor) -> Path | None:
    """Write the rules to rules/alerts.yaml, checked first (check_rules), the file before kept in the history;
    returns that copy (None for a first file)."""
    text = check_rules(ws, found)
    previous = rulefile.replace(ws.layout.alert_rules, text, ws.layout.rules_history)
    with ws.db() as db:
        audit.record(db, actor, RULES_CHANGED, ws.layout.alert_rules.name, rules=len(found))
    return previous


@dataclass(frozen=True)
class EventInfo:
    """An event a rule may watch, and the conditions it allows."""

    kind: EventKind
    label: str
    days: bool
    amount: bool
    text: bool


def event_catalog() -> list[EventInfo]:
    found: list[EventInfo] = []
    for kind in EventKind:
        can = alert_rules.applicable(kind)
        found.append(EventInfo(kind, EVENT_KIND[kind], can.days, can.amount, can.text))
    return found


@dataclass(frozen=True)
class Preview:
    count: int  # the notifications the rule would have given in the days
    days: int
    examples: list[Message]  # the newest few, as the interface's box shows them


def preview(ws: Workspace, rule: AlertRule, days: int = 30, at: datetime | None = None) -> Preview:
    """How often the rule would have spoken over the last days, off or on, with the newest notifications."""
    since = _iso((at or _now()) - timedelta(days=days))
    with ws.db() as db:
        found = events.since_time(db, since)
    rule = replace(rule, enabled=True)
    keys: set[tuple[str, str]] = set()
    examples: list[Message] = []
    for event_id, e in found:
        key = (e.kind, _key(event_id, e))
        if key not in keys and alert_rules.matches(rule, Seen(e.kind, e.target, e.detail)):
            keys.add(key)
            examples.append(content.render(e.kind, e.target, e.detail, DetailLevel.FULL))
    return Preview(len(keys), days, examples[::-1][:5])


_BULK, _TESTED = "olay-", "deneme-"  # the keys of a notification whose event names no target, and of a test


def _key(event_id: int, e: Event) -> str:
    """What a notification is known by beside its rule and channel: the event's target, or the event itself when it
    names none (one standing for many)."""
    return e.target or f"{_BULK}{event_id}"


def event_target(n: Notification) -> str:
    """What the notification's event concerns (a document, a row, a bill, a month); "" when it names nothing."""
    return "" if n.key.startswith((_BULK, _TESTED)) else n.key


# --- the channels --------------------------------------------------------------------------------------


def stopped_channels(db: Database) -> dict[str, str]:
    """The channels a refused login or token stopped, each with why."""
    found = feed_state.load(db, STOPPED)
    return {str(k): str(v) for k, v in cast(dict[str, Any], found).items()} if isinstance(found, dict) else {}


def stop_channel(db: Database, channel: Channel, reason: str) -> None:
    """A refused login or token stops the channel until the user sets it up anew or turns it on again."""
    stopped = stopped_channels(db)
    if stopped.get(channel) != reason:
        feed_state.save(db, STOPPED, stopped | {channel.value: reason})
    log.warning("the %s channel stopped: a refused login or token", channel)


def resume_channel(db: Database, channel: Channel) -> None:
    stopped = stopped_channels(db)
    if channel in stopped:
        feed_state.save(db, STOPPED, {k: v for k, v in stopped.items() if k != channel})


def telegram_token() -> str:
    """The bot's token from the keyring; "" when none is kept or the keyring cannot be read."""
    try:
        return secrets.load(secrets.TELEGRAM_BOT) or ""
    except secrets.SecretError:
        return ""


def bot_calls(settings: config.Settings, timeout: float = 30.0) -> PostFor:
    """The Bot API calls of a bot, by its token. timeout: how long a call may take; a read that waits for the bot's
    messages takes longer than its wait."""

    def calls(token: str) -> Post:
        def post(method: str, form: Mapping[str, str]) -> tuple[int, bytes]:
            return egress.https_post(egress.TELEGRAM, f"/bot{token}/{method}", form, settings, timeout)

        return post

    return calls


@dataclass(frozen=True)
class ChannelState:
    channel: Channel
    on: bool  # turned on in the settings (the interface's box always is)
    stage: ChannelStage  # what stands in its way besides being off: READY for nothing
    note: str  # what it is, or what it still needs (Turkish)

    @property
    def ready(self) -> bool:
        """It can carry a notification now."""
        return self.on and self.stage is ChannelStage.READY


def _email_note(ws: Workspace, db: Database, settings: config.Settings) -> str:
    """Why the e-mail channel cannot send; "" when it can."""
    if settings.mail.connector != mail.IMAP:
        return (
            "E-posta kanalı, e-postası uygulama şifresiyle (IMAP) bağlı bir hesap ister. Bu hesap tarayıcı eklentisiyle "
            "bağlı (Gelişmiş Koruma'da uygulama şifresi yok); Telegram ve masaüstü kullanılabilir."
        )
    if not settings.mail.address:
        return "Önce e-posta hesabını uygulama şifresiyle kurun."
    try:
        mail.load_password(settings.mail.address)
    except mail.MailError:
        return "Uygulama şifresi kayıtlı değil; e-posta kurulumunu yenileyin."
    if mail.status(ws)["stopped"]:
        return "E-posta girişi reddedildi; e-posta kurulumunu yenileyin."
    return ""


def _telegram_state(db: Database, settings: config.Settings, on: bool, stopped: Mapping[str, str]) -> ChannelState:
    """The keyring is read only for a paired bot: an installation that never set Telegram up never touches it."""
    bot = feed_state.load(db, BOT)  # kept when a token was entered
    name = bot if isinstance(bot, str) else ""
    chat = settings.notify.telegram_chat
    token = telegram_token() if chat and bot is not None else ""
    if Channel.TELEGRAM in stopped:
        return ChannelState(Channel.TELEGRAM, on, ChannelStage.STOPPED, f"Durdu: {stopped[Channel.TELEGRAM]}")
    if bot is None:
        note = "Bot belirteci girilmedi: BotFather'da bir bot oluşturup belirtecini girin."
        return ChannelState(Channel.TELEGRAM, on, ChannelStage.NO_BOT, note)
    if not chat:
        note = "Botla sohbet eşleşmedi: eşleştirme kodunu bota gönderin."
        return ChannelState(Channel.TELEGRAM, on, ChannelStage.NOT_PAIRED, note)
    if not token:
        note = "Bot belirteci anahtar zincirinde bulunamadı; yeniden girin."
        return ChannelState(Channel.TELEGRAM, on, ChannelStage.TOKEN_LOST, note)
    return ChannelState(Channel.TELEGRAM, on, ChannelStage.READY, f"@{name} botuyla eşleşti." if name else "Eşleşti.")


def _desktop_state(on: bool, stopped: Mapping[str, str]) -> ChannelState:
    if Channel.DESKTOP in stopped:
        return ChannelState(Channel.DESKTOP, on, ChannelStage.STOPPED, f"Durdu: {stopped[Channel.DESKTOP]}")
    if not Desktop().available:
        return ChannelState(Channel.DESKTOP, on, ChannelStage.UNAVAILABLE, "Bu sistemde masaüstü bildirimi yok.")
    return ChannelState(Channel.DESKTOP, on, ChannelStage.READY, "Bu bilgisayarın bildirim merkezi.")


def _email_state(
    ws: Workspace, db: Database, settings: config.Settings, stopped: Mapping[str, str], full: bool
) -> ChannelState:
    on = Channel.EMAIL in settings.notify.channels
    if Channel.EMAIL in stopped:
        return ChannelState(Channel.EMAIL, on, ChannelStage.STOPPED, f"Durdu: {stopped[Channel.EMAIL]}")
    if not (on or full):
        return ChannelState(Channel.EMAIL, on, ChannelStage.READY, "Kapalı.")  # not looked at: the keyring rests
    reason = _email_note(ws, db, settings)
    if reason:
        return ChannelState(Channel.EMAIL, on, ChannelStage.UNAVAILABLE, reason)
    return ChannelState(Channel.EMAIL, on, ChannelStage.READY, "Kendi adresinize, uygulama şifresiyle gönderilir.")


def channel_states(ws: Workspace, db: Database, settings: config.Settings, full: bool = False) -> list[ChannelState]:
    """Every channel, whether it is on and what stands in its way, with a word on it. full: the e-mail channel is
    looked at also while it is off (it reads the keyring)."""
    on = set(settings.notify.channels)
    stopped = stopped_channels(db)
    return [
        ChannelState(Channel.IN_APP, True, ChannelStage.READY, "Arayüzdeki bildirim kutusu; her zaman açık."),
        _desktop_state(Channel.DESKTOP in on, stopped),
        _telegram_state(db, settings, Channel.TELEGRAM in on, stopped),
        _email_state(ws, db, settings, stopped, full),
    ]


def open_senders(ws: Workspace, db: Database, settings: config.Settings, every: bool = False) -> dict[Channel, Sender]:
    """The channels that can carry a notification now, each with what sends on it; every: also those turned off
    (a test the user asks for)."""
    found: dict[Channel, Sender] = {}
    for state in channel_states(ws, db, settings):
        if state.channel is Channel.IN_APP or not (state.ready or (every and _could(state, ws, db, settings))):
            continue
        if state.channel is Channel.DESKTOP:
            found[Channel.DESKTOP] = Desktop()
        elif state.channel is Channel.TELEGRAM:
            post = bot_calls(settings)(telegram_token())
            found[Channel.TELEGRAM] = Telegram(post, settings.notify.telegram_chat)
        else:
            found[Channel.EMAIL] = _email(ws, settings)
    return found


def _could(state: ChannelState, ws: Workspace, db: Database, settings: config.Settings) -> bool:
    """Whether a channel turned off would carry a notification if it were on."""
    on = replace(settings, notify=replace(settings.notify, channels=(*settings.notify.channels, state.channel.value)))
    return next(s.ready for s in channel_states(ws, db, on) if s.channel is state.channel)


def _email(ws: Workspace, settings: config.Settings) -> Email:
    account = mail.account(ws)
    if account is None:
        raise NotifyError("Önce e-posta hesabını uygulama şifresiyle kurun.")
    try:
        password = clean_password(account, mail.load_password(account.address))
    except mail.MailError as exc:
        raise NotifyError(f"Uygulama şifresi okunamadı: {exc}") from exc
    host = settings.mail.smtp_host
    return Email(lambda: egress.smtp(host, SMTP_PORT, settings), account.address, password)


# --- events into notifications -------------------------------------------------------------------------


def take_events(ws: Workspace, at: datetime | None = None) -> int:
    """Turn the events since the last run into notifications, one per rule, event key and channel; how many were
    made. The interface's box gets every one at once; the other channels' wait to be sent, or for the digest in the
    quiet hours."""
    at = at or _now()
    settings = _settings(ws)
    with ws.db() as db:
        last = feed_state.load(db, CURSOR)
        if not isinstance(last, int):  # the first run: what happened before it is no news
            feed_state.save(db, CURSOR, events.newest(db))
            return 0
        found = events.since(db, last, EVENTS_PER_RUN)
        if not found:
            return 0
        rules = load_rules(ws).rules
        ready = (
            []
            if mail.first_read(db, settings)
            else [s.channel for s in channel_states(ws, db, settings) if s.ready and s.channel is not Channel.IN_APP]
        )
        quiet = timing.quiet(settings.notify.quiet_hours, at)
        made = 0
        with db.transaction():
            for event_id, e in found:
                made += _notify(db, event_id, e, rules, ready, settings, quiet, _iso(at))
            feed_state.save(db, CURSOR, found[-1][0])
    return made


def _level(rule: AlertRule, channel: Channel, settings: config.Settings) -> DetailLevel:
    if channel is Channel.IN_APP:
        return DetailLevel.FULL
    return rule.detail or DetailLevel(settings.notify.detail.get(channel.value, DetailLevel.SUMMARY.value))


def _notify(
    db: Database,
    event_id: int,
    e: Event,
    rules: Sequence[AlertRule],
    ready: Sequence[Channel],
    settings: config.Settings,
    quiet: bool,
    at: str,
) -> int:
    made = 0
    for rule in rules:
        if not alert_rules.matches(rule, Seen(e.kind, e.target, e.detail)):
            continue
        for channel in (Channel.IN_APP, *(c for c in rule.channels if c in ready)):
            level = _level(rule, channel, settings)
            message = content.render(e.kind, e.target, e.detail, level)
            body = f"{message.body}\n{rule.note}" if rule.note else message.body  # the user's own words, last
            inside = channel is Channel.IN_APP
            n = Notification(
                id=0,
                created_at=at,
                rule=rule.name,
                event_id=event_id,
                kind=e.kind,
                key=_key(event_id, e),
                channel=channel,
                detail=level,
                title=message.title,
                body=body,
                status=DeliveryStatus.SENT
                if inside
                else DeliveryStatus.HELD
                if quiet and rule.quiet
                else DeliveryStatus.PENDING,
                urgent=not rule.quiet,
                sent_at=at if inside else "",
            )
            if stored.add(db, n) is not None:
                made += 1
    return made


# --- sending -------------------------------------------------------------------------------------------


@dataclass
class Sent:
    sent: int = 0
    failed: int = 0  # attempts that failed: tried again later, or given up
    held: int = 0  # kept back for the digest
    digests: int = 0


def deliver(ws: Workspace, at: datetime | None = None, senders: Mapping[Channel, Sender] | None = None) -> Sent:
    """Send what is due on each channel; keep back what the quiet hours or the channel's rate do not let out, and
    send what was kept back as one digest when they do."""
    at = at or _now()
    settings = _settings(ws)
    out = Sent()
    with ws.db() as db:
        due = stored.due(db, _iso(at))
        held = {c: stored.held(db, c) for c in PUSH}
        if not due and not any(held.values()):
            return out
        carriers = dict(senders) if senders is not None else open_senders(ws, db, settings)
        quiet = timing.quiet(settings.notify.quiet_hours, at)
        for n in due:
            _send(db, n, carriers, quiet, at, out)
        if not quiet:
            for channel in PUSH:
                out.digests += _digest(db, channel, carriers, at)
    return out


def _over_rate(db: Database, channel: Channel, at: datetime) -> bool:
    return stored.sent_since(db, channel, _iso(at - timing.RATE_WINDOW)) >= timing.RATE[channel]


def _send(db: Database, n: Notification, carriers: dict[Channel, Sender], quiet: bool, at: datetime, out: Sent) -> None:
    channel = Channel(n.channel)
    sender = carriers.get(channel)
    if sender is None:
        stored.give_up(db, [n.id], "Kanal kapatıldı ya da kurulumu eksik; bildirim gönderilmedi.")
        out.failed += 1
        return
    if (quiet and not n.urgent) or _over_rate(db, channel, at):
        stored.hold(db, n.id)
        out.held += 1
        return
    try:
        sender.send(Message(n.title, n.body))
    except SendError as exc:
        out.failed += 1
        if exc.refused:
            stored.fail(db, n.id, str(exc))
            stop_channel(db, channel, str(exc))
            del carriers[channel]
        elif n.attempts + 1 >= timing.MAX_ATTEMPTS:
            stored.fail(db, n.id, str(exc))
            log.warning("notification %d on %s given up after %d attempts", n.id, channel, n.attempts + 1)
        else:
            stored.retry(db, n.id, str(exc), _iso(at + timing.backoff(n.attempts + 1)))
        return
    stored.sent(db, [n.id], _iso(at))
    out.sent += 1


def _digest(db: Database, channel: Channel, carriers: dict[Channel, Sender], at: datetime) -> int:
    """Send what was kept back on the channel as one message, at most once per DIGEST_EVERY; whether it went."""
    waiting = stored.held(db, channel)
    if not waiting:
        return 0
    sender = carriers.get(channel)
    if sender is None:
        stored.give_up(db, [n.id for n in waiting], "Kanal kapatıldı ya da kurulumu eksik; özet gönderilmedi.")
        return 0
    last = stored.last_digest(db, channel)
    if (last and last > _iso(at - timing.DIGEST_EVERY)) or any(n.next_at > _iso(at) for n in waiting):
        return 0
    ids = [n.id for n in waiting]
    try:
        sender.send(content.digest([Message(n.title, n.body) for n in waiting]))
    except SendError as exc:
        attempts = max(n.attempts for n in waiting) + 1
        if exc.refused or attempts >= timing.MAX_ATTEMPTS:
            stored.give_up(db, ids, str(exc))
            if exc.refused:
                stop_channel(db, channel, str(exc))
                del carriers[channel]
        else:
            stored.held_failed(db, ids, str(exc), _iso(at + timing.backoff(attempts)))
        return 0
    stored.sent(db, ids, _iso(at), DeliveryStatus.DIGESTED)
    return 1


def run(ws: Workspace, at: datetime | None = None) -> Sent:
    """The background job: the new events into notifications, then what is due sent."""
    at = at or _now()
    take_events(ws, at)
    return deliver(ws, at)


# --- what the interface shows --------------------------------------------------------------------------


@dataclass(frozen=True)
class Status:
    quiet_hours: str
    detail: dict[Channel, DetailLevel]
    channels: list[ChannelState]
    counts: dict[DeliveryStatus, int]
    unread: int  # in the interface's box
    rules: Rules
    telegram_documents: bool  # the documents the paired chat sends the bot are taken in (ADR-0021)


def status(ws: Workspace) -> Status:
    settings = _settings(ws)
    with ws.db() as db:
        states = channel_states(ws, db, settings, full=True)
        counts = stored.counts(db)
        unread = stored.unread(db, Channel.IN_APP)
    detail = {c: DetailLevel(settings.notify.detail.get(c.value, DetailLevel.SUMMARY.value)) for c in PUSH}
    return Status(
        settings.notify.quiet_hours,
        detail,
        states,
        {s: counts.get(s.value, 0) for s in DeliveryStatus},
        unread,
        load_rules(ws),
        settings.notify.telegram_documents,
    )


def history(ws: Workspace, before: int = 0, limit: int = 50, channel: Channel | None = None) -> list[Notification]:
    """The notifications, newest first: of one channel, or of all."""
    with ws.db() as db:
        return stored.page(db, before, limit, channel.value if channel else "")


def unread(ws: Workspace) -> int:
    """The notifications in the interface's box not seen yet."""
    with ws.db() as db:
        return stored.unread(db, Channel.IN_APP)


def version(ws: Workspace) -> str:
    """Changes whenever a notification is made or settles; the event stream watches it."""
    with ws.db() as db:
        return stored.version(db)


def mark_read(ws: Workspace, up_to: int | None = None) -> int:
    """The interface's box seen, up to a notification or all; how many were unread."""
    with ws.db() as db:
        return stored.mark_read(db, Channel.IN_APP, _iso(_now()), up_to)


def set_preferences(
    ws: Workspace, quiet_hours: str, detail: Mapping[Channel, DetailLevel], channels: Sequence[Channel]
) -> config.Settings:
    """The quiet hours, each channel's level of detail and the channels turned on. A stopped channel the user turns
    on is tried again. Nothing of them goes to the log; the audit log names the setting only."""
    values: dict[str, Any] = {
        "quiet_hours": quiet_hours,
        "detail": {c.value: level.value for c, level in detail.items() if c in PUSH},
        "channels": [c.value for c in PUSH if c in channels],
    }
    saved = config.update(ws.layout.settings, "notify", values)
    with ws.db() as db:
        for channel in channels:
            resume_channel(db, channel)
        audit.record(db, Actor.USER, SETTINGS_CHANGED, "notify", channels=len(values["channels"]))
    return saved


def _tested(channel: Channel, detail: DetailLevel, error: str = "") -> Notification:
    """A test as the history keeps it: sent, or failed with its error."""
    at = _iso(_now())
    return Notification(
        id=0,
        created_at=at,
        rule=_TEST.title,
        event_id=0,
        kind=TEST_KIND,
        key=f"{_TESTED}{at}",
        channel=channel,
        detail=detail,
        title=_TEST.title,
        body=_TEST.body,
        status=DeliveryStatus.FAILED if error else DeliveryStatus.SENT,
        attempts=1 if error else 0,
        sent_at="" if error else at,
        error=error,
    )


def send_test(ws: Workspace, channel: Channel, senders: Mapping[Channel, Sender] | None = None) -> None:
    """A test notification now, on a channel turned on or not: the user asked for it, so a channel a refused login
    stopped is tried once again. The history keeps every attempt; NotifyError says why it did not go."""
    settings = _settings(ws)
    with ws.db() as db:
        if channel is Channel.IN_APP:
            stored.add(db, _tested(channel, DetailLevel.FULL))
            return
        resume_channel(db, channel)
        carriers = dict(senders) if senders is not None else open_senders(ws, db, settings, every=True)
        sender = carriers.get(channel)
        if sender is None:  # nothing was tried: the channel's note says what it still needs
            note = next(s.note for s in channel_states(ws, db, settings, full=True) if s.channel is channel)
            raise NotifyError(note)
        detail = DetailLevel(settings.notify.detail.get(channel.value, DetailLevel.SUMMARY.value))
        try:
            sender.send(_TEST)
        except SendError as exc:
            if exc.refused:
                stop_channel(db, channel, str(exc))
            stored.add(db, _tested(channel, detail, str(exc)))
            raise NotifyError(str(exc)) from None
        stored.add(db, _tested(channel, detail))


# --- Telegram ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenSet:
    bot: str  # the bot's user name
    in_keyring: bool  # False: the system has no keyring, and IPLIKCI_TELEGRAM_TOKEN must carry it


def set_telegram_token(ws: Workspace, token: str, actor: Actor, post_for: PostFor | None = None) -> TokenSet:
    """Check a bot's token with Telegram and keep it in the keyring; the chat paired with another bot is forgotten.
    The token never reaches a file, an argument or the log."""
    token = token.strip()
    if not _TOKEN.fullmatch(token):
        raise NotifyError("Bu bir Telegram bot belirteci değil: BotFather'ın verdiği '123456789:AA…' biçiminde olmalı.")
    settings = _settings(ws)
    try:
        name = bot_name((post_for or bot_calls(settings))(token))
    except SendError as exc:
        raise NotifyError(f"Belirteç denenemedi: {exc}") from None
    try:
        kept = secrets.store(secrets.TELEGRAM_BOT, token)
    except secrets.SecretError as exc:
        raise NotifyError(str(exc)) from exc
    with ws.db() as db:
        if feed_state.load(db, BOT) != name and settings.notify.telegram_chat:
            config.update(ws.layout.settings, "notify", {"telegram_chat": 0})
        feed_state.save(db, BOT, name)
        feed_state.save(db, OFFSET, 0)
        resume_channel(db, Channel.TELEGRAM)
        audit.record(db, actor, TELEGRAM_SET, "telegram")
    return TokenSet(name, kept)


def remove_telegram(ws: Workspace, actor: Actor) -> None:
    """Forget the bot's token and the paired chat."""
    secrets.delete(secrets.TELEGRAM_BOT)
    config.update(ws.layout.settings, "notify", {"telegram_chat": 0})
    with ws.db() as db:
        for name in (BOT, PAIRING, OFFSET):
            feed_state.save(db, name, None)
        resume_channel(db, Channel.TELEGRAM)
        audit.record(db, actor, TELEGRAM_REMOVED, "telegram")
