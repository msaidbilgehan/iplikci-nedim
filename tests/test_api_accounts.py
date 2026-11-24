"""The Hesaplar screen's API (F07): the open accounts in their groups with assets and debts apart and the closed ones
apart, an account's page with its rows, daily balance, months, fees and what its type adds, the name the user gives an
account, and where the money went between the accounts."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import background, rebuild
from iplikci.app.workspace import Busy, Workspace
from iplikci.fakes import Move, garanti, isbank, teb
from iplikci.storage import aliases, audit

from conftest import add

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}
CURRENT = "garanti-1234567"  # the Garanti current account of the fake documents
CARD = "garanti-1234"  # the Garanti Bonus card it pays
TEB = "teb-123456789"


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def tl(minor: int, currency: str = "TRY") -> dict[str, object]:
    return {"minor": minor, "currency": currency}


def client_for(ws: Workspace, today: date = date(2026, 11, 5)) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN, today=lambda: today)), base_url=BASE)


def signed_in(client: TestClient) -> TestClient:
    url = client.post("/api/login-links", headers=bearer()).json()["url"]
    client.get(url, follow_redirects=False)
    return client


def get(client: TestClient, path: str, **params: object) -> dict[str, object]:
    response = client.get(path, params=params, headers=bearer())
    assert response.status_code == 200, response.text
    return response.json()


def by_id(found: dict[str, object]) -> dict[str, dict[str, object]]:
    """Every account of the list, open and closed, by its id."""
    listed = [a for g in found["groups"] for a in g["accounts"]] + found["closed"]  # type: ignore[union-attr]
    return {a["account"]["id"]: a for a in listed}


@pytest.fixture(scope="module")
def demo_client(tmp_path_factory) -> TestClient:
    """The demo data folder's service, as on the day its baseline is taken."""
    ws = Workspace.load(demo.build(tmp_path_factory.mktemp("demo")))
    context = Context(ws=ws, token=TOKEN, ui=tmp_path_factory.mktemp("arayuz"), today=lambda: demo.AS_OF)
    return TestClient(create_app(context), base_url=BASE)


@pytest.fixture
def garanti_ws(ws: Workspace) -> Workspace:
    """The Garanti current account's October list and the Bonus card's statement it pays."""
    add(ws, "ekim.xls", garanti.account_xls())
    add(ws, "ekstre.pdf", garanti.bonus_statement())
    background.refresh(ws, date(2026, 11, 5))
    return ws


def rent_receipt() -> bytes:
    """A FAST receipt of 3 November, after the October list: the rent and its fee wait for the next list."""
    body = garanti.fast_body("KASIM KİRA", "VELİ ÖRNEKSOY")
    return garanti.receipt(
        "HESAPTAN FAST", "106/1234567", garanti.HOLDER, body, "- 1.250,00 TL", date(2026, 11, 3), "10.15.42.000009"
    )


# --- the gate --------------------------------------------------------------------------------------------------------


def test_the_accounts_need_a_session_or_the_token_and_naming_one_the_services_own_pages(ws, monkeypatch):
    context = Context(ws=ws, token=TOKEN)
    client = TestClient(create_app(context), base_url=BASE)
    for path in ("/api/accounts", "/api/accounts/flows", "/api/accounts/coverage", f"/api/accounts/{TEB}"):
        assert client.get(path).status_code == 401
    assert client.put(f"/api/accounts/{TEB}/alias", json={"alias": "Maaş"}, headers=bearer()).status_code == 403

    def busy():
        raise Busy("başka bir işlem belgeleri işliyor; biraz sonra yeniden deneyin")

    monkeypatch.setattr(context.analysis, "get", busy)
    refused = client.get("/api/accounts", headers=bearer())
    assert (refused.status_code, refused.json()["code"]) == (503, "busy")


# --- the list --------------------------------------------------------------------------------------------------------


def test_the_open_accounts_come_in_their_groups_with_assets_and_debts_apart(garanti_ws):
    found = get(client_for(garanti_ws), "/api/accounts")
    cards, current = found["groups"]
    assert (cards["group"], current["group"]) == ("cards", "current")  # in F07's order
    assert (cards["assets"], cards["debts"], cards["total"]) == (tl(0), tl(63489), tl(-63489))
    assert (current["assets"], current["debts"], current["total"]) == (tl(2394670), tl(0), tl(2394670))
    # The same estimate as the dashboard's net worth: the list's balance less the card's debt since its payment.
    assert (found["assets"], found["debts"], found["total"]) == (tl(2394670), tl(63489), tl(2331181))
    [card] = cards["accounts"]
    assert (card["balance"], card["value"], card["day"], card["type"]) == (
        tl(-63489),
        tl(-63489),
        "2026-10-10",
        "credit_card",
    )
    assert found["closed"] == []


