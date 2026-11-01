"""Notifications (F13, ADR-0010): the alert rules, the texts at each level, the quiet hours and the rate, one
notification per rule, event and channel, a failed one tried again and a sent one never again, the digest, and the
Telegram, desktop and e-mail channels. No test reaches the network, the keyring or the screen."""

import io
import json
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from iplikci import cli, egress
from iplikci.app import notify, rebuild
from iplikci.cli import notify as notify_cli
from iplikci.domain.codes import Actor, Channel, DeliveryStatus, DetailLevel, EventKind
from iplikci.notify import channels, content, timing
from iplikci.notify import rules as alert_rules
from iplikci.notify.channels import Desktop, Email, SendError, Telegram
from iplikci.notify.content import Message
from iplikci.notify.rules import DEFAULTS, AlertRule, Condition, RulesError, Seen
from iplikci.settings import config, secrets
from iplikci.storage import audit, events
from iplikci.storage import notifications as stored

TZ = timezone(timedelta(hours=3))
NOON = datetime(2026, 11, 2, 12, 0, tzinfo=TZ)
NIGHT = datetime(2026, 11, 2, 23, 30, tzinfo=TZ)
TOKEN = "123456789:" + "A" * 35

E = EventKind


# --- the rules -----------------------------------------------------------------------------------------


def test_the_shipped_rules_are_written_and_read_back_the_same():
    assert alert_rules.parse(alert_rules.dump(DEFAULTS)) == list(DEFAULTS)
    assert all(r.enabled for r in DEFAULTS) and len({r.key for r in DEFAULTS}) == len(DEFAULTS)


def test_a_rule_is_read_from_its_turkish_keys():
    text = """
- ad: Büyük market harcaması
  olay: transaction.large
  kosul: {tutar: 7500, metin: migros}
  kanallar: [telegram, eposta, uygulama]
  ayrinti: tam
  acik: false
"""
    [rule] = alert_rules.parse(text)
    assert rule == AlertRule(
        "Büyük market harcaması",
        E.TRANSACTION_LARGE,
        Condition(amount=Decimal(7500), text="migros"),
        (Channel.TELEGRAM, Channel.EMAIL),
        DetailLevel.FULL,
        enabled=False,
    )


@pytest.mark.parametrize(
    ("text", "said"),
    [
        ("- {ad: X, olay: transaction.large, renk: mavi}", "bilinmeyen anahtar 'renk'"),
        ("- {ad: X, olay: transaction.huge}", "bilinen bir olay"),
        ("- {ad: X, olay: transaction.large, kanallar: [faks]}", "bilinmeyen kanal 'faks'"),
        ("- {ad: X, olay: transaction.large, kosul: {gun: 3}}", "'gun' koşulu kullanılamaz"),
        ("- {ad: X, olay: payment.due_soon, kosul: {gun: 90}}", "0 ile 60 arasında"),
        ("- {ad: X, olay: transaction.large, kosul: {tutar: -5}}", "sıfır ya da daha büyük"),
        ("- {ad: X, olay: month.closed, ayrinti: uzun}", "'ayrinti' şunlardan biri"),
        ("- {ad: X, olay: month.closed}\n- {ad: x, olay: month.ended}", "iki kural var"),
        ("ad: X", "bir kural listesi olmalı"),
    ],
)
def test_a_rule_file_the_program_would_not_read_is_refused_with_the_reason(text, said):
    with pytest.raises(RulesError, match=said):
        alert_rules.parse(text)


def due(days: int, amount: str = "1234.56", **extra: object) -> Seen:
    detail = {"payment": "card_due", "title": "TEB Bonus •1234", "account": "teb-1234", "due": "2026-11-20"}
    return Seen(
        E.PAYMENT_DUE_SOON,
        "card_due|teb-1234|TEB Bonus •1234|2026-11-20",
        detail | {"days": days, "amount": amount} | extra,
    )


