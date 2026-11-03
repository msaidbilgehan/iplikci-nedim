"""The Pano screen's API (F06): the net worth, this month against the typical month, the payments due within a week,
the open alerts, the last seven months' closing, how fresh each account's documents are and the to-do count; every
card with its one-sentence comment and where it leads."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import background, backup, bridge, todos
from iplikci.app.mail import IMAP
from iplikci.app.reading import FORMAT_ALARM
from iplikci.app.workspace import Busy, Workspace
from iplikci.domain.codes import Actor, DocumentStatus
from iplikci.fakes import HOLDER, Move, garanti, teb
from iplikci.parsers import registry
from iplikci.storage import events
from iplikci.storage import mail as mail_store

from conftest import add

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
CURRENT = "garanti-1234567"  # the Garanti current account of the fake documents
CARD = "garanti-1234"  # the Garanti Bonus card it pays
TEB = "teb-123456789"


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def tl(minor: int, currency: str = "TRY") -> dict[str, object]:
    return {"minor": minor, "currency": currency}


def link(screen: str, id: str = "", **query: str) -> dict[str, object]:
    return {"screen": screen, "id": id, "query": query}


def client_for(ws: Workspace, today: date = date(2026, 11, 5)) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN, today=lambda: today)), base_url=BASE)


def board(ws: Workspace, today: date = date(2026, 11, 5)) -> dict[str, dict[str, object]]:
    response = client_for(ws, today).get("/api/dashboard", headers=bearer())
    assert response.status_code == 200, response.text
    return response.json()


def alerts(ws: Workspace, today: date = date(2026, 11, 5)) -> list[dict[str, object]]:
    return board(ws, today)["alerts"]["items"]  # type: ignore[return-value]


@pytest.fixture(scope="module")
def demo_client(tmp_path_factory) -> TestClient:
    """The demo data folder's service, as on the day its baseline is taken."""
    ws = Workspace.load(demo.build(tmp_path_factory.mktemp("demo")))
    context = Context(ws=ws, token=TOKEN, ui=tmp_path_factory.mktemp("arayuz"), today=lambda: demo.AS_OF)
    return TestClient(create_app(context), base_url=BASE)


@pytest.fixture(scope="module")
def demo_board(demo_client) -> dict[str, dict[str, object]]:
    return demo_client.get("/api/dashboard", headers=bearer()).json()


@pytest.fixture
def garanti_ws(ws: Workspace) -> Workspace:
    """The Garanti current account's October list and the Bonus card's statement it pays."""
    add(ws, "ekim.xls", garanti.account_xls())
    add(ws, "ekstre.pdf", garanti.bonus_statement())
    background.refresh(ws, date(2026, 11, 5))
    return ws


def _monthly_list(months: range, until: date) -> bytes:
    """A TEB list from the first day of the first month to until: 100 TL of shopping on the 5th and 300 TL on the 20th
    of every month, and 150 TL on the 5th of until's month."""
    moves = [Move(date(2026, 1, 1), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(5000))]
    for month in months:
        moves += [
            Move(date(2026, month, 5), "MIGROS ORNEK SUBE ISTANBUL", Decimal(-100)),
            Move(date(2026, month, 20), "MIGROS ORNEK SUBE ISTANBUL", Decimal(-300)),
        ]
    moves.append(Move(date(2026, until.month, 5), "MIGROS ORNEK SUBE ISTANBUL", Decimal(-150)))
    period = f"01/{months.start:02d}/2026 - {until:%d/%m/%Y}"
    return teb.account_export(teb.running_rows(moves), period=period)


# --- the gate --------------------------------------------------------------------------------------------------------


def test_the_dashboard_needs_a_session_or_the_token_and_says_when_the_documents_are_busy(ws, monkeypatch):
    context = Context(ws=ws, token=TOKEN)
    client = TestClient(create_app(context), base_url=BASE)
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard", headers=bearer()).status_code == 200

    def busy():
        raise Busy("başka bir işlem belgeleri işliyor; biraz sonra yeniden deneyin")

    monkeypatch.setattr(context.analysis, "get", busy)
    refused = client.get("/api/dashboard", headers=bearer())
    assert (refused.status_code, refused.json()["code"]) == (503, "busy")


