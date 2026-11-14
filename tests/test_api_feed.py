"""The Akış screen's API (F05): the event log a page at a time with what each event concerns now and where it leads,
and what stands now: the balances as far as the documents tell, the cards, the month's pace and the next 14 days."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import background, feed
from iplikci.app.workspace import Busy, Workspace
from iplikci.fakes import HOLDER, Move, garanti, teb
from iplikci.storage import events

from conftest import add

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
CURRENT = "garanti-1234567"  # the Garanti current account of the fake documents
CARD = "garanti-1234"  # the Garanti Bonus card they pay


def bearer(token: str = TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def tl(minor: int, currency: str = "TRY") -> dict[str, object]:
    return {"minor": minor, "currency": currency}


def client_for(ws: Workspace, today: date = date(2026, 11, 5)) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN, today=lambda: today)), base_url=BASE)


def log(ws: Workspace, *found: tuple[str, str, dict[str, object]]) -> None:
    with ws.db() as db:
        for kind, target, detail in found:
            events.append(db, kind, target, **detail)


def page(client: TestClient, **params: object) -> dict[str, object]:
    response = client.get("/api/feed", params=params, headers=bearer())
    assert response.status_code == 200, response.text
    return response.json()


def kinds(found: dict[str, object]) -> list[str]:
    return [item["kind"] for item in found["items"]]  # type: ignore[index]


# --- the Garanti account and its card, as the fake documents lay them out -----------------------------------------


def rent_receipt() -> bytes:
    """A FAST receipt of 3 November, after the October list: the rent and its fee wait for the next list."""
    body = garanti.fast_body("KASIM KİRA", "VELİ ÖRNEKSOY")
    return garanti.receipt(
        "HESAPTAN FAST", "106/1234567", HOLDER, body, "- 1.250,00 TL", date(2026, 11, 3), "10.15.42.000009"
    )


def november_list() -> bytes:
    """The November list: it shows the rent the receipt told of, its fee within the same row."""
    moves = [Move(date(2026, 11, 3), "FAST123456789-VELİ ÖRNEKSOY-KASIM KİRA", Decimal(-1250))]
    return garanti.account_xls(moves, opening=Decimal("23946.70"), period=(date(2026, 11, 1), date(2026, 11, 30)))


@pytest.fixture
def garanti_ws(ws: Workspace) -> Workspace:
    """The October list of the current account and the card's statement; the first analysis only takes note."""
    add(ws, "ekim.xls", garanti.account_xls())
    add(ws, "ekstre.pdf", garanti.bonus_statement())
    background.refresh(ws, date(2026, 11, 5))
    return ws


@pytest.fixture
def receipt_ws(garanti_ws: Workspace) -> Workspace:
    """Then the rent's receipt: its rows are new, and provisional."""
    add(garanti_ws, "dekont.pdf", rent_receipt())
    background.refresh(garanti_ws, date(2026, 11, 5))
    return garanti_ws


# --- the gate --------------------------------------------------------------------------------------------------------


def test_the_feed_needs_a_session_or_the_token_and_says_when_the_documents_are_busy(ws, monkeypatch):
    context = Context(ws=ws, token=TOKEN)
    client = TestClient(create_app(context), base_url=BASE)
    assert client.get("/api/feed").status_code == 401
    assert client.get("/api/feed/now").status_code == 401
    assert client.get("/api/feed", headers=bearer()).json() == {"items": [], "next": None}

    def busy():
        raise Busy("başka bir işlem belgeleri işliyor; biraz sonra yeniden deneyin")

    monkeypatch.setattr(context.analysis, "get", busy)
    for path in ("/api/feed", "/api/feed/now"):
        refused = client.get(path, headers=bearer())
        assert (refused.status_code, refused.json()["code"]) == (503, "busy")


# --- the event log ---------------------------------------------------------------------------------------------------


def test_the_feed_comes_newest_first_a_page_at_a_time(ws):
    log(ws, *[("document.received", f"{n}" * 64, {"source": "upload"}) for n in range(1, 6)])
    client = client_for(ws)
    first = page(client, limit=2)
    assert [item["id"] for item in first["items"]] == [5, 4] and first["next"] == 4
    second = page(client, limit=2, before=first["next"])
    assert [item["id"] for item in second["items"]] == [3, 2] and second["next"] == 2
    last = page(client, limit=2, before=second["next"])
    assert [item["id"] for item in last["items"]] == [1] and last["next"] is None