def test_a_rule_weighs_the_days_ahead_the_amount_and_the_title():
    three_days = AlertRule("3 gün", E.PAYMENT_DUE_SOON, Condition(days=3))
    assert not alert_rules.matches(three_days, due(6))
    assert alert_rules.matches(three_days, due(3))
    big = AlertRule("büyük", E.TRANSACTION_LARGE, Condition(amount=Decimal(5000), text="İSTANBUL"))
    large = Seen(E.TRANSACTION_LARGE, "fp", {"title": "Örnek Mağaza İstanbul", "amount": "6500.00"})
    assert alert_rules.matches(big, large)
    assert not alert_rules.matches(
        big, Seen(E.TRANSACTION_LARGE, "fp", {"title": "Örnek Mağaza İstanbul", "amount": "4999.99"})
    )
    assert not alert_rules.matches(big, Seen(E.TRANSACTION_LARGE, "fp", {"title": "Başka Yer", "amount": "6500.00"}))
    assert not alert_rules.matches(AlertRule("kapalı", E.TRANSACTION_LARGE, enabled=False), large)


def test_one_event_for_many_matches_only_a_rule_without_conditions():
    many = Seen(E.TRANSACTION_LARGE, "", {"count": 60})
    assert alert_rules.matches(AlertRule("hepsi", E.TRANSACTION_LARGE), many)
    assert not alert_rules.matches(AlertRule("büyük", E.TRANSACTION_LARGE, Condition(amount=Decimal(5000))), many)


# --- the texts -----------------------------------------------------------------------------------------


def test_a_due_date_is_told_in_full_in_summary_or_only_by_its_kind():
    full = content.render(E.PAYMENT_DUE_SOON, "k", due(3, minimum="246.91").detail, DetailLevel.FULL)
    assert full == Message(
        "Son ödeme yaklaşıyor",
        "TEB Bonus •1234 · Kart son ödemesi: 3 gün sonra (20.11.2026), 1.234,56 TL. Asgari ödeme 246,91 TL.",
    )
    summary = content.render(E.PAYMENT_DUE_SOON, "k", due(1).detail, DetailLevel.SUMMARY)
    assert summary.body == "Kart son ödemesi yarın: 1.234,56 TL."  # no merchant, no account
    minimal = content.render(E.PAYMENT_DUE_SOON, "k", due(0).detail, DetailLevel.MINIMAL)
    assert minimal.body == "Son ödeme yaklaşıyor — ayrıntı uygulamada."


def test_a_large_purchase_names_the_merchant_and_the_accounts_last_digits_only_in_full():
    detail = {"title": "ÖRNEK ELEKTRONİK", "amount": "6500", "account": "teb-1234", "date": "2026-11-01"}
    assert content.render(E.TRANSACTION_LARGE, "fp", detail, DetailLevel.FULL).body == (
        "ÖRNEK ELEKTRONİK: 6.500,00 TL (•1234, 01.11.2026)."
    )
    assert content.render(E.TRANSACTION_LARGE, "fp", detail, DetailLevel.SUMMARY).body == "Büyük harcama: 6.500,00 TL."


def test_a_month_and_one_event_for_many_are_told_plainly():
    assert content.render(E.MONTH_CLOSED, "2026-10", {}, DetailLevel.SUMMARY).body.startswith("Ekim 2026 kapandı")
    assert content.render(E.TRANSACTION_LARGE, "", {"count": 12}, DetailLevel.FULL).body == (
        "Büyük harcama: 12 yeni kayıt; ayrıntı uygulamada."
    )


def test_a_digest_names_twenty_notifications_and_counts_the_rest():
    found = content.digest([Message("t", f"bildirim {n}") for n in range(25)])
    assert found.body.splitlines()[0] == "Bekleyen 25 bildirim:"
    assert found.body.splitlines()[-1] == "… ve 5 bildirim daha; ayrıntı uygulamada."