def test_an_account_shows_its_balance_its_newest_document_and_this_months_money(garanti_ws):
    add(garanti_ws, "dekont.pdf", rent_receipt())
    account = by_id(get(client_for(garanti_ws), "/api/accounts"))[CURRENT]
    assert account["account"] == {"id": CURRENT, "label": "Garanti BBVA Vadesiz TL 1234567"}
    assert (account["balance"], account["day"], account["certainty"]) == (tl(2269227), "2026-11-03", "provisional")
    fresh = account["freshness"]
    assert (fresh["kind"], fresh["last"], fresh["behind"], fresh["expected"]) == ("receipt", "2026-11-03", 2, None)
    assert fresh["document"] and fresh["name"]
    # November so far: the rent and its fee, from the receipt only.
    assert account["month"] == {
        "month": "2026-11",
        "money_in": tl(0),
        "money_out": tl(125443),
        "rows": 2,
        "provisional": 2,
        "note": "",
    }


def test_this_months_money_is_not_told_as_none_before_a_document_reaches_the_month(garanti_ws):
    account = by_id(get(client_for(garanti_ws), "/api/accounts"))[CURRENT]
    assert account["freshness"]["last"] == "2026-10-31"  # the list ends with October
    assert account["month"] == {
        "month": "2026-11",
        "money_in": tl(0),
        "money_out": tl(0),
        "rows": 0,
        "provisional": 0,
        "note": "bu ayın hareketleri henüz hiçbir belgede yok",
    }


def test_money_a_teb_account_got_from_an_own_account_whose_cuzdan_ends_before_leaves_that_account(ws):
    # The deposit's cüzdan ends on 20 November; on the 24th the current account's shows 40.050 TL coming in from
    # another own TEB account (TEB names the receiving account only). The deposit is the only TEB account that could
    # have paid it, its interest since included: the money left it and is counted once.
    deposit = teb.passbook(
        [Move(date(2026, 11, 19), "CEPTETEB Marifetli Hesap net faiz geliri %13", Decimal("11.00"))],
        opening=Decimal("39989.00"),
        number="222333444",
        period=(date(2026, 11, 10), date(2026, 11, 20)),
        kind="CEPTETEB Marifetli",
        rate="Değişken faizlidir.",
    )
    current = teb.passbook(
        [Move(date(2026, 11, 24), "111222333 no.lu hesaba gönderilmiştir.", Decimal("40050.00"))],
        opening=Decimal(0),
        number="111222333",
        period=(date(2026, 11, 1), date(2026, 11, 24)),
    )
    add(ws, "marifetli.pdf", deposit)
    add(ws, "vadesiz.pdf", current)
    found = get(client_for(ws, today=date(2026, 11, 24)), "/api/accounts")
    held = by_id(found)["teb-222333444"]
    assert (held["balance"], held["value"]) == (tl(0), tl(0))
    assert "24.11.2026 tarihinde 40.050,00 TL TEB Vadesiz TL 111222333 hesabına geçti" in held["note"]
    [untold] = found["untold"]  # the interest of the days after the cüzdan, which went on with the rest
    assert (untold["account"]["id"], untold["value"]) == ("teb-222333444", tl(5000))
    assert (found["assets"], found["total"]) == (tl(4005000), tl(4000000))


