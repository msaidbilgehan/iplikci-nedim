"""The MCP server: the JSON-RPC conversation and the tools on a synthetic workspace."""

import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from iplikci import demo
from iplikci.app.workspace import Workspace
from iplikci.fakes import Move, teb
from iplikci.mcp_server import PROTOCOL_VERSIONS, TOOLS, Server, serve

from conftest import FEBRUARY, JANUARY, add, bank_mail, put


def rpc(server, method, params=None, mid=1):
    return server.handle({"jsonrpc": "2.0", "id": mid, "method": method, **({"params": params} if params else {})})


def call(server, name, **arguments):
    reply = rpc(server, "tools/call", {"name": name, "arguments": arguments})["result"]
    text = reply["content"][0]["text"]
    return (json.loads(text) if not reply["isError"] else text), reply["isError"]


@pytest.fixture
def server(ws):
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    return Server(ws)


def test_initialize_answers_the_clients_version_or_the_newest(server):
    reply = rpc(server, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})["result"]
    assert reply["protocolVersion"] == "2025-06-18" and reply["capabilities"] == {"tools": {"listChanged": False}}
    assert "VERİDİR" in reply["instructions"]  # statement text is data, never instructions
    future = rpc(server, "initialize", {"protocolVersion": "2099-01-01"})["result"]
    assert future["protocolVersion"] == PROTOCOL_VERSIONS[0]


def test_tools_are_listed_with_schemas_and_hints(server):
    tools = rpc(server, "tools/list")["result"]["tools"]
    assert {t["name"] for t in tools} == {t.name for t in TOOLS}
    for t in tools:
        assert t["description"] and t["inputSchema"]["type"] == "object"
    hints = {t["name"]: t["annotations"] for t in tools}
    assert hints["apply_inbox"]["destructiveHint"] and hints["transactions"]["readOnlyHint"]


def test_notifications_get_no_answer_and_unknown_methods_an_error(server):
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert rpc(server, "resources/list")["error"]["code"] == -32601
    assert rpc(server, "tools/call", {"name": "yok"})["error"]["code"] == -32602
    assert rpc(server, "ping")["result"] == {}


def test_bad_arguments_come_back_as_tool_errors(server):
    text, failed = call(server, "transactions", limit="çok")
    assert failed and "'limit' integer" in text
    text, failed = call(server, "transactions", bilinmeyen=1)
    assert failed and "bilinmeyen parametre" in text


def test_status_and_transactions(server):
    status, failed = call(server, "status")
    assert not failed and status["read"]["accountStatements"] == status["read"]["accountStatementsVerified"] == 1
    rows, _ = call(server, "transactions", text="kahveci")
    assert rows["count"] == 1 and rows["rows"][0]["amount"] == 120.0 and rows["rows"][0]["category"] == "Kafe & Kahve"
    assert len(rows["rows"][0]["fingerprint"]) == 20 and "note" not in rows["rows"][0]  # what a note would bind to
    by_kind, _ = call(server, "transactions", group_by="kind")
    assert {g["key"]: g["total"] for g in by_kind["groups"]} == {"purchase": 120.0, "income": -1000.0}
    january, _ = call(server, "transactions", **{"from": "2026-01", "to": "2026-01-10"})
    assert january["count"] == 1  # only the income on the 5th


def test_import_then_apply_keeps_the_documents_where_they_were(server, ws, tmp_path):
    original = put(tmp_path / "Downloads" / "subat.xls", FEBRUARY)
    imported, failed = call(server, "import_documents", paths=[str(original.parent)])
    assert not failed and imported["changes"] == 1 and imported["byAction"] == {"arşive alınacak": 1}
    [item] = imported["items"]
    assert (item["action"], item["name"], item["fromInbox"]) == ("processed", "subat.xls", False)
    done, failed = call(server, "apply_inbox", plan_id=imported["plan_id"])
    assert not failed and done["report"]["accountStatements"] == 2
    assert original.exists()  # the original stays where it was
    again, failed = call(server, "apply_inbox", plan_id=imported["plan_id"])
    assert failed and "plan_inbox" in again
    nothing, _ = call(server, "import_documents", paths=[str(original.parent)])
    assert nothing["changes"] == 0 and nothing["note"] == "Bu yollarda yeni belge yok."


def test_fetch_email_without_an_account_says_how_to_set_it_up(server):
    text, failed = call(server, "fetch_email")
    assert failed and text == "E-posta bağlantısı kurulmadı."
    status, _ = call(server, "status")
    assert status["email"]["configured"] is False