# --- timing --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hours", "clock", "quiet"),
    [
        ("23:00-08:00", "23:30", True),
        ("23:00-08:00", "07:59", True),
        ("23:00-08:00", "08:00", False),
        ("23:00-08:00", "12:00", False),
        ("13:00-14:00", "13:30", True),
        ("13:00-14:00", "14:00", False),
        ("", "03:00", False),
    ],
)
def test_the_quiet_hours_may_run_over_midnight(hours, clock, quiet):
    h, m = map(int, clock.split(":"))
    assert timing.quiet(hours, datetime(2026, 11, 2, h, m, tzinfo=TZ)) is quiet


def test_a_failed_attempt_waits_longer_each_time_an_hour_at_most():
    assert [timing.backoff(n).total_seconds() for n in (1, 2, 3, 7, 8)] == [60, 120, 240, 3600, 3600]


# --- the channels --------------------------------------------------------------------------------------


def test_a_desktop_notification_passes_its_text_as_arguments():
    message = Message("Büyük harcama", 'İçinde "tırnak" ve satır\nsonu')
    mac = Desktop(platform="darwin").command(message)
    assert (
        mac is not None and mac[0] == channels.OSASCRIPT and mac[-2:] == ["İplikçi Nedim: Büyük harcama", message.body]
    )
    assert all(message.body not in arg for arg in mac[:-1])  # never pasted into the script
    linux = Desktop(platform="linux", which=lambda name: f"/usr/bin/{name}").command(message)
    assert linux == [
        "/usr/bin/notify-send",
        "--app-name",
        "İplikçi Nedim",
        "İplikçi Nedim: Büyük harcama",
        message.body,
    ]
    assert Desktop(platform="linux", which=lambda name: None).command(message) is None
    assert not Desktop(platform="win32").available


def test_a_desktop_notification_that_fails_says_so():
    with pytest.raises(SendError, match="çıkış kodu 1"):
        Desktop(run=lambda args: 1, platform="darwin").send(Message("t", "b"))


def answer(result: object, status: int = 200, ok: bool = True, description: str = "") -> tuple[int, bytes]:
    body = {"ok": ok, "result": result} if ok else {"ok": False, "description": description}
    return status, json.dumps(body).encode()


def test_telegram_sends_to_the_paired_chat_and_reports_its_own_reason():
    sent: list[tuple[str, dict[str, str]]] = []
    Telegram(lambda m, f: (sent.append((m, dict(f))), answer({}))[1], 42).send(Message("Başlık", "Gövde"))
    assert sent == [("sendMessage", {"chat_id": "42", "text": "Başlık\nGövde", "disable_web_page_preview": "true"})]
    with pytest.raises(SendError, match="Telegram reddetti: Unauthorized") as refused:
        Telegram(lambda m, f: answer(None, 401, ok=False, description="Unauthorized"), 42).send(Message("t", "b"))
    assert refused.value.refused


def test_a_telegram_call_that_cannot_reach_the_api_never_shows_the_token():
    def broken(method, form):
        raise ValueError(f"https://api.telegram.org/bot{TOKEN}/sendMessage bozuk")

    with pytest.raises(SendError) as failed:
        Telegram(broken, 42).send(Message("t", "b"))
    assert TOKEN not in str(failed.value) and not failed.value.refused


def test_only_a_start_with_a_code_is_taken_from_the_bots_messages():
    updates = [
        {"update_id": 7, "message": {"text": "/start ab12cd34", "chat": {"id": 42}}},
        {"update_id": 8, "message": {"text": "merhaba", "chat": {"id": 43}}},
        {"update_id": 9, "message": {"text": "/start@ornek_bot ef56", "chat": {"id": 44}}},
        {"update_id": 10, "message": {"text": "/start", "chat": {"id": 45}}},
    ]
    found, after = channels.starts(lambda m, f: answer(updates), 7)
    assert [(s.chat, s.code) for s in found] == [(42, "ab12cd34"), (44, "ef56")]
    assert after == 11


