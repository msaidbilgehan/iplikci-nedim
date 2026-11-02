"""The notifications' API (F13): the box and the history, the alert rules and their preview, the channels'
settings, the Telegram bot and a test notification. Reading needs a session or the token; changing, the service's
own pages."""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.api.routes.events import _events as stream_of
from iplikci.app import notify
from iplikci.domain.codes import EventKind
from iplikci.notify.content import Message
from iplikci.settings import config, secrets
from iplikci.storage import audit, events

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}
BOT_TOKEN = "123456789:" + "B" * 35
NOON = datetime(2026, 11, 2, 12, 0).astimezone()


@pytest.fixture
def client(ws) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN, stream_limit=0.05, poll=0.01)), base_url=BASE)


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def signed_in(client: TestClient) -> TestClient:
    url = client.post("/api/login-links", headers=bearer()).json()["url"]
    assert client.get(url, follow_redirects=False).status_code == 303
    return client


@dataclass
class Shown:
    got: list[Message] = field(default_factory=list)


@pytest.fixture
def desk(monkeypatch) -> Shown:
    shown = Shown()

    @dataclass(frozen=True)
    class FakeDesktop:
        available: bool = True

        def send(self, message: Message) -> None:
            shown.got.append(message)

    monkeypatch.setattr(notify, "Desktop", FakeDesktop)
    return shown


def test_the_rules_are_read_with_the_token_and_changed_only_from_the_services_own_pages(client, ws):
    assert client.get("/api/rules/alerts").status_code == 401
    found = client.get("/api/rules/alerts", headers=bearer()).json()
    assert not found["own"] and found["problem"] == ""
    assert found["rules"][0] == {
        "name": "Son ödemeye 3 gün",
        "event": "payment.due_soon",
        "condition": {"days": 3, "amount": None, "text": ""},
        "channels": ["desktop", "telegram"],
        "detail": None,
        "enabled": True,
        "quiet": True,
    }
    due = next(e for e in found["events"] if e["kind"] == "payment.due_soon")
    assert (due["label"], due["days"], due["amount"], due["text"]) == ("Son ödeme yaklaşıyor", True, True, True)
    rule = {
        "name": "Büyük harcama",
        "event": "transaction.large",
        "condition": {"amount": 750000},
        "channels": ["telegram"],
    }
    assert client.put("/api/rules/alerts", json={"rules": [rule]}, headers=bearer()).status_code == 403
    signed_in(client)
    saved = client.put("/api/rules/alerts", json={"rules": [rule]}, headers=OWN_PAGE).json()
    assert saved["own"] and saved["rules"][0]["condition"] == {"days": None, "amount": 750000, "text": ""}
    assert "tutar: 7500" in ws.layout.alert_rules.read_text(encoding="utf-8")
    with ws.db() as db:
        assert [e.action for e in audit.entries(db)] == ["rules.alerts_changed"]


@pytest.mark.parametrize(
    ("rules", "says"),
    [
        (
            [
                {"name": "X", "event": "month.closed", "channels": []},
                {"name": "x", "event": "month.ended", "channels": []},
            ],
            "iki kural",
        ),
        ([{"name": "X", "event": "transaction.large", "condition": {"days": 3}, "channels": []}], "'gun' koşulu"),
    ],
    ids=["a name twice", "a condition the event has not"],
)
def test_rules_the_program_would_not_read_are_refused_and_nothing_is_written(client, ws, rules, says):
    signed_in(client)
    refused = client.put("/api/rules/alerts", json={"rules": rules}, headers=OWN_PAGE)
    assert refused.status_code == 400 and refused.json()["code"] == "rules_invalid" and says in refused.json()["title"]
    assert not ws.layout.alert_rules.exists()


def test_the_preview_says_how_often_a_rule_would_have_spoken(client, ws):
    with ws.db() as db:
        events.append(db, EventKind.MONTH_CLOSED, "2026-10")
        events.append(db, EventKind.MONTH_CLOSED, "2026-09")
    found = client.post(
        "/api/rules/alerts/preview",
        json={"rule": {"name": "Ay", "event": "month.closed", "channels": [], "enabled": False}},
        headers=bearer(),
    ).json()
    assert found["count"] == 2 and found["days"] == 30
    assert found["examples"][0] == {
        "title": "Ay kapandı",
        "body": "Eylül 2026 kapandı: bütün belgeleri geldi ve doğrulandı.",
    }


def test_the_box_lists_the_notifications_newest_first_and_marks_them_seen(client, ws, desk):
    notify.take_events(ws, NOON)  # the first run: nothing before it is news
    with ws.db() as db:
        events.append(db, EventKind.MONTH_CLOSED, "2026-10")
    notify.run(ws, NOON)  # outside the quiet hours
    found = client.get("/api/notifications?channel=in_app", headers=bearer()).json()
    assert found["unread"] == 1
    [item] = found["items"]
    assert (item["rule"], item["channel"], item["status"], item["read"]) == ("Ay kapandı", "in_app", "sent", False)
    assert item["target"] == "2026-10"  # what the event concerns: here a month
    everything = client.get("/api/notifications", headers=bearer()).json()
    assert [i["channel"] for i in everything["items"]] == ["desktop", "in_app"] and everything["next"] is None
    assert desk.got[0].title == "Ay kapandı"
    first = client.get("/api/notifications?limit=1", headers=bearer()).json()
    assert [i["channel"] for i in first["items"]] == ["desktop"] and first["next"] == first["items"][0]["id"]
    rest = client.get(f"/api/notifications?limit=1&before={first['next']}", headers=bearer()).json()
    assert [i["channel"] for i in rest["items"]] == ["in_app"] and rest["next"] is None  # no empty page after it
    signed_in(client)
    assert client.post("/api/notifications/read", json={}, headers=OWN_PAGE).json() == {"marked": 1}
    assert client.get("/api/notifications").json()["unread"] == 0


