"""The MCP server: the JSON-RPC conversation and the tools on a synthetic workspace."""

import io
import json
from pathlib import Path

import pytest

from iplikci.demo import teb_export
from iplikci.mcp_server import PROTOCOL_VERSIONS, TOOLS, Server, serve

from conftest import FEBRUARY, JANUARY, bank_mail, put


def rpc(server, method, params=None, mid=1):
    return server.handle({"jsonrpc": "2.0", "id": mid, "method": method, **({"params": params} if params else {})})


def call(server, name, **arguments):
    reply = rpc(server, "tools/call", {"name": name, "arguments": arguments})["result"]
    text = reply["content"][0]["text"]
    return (json.loads(text) if not reply["isError"] else text), reply["isError"]


FILED = "TEB/Vadesiz Hesap TL 123456789/2026-01-01 - 2026-01-31 TEB Vadesiz TL 123456789 Hesap Hareketleri.xls"


@pytest.fixture
def server(ws):
    put(ws.documents / FILED, teb_export(JANUARY))
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
    by_kind, _ = call(server, "transactions", group_by="kind")
    assert {g["key"]: g["total"] for g in by_kind["groups"]} == {"harcama": 120.0, "gelir": -1000.0}
    january, _ = call(server, "transactions", **{"from": "2026-01", "to": "2026-01-10"})
    assert january["count"] == 1  # only the income on the 5th


def test_import_then_apply_files_a_copy(server, ws, tmp_path):
    original = put(
        tmp_path / "Downloads" / "subat.xls",
        teb_export([("10/02/2026", "MARKET ALISVERIS", "-80,00", "800,00")], period="01/02/2026 - 28/02/2026"),
    )
    imported, failed = call(server, "import_documents", paths=[str(original.parent)])
    assert not failed and imported["copied"] == ["subat.xls"] and imported["plan"]["changes"] == 1
    done, failed = call(server, "apply_inbox", plan_id=imported["plan"]["plan_id"])
    assert not failed and done["report"]["accountStatements"] == 2
    assert original.exists()  # the original stays where it was
    again, failed = call(server, "apply_inbox", plan_id=imported["plan"]["plan_id"])
    assert failed and "plan_inbox" in again


def test_fetch_email_without_an_account_says_how_to_set_it_up(server):
    text, failed = call(server, "fetch_email")
    assert failed and "uv run iplikci eposta --kur" in text
    status, _ = call(server, "status")
    assert status["email"]["configured"] is False


def test_fetch_email_copies_new_documents_and_plans_them(server, ws, mail):
    mail.messages[101] = bank_mail(FEBRUARY)
    mail.messages[102] = bank_mail(teb_export(JANUARY))  # already filed
    got, failed = call(server, "fetch_email")
    assert not failed and got["emails"] == 2 and got["copied"] == ["HesapHareketleri.xls"]
    assert got["plan"]["changes"] == 1
    assert got["byVerdict"] == {"gelen kutusuna kopyalandı": 1, "zaten var — atlandı": 1}
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
    assert (january["status"], account["status"], account["coveredDays"]) == ("kapandi", "kapandi", 31)
    assert (january["totals"]["expense"], january["totals"]["income"]) == (120.0, 1000.0)
    text, failed = call(server, "month_end", month="Ocak")
    assert failed and "'month' biçimi" in text