@dataclass
class FakeSmtp:
    refuse: bool = False
    logins: list[tuple[str, str]] = field(default_factory=list)
    messages: list[object] = field(default_factory=list)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        if self.refuse:
            raise smtplib.SMTPAuthenticationError(535, b"refused")
        self.logins.append((user, password))

    def send_message(self, message):
        self.messages.append(message)


def test_an_email_goes_to_the_users_own_address_and_a_refused_login_stops_the_channel():
    server = FakeSmtp()
    Email(lambda: server, "kisi@example.com", "sifre").send(Message("Ay kapandı", "Ekim 2026 kapandı."))
    [sent] = server.messages
    assert (sent["From"], sent["To"], sent["Subject"]) == (
        "kisi@example.com",
        "kisi@example.com",
        "İplikçi Nedim: Ay kapandı",
    )
    with pytest.raises(SendError, match="girişi reddetti") as refused:
        Email(lambda: FakeSmtp(refuse=True), "kisi@example.com", "sifre").send(Message("t", "b"))
    assert refused.value.refused


def test_only_the_allowlisted_hosts_may_be_reached():
    settings = config.Settings()
    assert {egress.TELEGRAM, "imap.gmail.com", "smtp.gmail.com"} <= egress.allowed_hosts(settings)
    with pytest.raises(egress.Refused):
        egress.check("ornek.example", settings)


# --- the notifications ---------------------------------------------------------------------------------


@dataclass
class Recorder:
    """A channel that keeps what it was given; fails the first `failures` attempts."""

    failures: int = 0
    refused: bool = False
    got: list[Message] = field(default_factory=list)

    def send(self, message: Message) -> None:
        if self.refused:
            raise SendError("girişi reddetti", refused=True)
        if self.failures:
            self.failures -= 1
            raise SendError("ulaşılamadı")
        self.got.append(message)


@pytest.fixture
def desk(monkeypatch) -> Recorder:
    """The desktop channel as available everywhere, recording instead of showing."""
    recorder = Recorder()

    @dataclass(frozen=True)
    class FakeDesktop:
        available: bool = True

        def send(self, message: Message) -> None:
            recorder.send(message)

    monkeypatch.setattr(notify, "Desktop", FakeDesktop)
    return recorder


def started(ws, at=NOON) -> None:
    """The first run: the cursor stands at the newest event."""
    assert notify.take_events(ws, at) == 0


def happen(ws, kind: str, target: str, **detail) -> None:
    with ws.db() as db:
        events.append(db, kind, target, **detail)


def rows(ws) -> list[stored.Notification]:
    with ws.db() as db:
        return stored.every(db)


def test_the_history_before_the_first_run_is_no_news(ws, desk):
    happen(ws, E.MONTH_CLOSED, "2026-09")
    started(ws)
    happen(ws, E.MONTH_CLOSED, "2026-10")
    assert notify.take_events(ws, NOON) == 2  # the box and the desktop
    assert {(n.key, n.channel, n.status) for n in rows(ws)} == {
        ("2026-10", Channel.IN_APP, DeliveryStatus.SENT),
        ("2026-10", Channel.DESKTOP, DeliveryStatus.PENDING),
    }


def test_the_same_event_twice_gives_one_notification_per_channel(ws, desk):
    started(ws)
    happen(ws, E.MONTH_CLOSED, "2026-10")
    happen(ws, E.MONTH_CLOSED, "2026-10")  # the month reopened and closed again
    notify.take_events(ws, NOON)
    assert len(rows(ws)) == 2


