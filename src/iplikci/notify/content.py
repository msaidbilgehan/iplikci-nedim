"""What a notification says, at each level of detail (ADR-0010): in full the event, the amount, the merchant or other
party and the account's last digits; in summary the event and the amount; at the least only the kind of event, the
rest being in the app. The texts are Turkish and are made from the event alone (its kind, target and detail, as the
feed writes them: architecture §13), so a notification says what was true when it happened."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from ..domain.codes import DetailLevel, EventKind, PaymentKind
from ..domain.labels import EVENT_KIND, MONTHS, PAYMENT_KIND, format_amount

APP = "İplikçi Nedim"
IN_THE_APP = "ayrıntı uygulamada"
DIGEST_LINES = 20  # a digest names this many notifications; the rest it counts

E = EventKind


@dataclass(frozen=True, slots=True)
class Message:
    title: str  # the kind of event: a desktop notification's title, an e-mail's subject
    body: str


def label(kind: str) -> str:
    try:
        return EVENT_KIND[EventKind(kind)]
    except ValueError:
        return kind


def _tl(value: Any) -> str:
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return ""
    return f"{format_amount(amount)} TL" if amount.is_finite() else ""


def _day(value: Any) -> str:
    try:
        return f"{date.fromisoformat(str(value)):%d.%m.%Y}"
    except ValueError:
        return ""


def _month(value: str) -> str:
    """A month as the interface writes it: "2026-10" → "Ekim 2026"."""
    found = re.fullmatch(r"(\d{4})-(0[1-9]|1[0-2])", value)
    return f"{MONTHS[int(found[2]) - 1]} {found[1]}" if found else value


def _when(days: Any) -> str:
    if not isinstance(days, int) or isinstance(days, bool):
        return ""
    return {0: "bugün", 1: "yarın"}.get(days, f"{days} gün sonra")


def _digits(account: Any) -> str:
    """The account's last digits, as the interface marks them: "teb-1234" → "•1234"."""
    found = re.search(r"(\d{4})$", str(account))
    return f"•{found[1]}" if found else ""


def _payment(value: Any) -> str:
    try:
        return PAYMENT_KIND[PaymentKind(value)]
    except ValueError:
        return "Ödeme"


def _where(d: Mapping[str, Any]) -> str:
    """The account's last digits and the day, in brackets: " (•1234, 01.11.2026)"."""
    parts = [p for p in (_digits(d.get("account", "")), _day(d.get("date", ""))) if p]
    return f" ({', '.join(parts)})" if parts else ""


def _text(kind: EventKind, target: str, d: Mapping[str, Any], full: bool) -> str:
    title, amount = str(d.get("title", "")), _tl(d.get("amount", ""))
    if kind is E.PAYMENT_DUE_SOON:
        when, payment = _when(d.get("days")), _payment(d.get("payment"))
        if not full:
            return f"{payment} {when}: {amount}."
        minimum = f" Asgari ödeme {_tl(d['minimum'])}." if d.get("minimum") else ""
        return f"{title} · {payment}: {when} ({_day(d.get('due'))}), {amount}.{minimum}"
    if kind is E.BALANCE_FORECAST_NEGATIVE:
        when, balance = _when(d.get("days")), _tl(d.get("balance", ""))
        if not full:
            return f"Öngörüye göre bakiye {when} eksiye düşüyor: {balance}."
        return f"{title}: öngörüye göre bakiye {_day(d.get('day'))} günü ({when}) {balance} olacak."
    if kind is E.EXPECTED_PAYMENT_MISSING:
        if not full:
            return f"Beklenen bir ödeme görünmedi: {amount}."
        return f"{title}: {_day(d.get('expected'))} günü beklenen {amount} ödeme görünmedi."
    if kind is E.INCOME_RECEIVED:
        return f"{title}: {amount} geldi{_where(d)}." if full else f"Gelir geldi: {amount}."
    if kind is E.INCOME_LATE:
        if not full:
            return f"Beklenen bir gelir gecikti: {amount}."
        return f"{title}: {_day(d.get('expected'))} günü beklenen {amount} henüz gelmedi."
    if kind is E.SUBSCRIPTION_PRICE_CHANGED:
        old, new = _tl(d.get("old", "")), _tl(d.get("new", ""))
        if not full:
            return f"Bir abonelik zamlandı: {old} yerine {new}."
        return f"{title}: {_day(d.get('since'))} gününden beri {old} yerine {new} ödeniyor."
    if kind is E.SUBSCRIPTION_PAID_AFTER_CANCEL:
        if not full:
            return f"İptal ettiğiniz bir abonelikten ödeme alındı: {amount}."
        return (
            f"{title}: kurallarınızda {_month(str(d.get('cancelled', '')))} sonunda bittiği yazıyor, ama "
            f"{_day(d.get('date'))} günü {amount} ödendi. Aboneliği kontrol edin."
        )
    if kind is E.TRANSACTION_LARGE:
        return f"{title}: {amount}{_where(d)}." if full else f"Büyük harcama: {amount}."
    if kind is E.EVIDENCE_UNMATCHED:
        if not full:
            return f"Bir dekont ekstrede görünmüyor: {amount}."
        return f"{title}: {amount} tutarındaki dekont kapsayan ekstrede görünmüyor{_where(d)}."
    return _plain(kind, target, d)