def test_a_notice_paying_out_more_than_the_list_shows_leaves_the_account_at_zero_and_the_totals_take_it_off(ws):
    # The list was taken in the morning with the account emptied; the afternoon's notice tells 7.500 TL sent on. The
    # bank paid it, so the money came in first, which no document tells: an FX sale or a transfer in sends no notice.
    moves = [
        Move(date(2026, 10, 5), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(3000)),
        Move(date(2026, 10, 6), "MIGROS ORNEK SUBE ISTANBUL", Decimal(-3000)),
    ]
    add(ws, "ekim.xls", garanti.account_xls(moves, opening=Decimal(0)))
    sent = datetime(2026, 10, 31, 16, 5, tzinfo=timezone(timedelta(hours=3)))
    add(ws, "bildirim.eml", garanti.transfer_notice(sent=sent, amount="7.500,00", note="KART ODEMESI"))
    client = client_for(ws)
    found = get(client, "/api/accounts")
    account = by_id(found)[CURRENT]
    assert (account["balance"], account["value"], account["certainty"]) == (tl(0), tl(0), "provisional")
    assert "arada belgelerde olmayan en az 7.500,00 TL girmiş olmalı" in account["note"]
    [untold] = found["untold"]
    assert (untold["account"]["id"], untold["value"], untold["day"]) == (CURRENT, tl(750000), "2026-10-31")
    assert (found["assets"], found["debts"], found["total"]) == (tl(0), tl(0), tl(-750000))  # no debt: money moved
    board = get(client, "/api/dashboard")
    worth = get(client, "/api/holdings")["worth"]
    assert board["net_worth"]["total"] == worth["total"] == found["total"]
    assert board["net_worth"]["untold"] == worth["untold"] == found["untold"]
    assert "belgelerde nereden geldiği görünmeyen 7.500,00 TL düşüldü" in board["net_worth"]["say"]
    assert all(s["situation"] != "in_debt" for s in board["sayings"])  # there is no debt to speak of
    [start] = get(client, "/api/forecast")["accounts"]
    assert start["start"]["balance"] == tl(0)


def test_an_accounts_day_after_its_list_stays_at_zero_when_a_notice_pays_out_more_than_it_held(ws):
    moves = [
        Move(date(2026, 10, 5), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(3000)),
        Move(date(2026, 10, 6), "MIGROS ORNEK SUBE ISTANBUL", Decimal(-3000)),
    ]
    add(ws, "ekim.xls", garanti.account_xls(moves, opening=Decimal(0)))
    sent = datetime(2026, 11, 2, 11, 30, tzinfo=timezone(timedelta(hours=3)))
    add(ws, "bildirim.eml", garanti.transfer_notice(sent=sent, amount="2.000,00", note="KART ODEMESI"))
    found = get(client_for(ws), f"/api/accounts/{CURRENT}")
    day = {p["day"]: p for p in found["curve"]}["2026-11-02"]
    assert (day["balance"], day["certainty"]) == (tl(0), "provisional")
    assert "bakiye 0 sayıldı" in found["curve_note"]


def test_an_account_whose_documents_stopped_long_before_the_others_is_closed_and_in_no_total(ws):
    old = [Move(date(2026, 1, 1), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(1000))]
    add(ws, "eski.xls", teb.account_export(teb.running_rows(old), number="111111111", period="01/01/2026 - 31/03/2026"))
    add(ws, "ekim.xls", garanti.account_xls())  # its documents end on 31 October: 214 days after the old one's
    found = get(client_for(ws), "/api/accounts")
    [gone] = found["closed"]
    assert (gone["account"]["id"], gone["closed"], gone["value"]) == ("teb-111111111", True, None)
    assert (gone["balance"], gone["day"]) == (tl(100000), "2026-03-31") and "toplamlara girmez" in gone["note"]
    assert "teb-111111111" not in {a["account"]["id"] for g in found["groups"] for a in g["accounts"]}
    assert found["assets"] == tl(2394670)  # the Garanti list's only


def test_the_coverage_gives_each_accounts_months_as_its_statements_cover_them_the_open_accounts_first(ws):
    old = [Move(date(2026, 1, 1), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(1000))]
    add(ws, "eski.xls", teb.account_export(teb.running_rows(old), number="111111111", period="01/01/2026 - 15/03/2026"))
    add(ws, "ekim.xls", garanti.account_xls())  # 1–31 October
    found = get(client_for(ws), "/api/accounts/coverage")
    assert found["months"] == [f"2026-{m:02d}" for m in range(1, 11)]  # the first covered month to the last
    current, gone = found["accounts"]
    assert (current["account"]["id"], current["closed"]) == (CURRENT, False)
    assert current["shares"] == ["0"] * 9 + ["1"]
    assert current["link"] == {"screen": "account", "id": CURRENT, "query": {}}
    assert (gone["account"]["id"], gone["closed"]) == ("teb-111111111", True)
    assert gone["shares"] == ["1", "1", "0.484"] + ["0"] * 7  # 15 of March's 31 days