def test_a_due_date_rule_speaks_once_at_its_threshold(ws, desk):
    started(ws)
    for days in (6, 3, 1):  # the feed tells an item at 7, 3, 1 and 0 days
        happen(ws, E.PAYMENT_DUE_SOON, due(days).target, **due(days).detail)
    notify.take_events(ws, NOON)
    box = [n for n in rows(ws) if n.channel == Channel.IN_APP]
    assert [n.rule for n in box] == ["Son ödemeye 3 gün"]
    assert "3 gün sonra" in box[0].body  # the first event within its three days


def test_a_sent_notification_is_never_sent_again(ws, desk):
    started(ws)
    happen(ws, E.BACKUP_FAILED, "2026-11-02", stage="backup")
    notify.run(ws, NOON)
    notify.run(ws, NOON + timedelta(minutes=5))
    assert [m.body for m in desk.got] == ["Yedek alınamadı; Sistem ekranına bakın."]


def test_a_failed_notification_is_tried_again_later_until_it_goes(ws, desk):
    desk.failures = 2
    started(ws)
    happen(ws, E.BACKUP_FAILED, "2026-11-02", stage="backup")
    assert notify.run(ws, NOON).failed == 1
    assert notify.deliver(ws, NOON + timedelta(seconds=30)).failed == 0  # not before its wait of a minute
    assert notify.deliver(ws, NOON + timedelta(minutes=1)).failed == 1  # the second attempt fails too
    assert notify.deliver(ws, NOON + timedelta(minutes=4)).sent == 1
    [sent] = [n for n in rows(ws) if n.channel == Channel.DESKTOP]
    assert (sent.status, sent.attempts, sent.error) == (DeliveryStatus.SENT, 2, "")
    assert notify.deliver(ws, NOON + timedelta(hours=2)).sent == 0


def test_a_notification_that_keeps_failing_is_given_up(ws, desk):
    desk.failures = 100
    started(ws)
    happen(ws, E.BACKUP_FAILED, "2026-11-02", stage="backup")
    notify.take_events(ws, NOON)
    at = NOON
    for _ in range(timing.MAX_ATTEMPTS):
        notify.deliver(ws, at)
        at += timedelta(hours=1)
    [given_up] = [n for n in rows(ws) if n.channel == Channel.DESKTOP]
    assert (given_up.status, given_up.attempts) == (DeliveryStatus.FAILED, timing.MAX_ATTEMPTS)


def test_a_refused_login_stops_its_channel_until_the_user_turns_it_on_again(ws, desk):
    desk.refused = True
    started(ws)
    happen(ws, E.BACKUP_FAILED, "2026-11-02", stage="backup")
    notify.run(ws, NOON)
    [refused] = [n for n in rows(ws) if n.channel == Channel.DESKTOP]
    assert (refused.status, refused.attempts) == (DeliveryStatus.FAILED, 1)
    happen(ws, E.MONTH_CLOSED, "2026-10")
    notify.take_events(ws, NOON)
    assert not [n for n in rows(ws) if n.key == "2026-10" and n.channel == Channel.DESKTOP]  # stopped: nothing new
    state = {s.channel: s for s in notify.status(ws).channels}[Channel.DESKTOP]
    assert not state.ready and state.note.startswith("Durdu")
    notify.set_preferences(ws, "23:00-08:00", {}, [Channel.DESKTOP])
    assert {s.channel: s for s in notify.status(ws).channels}[Channel.DESKTOP].ready


def test_the_quiet_hours_keep_notifications_back_for_one_digest(ws, desk):
    started(ws, NIGHT)
    happen(ws, E.MONTH_CLOSED, "2026-10")
    happen(ws, E.BACKUP_FAILED, "2026-11-02", stage="backup")
    notify.run(ws, NIGHT)
    assert desk.got == []
    assert {n.status for n in rows(ws) if n.channel == Channel.DESKTOP} == {DeliveryStatus.HELD}
    morning = NIGHT + timedelta(hours=9)
    assert notify.deliver(ws, morning).digests == 1
    [digest] = desk.got
    assert digest.title == "Bildirim özeti" and digest.body.startswith("Bekleyen 2 bildirim:")
    assert {n.status for n in rows(ws) if n.channel == Channel.DESKTOP} == {DeliveryStatus.DIGESTED}
    assert notify.deliver(ws, morning + timedelta(minutes=5)).digests == 0


