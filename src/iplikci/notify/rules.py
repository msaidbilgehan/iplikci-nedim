"""The alert rules (architecture §14): rules/alerts.yaml in the data folder, or the rules shipped with the app until
the user changes one. The file is the user's, so its keys and values are Turkish:

    - ad: Son ödemeye 3 gün          # the name the interface shows; one rule per name
      olay: payment.due_soon         # the event it watches (architecture §13)
      kosul: {gun: 3}                # gun: at most so many days ahead; tutar: at least so many TL; metin: in the title
      kanallar: [masaustu, telegram] # besides the interface's box, which always gets it: masaustu, telegram, eposta
      ayrinti: ozet                  # tam, ozet or asgari; left out, each channel's own level from the settings
      sessiz_saat: false             # goes out at once in the quiet hours too; left out, it keeps to them
      acik: false                    # left out, the rule is on

A rule speaks once of an event's key (its kind and target) on each channel; a later event with the same key finds
the notification there (app.notify). A file the program would not read is refused whole, with the reason.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import yaml

from ..domain.codes import Channel, DetailLevel, EventKind
from ..domain.text import fold

CHANNEL_NAMES: dict[str, Channel] = {"masaustu": Channel.DESKTOP, "telegram": Channel.TELEGRAM, "eposta": Channel.EMAIL}
DETAIL_NAMES: dict[str, DetailLevel] = {
    "tam": DetailLevel.FULL,
    "ozet": DetailLevel.SUMMARY,
    "asgari": DetailLevel.MINIMAL,
}
_KEYS = ("ad", "olay", "kosul", "kanallar", "ayrinti", "sessiz_saat", "acik")
_NAME_LIMIT = 80
MAX_DAYS = 60  # the calendar's horizon (F09): a due date further away is no event yet

E = EventKind
# The events whose detail says how many days ahead it is (gun), which amount it is about (tutar) and what it is
# about (metin), as the feed writes them (architecture §13).
DAYS_EVENTS = frozenset({E.PAYMENT_DUE_SOON, E.BALANCE_FORECAST_NEGATIVE})
AMOUNT_FIELDS: dict[EventKind, str] = {
    E.PAYMENT_DUE_SOON: "amount",
    E.BALANCE_FORECAST_NEGATIVE: "balance",
    E.EXPECTED_PAYMENT_MISSING: "amount",
    E.INCOME_RECEIVED: "amount",
    E.INCOME_LATE: "amount",
    E.SUBSCRIPTION_PRICE_CHANGED: "new",
    E.SUBSCRIPTION_PAID_AFTER_CANCEL: "amount",
    E.TRANSACTION_LARGE: "amount",
    E.EVIDENCE_UNMATCHED: "amount",
}
TITLE_EVENTS = frozenset(AMOUNT_FIELDS)
_DEFAULT_CHANNELS = (Channel.DESKTOP, Channel.TELEGRAM)


class RulesError(ValueError):
    """The rules are not what the program reads; the message names the rule and the fix, in Turkish."""


@dataclass(frozen=True, slots=True)
class Condition:
    days: int | None = None  # gun: the event is at most this many days ahead
    amount: Decimal | None = None  # tutar: the event's amount is at least this many TL
    text: str = ""  # metin: the event's title holds this text

    @property
    def empty(self) -> bool:
        return self.days is None and self.amount is None and not self.text


@dataclass(frozen=True, slots=True)
class AlertRule:
    name: str
    event: EventKind
    condition: Condition = Condition()
    channels: tuple[Channel, ...] = _DEFAULT_CHANNELS  # besides the interface's box, which always gets it
    detail: DetailLevel | None = None  # None: each channel's own level from the settings
    enabled: bool = True
    quiet: bool = True  # keeps to the quiet hours; False: goes out at once even then

    @property
    def key(self) -> str:
        """What tells the rule from the others, whatever its letters' case: the notifications name it so."""
        return fold(self.name)


def _rule(name: str, event: EventKind, *, days: int | None = None) -> AlertRule:
    return AlertRule(name, event, Condition(days=days))