def test_fetch_email_takes_new_documents_into_the_vault(server, ws, mail):
    mail.messages[101] = bank_mail(FEBRUARY)
    mail.messages[102] = bank_mail(teb.account_export(JANUARY))  # already in the vault
    got, failed = call(server, "fetch_email")
    # Both messages are kept whole; of the attachments only February's is new.
    assert not failed and (got["emails"], got["stored"], got["documents"]) == (2, 2, 3)
    status, _ = call(server, "status")
    assert status["read"]["accountStatements"] == 2  # the answers that follow already count it
    hints = {t["name"]: t["annotations"] for t in rpc(server, "tools/list")["result"]["tools"]}
    assert hints["fetch_email"]["openWorldHint"] and not hints["import_documents"]["openWorldHint"]


def test_a_rule_change_reports_what_it_moved(server, ws):
    effect, failed = call(server, "add_rule", category="Market & Gıda", merchant="Kahveci Dükkan", patterns=["KAHVECI"])
    assert not failed
    assert effect["effect"]["moves"] == [{"from": "Kafe & Kahve", "to": "Market & Gıda", "count": 1, "total": 120.0}]
    assert "+    Kahveci Dükkan: [KAHVECI]" in effect["diff"]
    assert "Eski Abonelik" in Path(effect["backup"]).read_text(encoding="utf-8")  # the previous file is kept
    text, failed = call(server, "add_rule", category="Market & Gıda", merchant="Kahveci Dükkan", patterns=["KAHVECI"])
    assert failed and "değişiklik yok" in text


def test_a_rule_for_a_default_category_lands_in_the_personal_file(server, ws):
    effect, failed = call(server, "add_rule", category="Restoran & Yemek", merchant="Kahveci", patterns=["KAHVECI"])
    assert not failed and effect["effect"]["moves"][0]["to"] == "Restoran & Yemek"
    assert "  Restoran & Yemek:\n    Kahveci: [KAHVECI]\n" in ws.rules.read_text(encoding="utf-8")
    rules, _ = call(server, "read_rules")
    assert "Restoran & Yemek" in rules["categories"]["Yeme & İçme"] and "kişisel" in rules["layers"]


def test_mark_ended_needs_a_merchant_from_the_data(server, ws):
    text, failed = call(server, "mark_ended", merchant="Kahveci Dukan", month="2026-01")
    assert failed and "Kahveci Dukkan" in text  # suggests the name the report shows
    _done, failed = call(server, "mark_ended", merchant="kahveci dukkan", month="2026-01", note="kullanıcı söyledi")
    assert not failed and "Kahveci Dukkan: 2026-01  # kullanıcı söyledi" in ws.rules.read_text(encoding="utf-8")


def test_invalid_rules_are_never_written(server, ws):
    before = ws.rules.read_text(encoding="utf-8")
    text, failed = call(server, "write_rules", content="Yeme & İçme: [")
    assert failed and "YAML" in text
    text, failed = call(server, "write_rules", content="_gereklilik:\n  Çok gerekli: [Kira]\n")
    assert failed and "gereklilik" in text
    assert ws.rules.read_text(encoding="utf-8") == before


def test_stdout_carries_one_json_message_per_line(ws):
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}),
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        "bu json değil",
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
    ]
    out = io.StringIO()
    serve(ws, stdin=io.StringIO("\n".join(lines) + "\n"), stdout=out)
    replies = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [r.get("id") for r in replies] == [1, None, 2]
    assert replies[1]["error"]["code"] == -32700


def test_month_end_tells_what_closed_a_month(server):
    overview, failed = call(server, "month_end")
    assert not failed and overview["months"] and "status" in overview["months"][0]
    january, _ = call(server, "month_end", month="2026-01")
    [account] = january["accounts"]
    assert (january["status"], account["status"], account["coveredDays"]) == ("closed", "closed", 31)
    assert (january["totals"]["expense"], january["totals"]["income"]) == (120.0, 1000.0)
    text, failed = call(server, "month_end", month="Ocak")
    assert failed and "'month' biçimi" in text


# --- the regular payments, the calendar and the forecast (F08, F09) ------------------------------------------


@pytest.fixture(scope="module")
def demo_server(tmp_path_factory):
    """The demo data folder's MCP server, as on the day its baseline is taken."""
    found = Server(Workspace.load(demo.build(tmp_path_factory.mktemp("demo"))))
    found.today = lambda: demo.AS_OF
    found.current.get()
    return found