def test_the_feed_narrows_to_kinds_by_their_code_or_their_family(ws):
    log(
        ws,
        ("document.received", "a" * 64, {"source": "email"}),
        ("document.unreadable", "a" * 64, {"parser": "", "reason": "şifreli PDF"}),
        ("month.closed", "2026-10", {}),
        ("transaction.created", "", {"count": 120, "from": "2026-01-02", "to": "2026-10-31"}),
    )
    client = client_for(ws)
    assert kinds(page(client, kind="document")) == ["document.unreadable", "document.received"]
    assert kinds(page(client, kind="document.")) == ["document.unreadable", "document.received"]
    assert kinds(page(client, kind="month.closed")) == ["month.closed"]
    assert kinds(page(client, kind=["month.closed", "transaction"])) == ["transaction.created", "month.closed"]
    refused = client.get("/api/feed", params={"kind": "Belge!"}, headers=bearer())
    assert (refused.status_code, refused.json()["code"]) == (400, "kind_invalid")


def test_a_narrow_filter_gives_a_short_page_and_where_to_go_on(ws, monkeypatch):
    monkeypatch.setattr(feed, "SCAN", 3)  # the events one page looks at
    log(ws, ("month.closed", "2026-01", {}), *[("document.received", "b" * 64, {}) for _ in range(4)])
    client = client_for(ws)
    first = page(client, account=CURRENT)
    assert first == {"items": [], "next": 3}  # three events looked at, none concerns the account, more to read
    second = page(client, account=CURRENT, before=first["next"])
    assert second == {"items": [], "next": None}  # the log's start


def test_an_events_details_come_typed_with_their_amounts_in_minor_units(ws):
    due = {
        "payment": "card_due",
        "title": "Garanti Bonus •1234",
        "account": CARD,
        "due": "2026-11-08",
        "days": 3,
        "amount": "3884.89",
        "minimum": "194.24",
    }
    negative = {"account": CURRENT, "title": "Garanti", "day": "2026-11-20", "days": 15, "balance": "-412.50"}
    unmatched = {
        "title": "ÖRNEK",
        "amount": "19.99",
        "account": "garanti-usd-1",
        "date": "2026-10-12",
        "currency": "USD",
    }
    log(
        ws,
        ("payment.due_soon", f"card_due|{CARD}|Garanti Bonus •1234|2026-11-08", due),
        ("balance.forecast_negative", f"{CURRENT}|2026-11-20", negative),
        ("evidence.unmatched", "c" * 20, unmatched),
        ("deposit.maturity_soon", "vadeli-1", {"amount": "çok", "account": "vadeli-1"}),  # a kind not known yet
    )
    items = page(client_for(ws))["items"]
    maturity, unseen, overdrawn, card = items
    assert card["label"] == "Son ödeme yaklaşıyor"
    assert (
        card["text"]
        == "Garanti Bonus •1234 · Kart son ödemesi: 3 gün sonra (08.11.2026), 3.884,89 TL. Asgari ödeme 194,24 TL."
    )
    assert card["account"] == {"id": CARD, "label": CARD}  # the analysis knows no such account: its id stands
    detail = card["detail"]
    assert (detail["amount"], detail["minimum"], detail["day"], detail["days"], detail["payment"]) == (
        tl(388489),
        tl(19424),
        "2026-11-08",
        3,
        "card_due",
    )
    assert card["link"] == {"screen": "calendar", "id": "2026-11-08", "query": {}}
    assert overdrawn["detail"]["balance"] == tl(-41250)  # below zero: overdrawn
    assert overdrawn["link"] == {"screen": "forecast", "id": CURRENT, "query": {}}
    assert unseen["detail"]["amount"] == tl(1999, "USD")  # no rate valued it: in the account's currency
    assert unseen["row"] is None and unseen["certainty"] is None  # the analysis has no such row
    assert (maturity["label"], maturity["link"], maturity["detail"]["amount"]) == ("deposit.maturity_soon", None, None)
    assert maturity["account"] == {"id": "vadeli-1", "label": "vadeli-1"}