def test_receipts_alone_cover_no_month(ws):
    add(ws, "dekont.pdf", rent_receipt())
    assert get(client_for(ws), "/api/accounts/coverage") == {"months": [], "accounts": []}


# --- an account's page -----------------------------------------------------------------------------------------------


def test_a_current_accounts_page_has_its_daily_balance_its_months_and_regular_payments(demo_client):
    found = get(demo_client, f"/api/accounts/{TEB}")
    curve = {p["day"]: p for p in found["curve"]}
    assert curve["2026-01-01"]["balance"] == tl(4000000) and curve["2026-10-31"]["balance"] == tl(17738260)
    assert "2026-07-02" not in curve  # the days no list covers are left blank, never filled in
    assert all(p["certainty"] == "confirmed" for p in found["curve"])
    assert found["curve_note"] == "Gün sonu bakiyeleri hesap dökümlerinden."
    september = next(m for m in found["months"] if m["month"] == "2026-09")
    # September's money out carries the TEB card's payment of 738 TL.
    assert (september["money_in"], september["money_out"], september["complete"]) == (tl(4000000), tl(2066599), True)
    assert found["months"][-1]["month"] == "2026-11" and not found["months"][-1]["complete"]
    assert found["fees"]["categories"] == [{"category": "Transfer & İşlem Ücretleri", "amount": tl(7200)}]
    assert "2026-07" not in found["fees"]["months"]  # an incomplete month is no part of the window
    assert "Spotify" in {p["payee"] for p in found["payments"]}
    assert [p["payee"] for p in found["income"]] == ["Örnek İşveren A.Ş."]
    assert (found["card"], found["overdraft"], found["holding"], found["loan"]) == (None, None, None, None)


def test_an_accounts_rows_come_a_page_at_a_time_newest_first(demo_client):
    first = get(demo_client, f"/api/accounts/{TEB}", limit=3)
    assert (
        len(first["rows"]) == 3 and first["next"] == 3 and first["totals"]["count"] == 94
    )  # with the TEB card's five payments
    days = [r["day"] for r in first["rows"]]
    assert days == sorted(days, reverse=True) and {r["account"]["id"] for r in first["rows"]} == {TEB}
    second = get(demo_client, f"/api/accounts/{TEB}", limit=3, offset=3)
    assert second["offset"] == 3 and second["rows"][0]["day"] <= days[-1]


def test_a_card_page_shows_its_statements_how_each_was_paid_and_its_installments(garanti_ws):
    card = get(client_for(garanti_ws), f"/api/accounts/{CARD}")["card"]
    [statement] = card["statements"]
    assert (statement["cut"], statement["start"], statement["total"], statement["due"]) == (
        "2026-10-05",
        "2026-09-06",
        tl(388489),
        "2026-10-15",
    )
    assert (statement["limit"], statement["minimum"], statement["verified"]) == (tl(4500000), tl(155396), True)
    # 3.250 TL paid on 10 October, before the due date passed: less than the balance, more than nothing.
    assert (statement["paid"], statement["status"]) == (tl(325000), "partial")
    assert card["statement"]["debt"] == tl(63489)
    [purchase] = card["installments"]  # 250 TL × 12, the 8th on this statement
    assert (purchase["number"], purchase["count"], purchase["remaining"]) == (8, 12, tl(100000))
    assert card["schedule"] == [
        {"month": "2026-11", "amount": tl(25000), "count": 1},
        {"month": "2026-12", "amount": tl(25000), "count": 1},
        {"month": "2027-01", "amount": tl(25000), "count": 1},
        {"month": "2027-02", "amount": tl(25000), "count": 1},
    ]
    assert card["left"] == tl(100000)


def test_the_newest_statement_before_its_due_date_is_still_open(ws):
    add(ws, "ekstre.pdf", garanti.bonus_statement())
    [statement] = get(client_for(ws, date(2026, 10, 10)), f"/api/accounts/{CARD}")["card"]["statements"]
    assert (statement["paid"], statement["status"]) == (tl(0), "open")