def test_a_channel_above_its_rate_keeps_the_rest_for_a_digest(ws, desk):
    started(ws)
    for n in range(12):
        happen(ws, E.MONTH_CLOSED, f"2025-{n + 1:02d}")
    sent = notify.run(ws, NOON)
    assert (sent.sent, sent.held, sent.digests) == (timing.RATE[Channel.DESKTOP], 2, 1)
    assert len(desk.got) == timing.RATE[Channel.DESKTOP] + 1


def test_the_interface_box_counts_what_was_not_seen(ws, desk):
    started(ws)
    happen(ws, E.MONTH_CLOSED, "2026-10")
    happen(ws, E.MONTH_ENDED, "2026-10", status="waiting")
    notify.take_events(ws, NOON)
    assert notify.status(ws).unread == 2
    assert notify.mark_read(ws) == 2
    assert notify.status(ws).unread == 0


def test_a_rule_the_user_turned_off_says_nothing(ws, desk):
    rules = [r if r.event != E.MONTH_CLOSED else AlertRule(r.name, r.event, enabled=False) for r in DEFAULTS]
    notify.save_rules(ws, rules, Actor.USER)
    started(ws)
    happen(ws, E.MONTH_CLOSED, "2026-10")
    assert notify.take_events(ws, NOON) == 0


def test_saved_rules_keep_the_file_before_and_are_audited(ws):
    first = notify.save_rules(ws, DEFAULTS[:2], Actor.USER)
    second = notify.save_rules(ws, DEFAULTS[:3], Actor.MCP)
    assert first is None and second is not None and second.parent == ws.layout.rules_history
    assert notify.load_rules(ws) == notify.Rules(list(DEFAULTS[:3]), own=True)
    with ws.db() as db:
        assert [(e.actor, e.action) for e in audit.entries(db)] == [
            (Actor.USER, notify.RULES_CHANGED),
            (Actor.MCP, notify.RULES_CHANGED),
        ]


def test_a_broken_rule_file_leaves_the_shipped_rules_in_place_and_says_why(ws):
    ws.layout.alert_rules.parent.mkdir(parents=True, exist_ok=True)
    ws.layout.alert_rules.write_text("- {ad: X, olay: yok}", encoding="utf-8")
    found = notify.load_rules(ws)
    assert found.rules == list(DEFAULTS) and "bilinen bir olay" in found.problem


def test_the_preview_counts_what_the_rule_would_have_said_in_thirty_days(ws):
    for days in (6, 3, 1):
        happen(ws, E.PAYMENT_DUE_SOON, due(days).target, **due(days).detail)
    happen(ws, E.PAYMENT_DUE_SOON, "other", **(due(2).detail | {"title": "Başka kart"}))
    found = notify.preview(ws, AlertRule("3 gün", E.PAYMENT_DUE_SOON, Condition(days=3), enabled=False))
    assert found.count == 2 and found.examples[0].body.startswith("Başka kart")


# --- Telegram ------------------------------------------------------------------------------------------


@pytest.fixture
def keyring(monkeypatch) -> dict[str, str]:
    kept: dict[str, str] = {}
    monkeypatch.setattr(secrets, "store", lambda secret, value: kept.update({secret.account: value}) or True)
    monkeypatch.setattr(secrets, "load", lambda secret: kept.get(secret.account))
    monkeypatch.setattr(secrets, "delete", lambda secret: kept.pop(secret.account, None))
    return kept