def test_the_channels_settings_say_what_each_channel_needs_and_are_changed_from_the_own_pages(client, ws, desk):
    found = client.get("/api/notify/settings", headers=bearer()).json()
    assert found["quiet_hours"] == "23:00-08:00"
    states = {s["channel"]: s for s in found["channels"]}
    assert states["in_app"]["ready"] and states["desktop"]["ready"]
    assert not states["telegram"]["ready"] and "belirteci girilmedi" in states["telegram"]["note"]
    assert (states["desktop"]["stage"], states["telegram"]["stage"]) == ("ready", "no_bot")
    signed_in(client)
    wrong = client.put(
        "/api/notify/settings", json={"quiet_hours": "25:00-08:00", "detail": {}, "channels": []}, headers=OWN_PAGE
    )
    assert (wrong.status_code, wrong.json()["code"]) == (422, "invalid_request")
    saved = client.put(
        "/api/notify/settings",
        json={"quiet_hours": "", "detail": {"telegram": "minimal"}, "channels": ["telegram"]},
        headers=OWN_PAGE,
    ).json()
    assert saved["quiet_hours"] == "" and saved["detail"]["telegram"] == "minimal"
    settings = config.load(ws.layout.settings).notify
    assert (settings.channels, settings.detail["telegram"]) == (("telegram",), "minimal")


@dataclass
class FakeBot:
    updates: list[dict[str, object]] = field(default_factory=list)

    def post_for(self, token: str):
        def post(method: str, form):
            result: object = {}
            if method == "getMe":
                result = {"username": "ornek_bot"}
            elif method == "getUpdates":
                result = self.updates
            return 200, json.dumps({"ok": True, "result": result}).encode()

        return post


def test_a_telegram_bot_is_set_up_and_paired_from_the_own_pages(client, ws, monkeypatch):
    kept: dict[str, str] = {}
    monkeypatch.setattr(secrets, "store", lambda secret, value: kept.update({secret.account: value}) or True)
    monkeypatch.setattr(secrets, "load", lambda secret: kept.get(secret.account))
    monkeypatch.setattr(secrets, "delete", lambda secret: kept.pop(secret.account, None))
    bot = FakeBot()
    monkeypatch.setattr(notify, "_post_for", lambda settings: bot.post_for)
    signed_in(client)
    refused = client.post("/api/notify/telegram/token", json={"token": "parola"}, headers=OWN_PAGE)
    assert refused.status_code == 400 and "bot belirteci değil" in refused.json()["title"]
    set_up = client.post("/api/notify/telegram/token", json={"token": BOT_TOKEN}, headers=OWN_PAGE).json()
    assert set_up == {"bot": "ornek_bot", "in_keyring": True}
    pairing = client.post("/api/notify/telegram/pairing", headers=OWN_PAGE).json()
    assert pairing["link"] == f"https://t.me/ornek_bot?start={pairing['code']}"
    assert datetime.fromisoformat(pairing["expires"]) > datetime.now().astimezone()
    assert client.post("/api/notify/telegram/check", headers=OWN_PAGE).json() == {"paired": False}
    bot.updates = [{"update_id": 1, "message": {"text": f"/start {pairing['code']}", "chat": {"id": 42}}}]
    assert client.post("/api/notify/telegram/check", headers=OWN_PAGE).json() == {"paired": True}
    assert config.load(ws.layout.settings).notify.telegram_chat == 42
    assert BOT_TOKEN not in json.dumps(client.get("/api/notify/settings").json())  # the token never comes back
    assert client.delete("/api/notify/telegram", headers=OWN_PAGE).status_code == 204
    assert kept == {}


def test_a_test_notification_goes_out_or_says_why_not(client, desk):
    signed_in(client)
    assert client.post("/api/notify/test", json={"channel": "desktop"}, headers=OWN_PAGE).status_code == 204
    assert desk.got[-1].title == "Deneme bildirimi"
    assert client.post("/api/notify/test", json={"channel": "in_app"}, headers=OWN_PAGE).status_code == 204
    [test] = client.get("/api/notifications?channel=in_app").json()["items"]
    assert (test["kind"], test["target"]) == ("test", "")  # a test concerns nothing
    refused = client.post("/api/notify/test", json={"channel": "email"}, headers=OWN_PAGE)
    assert refused.status_code == 400 and refused.json()["code"] == "notify_refused"


def test_the_stream_tells_when_a_notification_is_made_after_its_event(ws, desk):
    notify.take_events(ws, NOON)  # the first run: nothing before it is news

    async def read() -> list[str]:
        stream = stream_of(Context(ws=ws, token=TOKEN, stream_limit=5, poll=0.01), 0)
        assert await anext(stream) == "retry: 3000\n\n"
        with ws.db() as db:
            events.append(db, EventKind.MONTH_CLOSED, "2026-10")
        told = [await asyncio.wait_for(anext(stream), 5)]  # the event, before any notification
        notify.run(ws, NOON)  # the notification follows its event by a moment
        told.append(await asyncio.wait_for(anext(stream), 5))
        await stream.aclose()
        return told

    event, signal = asyncio.run(read())
    assert event.startswith("id: 1\ndata: {") and '"kind":"month.closed"' in event
    assert signal == "event: notifications\ndata: 2:2\n\n"  # no id: the event log's place stays where it was