# The rules every installation starts with, all on (architecture §14; F01 for the extension's silence and alarm).
DEFAULTS: tuple[AlertRule, ...] = (
    _rule("Son ödemeye 3 gün", E.PAYMENT_DUE_SOON, days=3),
    _rule("Hesap eksiye düşecek", E.BALANCE_FORECAST_NEGATIVE),
    _rule("Büyük harcama", E.TRANSACTION_LARGE),
    _rule("Düzenli ödeme tutarı değişti", E.SUBSCRIPTION_PRICE_CHANGED),
    _rule("İptalden sonra ödeme", E.SUBSCRIPTION_PAID_AFTER_CANCEL),
    _rule("Beklenen ödeme gelmedi", E.EXPECTED_PAYMENT_MISSING),
    _rule("Maaş gecikti", E.INCOME_LATE),
    _rule("Ay bitti", E.MONTH_ENDED),
    _rule("Ay kapandı", E.MONTH_CLOSED),
    _rule("Ay kontrol gerektiriyor", E.MONTH_NEEDS_CHECK),
    _rule("Ekstrede görünmeyen dekont", E.EVIDENCE_UNMATCHED),
    _rule("E-posta girişi reddedildi", E.MAIL_AUTH_FAILED),
    _rule("Okuyucu biçim alarmı", E.PARSER_FORMAT_ALARM),
    _rule("Tarayıcı eklentisi görünmüyor", E.MAIL_BRIDGE_SILENT),
    _rule("Eklenti Gmail sayfasını tanımadı", E.MAIL_BRIDGE_ALARM),
    _rule("Yedek alınamadı", E.BACKUP_FAILED),
)

HEADER = """\
# Bildirim kuralları (İplikçi Nedim). Her kural bir olayı izler; olay olunca bildirim, uygulamadaki bildirim
# kutusuna ve seçilen kanallara gider. Bir olay için her kanala tek bildirim gider.
#
#   ad        kuralın adı (her kuralın adı ayrı)
#   olay      izlenen olay, ör. payment.due_soon (liste: Bildirimler ekranı)
#   kosul     isteğe bağlı: gun (en çok kaç gün kala), tutar (en az kaç TL), metin (başlığında geçen yazı)
#   kanallar  masaustu, telegram, eposta; boş liste: yalnızca uygulamadaki kutu
#   ayrinti   tam, ozet ya da asgari; yazılmazsa her kanalın kendi ayarı
#   sessiz_saat  false: sessiz saatte de hemen gider (yazılmazsa sessiz saatte özete kalır)
#   acik      false: kural kapalı
"""


@dataclass(frozen=True, slots=True)
class Applicable:
    """Which conditions a rule on an event may set."""

    days: bool
    amount: bool
    text: bool


def applicable(event: EventKind) -> Applicable:
    return Applicable(event in DAYS_EVENTS, event in AMOUNT_FIELDS, event in TITLE_EVENTS)


# --- reading -------------------------------------------------------------------------------------------