@dataclass
class FakeBot:
    updates: list[dict[str, object]] = field(default_factory=list)
    sent: list[dict[str, str]] = field(default_factory=list)

    def post_for(self, token: str):
        def post(method: str, form):
            if method == "getMe":
                return answer({"username": "ornek_bot"})
            if method == "getUpdates":
                return answer([u for u in self.updates if int(u["update_id"]) >= int(form["offset"])])
            self.sent.append(dict(form))
            return answer({})

        return post


def test_a_bot_is_paired_by_the_code_its_chat_sends(ws, keyring):
    bot = FakeBot()
    assert notify.set_telegram_token(ws, TOKEN, Actor.USER, bot.post_for) == notify.TokenSet("ornek_bot", True)
    assert keyring == {"telegram-bot": TOKEN}
    pairing = notify.start_pairing(ws, NOON)
    assert pairing.link == f"https://t.me/ornek_bot?start={pairing.code}"
    bot.updates = [{"update_id": 1, "message": {"text": "/start yanlis", "chat": {"id": 7}}}]
    assert not notify.check_pairing(ws, NOON, bot.post_for)
    bot.updates.append({"update_id": 2, "message": {"text": f"/start {pairing.code}", "chat": {"id": 42}}})
    assert notify.check_pairing(ws, NOON, bot.post_for)
    assert config.load(ws.layout.settings).notify.telegram_chat == 42
    assert bot.sent[-1]["chat_id"] == "42"  # greeted
    state = {s.channel: s for s in notify.status(ws).channels}[Channel.TELEGRAM]
    assert state.ready and state.note == "@ornek_bot botuyla eşleşti."


def test_a_pairing_code_lasts_ten_minutes(ws, keyring):
    bot = FakeBot()
    notify.set_telegram_token(ws, TOKEN, Actor.USER, bot.post_for)
    notify.start_pairing(ws, NOON)
    with pytest.raises(notify.NotifyError, match="süresi doldu"):
        notify.check_pairing(ws, NOON + timedelta(minutes=11), bot.post_for)


def test_what_is_no_bot_token_is_refused_before_it_is_tried(ws, keyring):
    with pytest.raises(notify.NotifyError, match="bot belirteci değil"):
        notify.set_telegram_token(ws, "parola123", Actor.USER, FakeBot().post_for)
    assert keyring == {}


def test_removing_telegram_forgets_the_token_and_the_chat(ws, keyring):
    bot = FakeBot()
    notify.set_telegram_token(ws, TOKEN, Actor.USER, bot.post_for)
    config.update(ws.layout.settings, "notify", {"telegram_chat": 42})
    notify.remove_telegram(ws, Actor.USER)
    assert keyring == {} and config.load(ws.layout.settings).notify.telegram_chat == 0
    state = {s.channel: s for s in notify.status(ws).channels}[Channel.TELEGRAM]
    assert not state.ready and "belirteci girilmedi" in state.note


def test_a_never_set_up_telegram_never_reads_the_keyring(ws, desk):
    started(ws)  # the keyring refuses every test (conftest): reaching it would fail this one
    happen(ws, E.MONTH_CLOSED, "2026-10")
    notify.run(ws, NOON)


def test_the_email_channel_says_why_an_account_under_advanced_protection_has_none(ws):
    config.update(ws.layout.settings, "mail", {"connector": "browser_bridge"})
    state = {s.channel: s for s in notify.status(ws).channels}[Channel.EMAIL]
    assert not state.ready and "Gelişmiş Koruma" in state.note


def test_a_test_notification_goes_to_the_channel_asked_or_says_why_not(ws, desk):
    notify.send_test(ws, Channel.DESKTOP)
    assert desk.got[-1].title == "Deneme bildirimi"
    notify.send_test(ws, Channel.IN_APP)
    assert notify.status(ws).unread == 1
    with pytest.raises(notify.NotifyError, match="belirteci girilmedi"):
        notify.send_test(ws, Channel.TELEGRAM)


# --- primary data --------------------------------------------------------------------------------------