def test_an_account_that_went_below_zero_shows_its_days_below_zero(ws):
    moves = [
        Move(date(2026, 1, 1), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(1000)),
        Move(date(2026, 1, 10), "MIGROS ORNEK SUBE ISTANBUL", Decimal(-1500)),
        Move(date(2026, 1, 20), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(2000)),
    ]
    add(ws, "teb.xls", teb.account_export(teb.running_rows(moves), period="01/01/2026 - 31/01/2026"))
    found = get(client_for(ws, date(2026, 2, 3)), f"/api/accounts/{TEB}")
    overdraft = found["overdraft"]
    assert overdraft["days_below"] == 10  # 10–19 January, at -500 TL
    assert (overdraft["used"], overdraft["limit"], overdraft["window_end"]) == (tl(0), None, "2026-01-31")
    assert {p["day"]: p["balance"] for p in found["curve"]}["2026-01-15"] == tl(-50000)


def test_a_deposit_shows_its_principal_and_says_what_its_documents_do_not_print(ws):
    add(ws, "cuzdan.pdf", isbank.passbook())
    found = get(client_for(ws, date(2024, 2, 1)), "/api/accounts")
    [deposit] = [a for g in found["groups"] for a in g["accounts"] if a["type"] == "deposit"]
    page = get(client_for(ws, date(2024, 2, 1)), f"/api/accounts/{deposit['account']['id']}")["deposit"]
    assert page["principal"] == deposit["balance"] and page["principal"] is not None
    assert (page["rate"], page["maturity"], page["interest"]) == (None, None, None)
    assert "yazmıyor" in page["note"]


def test_a_brokerage_account_shows_its_portfolio_at_the_statements_market_value(demo_client):
    found = get(demo_client, "/api/accounts/garanti-yatirim-1234567-101")["brokerage"]
    [share] = found["securities"]
    assert (share["code"], share["quantity"], share["value"], share["as_of"]) == (
        "ORNEK",
        "20.00",
        tl(134200),
        "2026-10-30",
    )
    assert (found["worth"], found["as_of"]) == (tl(134200), "2026-10-30")


def test_an_unknown_account_is_not_found(demo_client):
    refused = demo_client.get("/api/accounts/yok-boyle", headers=bearer())
    assert (refused.status_code, refused.json()["code"]) == (404, "account_not_found")


# --- the name the user gives an account ------------------------------------------------------------------------------


def test_a_name_given_to_an_account_shows_on_the_screens_and_the_bank_label_stays(garanti_ws):
    client = signed_in(client_for(garanti_ws))
    named = client.put(f"/api/accounts/{CURRENT}/alias", json={"alias": "  Maaş   hesabı "}, headers=OWN_PAGE)
    assert named.status_code == 200
    assert named.json() == {"account": {"id": CURRENT, "label": "Maaş hesabı"}, "alias": "Maaş hesabı"}
    account = by_id(get(client, "/api/accounts"))[CURRENT]
    assert (account["account"]["label"], account["alias"], account["label"]) == (
        "Maaş hesabı",
        "Maaş hesabı",
        "Garanti BBVA Vadesiz TL 1234567",
    )
    [balance] = get(client, "/api/feed/now")["balances"]
    assert balance["account"] == {"id": CURRENT, "label": "Maaş hesabı"}
    with garanti_ws.db() as db:
        [entry] = audit.entries(db, aliases.SET)
    assert (entry.target, entry.detail) == (CURRENT, {})  # the account's id only, never the name
    cleared = client.put(f"/api/accounts/{CURRENT}/alias", json={"alias": ""}, headers=OWN_PAGE).json()
    assert cleared == {"account": {"id": CURRENT, "label": "Garanti BBVA Vadesiz TL 1234567"}, "alias": ""}
    with garanti_ws.db() as db:
        assert aliases.every(db) == {} and len(audit.entries(db, aliases.REMOVED)) == 1


def test_a_name_too_long_or_for_no_account_is_refused(garanti_ws):
    client = signed_in(client_for(garanti_ws))
    long = client.put(f"/api/accounts/{CURRENT}/alias", json={"alias": "x" * 61}, headers=OWN_PAGE)
    assert (long.status_code, long.json()["code"]) == (400, "alias_refused")
    unknown = client.put("/api/accounts/yok-boyle/alias", json={"alias": "Kumbara"}, headers=OWN_PAGE)
    assert (unknown.status_code, unknown.json()["code"]) == (404, "account_not_found")


