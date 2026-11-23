"""The Pano screen's API (F06): the net worth, this month against the typical month, the payments due within a week,
the open alerts, the last seven months' closing, how fresh each account's documents are and the to-do count; every
card with its one-sentence comment and where it leads."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.analysis import Start
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import background, backup, bridge, now, outlook, todos
from iplikci.app.mail import IMAP
from iplikci.app.reading import FORMAT_ALARM
from iplikci.app.workspace import Busy, Workspace
from iplikci.domain.codes import Actor, DocumentStatus
from iplikci.fakes import HOLDER, Move, garanti, isbank, teb
from iplikci.forecast import AccountForecast, Forecast
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
    assert found["sayings"] == [
        {
            "situation": "no_data",
            "mood": "neutral",
            "reason": "Henüz belge yok; paranın nasıl gittiği bilinmiyor.",
            "quote": {"id": "dont_know", "lines": ["İsa Muhammed aşkına bilmiyorum."]},
        }
    ]


# --- the net worth ---------------------------------------------------------------------------------------------------


def test_the_net_worth_adds_up_what_stands_now_and_names_what_has_no_value(demo_client, demo_board):
    worth = demo_board["net_worth"]
    now = demo_client.get("/api/feed/now", headers=bearer()).json()
    # What stands now is the assets; the four cards' statement debts come off them.
    assert worth["assets"] == tl(sum(b["value"]["minor"] for b in now["balances"]))
    assert (worth["total"], worth["assets"], worth["debts"], worth["certainty"]) == (
        tl(17341962),
        tl(17872460),
        tl(530498),
        "confirmed",
    )
    assert [(p["account"]["id"], p["value"]) for p in worth["parts"]] == [
        (TEB, tl(17738260)),
        ("isbank-9753", tl(-163000)),
        ("qnb-1357", tl(-139699)),
        ("garanti-2468", tl(-136599)),
        ("garanti-yatirim-1234567-101", tl(134200)),
        ("teb-4321", tl(-91200)),
    ]
    assert worth["left_out"] == now["unknown"]  # the Garanti account known only from receipts
    euro, dollar, gold = worth["currencies"]
    # At the demo's made-up TCMB bulletin of its last business day: what the TL would buy, at the selling rate.
    assert (euro["amount"], euro["rate"], euro["note"]) == (
        {"minor": 307626, "currency": "EUR"},  # 173.419,62 / 56,3735
        "56.3735",
        "TCMB 13.11.2026 döviz satış kuruyla",
    )
    assert (dollar["amount"], dollar["rate_source"]) == ({"minor": 344932, "currency": "USD"}, "tcmb")
    assert (gold["currency"], gold["amount"], gold["note"]) == ("GR", None, "gram altının TL fiyatı belgelerde yok")
    assert worth["say"] == "Net varlığınız 173.419,62 TL; 1 hesabın TL değeri bilinmediği için toplama girmedi."
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
    # Only the cards' statements reach into November, 45% of its days so far: too few to compare with a typical month.
    assert demo_board["month"]["say"] == (
        "Gelen belgelere göre bu ay 1.931,98 TL harcandı; bugüne kadarki günlerin yalnızca %45'i belgelerle kapsandı, "
        "karşılaştırmak için erken."
    )
    assert demo_board["month"]["pace"]["note"].endswith(
        "sonra eklenir. Bugüne kadarki günlerin %45'i belgelerle kapsandı. Tipik ay: Nisan 2026 – Ekim 2026 "
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
    # The cards' statements due this week, at their full debt, and the coffee that comes every month.
    assert [(i["title"], i["day"], i["amount"]) for i in due["items"]] == [
        ("TEB Bonus •4321", "2026-11-15", tl(91200)),
        ("İş Bankası Maximum •9753", "2026-11-17", tl(163000)),
        ("Ornek Kahve", "2026-11-19", tl(18000)),
        ("Garanti Bonus •2468", "2026-11-20", tl(136599)),
    ]
    assert due["total"] == tl(408799)
    assert due["say"] == "Önümüzdeki 7 günde 4 ödeme var, toplam 4.087,99 TL (tahmini); ilki bugün: TEB Bonus •4321."
    assert due["link"] == link("calendar")


# --- the alerts ------------------------------------------------------------------------------------------------------


def test_a_finding_that_asks_for_attention_is_an_alert_that_leads_to_its_rows(demo_board):
    found = demo_board["alerts"]["items"]
    assert [(a["kind"], a["level"], a["title"]) for a in found] == [
        ("finding", "warning", "Borç nasıl değişti"),  # the cards opened since May carry their statements' debts
        ("finding", "warning", "En büyük alışkanlık"),
        ("finding", "warning", "Faiz ve banka ücretleri"),
    ]
    fees = found[-1]
    assert fees["link"] == link("transactions", kind="interest_fee")
    assert demo_board["alerts"]["say"] == "3 açık uyarı var; ilki: Borç nasıl değişti."


def test_an_account_whose_forecast_goes_below_zero_is_an_alert(ws):
    add(ws, "teb.xls", teb.account_export(teb.running_rows(list(teb.ACCOUNT_MOVES))))
    [negative] = [a for a in alerts(ws, date(2026, 11, 15)) if a["kind"] == "negative"]
    assert (negative["level"], negative["account"]["id"], negative["count"]) == ("warning", TEB, 1)  # 40 days away
    assert negative["text"] == (
        "TEB Vadesiz TL 123456789: öngörüye göre bakiye 25.12.2026 günü (40 gün sonra) -146,03 TL olacak."
    )
    assert negative["link"] == link("forecast", TEB)


def _falling_total(today: date, step: int = 100) -> outlook.CashFlow:
    """Two TL accounts whose total goes below zero though neither warns of itself: a deposit that stays at 1.000 TL and
    an overdraft account whose credit in use grows by step TL a day, with no income coming."""
    days = [today + timedelta(days=i) for i in range(60)]

    def account(id: str, balance: Decimal, step: Decimal, overdraft: bool) -> AccountForecast:
        start = Start(balance, balance, today, False, 0, today)
        path = [(day, balance + step * i) for i, day in enumerate(days)]
        return AccountForecast(id, id, start, path, [], None, None, [], overdraft=overdraft)

    accounts = [account("vadeli", Decimal(1000), Decimal(0), False), account("kmh", Decimal(0), Decimal(-step), True)]
    return outlook.CashFlow(Forecast(today, days[-1], accounts, [], [], []), {})


def test_a_total_the_foreign_currency_covers_says_so_and_is_no_alarm(ws, monkeypatch):
    # The income comes in another currency: the TL accounts fall, the money is in the foreign currency accounts.
    add(ws, "teb.xls", teb.account_export(teb.running_rows(list(teb.ACCOUNT_MOVES))))
    today = date(2026, 11, 15)
    monkeypatch.setattr(outlook, "cash_flow", lambda _a, day: _falling_total(day))
    monkeypatch.setattr(now, "cover", lambda _a: Decimal(6000))
    found = board(ws, today)
    [negative] = [a for a in found["alerts"]["items"] if a["kind"] == "negative"]
    assert (negative["level"], negative["title"]) == ("warning", "TL hesaplarının toplamı eksiye düşecek")
    assert negative["text"] == (
        "TL hesaplarınızın toplamı: öngörüye göre 26.11.2026 günü (11 gün sonra) -100,00 TL olacak. Öngörü TL "
        "hesaplarınıza düzenli bir gelir beklemiyor. 13.01.2027 gününe kadar en çok 4.900,00 TL eksik kalıyor; döviz "
        "ve yatırımlarınız bugünkü değeriyle 6.000,00 TL: eksiye düşmeden önce bir kısmını TL'ye çevirmeniz yeter."
    )
    first = found["sayings"][0]
    assert (first["situation"], first["mood"]) == ("going_negative", "warning")
    assert first["reason"].endswith("bir kısmını Türk lirasına çevirmeniz yeter.")
    monkeypatch.setattr(outlook, "cash_flow", lambda _a, day: _falling_total(day, step=200))  # in six days
    monkeypatch.setattr(now, "cover", lambda _a: Decimal(20000))
    soon = board(ws, today)  # within the week, and the money is there: a warning still
    assert [a["level"] for a in soon["alerts"]["items"] if a["kind"] == "negative"] == ["warning"]
    monkeypatch.setattr(now, "cover", lambda _a: Decimal(1000))
    short = board(ws, today)
    [negative] = [a for a in short["alerts"]["items"] if a["kind"] == "negative"]
    assert negative["level"] == "critical" and negative["text"].endswith("1.000,00 TL, hepsini karşılamıyor.")
    assert (short["sayings"][0]["mood"], short["sayings"][0]["reason"]) == (
        "critical",
        "Öngörüye göre Türk lirası hesaplarınızın toplamı 6 gün sonra eksiye düşecek.",
    )


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
            "waiting_for": "1–4 Temmuz için hesap dökümü eksik",
        }
    ]
    # July's income is what its list shows, not a certain figure: the salary of the 1st is in the days it misses.
    assert (july["income"], july["left"]) == (tl(0), tl(-1271998))
    assert july["income_note"] == (
        "gelir eksik olabilir: TEB Vadesiz TL 123456789 dökümü ayın tamamını kapsamıyor; maaş bu ay görünmüyor: "
        "dökümün kapsamadığı günlerde yatmış olabilir"
    )
    assert months[-2]["income_note"] == "hesap dökümlerindeki gelen para"
    assert (months[-1]["income"], months[-1]["link"]) == (None, link("month", "2026-11"))
    assert closing["say"] == "Temmuz 2026'da belge eksik; diğer 5 ay kapandı."
    assert closing["link"] == link("month", "2026-07")
    # A month a missing list holds open, a closed one and the running one promise no day to close.
    assert [m["closes_by"] for m in months] == [None] * 7


def test_a_month_waiting_for_a_cards_statement_says_by_when_it_closes(garanti_ws):
    def october(today: date) -> dict[str, object]:
        return next(m for m in board(garanti_ws, today)["closing"]["months"] if m["month"] == "2026-10")

    # The card's statement of 5 October leaves the month's last days to the next one, cut on 4 November as it prints.
    waiting = october(date(2026, 11, 3))
    assert (waiting["status"], waiting["closes_by"]) == ("waiting", "2026-11-04")
    assert [w["account"]["id"] for w in waiting["waiting"]] == [CARD]  # type: ignore[union-attr]
    # Days after that cut the statement is late: the month still waits for it, but no day is promised.
    late = october(date(2026, 11, 11))
    assert (late["status"], late["closes_by"]) == ("waiting", None)


def test_a_months_saving_holds_what_went_into_a_deposit_with_its_parts_leading_to_their_rows(ws):
    """İş Bankası's "Vadeli Hesap", filled from the current account, earns interest: what came into it is set aside,
    and the part's link lists the rows its saving adds up to."""
    add(ws, "vadeli.xls", isbank.deposit_xls())
    today = date(2026, 11, 21)
    november = next(m for m in board(ws, today)["closing"]["months"] if m["month"] == "2026-11")
    assert november["saving"] == tl(3002062)  # 30.000 moved in, 25,00 of interest less 4,38 of tax withheld
    rows = link("transactions", **{"from": "2026-11-01", "to": "2026-11-30", "saving": "deposit"})
    assert november["saving_parts"] == [
        {"part": "deposit", "category": "", "label": "Vadeli hesap", "amount": tl(3002062), "link": rows}
    ]
    response = client_for(ws, today).get("/api/transactions", params=rows["query"], headers=bearer())
    assert response.status_code == 200, response.text
    found = response.json()
    assert (len(found["rows"]), found["totals"]["saving"]) == (3, tl(3002062))