def _plain(kind: EventKind, target: str, d: Mapping[str, Any]) -> str:
    """The events that carry no amount: the same text at both levels."""
    month = _month(target)
    if kind is E.MONTH_ENDED:
        return f"{month} bitti; ay sonu sayfası hazır, ekstreleri bekleniyor."
    if kind is E.MONTH_CLOSED:
        return f"{month} kapandı: bütün belgeleri geldi ve doğrulandı."
    if kind is E.MONTH_NEEDS_CHECK:
        return f"{month} kontrol gerektiriyor: belgeleri birbirini tutmuyor."
    if kind is E.BACKUP_FAILED:
        if d.get("stage") == "rehearsal":
            return "Geri yükleme provası geçmedi; Sistem ekranına bakın."
        return "Yedek alınamadı; Sistem ekranına bakın."
    return {
        E.PARSER_FORMAT_ALARM: "Bir belge tanındı ama okunamadı; bankanın biçimi değişmiş olabilir. Sistem ekranına bakın.",
        E.MAIL_AUTH_FAILED: "E-posta girişi reddedildi ve alım durdu; e-posta kurulumunu yenileyin.",
        E.MAIL_BRIDGE_ALARM: "Tarayıcı eklentisi Gmail'in sayfasını tanımadı ve durdu; eklentiyi güncelleyin.",
        E.MAIL_BRIDGE_SILENT: "Tarayıcı eklentisi bir gündür görünmedi; yeni e-postalar tarayıcı açılınca gelir.",
        E.DOCUMENT_RECEIVED: "Yeni bir belge geldi.",
        E.DOCUMENT_PROCESSED: "Bir belge okundu.",
        E.DOCUMENT_UNPROCESSED: "Bir belge tanınmadı; işlenmeden saklandı.",
        E.DOCUMENT_UNREADABLE: "Bir belge okunamadı; Belgeler ekranına bakın.",
        E.TRANSACTION_CREATED: f"Yeni bir işlem{_where(d)}.",
        E.TRANSACTION_CONFIRMED: "Geçici bir işlem ekstreyle kesinleşti.",
        E.INVOICE_MATCHED: "Bir fatura onu ödeyen banka satırıyla eşleşti.",
        E.INVOICE_PENDING: "Bir fatura ödenmesini bekliyor.",
        E.INVOICE_UNMATCHED: "Bir fatura hiçbir banka satırıyla eşleşmedi; yalnızca bilgi.",
        E.BRIDGE_PAIRED: "Tarayıcı eklentisi eşleşti.",
        E.BRIDGE_REVOKED: "Bir tarayıcı eklentisinin eşleşmesi iptal edildi.",
    }.get(kind, f"{label(kind)}.")


def render(kind: str, target: str, detail: Mapping[str, Any], level: DetailLevel) -> Message:
    """The notification of an event at a level of detail."""
    title = label(kind)
    if level is DetailLevel.MINIMAL:
        return Message(title, f"{title} — {IN_THE_APP}.")
    if not target and "count" in detail:  # one event for many: only their number
        return Message(title, f"{title}: {detail['count']} yeni kayıt; {IN_THE_APP}.")
    try:
        code = EventKind(kind)
    except ValueError:
        return Message(title, f"{title}.")
    return Message(title, _text(code, target, detail, level is DetailLevel.FULL))


def digest(messages: Sequence[Message]) -> Message:
    """The notifications kept back by the quiet hours or the channel's rate, in one message."""
    shown = [f"• {m.body}" for m in messages[:DIGEST_LINES]]
    if len(messages) > DIGEST_LINES:
        shown.append(f"… ve {len(messages) - DIGEST_LINES} bildirim daha; {IN_THE_APP}.")
    return Message("Bildirim özeti", f"Bekleyen {len(messages)} bildirim:\n" + "\n".join(shown))