def test_an_empty_data_folder_has_cards_that_say_there_is_nothing_yet(ws):
    found = board(ws)
    assert found["net_worth"]["say"] == (
        "Henüz bakiyesi bilinen bir hesap yok; ekstre ve dökümler geldikçe burada görünür."
    )
    assert found["due"]["say"] == "Önümüzdeki 7 günde ödenecek bir şey görünmüyor."
    assert found["alerts"] == {"items": [], "say": "Açık uyarı yok.", "link": link("notifications")}
    assert found["freshness"]["say"] == "Henüz belgesi gelen bir hesap yok."
    assert found["todo"] == {"kinds": [], "total": 0, "say": "Yapılacak bir şey yok.", "link": link("todo")}


# --- the net worth ---------------------------------------------------------------------------------------------------


def test_the_net_worth_adds_up_what_stands_now_and_names_what_has_no_value(demo_client, demo_board):
    worth = demo_board["net_worth"]
    now = demo_client.get("/api/feed/now", headers=bearer()).json()
    assert worth["total"] == tl(sum(b["value"]["minor"] for b in now["balances"]))  # the demo has no cards
    assert (worth["total"], worth["assets"], worth["debts"], worth["certainty"]) == (
        tl(18572210),
        tl(18572210),
        tl(0),
        "confirmed",
    )
    assert [(p["account"]["id"], p["value"]) for p in worth["parts"]] == [
        (TEB, tl(18438010)),
        ("garanti-yatirim-1234567-101", tl(134200)),
    ]
    assert worth["left_out"] == now["unknown"]  # the Garanti account known only from receipts
    euro, dollar, gold = worth["currencies"]
    # At the demo's made-up TCMB bulletin of its last business day: what the TL would buy, at the selling rate.
    assert (euro["amount"], euro["rate"], euro["note"]) == (
        {"minor": 329449, "currency": "EUR"},  # 185.722,10 / 56,3735
        "56.3735",
        "TCMB 13.11.2026 döviz satış kuruyla",
    )
    assert (dollar["amount"], dollar["rate_source"]) == ({"minor": 369401, "currency": "USD"}, "tcmb")
    assert (gold["currency"], gold["amount"], gold["note"]) == ("GR", None, "gram altının TL fiyatı belgelerde yok")
    assert worth["say"] == "Net varlığınız 185.722,10 TL; 1 hesabın TL değeri bilinmediği için toplama girmedi."
    assert worth["link"] == link("accounts")


def test_a_cards_debt_counts_against_the_net_worth(garanti_ws):
    worth = board(garanti_ws)["net_worth"]
    # The list's closing balance, less what the card's statement still asks after the payment of 10 October.
    assert (worth["assets"], worth["debts"], worth["total"]) == (tl(2394670), tl(63489), tl(2331181))
    assert [(p["account"]["id"], p["value"]) for p in worth["parts"]] == [(CURRENT, tl(2394670)), (CARD, tl(-63489))]
    assert worth["say"] == "Net varlığınız 23.311,81 TL."


def test_the_net_worth_is_told_in_a_currency_at_the_newest_rate_the_documents_print(ws):
    moves = [
        Move(date(2026, 10, 1), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(37000)),
        Move(date(2026, 10, 10), "DÖVİZ ALIŞ EUR: 36,50", Decimal(-3650)),
        Move(date(2026, 10, 20), "DÖVİZ ALIŞ EUR: 37,00", Decimal(-3700)),
    ]
    add(ws, "teb.xls", teb.account_export(teb.running_rows(moves), period="01/10/2026 - 31/10/2026"))
    worth = board(ws)["net_worth"]
    assert worth["total"] == tl(2965000)
    euro, dollar, _ = worth["currencies"]
    # 29.650 TL at the rate of 20 October: 801,351… EUR, rounded half up.
    assert euro == {
        "currency": "EUR",
        "amount": tl(80135, "EUR"),
        "rate": "37.00",
        "rate_day": "2026-10-20",
        "note": "20.10.2026 belgesindeki kurla",
        "rate_source": "document",
    }
    assert (dollar["amount"], dollar["rate"], dollar["note"]) == (None, None, "belgelerde USD kuru yok")


