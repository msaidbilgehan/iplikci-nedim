"""The notifications (F13, ADR-0010): the interface's box and the history, the alert rules with their preview, the
channels' settings, the Telegram bot and its pairing, and a test on a channel. The browser changes them only from
the service's own pages (the guard); the API token reads them. A bot's token goes to the keyring, never to the log
or back to the browser."""

from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request, Response

from ...app import notify
from ...app.notify import Actor, AlertRule, Channel, Condition, Notification, NotifyError, RulesError, SettingsError
from ..context import context_of
from ..guard import Principal
from ..models import (
    AlertConditionModel,
    AlertPreviewIn,
    AlertPreviewOut,
    AlertRuleModel,
    AlertRulesIn,
    AlertRulesOut,
    ChannelStateOut,
    EventInfoOut,
    NotificationOut,
    NotificationsOut,
    NotificationsReadIn,
    NotificationsReadOut,
    NotifyMessageOut,
    NotifySettingsIn,
    NotifySettingsOut,
    NotifyTestIn,
    TelegramCheckOut,
    TelegramPairingOut,
    TelegramTokenIn,
    TelegramTokenOut,
)
from ..problems import Problem
from .deps import only

router = APIRouter()

READ = [Depends(only(Principal.BROWSER, Principal.CLIENT))]
WRITE = [Depends(only(Principal.BROWSER))]
_KURUS = Decimal(100)


def _notification(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        created_at=n.created_at,
        rule=n.rule,
        kind=n.kind,
        target=notify.event_target(n),
        channel=Channel(n.channel),
        detail=notify.DetailLevel(n.detail),
        title=n.title,
        body=n.body,
        status=notify.DeliveryStatus(n.status),
        attempts=n.attempts,
        sent_at=n.sent_at,
        error=n.error,
        read=bool(n.read_at),
    )


def _rule_out(rule: AlertRule) -> AlertRuleModel:
    c = rule.condition
    return AlertRuleModel(
        name=rule.name,
        event=rule.event,
        condition=AlertConditionModel(
            days=c.days, amount=None if c.amount is None else int(c.amount * _KURUS), text=c.text
        ),
        channels=list(rule.channels),
        detail=rule.detail,
        enabled=rule.enabled,
        quiet=rule.quiet,
    )


def _rule_in(rule: AlertRuleModel) -> AlertRule:
    c = rule.condition
    return AlertRule(
        rule.name.strip(),
        rule.event,
        Condition(c.days, None if c.amount is None else Decimal(c.amount) / _KURUS, c.text.strip()),
        tuple(dict.fromkeys(ch for ch in rule.channels if ch is not Channel.IN_APP)),
        rule.detail,
        rule.enabled,
        rule.quiet,
    )


def _rules_out(found: notify.Rules) -> AlertRulesOut:
    return AlertRulesOut(
        rules=[_rule_out(r) for r in found.rules],
        own=found.own,
        problem=found.problem,
        events=[
            EventInfoOut(kind=e.kind, label=e.label, days=e.days, amount=e.amount, text=e.text)
            for e in notify.event_catalog()
        ],
    )


def _settings_out(request: Request) -> NotifySettingsOut:
    found = notify.status(context_of(request).ws)
    return NotifySettingsOut(
        quiet_hours=found.quiet_hours,
        detail=dict(found.detail),
        channels=[ChannelStateOut(channel=s.channel, on=s.on, ready=s.ready, note=s.note) for s in found.channels],
        counts=dict(found.counts),
        unread=found.unread,
    )


@router.get("/api/notifications", dependencies=READ)
def notifications(
    request: Request,
    before: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    channel: Channel | None = None,
) -> NotificationsOut:
    """The notifications, newest first: of one channel (the interface's box is in_app), or of all."""
    ws = context_of(request).ws
    items = notify.history(ws, before, limit, channel)
    return NotificationsOut(items=[_notification(n) for n in items], unread=notify.status(ws).unread)


@router.post("/api/notifications/read", dependencies=WRITE)
def notifications_read(request: Request, body: NotificationsReadIn) -> NotificationsReadOut:
    """The interface's box seen, up to a notification or all."""
    return NotificationsReadOut(marked=notify.mark_read(context_of(request).ws, body.up_to))