def test_the_notifications_are_primary_data_and_an_older_dump_still_loads(ws, desk):
    started(ws)
    happen(ws, E.MONTH_CLOSED, "2026-10")
    notify.take_events(ws, NOON)
    with ws.db() as db:
        primary = rebuild.export(db)
    loaded = rebuild.load(rebuild.dump(primary))
    assert loaded.notifications == primary.notifications and len(loaded.notifications) == 2
    older = json.loads(rebuild.dump(primary))
    older["version"] = 2
    del older["notifications"]
    assert rebuild.load(json.dumps(older)).notifications == []


def test_the_notify_settings_are_checked(tmp_path):
    path = tmp_path / "settings.toml"
    path.write_text('[notify]\nchannels = ["desktop", "faks"]\n', encoding="utf-8")
    with pytest.raises(config.SettingsError, match="email, telegram, desktop"):
        config.load(path)
    path.write_text('[notify]\nchannels = ["telegram"]\ntelegram_chat = 42\n', encoding="utf-8")
    assert (config.load(path).notify.channels, config.load(path).notify.telegram_chat) == (("telegram",), 42)


# --- the command line ----------------------------------------------------------------------------------


def test_the_commands_show_the_channels_the_rules_and_the_history(ws, desk, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    started(ws)
    happen(ws, E.MONTH_CLOSED, "2026-10")
    notify.run(ws, NOON)
    assert cli.main(["bildirim", "durum"]) == 0
    out = capsys.readouterr().out
    assert "Sessiz saat: 23:00-08:00" in out and "Masaüstü: hazır" in out and "belirteci girilmedi" in out
    assert cli.main(["bildirim", "kurallar"]) == 0
    out = capsys.readouterr().out
    assert "Uygulamayla gelen kurallar" in out and "Son ödemeye 3 gün: Son ödeme yaklaşıyor [en çok 3 gün kala]" in out
    assert cli.main(["bildirim", "gecmis", "--kanal", "masaustu"]) == 0
    assert "Masaüstü  Gönderildi" in capsys.readouterr().out
    assert cli.main(["bildirim", "dene", "telegram"]) == 1
    assert "belirteci girilmedi" in capsys.readouterr().err


def test_telegram_is_set_up_with_the_token_read_from_a_line_never_an_argument(ws, keyring, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    bot = FakeBot()
    monkeypatch.setattr(notify, "_post_for", lambda settings: bot.post_for)
    monkeypatch.setattr(notify_cli.sys, "stdin", io.StringIO(TOKEN + "\n"))
    looked: list[bool] = []

    def check(ws_):
        looked.append(True)
        return len(looked) == 2  # the code comes at the second look

    monkeypatch.setattr(notify, "check_pairing", check)
    monkeypatch.setattr(notify_cli.time, "sleep", lambda seconds: None)
    assert cli.main(["telegram", "kur"]) == 0
    out = capsys.readouterr().out
    assert "Bot doğrulandı: @ornek_bot" in out and "/start " in out and "Eşleşti" in out
    assert TOKEN not in out and keyring == {"telegram-bot": TOKEN}


def test_a_rule_may_send_in_the_quiet_hours_too(ws, desk):
    urgent = [r if r.event != E.BACKUP_FAILED else AlertRule(r.name, r.event, quiet=False) for r in DEFAULTS]
    notify.save_rules(ws, urgent, Actor.USER)
    assert "sessiz_saat: false" in ws.layout.alert_rules.read_text(encoding="utf-8")
    assert notify.load_rules(ws).rules == urgent
    started(ws, NIGHT)
    happen(ws, E.BACKUP_FAILED, "2026-11-02", stage="backup")
    happen(ws, E.MONTH_CLOSED, "2026-10")
    notify.run(ws, NIGHT)
    assert [m.body for m in desk.got] == ["Yedek alınamadı; Sistem ekranına bakın."]  # the month waits for the digest