def test_a_regular_payments_new_price_is_labelled_by_whether_it_rose_or_fell(ws):
    def price(old: str, new: str) -> dict[str, str]:
        return {"title": "Örnek Dernek", "old": old, "new": new, "since": "2026-10-01"}

    log(
        ws,
        ("subscription.price_changed", "a|2026-10-01", price("2400.00", "1900.00")),
        ("subscription.price_changed", "b|2026-10-01", price("4000.00", "4400.00")),
    )
    rose, fell = page(client_for(ws))["items"]
    assert (fell["label"], fell["detail"]["old"], fell["detail"]["new"]) == (
        "Düzenli ödeme ucuzladı",
        tl(240000),
        tl(190000),
    )
    assert fell["text"] == "Örnek Dernek: 01.10.2026 gününden beri 2.400,00 TL yerine 1.900,00 TL ödeniyor."
    assert rose["label"] == "Düzenli ödeme zammı"


def test_many_new_rows_at_once_are_one_event_that_leads_to_their_days(ws):
    log(ws, ("transaction.created", "", {"count": 120, "from": "2026-01-02", "to": "2026-10-31"}))
    [item] = page(client_for(ws))["items"]
    assert item["text"] == "02.01.2026 – 31.10.2026 arasında 120 yeni işlem."
    assert (item["detail"]["count"], item["detail"]["first"], item["detail"]["last"]) == (
        120,
        "2026-01-02",
        "2026-10-31",
    )
    assert item["detail"]["day"] is None
    assert item["link"] == {"screen": "transactions", "id": "", "query": {"from": "2026-01-02", "to": "2026-10-31"}}


def test_a_document_event_names_the_document_and_the_accounts_it_holds(garanti_ws):
    client = client_for(garanti_ws)
    processed = page(client, kind="document.processed")["items"]
    by_name = {item["document"]["name"]: item for item in processed}
    assert len(by_name) == 2
    for item in by_name.values():
        assert item["document"]["status"] == "processed"
        assert item["link"] == {"screen": "document", "id": item["target"], "query": {}}
    accounts = {item["account"]["id"] for item in processed}
    assert accounts == {CURRENT, CARD}
    card = next(item for item in processed if item["account"]["id"] == CARD)
    assert card["detail"]["document_kind"] == "card_statement" and card["detail"]["reader"]


def test_a_new_rows_event_shows_the_row_and_its_certainty_and_leads_to_it(receipt_ws):
    created = page(client_for(receipt_ws), kind="transaction.created")["items"]
    assert len(created) == 2  # the rent and its fee, from the receipt
    rent = next(item for item in created if item["row"]["amount"] == tl(125000))
    assert rent["certainty"] == "provisional" and rent["detail"]["provisional"] is True
    assert rent["account"]["id"] == CURRENT and rent["row"]["direction"] == "out" and rent["row"]["counted"]
    assert rent["row"]["fingerprint"] == rent["target"]
    assert rent["link"] == {"screen": "transaction", "id": rent["target"], "query": {}}
    assert rent["row"]["document"] and rent["row"]["day"] == "2026-11-03"


def test_a_receipts_row_a_statement_confirmed_since_leads_to_the_statements_row(receipt_ws):
    client = client_for(receipt_ws, date(2026, 12, 2))
    told = {item["target"]: item for item in page(client, kind="transaction.created")["items"]}
    add(receipt_ws, "kasim.xls", november_list())
    background.refresh(receipt_ws, date(2026, 12, 2))
    found = page(client, kind="transaction")["items"]
    confirmed = [item for item in found if item["kind"] == "transaction.confirmed"]
    assert {item["target"] for item in confirmed} == set(told)
    before = {
        item["target"]: item for item in found if item["target"] in told and item["kind"] == "transaction.created"
    }
    rent = next(item for item in before.values() if item["row"]["amount"] == tl(125000))
    assert rent["certainty"] == "confirmed" and rent["row"]["fingerprint"] != rent["target"]  # the list's own row
    assert rent["link"]["id"] == rent["row"]["fingerprint"] and rent["row"]["counted"]
    fee = next(item for item in before.values() if item is not rent)
    # The list prints the transfer without its fee: the receipt is confirmed, its fee row counts no more on its own.
    assert fee["certainty"] == "confirmed" and fee["row"]["fingerprint"] == fee["target"]
    assert not fee["row"]["counted"] and not fee["row"]["expense"]