# --- this month ------------------------------------------------------------------------------------------------------


def test_this_month_is_compared_with_the_same_days_of_the_typical_month(ws):
    add(ws, "liste.xls", _monthly_list(range(1, 7), date(2026, 7, 10)))
    month = board(ws, date(2026, 7, 10))["month"]
    assert (month["pace"]["spent"], month["pace"]["by_day"]) == (tl(15000), tl(10000))
    assert (
        month["say"]
        == "Gelen belgelere göre bu ay 150,00 TL harcandı; tipik ayın aynı günlerinden (100,00 TL) %50 fazla."
    )
    assert month["link"] == link("month", "2026-07")


def test_this_month_is_not_compared_before_its_documents_or_three_complete_months(ws, demo_board):
    # No document reaches November yet: that nothing was spent is not known, so no amount is said.
    assert demo_board["month"]["say"] == (
        "Bu ayın günlerini kapsayan ekstre ya da döküm henüz gelmedi, karşılaştırmak için erken."
    )
    assert demo_board["month"]["pace"]["note"].endswith(
        "sonra eklenir. Bu ayın günlerini kapsayan ekstre ya da döküm henüz gelmedi. Tipik ay: Nisan 2026 – Ekim 2026 "
        "arasındaki 6 tam ayın medyanı."
    )
    add(ws, "liste.xls", _monthly_list(range(1, 3), date(2026, 3, 10)))
    assert board(ws, date(2026, 3, 10))["month"]["say"] == (
        "Gelen belgelere göre bu ay 150,00 TL harcandı; tipik ayla karşılaştırmak için en az 3 tam ay gerekiyor."
    )


def test_this_months_spending_a_receipt_tells_before_any_list_is_not_compared(ws):
    add(ws, "liste.xls", _monthly_list(range(1, 7), date(2026, 6, 30)))
    dues = garanti.fast_body("TEMMUZ AİDAT ÖDEMESİ", "ÖRNEK SİTE YÖNETİMİ")
    paid = garanti.receipt("HESAPTAN FAST", "106/1234567", HOLDER, dues, "- 1.250,00 TL", date(2026, 7, 5))
    add(ws, "dekont.pdf", paid)
    assert board(ws, date(2026, 7, 10))["month"]["say"] == (
        "Gelen belgelere göre bu ay 1.254,43 TL harcandı; ayın günlerini kapsayan ekstre ya da döküm henüz gelmedi, "
        "karşılaştırmak için erken."
    )


# --- the payments due soon -------------------------------------------------------------------------------------------


def test_the_payments_due_within_a_week_are_the_calendars_the_user_sees_to(demo_client, demo_board):
    due = demo_board["due"]
    calendar = demo_client.get("/api/calendar", headers=bearer()).json()["items"]
    to_pay = {"card_due", "bill", "loan", "regular", "periodic"}  # not income, nor a card's later installments
    assert due["end"] == "2026-11-21"
    assert due["items"] == [i for i in calendar if i["day"] <= "2026-11-21" and i["kind"] in to_pay]
    [coffee] = due["items"]
    assert (coffee["title"], coffee["day"], coffee["amount"]) == ("Ornek Kahve", "2026-11-19", tl(18000))
    assert due["total"] == tl(18000)
    assert due["say"] == "Önümüzdeki 7 günde 1 ödeme var, toplam 180,00 TL (tahmini); ilki 19.11.2026: Ornek Kahve."
    assert due["link"] == link("calendar")