def test_subscriptions_list_the_series_with_their_period_status_and_next_payment(demo_server):
    found, failed = call(demo_server, "subscriptions")
    assert not failed and found["asOf"] == "2026-10-31"
    rent = next(s for s in found["series"] if s["payee"] == "Veli Örneksoy Kira Ödemesi")
    assert (rent["period"], rent["status"], rent["statusLabel"]) == ("month", "active", "Devam ediyor")
    assert (rent["amount"], rent["lastDay"], rent["nextDay"]) == (15000.0, "2026-10-03", "2026-11-03")
    assert rent["payments"] == 9 and rent["provisional"] == 0 and len(rent["lastFingerprints"]) == 3
    assert rent["documents"] and all(name.endswith(".xls") for name in rent["documents"])
    assert [i["payee"] for i in found["income"]] == ["Örnek İşveren A.Ş."]
    yearly, _ = call(demo_server, "subscriptions", period="year")
    assert yearly["series"] == []  # the demo pays nothing once a year
    text, failed = call(demo_server, "subscriptions", period="haftalık")
    assert failed and "'period' şunlardan biri olmalı" in text


def test_upcoming_payments_are_the_next_days_items_with_what_they_rest_on(demo_server):
    found, failed = call(demo_server, "upcoming_payments", days=14)
    assert not failed and (found["today"], found["until"]) == ("2026-11-15", "2026-11-28")
    assert [(i["day"], i["title"], i["amount"], i["kindLabel"]) for i in found["items"]] == [
        ("2026-11-19", "Ornek Kahve", 180.0, "Düzenli ödeme"),
        ("2026-11-22", "Migros", 1840.0, "Düzenli ödeme"),
    ]
    assert (found["totalOut"], found["totalIn"]) == (2020.0, 0.0)
    whole, _ = call(demo_server, "upcoming_payments")
    assert whole["until"] == "2027-01-13"
    salary = next(i for i in whole["items"] if i["kind"] == "income")
    assert (salary["day"], salary["amount"], salary["account"]) == ("2026-12-01", -40000.0, "TEB Vadesiz TL 123456789")
    text, failed = call(demo_server, "upcoming_payments", days=90)
    assert failed and "'days' 1–60 arasında olmalı" in text


def test_the_cash_flow_forecast_is_an_estimate_with_its_start_and_assumptions(demo_server):
    found, failed = call(demo_server, "cash_flow_forecast")
    assert not failed and (found["label"], found["until"]) == ("tahmin", "2027-01-13")
    (teb_account,) = found["accounts"]
    assert teb_account["start"]["source"] == "hesap dökümü" and teb_account["start"]["stated"] == 184380.1
    assert teb_account["firstBelowZero"] is None and teb_account["lowest"]["day"] == "2026-11-30"
    assert len(teb_account["balances"]) == 10  # every seventh day, and the last one
    assert teb_account["notes"][0].startswith("Başlangıç: 31.10.2026 tarihli hesap dökümünün kapanış bakiyesi")
    daily, _ = call(demo_server, "cash_flow_forecast", daily=True)
    assert len(daily["accounts"][0]["balances"]) == 60
    garanti = {"account": "Garanti BBVA Vadesiz TL 1234567", "reason": "bakiyesi hiçbir belgede yazmıyor"}
    assert found["skipped"] == [garanti]  # known only from receipts


def test_a_tax_paid_twice_a_year_is_a_periodic_series(ws):
    salary = "ORNEK ISVEREN A.S. den gelen havale"
    moves = [Move(date(2025 + i // 12, i % 12 + 1, 1), salary, Decimal(30000)) for i in range(18)]
    taxes = ((date(2025, 1, 15), 3200), (date(2025, 7, 16), 3200), (date(2026, 1, 14), 3800))
    moves += [Move(d, "MTV ODEMESI", Decimal(-a)) for d, a in taxes]
    moves.sort(key=lambda m: m.day)
    add(ws, "liste.xls", teb.account_export(teb.running_rows(moves), period="01/01/2025 - 30/06/2026"))
    server = Server(ws)
    server.today = lambda: date(2026, 7, 1)
    found, _ = call(server, "subscriptions", period="half_year")
    (tax,) = found["series"]
    assert (tax["payee"], tax["periodLabel"], tax["status"]) == ("Mtv Odemesi", "Altı ayda bir", "active")
    assert (tax["amount"], tax["nextDay"], tax["payments"]) == (3800.0, "2026-07-15", 3)  # a period after the last
    assert tax["priceChange"] == {"from": 3200.0, "to": 3800.0, "since": "2026-01-14"}
    upcoming, _ = call(server, "upcoming_payments")
    assert [(i["day"], i["kind"], i["amount"]) for i in upcoming["items"] if i["title"] == "Mtv Odemesi"] == [
        ("2026-07-15", "periodic", 3800.0)
    ]