def test_the_feed_narrows_to_an_accounts_events_and_to_a_rows_certainty(receipt_ws):
    client = client_for(receipt_ws)
    mine = page(client, account=CURRENT)["items"]
    assert {item["kind"] for item in mine} >= {"document.processed", "transaction.created"}
    assert all(item["account"] is None or item["account"]["id"] == CURRENT for item in mine)
    card = page(client, account=CARD)["items"]
    assert card and {item["kind"] for item in card} <= {"document.received", "document.processed"}
    provisional = page(client, certainty="provisional")["items"]
    assert len(provisional) == 2 and all(item["kind"] == "transaction.created" for item in provisional)
    assert page(client, certainty="excluded")["items"] == []


# --- what stands now -------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def demo_client(tmp_path_factory) -> TestClient:
    """The demo data folder's service, as on the day its baseline is taken."""
    ws = Workspace.load(demo.build(tmp_path_factory.mktemp("demo")))
    context = Context(ws=ws, token=TOKEN, ui=tmp_path_factory.mktemp("arayuz"), today=lambda: demo.AS_OF)
    return TestClient(create_app(context), base_url=BASE)


def test_what_stands_now_names_each_accounts_balance_as_the_documents_tell(demo_client):
    found = demo_client.get("/api/feed/now", headers=bearer()).json()
    assert found["today"] == "2026-11-15"
    current, brokerage = found["balances"]
    assert current["account"] == {"id": "teb-123456789", "label": "TEB Vadesiz TL 123456789"}
    assert (current["balance"], current["value"], current["stated"]) == (tl(17738260), tl(17738260), tl(17738260))
    assert (current["source"], current["on"], current["moves"], current["certainty"]) == (
        "statement",
        "2026-10-31",
        0,
        "confirmed",
    )
    assert current["note"] == "31.10.2026 dökümünde 177.382,60 TL"
    assert (brokerage["type"], brokerage["source"], brokerage["balance"]) == ("brokerage", "portfolio", tl(134200))
    assert found["unknown"] == [
        {
            "account": {"id": "garanti-1234567", "label": "Garanti BBVA Vadesiz TL 1234567"},
            "reason": "bakiyesi hiçbir belgede yazmıyor",  # known only from receipts
        }
    ]
    # The four cards, each with its newest statement's debt and minimum, newest cut first.
    assert [(c["account"]["id"], c["cut"], c["total"], c["minimum"]) for c in found["cards"]] == [
        ("garanti-2468", "2026-11-10", tl(136599), tl(54640)),
        ("qnb-1357", "2026-11-12", tl(139699), tl(55880)),
        ("teb-4321", "2026-11-05", tl(91200), tl(36480)),
        ("isbank-9753", "2026-11-07", tl(163000), tl(65200)),
    ]


def test_the_next_fourteen_days_are_the_calendars_items_up_to_their_last_day(demo_client):
    found = demo_client.get("/api/feed/now", headers=bearer()).json()
    calendar = demo_client.get("/api/calendar", headers=bearer()).json()
    assert found["end"] == "2026-11-28"
    assert found["upcoming"] == [item for item in calendar["items"] if item["day"] <= "2026-11-28"]
    assert found["upcoming"] and all("2026-11-15" <= item["day"] for item in found["upcoming"])


def test_a_balance_moved_by_receipts_after_its_list_is_provisional_and_says_so(receipt_ws):
    found = client_for(receipt_ws).get("/api/feed/now", headers=bearer()).json()
    [current] = found["balances"]
    assert (current["stated"], current["balance"], current["moves"], current["through"]) == (
        tl(2394670),
        tl(2269227),  # the rent and its fee came after the list
        2,
        "2026-11-03",
    )
    assert current["certainty"] == "provisional"
    assert current["note"] == (
        "31.10.2026 dökümünde 23.946,70 TL; sonraki 2 dekont ve bildirimle −1.254,43 TL (geçici: ekstre ya da döküm "
        "gelince kesinleşir)"
    )