def parse(text: str, name: str = "alerts.yaml") -> list[AlertRule]:
    """The rules a file's text holds; RulesError when the program would not read it."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RulesError(f"{name} okunamadı: {exc}") from exc
    if data is None:
        return []
    if not isinstance(data, list):
        raise RulesError(f"{name} bir kural listesi olmalı: her kural '- ad: …' ile başlar")
    rules: list[AlertRule] = []
    seen: set[str] = set()
    for n, item in enumerate(cast(list[Any], data), 1):
        rule = _read(item, f"{name}, {n}. kural")
        if rule.key in seen:
            raise RulesError(f"{name}: '{rule.name}' adında iki kural var; her kuralın adı ayrı olmalı")
        seen.add(rule.key)
        rules.append(rule)
    return rules


def _read(item: Any, where: str) -> AlertRule:
    if not isinstance(item, dict):
        raise RulesError(f"{where} 'ad', 'olay' ve 'kanallar' anahtarlarıyla bir eşleme olmalı")
    values = cast(dict[Any, Any], item)
    for key in values:
        if key not in _KEYS:
            raise RulesError(f"{where}: bilinmeyen anahtar {key!r} (anahtarlar: {', '.join(_KEYS)})")
    name = values.get("ad")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > _NAME_LIMIT or "\n" in name:
        raise RulesError(f"{where}: 'ad' en çok {_NAME_LIMIT} harflik tek satırlık bir ad olmalı")
    where = f"'{name.strip()}' kuralı"
    try:
        event = EventKind(values.get("olay"))
    except ValueError:
        raise RulesError(f"{where}: 'olay' bilinen bir olay olmalı, ör. payment.due_soon") from None
    enabled, quiet = values.get("acik", True), values.get("sessiz_saat", True)
    for key, value in (("acik", enabled), ("sessiz_saat", quiet)):
        if not isinstance(value, bool):
            raise RulesError(f"{where}: '{key}' true ya da false olmalı")
    return AlertRule(
        name.strip(),
        event,
        _condition(values.get("kosul"), event, where),
        _channels(values.get("kanallar", ["masaustu", "telegram"]), where),
        _detail(values.get("ayrinti"), where),
        bool(enabled),
        bool(quiet),
    )


def _condition(value: Any, event: EventKind, where: str) -> Condition:
    if value is None:
        return Condition()
    if not isinstance(value, dict):
        raise RulesError(f"{where}: 'kosul' bir eşleme olmalı, ör. {{gun: 3}}")
    found = cast(dict[Any, Any], value)
    can = applicable(event)
    days: int | None = None
    amount: Decimal | None = None
    text = ""
    for key, item in found.items():
        if key == "gun" and can.days:
            if not isinstance(item, int) or isinstance(item, bool) or not 0 <= item <= MAX_DAYS:
                raise RulesError(f"{where}: 'gun' 0 ile {MAX_DAYS} arasında bir gün sayısı olmalı")
            days = item
        elif key == "tutar" and can.amount:
            amount = _amount(item, where)
        elif key == "metin" and can.text:
            if not isinstance(item, str) or not item.strip():
                raise RulesError(f"{where}: 'metin' boş olmayan bir yazı olmalı")
            text = item.strip()
        elif key in ("gun", "tutar", "metin"):
            raise RulesError(f"{where}: {event} olayında '{key}' koşulu kullanılamaz")
        else:
            raise RulesError(f"{where}: bilinmeyen koşul {key!r} (koşullar: gun, tutar, metin)")
    return Condition(days, amount, text)


def _amount(value: Any, where: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise RulesError(f"{where}: 'tutar' bir TL tutarı olmalı, ör. 5000")
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        raise RulesError(f"{where}: 'tutar' bir TL tutarı olmalı, ör. 5000") from None
    if not amount.is_finite() or amount < 0:
        raise RulesError(f"{where}: 'tutar' sıfır ya da daha büyük bir TL tutarı olmalı")
    return amount


def _channels(value: Any, where: str) -> tuple[Channel, ...]:
    if not isinstance(value, list):
        raise RulesError(f"{where}: 'kanallar' bir liste olmalı, ör. [masaustu, telegram]")
    found: list[Channel] = []
    for item in cast(list[Any], value):
        if item == "uygulama":  # the interface's box always gets it
            continue
        channel = CHANNEL_NAMES.get(item) if isinstance(item, str) else None
        if channel is None:
            raise RulesError(f"{where}: bilinmeyen kanal {item!r} (kanallar: {', '.join(CHANNEL_NAMES)})")
        if channel not in found:
            found.append(channel)
    return tuple(found)


def _detail(value: Any, where: str) -> DetailLevel | None:
    if value is None:
        return None
    level = DETAIL_NAMES.get(value) if isinstance(value, str) else None
    if level is None:
        raise RulesError(f"{where}: 'ayrinti' şunlardan biri olmalı: {', '.join(DETAIL_NAMES)}")
    return level


# --- writing -------------------------------------------------------------------------------------------

_CHANNEL_FILE = {channel: name for name, channel in CHANNEL_NAMES.items()}
_DETAIL_FILE = {level: name for name, level in DETAIL_NAMES.items()}


def _quoted(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)  # a JSON string is a YAML double-quoted scalar


def dump(rules: Sequence[AlertRule]) -> str:
    """The rules as the file writes them, after its explanation; parse(dump(rules)) gives them back."""
    lines = [HEADER]
    for rule in rules:
        lines.append(f"- ad: {_quoted(rule.name)}")
        lines.append(f"  olay: {rule.event}")
        c = rule.condition
        parts = [
            *([f"gun: {c.days}"] if c.days is not None else []),
            *([f"tutar: {c.amount}"] if c.amount is not None else []),
            *([f"metin: {_quoted(c.text)}"] if c.text else []),
        ]
        if parts:
            lines.append(f"  kosul: {{{', '.join(parts)}}}")
        lines.append(f"  kanallar: [{', '.join(_CHANNEL_FILE[ch] for ch in rule.channels)}]")
        if rule.detail is not None:
            lines.append(f"  ayrinti: {_DETAIL_FILE[rule.detail]}")
        if not rule.quiet:
            lines.append("  sessiz_saat: false")
        if not rule.enabled:
            lines.append("  acik: false")
    return "\n".join(lines) + "\n"


# --- matching ------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Seen:
    """An event as the rules weigh it."""

    kind: str
    target: str
    detail: Mapping[str, Any] = field(default_factory=dict[str, Any])

    @property
    def bulk(self) -> bool:
        """One event standing for many (more than the feed tells one by one): it carries only their number."""
        return not self.target and "count" in self.detail


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, int | str):
        return None
    try:
        found = Decimal(value)
    except InvalidOperation:
        return None
    return found if found.is_finite() else None


def matches(rule: AlertRule, event: Seen) -> bool:
    """Whether the rule speaks of the event. One that stands for many matches only a rule without conditions: the
    conditions cannot be weighed on a number."""
    if not rule.enabled or rule.event != event.kind:
        return False
    c = rule.condition
    if event.bulk:
        return c.empty
    if c.days is not None:
        days = event.detail.get("days")
        if not isinstance(days, int) or isinstance(days, bool) or days > c.days:
            return False
    if c.amount is not None:
        amount = _decimal(event.detail.get(AMOUNT_FIELDS.get(EventKind(event.kind), "amount")))
        if amount is None or abs(amount) < c.amount:
            return False
    return not c.text or fold(c.text) in fold(str(event.detail.get("title", "")))