# --- the alerts ------------------------------------------------------------------------------------------------------


def test_a_finding_that_asks_for_attention_is_an_alert_that_leads_to_its_rows(demo_board):
    [fees] = demo_board["alerts"]["items"]
    assert (fees["kind"], fees["level"], fees["title"]) == ("finding", "warning", "Faiz ve banka ücretleri")
    assert fees["link"] == link("transactions", kind="interest_fee")
    assert demo_board["alerts"]["say"] == "Bir açık uyarı var: Faiz ve banka ücretleri."


def test_an_account_whose_forecast_goes_below_zero_is_an_alert(ws):
    add(ws, "teb.xls", teb.account_export(teb.running_rows(list(teb.ACCOUNT_MOVES))))
    [negative] = [a for a in alerts(ws, date(2026, 11, 15)) if a["kind"] == "negative"]
    assert (negative["level"], negative["account"]["id"], negative["count"]) == ("warning", TEB, 1)  # 40 days away
    assert negative["text"] == (
        "TEB Vadesiz TL 123456789: öngörüye göre bakiye 25.12.2026 günü (40 gün sonra) -146,03 TL olacak."
    )
    assert negative["link"] == link("forecast", TEB)


def test_unreadable_documents_and_a_readers_format_alarm_are_alerts_as_the_to_do_list_has_them(ws):
    [first] = add(ws, "bozuk.zip", b"PK\x03\x04yarim kalmis").stored
    [second] = add(ws, "baska.zip", b"PK\x03\x04o da yarim").stored
    assert first.status is second.status is DocumentStatus.UNREADABLE
    reader = registry.find("garanti.bonus_card")
    assert reader is not None
    with ws.db() as db:
        events.append(db, FORMAT_ALARM, "c" * 64, parser=reader.id, version=registry.version_of(reader))
        events.append(db, FORMAT_ALARM, "d" * 64, parser=reader.id, version="0")  # the reader's older version
    unreadable, alarm = alerts(ws)
    assert (unreadable["kind"], unreadable["count"]) == ("unreadable", 2)
    assert unreadable["link"] == link("documents", status="unreadable")
    assert (alarm["kind"], alarm["count"], alarm["link"]) == ("format_alarm", 1, link("system"))
    assert alarm["text"].startswith(f"{reader.name}: 1 belgede okuyucu bankanın biçimini tanımadı")
    todos.ignore(ws, f"document:{first.sha256}", True, Actor.USER)  # taken off the to-do list: off the alerts too
    assert [(a["kind"], a["count"]) for a in alerts(ws)] == [("unreadable", 1), ("format_alarm", 1)]


def test_a_stopped_mail_intake_and_a_failed_backup_are_critical_alerts(ws, mail):
    with ws.db() as db:
        state = mail_store.load(db, IMAP)
        state.stopped, state.last_error = True, "giriş reddedildi"
        mail_store.save(db, state)
        events.record(db, backup.FAILED, "2026-11-05", stage="backup", error="OSError")
    found = board(ws)["alerts"]
    assert [(a["kind"], a["level"]) for a in found["items"]] == [
        ("mail_stopped", "critical"),
        ("backup_failed", "critical"),
    ]
    assert found["say"] == "2 açık uyarı var, 2 tanesi kritik; ilki: E-posta alımı durdu."


def test_a_silent_browser_extension_is_an_alert_until_one_delivers_again(ws):
    first = bridge.pair(ws, "Chrome")
    with ws.db() as db:
        two_days = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        db.execute("UPDATE bridges SET last_seen = ? WHERE id = ?", (two_days, first.id))
    [silent] = alerts(ws)
    assert (silent["kind"], silent["level"]) == ("bridge_silent", "warning")
    assert silent["text"] == "Tarayıcı eklentisi 2 gündür görünmedi; yeni e-postalar tarayıcı açılınca gelir."
    bridge.pair(ws, "Başka bir Chrome")  # another extension, just seen
    assert alerts(ws) == []