def test_freshness_flags_a_card_whose_next_statement_is_late(garanti_ws):
    fresh = board(garanti_ws, date(2026, 11, 5))["freshness"]
    card, current = fresh["accounts"]  # the most behind first
    assert (card["account"]["id"], card["kind"], card["last"], card["expected"], card["late"]) == (
        CARD,
        "card_statement",
        "2026-10-05",
        "2026-11-04",  # the next cut the statement prints, not the same day a month on
        False,
    )
    assert card["note"] == "son ekstre 05.10.2026; sonraki 04.11.2026"
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
        "son ekstre 05.10.2026; sonraki 04.11.2026 (gecikti)",
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


# --- İplikçi Nedim's word ---------------------------------------------------------------------------------------------


def test_nedim_says_the_last_closed_months_verdict_as_the_pano_does_and_then_its_fees(demo_board):
    october = next(m for m in demo_board["closing"]["months"] if m["month"] == "2026-10")
    assert october["status"] == "closed"
    # What is left is the month-end page's: the income less what went out and what was saved.
    minor = {key: october[key]["minor"] for key in ("income", "expense", "people", "debt", "out", "saving", "left")}
    assert minor["out"] == minor["expense"] + minor["people"] + minor["debt"]
    assert minor["left"] == minor["income"] - minor["out"] - minor["saving"]
    assert round(minor["left"] / minor["income"] * 100) == 37
    found = demo_board["sayings"]
    first = found[0]
    assert (first["situation"], first["mood"], first["reason"]) == (
        "good",
        "good",
        "Ekim 2026'da gelen paranın %37'si elde kaldı.",
    )
    good = [s for s in found if s["situation"] == "good"]
    assert {s["quote"]["id"] for s in good} == {"money_for_the_able", "never_say_no", "hide_your_goods"}
    fees = [s for s in found if s["situation"] == "fees"]
    assert {s["reason"] for s in fees} == {"Ekim 2026'da bankalara faiz ve ücret ödendi."}
    assert {s["mood"] for s in fees} == {"warning"}
    toilet = next(s["quote"] for s in fees if s["quote"]["id"] == "toilet")
    assert toilet["lines"] == [
        "Allah belasını versin büyük Ortadoğu'nun… Tuvalet mi canım bu? Küçük bin, büyük iki bin."
    ]
    assert [s["situation"] for s in found] == ["good"] * len(good) + ["fees"] * len(fees)
    assert len({s["quote"]["id"] for s in found}) == len(found)  # each line once