def test_the_names_given_to_accounts_survive_the_rebuild_and_older_dumps_still_load(garanti_ws):
    client = signed_in(client_for(garanti_ws))
    client.put(f"/api/accounts/{CURRENT}/alias", json={"alias": "Maaş hesabı"}, headers=OWN_PAGE)
    with garanti_ws.db() as db:
        primary = rebuild.export(db)
    again = rebuild.load(rebuild.dump(primary))
    assert [(a.account, a.alias) for a in again.aliases] == [(CURRENT, "Maaş hesabı")]
    older = rebuild.dump(primary).replace(f'"version": {rebuild.VERSION}', '"version": 3')
    assert rebuild.load(older).aliases == again.aliases  # a version 3 dump read back, its names as they are
    report = rebuild.check(garanti_ws, today=date(2026, 11, 5))
    assert report.ok, report.differences


# --- where the money went --------------------------------------------------------------------------------------------


def test_the_flow_joins_a_card_payment_to_the_card_it_paid(garanti_ws):
    found = get(client_for(garanti_ws), "/api/accounts/flows", **{"from": "2026-10-01", "to": "2026-10-31"})
    assert (found["start"], found["end"]) == ("2026-10-01", "2026-10-31")
    edges = {(e["source"], e["target"]): e for e in found["edges"]}
    payment = edges[(CURRENT, CARD)]
    assert (payment["amount"], payment["rows"], payment["kinds"]) == (tl(325000), 1, ["card_payment"])
    assert payment["link"]["screen"] == "transactions" and payment["link"]["query"]["from"] == "2026-10-01"
    nodes = {n["id"]: n for n in found["nodes"]}
    assert nodes[CARD]["account"]["id"] == CARD and nodes[CARD]["kind"] == "account"
    income = [e for e in found["edges"] if e["target"] == CURRENT and nodes[e["source"]]["kind"] == "income"]
    assert sum(e["amount"]["minor"] for e in income) >= 4000000  # the salary


def test_a_band_leads_to_the_rows_it_adds_up_its_spending_group_or_its_payer_alone(demo_client):
    found = get(demo_client, "/api/accounts/flows", **{"from": "2026-10-01", "to": "2026-10-31"})
    nodes = {n["id"]: n for n in found["nodes"]}
    spent = [e for e in found["edges"] if nodes[e["target"]]["kind"] == "spending"]
    came = [e for e in found["edges"] if nodes[e["source"]]["kind"] == "income"]
    assert len(spent) >= 2 and came
    for edge in spent:
        assert edge["link"]["query"]["group"] == nodes[edge["target"]]["name"]
        rows = get(demo_client, "/api/transactions", **edge["link"]["query"])
        assert rows["totals"]["spent"] == edge["amount"]  # the group's rows, not every purchase of the account
    for edge in came:
        rows = get(demo_client, "/api/transactions", **edge["link"]["query"])
        assert rows["totals"]["money_in"] == edge["amount"]


def test_a_transfer_between_own_accounts_flows_to_the_account_it_reached(ws):
    out = [
        Move(date(2026, 10, 1), "ÖRNEK İŞVEREN A.Ş. den gelen havale", Decimal(5000)),
        Move(date(2026, 10, 10), "ÖRNEK KULLANICI hesabına giden havale", Decimal(-1000)),
    ]
    into = [Move(date(2026, 10, 10), "ÖRNEK KULLANICI den gelen havale", Decimal(1000))]
    period = "01/10/2026 - 31/10/2026"
    add(ws, "a.xls", teb.account_export(teb.running_rows(out), period=period))
    add(ws, "b.xls", teb.account_export(teb.running_rows(into), number="222222222", period=period))
    found = get(client_for(ws), "/api/accounts/flows", **{"from": "2026-10-01", "to": "2026-10-31"})
    edges = {(e["source"], e["target"]): e for e in found["edges"]}
    assert edges[(TEB, "teb-222222222")]["amount"] == tl(100000)
    assert ("teb-222222222", TEB) not in edges  # told once, from the side the money left


def test_the_flow_looks_at_the_newest_complete_month_by_default_and_refuses_a_backward_window(demo_client):
    found = get(demo_client, "/api/accounts/flows")
    assert (found["start"], found["end"]) == ("2026-10-01", "2026-10-31")
    assert found["edges"][0]["amount"] == tl(4000000)  # the salary into the TEB account, the largest
    refused = demo_client.get(
        "/api/accounts/flows", params={"from": "2026-10-31", "to": "2026-10-01"}, headers=bearer()
    )
    assert (refused.status_code, refused.json()["code"]) == (400, "window_invalid")