def test_a_card_shows_its_statement_what_it_still_asks_and_the_period_it_is_in(garanti_ws):
    [card] = client_for(garanti_ws).get("/api/feed/now", headers=bearer()).json()["cards"]
    assert card["account"]["id"] == CARD and card["type"] == "credit_card"
    assert (card["cut"], card["total"], card["due"], card["minimum"], card["limit"]) == (
        "2026-10-05",
        tl(388489),
        "2026-10-15",
        tl(155396),  # under the period's debt
        tl(4500000),
    )
    # The list paid 3.250 TL on 10 October, after the cut: the statement still asks the rest.
    assert (card["paid"], card["debt"], card["certainty"]) == (tl(325000), tl(63489), "confirmed")
    assert card["last"] == {"start": "2026-09-06", "end": "2026-10-05", "spent": tl(288489), "rows": 11}
    # The period it is in ends on the next cut the statement prints.
    assert card["current"] == {"start": "2026-10-06", "end": "2026-11-04", "spent": tl(0), "rows": 0}
    assert card["note"] == (
        "05.10.2026 ekstresi 3.884,89 TL; sonra 3.250,00 TL ödendi; bu dönemin harcamaları 04.11.2026 kesimli "
        "ekstreyle gelir"
    )


def _monthly_list(months: range, until: date) -> bytes:
    """A TEB list from the first day of the first month to until: two shopping trips a month, 100 TL on the 5th and
    300 TL on the 20th, and 150 TL on the 5th of until's month."""
    moves = [Move(date(2026, 1, 1), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(5000))]
    for month in months:
        moves += [
            Move(date(2026, month, 5), "MIGROS ORNEK SUBE ISTANBUL", Decimal(-100)),
            Move(date(2026, month, 20), "MIGROS ORNEK SUBE ISTANBUL", Decimal(-300)),
        ]
    moves.append(Move(date(2026, until.month, 5), "MIGROS ORNEK SUBE ISTANBUL", Decimal(-150)))
    period = f"01/{months.start:02d}/2026 - {until:%d/%m/%Y}"
    return teb.account_export(teb.running_rows(moves), period=period)


def test_the_months_pace_compares_the_month_so_far_with_the_same_days_of_complete_months(ws):
    add(ws, "liste.xls", _monthly_list(range(1, 7), date(2026, 7, 10)))
    pace = client_for(ws, date(2026, 7, 10)).get("/api/feed/now", headers=bearer()).json()["pace"]
    assert (pace["month"], pace["partial"], pace["day"], pace["days"]) == ("2026-07", True, 10, 31)
    assert (pace["spent"], pace["provisional"]) == (tl(15000), tl(0))
    # Six complete months of 400 TL, 100 of it by the 10th.
    assert (pace["typical"], pace["by_day"]) == (tl(40000), tl(10000))
    assert pace["months"] == ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]
    assert pace["covered"] == 1.0
    assert pace["note"] == (
        "Temmuz 2026 sürüyor: rakamlar bugüne kadar gelen belgelerden; kart harcamaları ekstre kesiminden sonra "
        "eklenir. Bugüne kadarki günlerin %100'ü belgelerle kapsandı. Tipik ay: Ocak 2026 – Haziran 2026 arasındaki 6 "
        "tam ayın medyanı."
    )


def test_without_three_complete_months_there_is_no_typical_month_to_compare_with(ws):
    add(ws, "liste.xls", _monthly_list(range(1, 3), date(2026, 3, 10)))
    pace = client_for(ws, date(2026, 3, 10)).get("/api/feed/now", headers=bearer()).json()["pace"]
    assert (pace["typical"], pace["by_day"], pace["months"]) == (None, None, [])
    assert pace["note"].endswith("Tipik ay için en az 3 tam ay gerekiyor; şimdilik 2 tam ay var.")