def test_nedim_tells_the_month_that_ended_before_its_cards_statement_comes_for_now(garanti_ws):
    """October waits for the card's statement that covers its last days: it is the month he speaks of, as the Pano
    tells it, and what is left is so far."""
    found = board(garanti_ws, date(2026, 11, 3))
    october = next(m for m in found["closing"]["months"] if m["month"] == "2026-10")
    assert october["status"] == "waiting"
    first = found["sayings"][0]
    assert (first["situation"], first["reason"]) == ("good", "Ekim 2026'da gelen paranın şimdilik %60'ı elde kaldı.")


def test_a_forecast_below_zero_is_what_nedim_says_first_and_the_extension_hears_the_same(ws):
    add(ws, "teb.xls", teb.account_export(teb.running_rows(list(teb.ACCOUNT_MOVES))))
    today = date(2026, 11, 15)
    first = board(ws, today)["sayings"][0]
    assert (first["situation"], first["mood"], first["reason"]) == (
        "going_negative",
        "warning",  # 40 days away: a week or less is critical
        "Öngörüye göre hesaplarınızdan biri 40 gün sonra eksiye düşecek.",
    )
    assert first["quote"]["id"] in {"linden_tree", "two_lindens", "dark_future", "bride"}  # nerves, a dark future
    extension = bridge.pair(ws, "Chrome")
    heard = client_for(ws, today).get("/api/bridge/sayings", headers={"Authorization": f"Bearer {extension.token}"})
    assert heard.status_code == 200, heard.text
    assert heard.json()["items"] == board(ws, today)["sayings"]