# --- the closing, the documents' freshness and the to-do list --------------------------------------------------------


def test_the_last_seven_months_closing_leads_to_the_oldest_month_still_open(demo_board):
    closing = demo_board["closing"]
    months = closing["months"]
    assert [(m["month"], m["status"]) for m in months] == [
        ("2026-05", "closed"),
        ("2026-06", "closed"),
        ("2026-07", "missing"),
        ("2026-08", "closed"),
        ("2026-09", "closed"),
        ("2026-10", "closed"),
        ("2026-11", "running"),
    ]
    july = months[2]
    assert july["waiting"] == [
        {
            "account": {"id": TEB, "label": "TEB Vadesiz TL 123456789"},
            "waiting_for": "1–4 Temmuz hesap dökümü eksik",
        }
    ]
    # July's income is what its list shows, not a certain figure: the salary of the 1st is in the days it misses.
    assert (july["income"], july["left"]) == (tl(0), tl(-903999))
    assert july["income_note"] == (
        "gelir eksik olabilir: TEB Vadesiz TL 123456789 dökümü ayın tamamını kapsamıyor; maaş bu ay görünmüyor: "
        "dökümün kapsamadığı günlerde yatmış olabilir"
    )
    assert months[-2]["income_note"] == "hesap dökümlerindeki gelen para"
    assert (months[-1]["income"], months[-1]["link"]) == (None, link("month", "2026-11"))
    assert closing["say"] == "Temmuz 2026'da belge eksik; diğer 5 ay kapandı."
    assert closing["link"] == link("month", "2026-07")


def test_freshness_flags_a_card_whose_next_statement_is_late(garanti_ws):
    fresh = board(garanti_ws, date(2026, 11, 5))["freshness"]
    card, current = fresh["accounts"]  # the most behind first
    assert (card["account"]["id"], card["kind"], card["last"], card["expected"], card["late"]) == (
        CARD,
        "card_statement",
        "2026-10-05",
        "2026-11-05",
        False,
    )
    assert (current["kind"], current["expected"], current["note"]) == (
        "account_statement",
        None,
        "son döküm 31.10.2026",
    )
    assert fresh["link"] == link("accounts") and card["link"] == link("account", CARD)
    late = board(garanti_ws, date(2026, 11, 11))["freshness"]
    card = late["accounts"][0]
    assert (card["late"], card["behind"], card["note"]) == (
        True,
        37,
        "son ekstre 05.10.2026; sonraki ~05.11.2026 (gecikti)",
    )
    assert late["say"] == f"1 hesabın beklenen ekstresi gecikti: {card['account']['label']}."


def test_freshness_names_the_account_known_only_from_receipts(demo_board):
    fresh = demo_board["freshness"]
    behind = fresh["accounts"][0]
    assert (behind["account"]["id"], behind["kind"], behind["last"], behind["behind"]) == (
        CURRENT,
        "receipt",
        "2026-09-10",
        66,
    )
    assert behind["note"] == "yalnızca dekont ve banka bildirimlerinden biliniyor"
    teb_account = next(f for f in fresh["accounts"] if f["account"]["id"] == TEB)
    assert teb_account["missing"] == ["2026-07"]
    assert fresh["say"] == (
        "Geciken ekstre yok; en geride kalan Garanti BBVA Vadesiz TL 1234567, belgeleri 10.09.2026 tarihine kadar."
    )


def test_the_to_do_numbers_are_the_to_do_lists(demo_client, demo_board):
    listed = demo_client.get("/api/todos", headers=bearer()).json()
    todo = demo_board["todo"]
    assert todo["total"] == len(listed["items"]) == 2
    assert {k["kind"]: k["count"] for k in todo["kinds"]} == {k: n for k, n in listed["counts"].items() if n}
    assert todo["kinds"][0]["link"] == link("todo", "missing_documents")
    assert todo["say"] == "2 iş bekliyor: Eksik belge (1), İşlenmeyen belge (1)."