@router.get("/api/rules/alerts", dependencies=READ)
def alert_rules(request: Request) -> AlertRulesOut:
    """The alert rules, the user's or the shipped ones, and the events a rule may watch."""
    return _rules_out(notify.load_rules(context_of(request).ws))


@router.put("/api/rules/alerts", dependencies=WRITE)
def alert_rules_set(request: Request, body: AlertRulesIn) -> AlertRulesOut:
    """Replace the alert rules; checked first (a name twice, a condition its event has not), the file before kept in
    the history."""
    ws = context_of(request).ws
    try:
        notify.save_rules(ws, [_rule_in(r) for r in body.rules], Actor.USER)
    except RulesError as exc:
        raise Problem(400, "rules_invalid", str(exc)) from exc
    return _rules_out(notify.load_rules(ws))


@router.post("/api/rules/alerts/preview", dependencies=READ)
def alert_rule_preview(request: Request, body: AlertPreviewIn) -> AlertPreviewOut:
    """How often a rule would have spoken in the last thirty days, with its newest notifications."""
    found = notify.preview(context_of(request).ws, _rule_in(body.rule))
    examples = [NotifyMessageOut(title=m.title, body=m.body) for m in found.examples]
    return AlertPreviewOut(count=found.count, days=found.days, examples=examples)


@router.get("/api/notify/settings", dependencies=READ)
def notify_settings(request: Request) -> NotifySettingsOut:
    """The quiet hours, each channel's level of detail, and whether each channel is on and can carry a
    notification, with what it still needs."""
    return _settings_out(request)


@router.put("/api/notify/settings", dependencies=WRITE)
def notify_settings_set(request: Request, body: NotifySettingsIn) -> NotifySettingsOut:
    try:
        notify.set_preferences(context_of(request).ws, body.quiet_hours, body.detail, body.channels)
    except SettingsError as exc:
        raise Problem(409, "settings_invalid", str(exc)) from exc
    return _settings_out(request)


def _refused(exc: NotifyError) -> Problem:
    return Problem(400, "notify_refused", str(exc))


@router.post("/api/notify/telegram/token", dependencies=WRITE)
def telegram_token(request: Request, body: TelegramTokenIn) -> TelegramTokenOut:
    """Check the bot's token with Telegram and keep it in the keyring."""
    try:
        found = notify.set_telegram_token(context_of(request).ws, body.token, Actor.USER)
    except NotifyError as exc:
        raise _refused(exc) from exc
    return TelegramTokenOut(bot=found.bot, in_keyring=found.in_keyring)


@router.post("/api/notify/telegram/pairing", dependencies=WRITE)
def telegram_pairing(request: Request) -> TelegramPairingOut:
    """A code to send the bot as "/start <code>" within ten minutes."""
    try:
        found = notify.start_pairing(context_of(request).ws)
    except NotifyError as exc:
        raise _refused(exc) from exc
    return TelegramPairingOut(code=found.code, expires=found.expires, bot=found.bot, link=found.link)


@router.post("/api/notify/telegram/check", dependencies=WRITE)
def telegram_check(request: Request) -> TelegramCheckOut:
    """Whether the code came: the bot's new messages are read once."""
    try:
        return TelegramCheckOut(paired=notify.check_pairing(context_of(request).ws))
    except NotifyError as exc:
        raise _refused(exc) from exc


@router.delete("/api/notify/telegram", status_code=204, dependencies=WRITE)
def telegram_remove(request: Request) -> Response:
    """Forget the bot's token and the paired chat."""
    notify.remove_telegram(context_of(request).ws, Actor.USER)
    return Response(status_code=204)


@router.post("/api/notify/test", status_code=204, dependencies=WRITE)
def notify_test(request: Request, body: NotifyTestIn) -> Response:
    """A test notification now on a channel; the reason when it does not go."""
    try:
        notify.send_test(context_of(request).ws, body.channel)
    except NotifyError as exc:
        raise _refused(exc) from exc
    return Response(status_code=204)
