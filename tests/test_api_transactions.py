"""The Transactions screen (F04): the rows filtered, sorted and paged with their totals, as CSV too; one row with
where it is printed and why it is what it is; corrections on one row or many, kept by fingerprint; kept views."""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from iplikci import demo, report
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.api.models import link_out
from iplikci.app.analysis import analyze
from iplikci.app.transactions import Filter, TransactionKind, rows_link
from iplikci.app.workspace import Workspace
from iplikci.fakes import teb

from conftest import add

TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"
OWN_PAGE = {"Origin": BASE, "X-Iplikci": "1"}
COFFEE = {"category": "Kafe & Kahve"}


def bearer() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def client_for(ws: Workspace) -> TestClient:
    return TestClient(create_app(Context(ws=ws, token=TOKEN, today=lambda: demo.AS_OF)), base_url=BASE)


def signed_in(client: TestClient) -> TestClient:
    url = client.post("/api/login-links", headers=bearer()).json()["url"]
    assert client.get(url, follow_redirects=False).status_code == 303
    return client


@pytest.fixture(scope="module")
def demo_home(tmp_path_factory):
    return demo.build(tmp_path_factory.mktemp("demo") / "veri")


@pytest.fixture
def client(demo_home) -> TestClient:
    return client_for(Workspace.load(demo_home))


@pytest.fixture
def own(tmp_path) -> TestClient:
    """A demo of its own, for the tests that change it."""
    return signed_in(client_for(Workspace.load(demo.build(tmp_path / "demo"))))


def coffee(client: TestClient) -> list[dict]:
    return client.get("/api/transactions", params=COFFEE, headers=bearer()).json()["rows"]


def test_the_list_pages_the_rows_newest_first_with_the_totals_of_all_of_them(client):
    found = client.get("/api/transactions", params={"limit": 10}, headers=bearer()).json()
    days = [r["day"] for r in found["rows"]]
    assert len(days) == 10 and days == sorted(days, reverse=True) and found["next"] == 10
    total = found["totals"]
    assert (total["count"], total["counted"], total["excluded"], total["provisional"]) == (93, 93, 0, 0)
    last = client.get("/api/transactions", params={"offset": 90, "limit": 10}, headers=bearer()).json()
    assert len(last["rows"]) == 3 and last["next"] is None


def test_the_filters_keep_a_category_a_merchant_or_words_and_the_totals_follow(client):
    rows = coffee(client)
    assert len(rows) == 10 and {r["category"] for r in rows} == {"Kafe & Kahve"}
    found = client.get("/api/transactions", params=COFFEE, headers=bearer()).json()["totals"]
    assert found["spent"]["minor"] == sum(r["amount"]["minor"] for r in rows) > 0
    by_merchant = client.get("/api/transactions", params={"merchant": "ornek kahve"}, headers=bearer()).json()
    assert by_merchant["totals"]["count"] == 10
    words = client.get("/api/transactions", params={"q": "kahve ornek"}, headers=bearer()).json()
    assert words["totals"]["count"] == 10
    cheapest = client.get(
        "/api/transactions", params={**COFFEE, "sort": "amount", "order": "asc"}, headers=bearer()
    ).json()["rows"]
    assert [r["amount"]["minor"] for r in cheapest] == sorted(r["amount"]["minor"] for r in rows)


def test_the_filters_take_the_names_the_other_screens_link_with(client):
    march = client.get("/api/transactions", params={"from": "2026-03-01", "to": "2026-03-31"}, headers=bearer())
    assert {r["day"][:7] for r in march.json()["rows"]} == {"2026-03"}
    fees = client.get("/api/transactions", params={"kind": "interest_fee"}, headers=bearer()).json()
    assert fees["totals"]["count"] == 11
    both = client.get("/api/transactions", params={"kind": ["interest_fee", "income"]}, headers=bearer()).json()
    assert both["totals"]["count"] == 20
    assert client.get("/api/transactions", params={"certainty": "provisional"}, headers=bearer()).json()["rows"] == []
    assert client.get("/api/transactions", params={"kind": "faks"}, headers=bearer()).status_code == 422


def test_a_filter_written_as_a_links_query_opens_the_list_on_the_same_rows(client):
    kinds = frozenset({TransactionKind.PURCHASE, TransactionKind.REFUND, TransactionKind.INTEREST_FEE})
    f = Filter(start=date(2026, 8, 1), end=date(2026, 10, 31), kinds=kinds, categories=frozenset({"Kafe & Kahve"}))
    link = link_out(rows_link(f))
    assert link is not None and link.screen == "transactions"
    assert link.query == {  # many values as a list, one as a string, in a steady order
        "from": "2026-08-01",
        "to": "2026-10-31",
        "kind": ["interest_fee", "purchase", "refund"],
        "category": "Kafe & Kahve",
    }
    found = client.get("/api/transactions", params=link.query, headers=bearer()).json()
    assert found["totals"]["count"] == 3 and {r["day"][:7] for r in found["rows"]} == {"2026-08", "2026-09", "2026-10"}


def test_the_csv_holds_every_row_the_filters_keep_for_turkish_excel(client):
    response = client.get("/api/transactions.csv", params=COFFEE, headers=bearer())
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="iplikci-islemler-2026-11-15.csv"' in response.headers["content-disposition"]
    text = response.content.decode("utf-8")
    lines = text.lstrip("﻿").splitlines()
    assert text.startswith("﻿") and lines[0].startswith("Tarih;Ay;Banka;Hesap") and len(lines) == 11
    assert ";Kafe & Kahve;" in lines[1] and "," in lines[1].split(";")[10]


def test_a_description_that_starts_like_a_formula_is_exported_as_text(ws, tmp_path):
    formula = '=HYPERLINK("http://ornek.example";"tikla")'  # a transfer's description, which its sender writes
    moves = [("20/10/2026", formula, "-50,00", "950,00"), ("21/10/2026", "ORNEK GELEN", "50,00", "1.000,00")]
    add(ws, "hareket.xls", teb.account_export(moves))
    text = client_for(ws).get("/api/transactions.csv", headers=bearer()).content.decode("utf-8")
    rows = text.lstrip("\ufeff").splitlines()[1:]
    assert any("'=HYPERLINK" in row for row in rows)
    assert any(";-50,00;" in row for row in rows) and "'-50,00" not in text  # money in stays a number
    a = analyze(ws)
    report.write_csv(a.dataset, tmp_path / "rapor.csv")
    assert "'=HYPERLINK" in (tmp_path / "rapor.csv").read_text(encoding="utf-8-sig")
    report.write_xlsx(a.dataset, tmp_path / "rapor.xlsx", a.insights, a.months)
    sheet = load_workbook(tmp_path / "rapor.xlsx")["İşlemler"]
    found = [c.data_type for line in sheet.iter_rows() for c in line if str(c.value).startswith("=HYPERLINK")]
    assert found and set(found) == {"s"}  # the merchant's and the description's cells, as text


def test_a_rows_detail_names_where_it_is_printed_and_why_it_is_what_it_is(client):
    row = coffee(client)[0]
    found = client.get(f"/api/transactions/{row['fingerprint']}", headers=bearer()).json()
    assert found["printed"]["document"] == row["document"] and found["printed"]["row"] is not None
    why = found["why"]
    assert (why["category"], why["rule"], why["layer"]) == ("transfer_rule", "KAHVE", "shipped")
    assert why["transfer"] == "rule"  # an account list's row, resolved by the rule that names its party
    assert (why["necessity"], why["necessity_layer"]) == ("category", "shipped")
    assert found["correctable"] and found["annotation"] is None and found["told"] == []


def test_a_receipts_row_says_no_statement_covers_its_days(client):
    rows = client.get("/api/transactions", params={"account": "garanti-1234567"}, headers=bearer()).json()["rows"]
    found = client.get(f"/api/transactions/{rows[0]['fingerprint']}", headers=bearer()).json()
    [told] = found["told"]
    assert told["status"] == "no_statement" and told["printed"]["kind"] == "receipt"


def test_an_unknown_fingerprint_is_not_found(client):
    assert client.get(f"/api/transactions/{'0' * 20}", headers=bearer()).status_code == 404
    assert client.get("/api/transactions/kahve", headers=bearer()).status_code == 422


def test_a_correction_on_one_row_is_kept_shown_and_given_back_to_the_rules(own):
    fp = coffee(own)[0]["fingerprint"]
    body = {"category": "market & gıda", "note": "deneme", "tags": ["ev"]}
    assert own.put(f"/api/transactions/{fp}/annotation", json=body, headers=bearer()).status_code == 403
    kept = own.put(f"/api/transactions/{fp}/annotation", json=body, headers=OWN_PAGE).json()
    assert (kept["category"], kept["note"], kept["tags"]) == ("Market & Gıda", "deneme", ["ev"])
    found = own.get(f"/api/transactions/{fp}", headers=bearer()).json()
    assert (found["row"]["category"], found["row"]["tags"]) == ("Market & Gıda", ["ev"])
    assert found["why"]["category"] == "user"
    back = own.put(f"/api/transactions/{fp}/annotation", json={"category": "", "necessity": ""}, headers=OWN_PAGE)
    assert back.json()["category"] == "" and back.json()["note"] == "deneme"
    assert own.get(f"/api/transactions/{fp}", headers=bearer()).json()["row"]["category"] == "Kafe & Kahve"
    gone = own.put(f"/api/transactions/{fp}/annotation", json={"note": "", "tags": []}, headers=OWN_PAGE)
    assert gone.status_code == 200 and gone.json() is None


def test_a_correction_the_rules_cannot_name_is_refused(own):
    fp = coffee(own)[0]["fingerprint"]
    wrong = own.put(f"/api/transactions/{fp}/annotation", json={"category": "Kafe ve Kahve"}, headers=OWN_PAGE)
    assert (wrong.status_code, wrong.json()["code"]) == (400, "correction_refused")
    assert "Kafe & Kahve" in wrong.json()["title"]  # the near miss is suggested
    nothing = own.put(f"/api/transactions/{fp}/annotation", json={}, headers=OWN_PAGE)
    assert nothing.status_code == 400


def test_the_selected_rows_get_one_category_or_more_tags(own):
    first, second = (r["fingerprint"] for r in coffee(own)[:2])
    body = {"fingerprints": [first, second, "f" * 20], "tags": ["iş", "toplantı"]}
    found = own.post("/api/transactions/bulk", json=body, headers=OWN_PAGE).json()
    assert found == {"changed": 2, "skipped": ["f" * 20]}
    tagged = own.get("/api/transactions", params={"tag": "toplantı"}, headers=bearer()).json()["rows"]
    assert {r["fingerprint"] for r in tagged} == {first, second}
    moved = own.post(
        "/api/transactions/bulk", json={"fingerprints": [first], "category": "Market & Gıda"}, headers=OWN_PAGE
    ).json()
    assert moved["changed"] == 1
    row = own.get(f"/api/transactions/{first}", headers=bearer()).json()["row"]
    assert (row["category"], row["tags"]) == ("Market & Gıda", ["iş", "toplantı"])
    assert own.post("/api/transactions/bulk", json={"fingerprints": [first]}, headers=OWN_PAGE).status_code == 400


def test_a_row_is_split_into_parts_listed_on_their_own_and_joined_again(own):
    row = coffee(own)[0]
    fp, minor = row["fingerprint"], row["amount"]["minor"]
    parts = [{"minor": minor - 1000, "category": "Kafe & Kahve"}, {"minor": 1000, "category": "market & gıda"}]
    kept = own.put(f"/api/transactions/{fp}/annotation", json={"parts": parts}, headers=OWN_PAGE)
    assert kept.status_code == 200
    listed = [r for r in own.get("/api/transactions", headers=bearer()).json()["rows"] if r["split_of"] == fp]
    assert [(r["fingerprint"], r["amount"]["minor"], r["category"]) for r in listed] == [
        (f"{fp}-1", minor - 1000, "Kafe & Kahve"),
        (f"{fp}-2", 1000, "Market & Gıda"),
    ]
    market = own.get("/api/transactions", params={"category": "Market & Gıda"}, headers=bearer()).json()
    assert f"{fp}-2" in {r["fingerprint"] for r in market["rows"]}
    # A part's detail is its row's, whole, with every part.
    found = own.get(f"/api/transactions/{fp}-2", headers=bearer()).json()
    assert (found["row"]["fingerprint"], found["row"]["amount"]["minor"], found["splittable"]) == (fp, minor, True)
    assert [p["fingerprint"] for p in found["parts"]] == [f"{fp}-1", f"{fp}-2"] and found["why"]["category"] != "split"
    # A category for many rows leaves a split one alone; its tags go on the row.
    bulk = own.post(
        "/api/transactions/bulk", json={"fingerprints": [f"{fp}-1"], "category": "Market & Gıda"}, headers=OWN_PAGE
    )
    assert bulk.json() == {"changed": 0, "skipped": [f"{fp}-1"]}
    tags = {"fingerprints": [f"{fp}-1", f"{fp}-2"], "tags": ["bölünmüş"]}
    assert own.post("/api/transactions/bulk", json=tags, headers=OWN_PAGE).json() == {"changed": 1, "skipped": []}
    assert own.get(f"/api/transactions/{fp}", headers=bearer()).json()["annotation"]["tags"] == ["bölünmüş"]
    joined = own.put(f"/api/transactions/{fp}-1/annotation", json={"parts": []}, headers=OWN_PAGE).json()
    assert joined["tags"] == ["bölünmüş"]
    assert not [r for r in own.get("/api/transactions", headers=bearer()).json()["rows"] if r["split_of"]]


def test_a_split_that_does_not_add_up_or_a_row_that_cannot_be_split_is_refused(own):
    row = coffee(own)[0]
    fp, minor = row["fingerprint"], row["amount"]["minor"]
    short = [{"minor": minor - 1000, "category": "Kafe & Kahve"}, {"minor": 999, "category": "Market & Gıda"}]
    refused = own.put(f"/api/transactions/{fp}/annotation", json={"parts": short}, headers=OWN_PAGE)
    assert (refused.status_code, refused.json()["code"]) == (400, "correction_refused")
    assert "toplamı" in refused.json()["title"]
    zero = [{"minor": 0, "category": "Kafe & Kahve"}, {"minor": minor, "category": "Market & Gıda"}]
    assert own.put(f"/api/transactions/{fp}/annotation", json={"parts": zero}, headers=OWN_PAGE).status_code == 422


def test_a_split_rows_category_is_in_its_parts_and_one_for_the_row_itself_is_refused(own):
    row = coffee(own)[0]
    fp, minor = row["fingerprint"], row["amount"]["minor"]
    url = f"/api/transactions/{fp}/annotation"
    parts = [{"minor": minor - 1000, "category": "Kafe & Kahve"}, {"minor": 1000, "category": "Market & Gıda"}]
    both = own.put(url, json={"parts": parts, "category": "Market & Gıda"}, headers=OWN_PAGE)
    assert (both.status_code, both.json()["code"]) == (400, "correction_refused")
    assert own.put(url, json={"parts": parts}, headers=OWN_PAGE).status_code == 200
    for change in ({"category": "Market & Gıda"}, {"necessity": "required"}):  # it would not show: the parts count
        refused = own.put(f"/api/transactions/{fp}-1/annotation", json=change, headers=OWN_PAGE)
        assert (refused.status_code, refused.json()["code"]) == (400, "correction_refused")
        assert "her parçada" in refused.json()["title"]
    noted = own.put(url, json={"note": "ikiye bölündü"}, headers=OWN_PAGE).json()
    assert [p["minor"] for p in noted["parts"]] == [minor - 1000, 1000]  # the split as the user made it
    joined = own.put(url, json={"parts": [], "category": "Market & Gıda"}, headers=OWN_PAGE).json()
    assert (joined["category"], joined["parts"], joined["note"]) == ("Market & Gıda", [], "ikiye bölündü")


def test_a_split_a_rule_change_no_longer_takes_is_previewed_flagged_and_put_on_the_to_do_list(own):
    row = coffee(own)[0]
    fp, minor = row["fingerprint"], row["amount"]["minor"]
    parts = [{"minor": minor - 1000, "category": "Kafe & Kahve"}, {"minor": 1000, "category": "Market & Gıda"}]
    assert own.put(f"/api/transactions/{fp}/annotation", json={"parts": parts}, headers=OWN_PAGE).status_code == 200
    # A rule counting the merchant as savings makes its rows a kind that is not split: the parts' move is shown too.
    pension = {
        "action": "merchant",
        "category": "Bireysel Emeklilik (BES)",
        "merchant": "Ornek Kahve",
        "patterns": ["ORNEK KAHVE"],
    }
    preview = own.post("/api/rules/categories/preview", json=pension, headers=bearer()).json()
    moves = {(m["before"], m["after"]): m["count"] for m in preview["moves"]}
    assert moves == {("Kafe & Kahve", "Bireysel Emeklilik (BES)"): 10, ("Market & Gıda", "Bireysel Emeklilik (BES)"): 1}
    assert own.put("/api/rules/categories", json=pension, headers=OWN_PAGE).json()["saved"]
    found = own.get(f"/api/transactions/{fp}-2", headers=bearer()).json()  # a part's address finds its row whole
    assert (found["row"]["fingerprint"], found["parts"], found["split_dropped"]) == (fp, [], True)
    assert [p["minor"] for p in found["annotation"]["parts"]] == [minor - 1000, 1000]
    listed = own.get("/api/todos", headers=bearer()).json()
    [todo] = [t for t in listed["items"] if t["kind"] == "split_dropped"]
    assert (todo["target"], todo["link"]["screen"], todo["link"]["id"]) == (fp, "transaction", fp)
    assert "2 parçaya" in todo["detail"] and "Birikim & yatırım" in todo["detail"]
    assert listed["counts"]["split_dropped"] == 1


def test_money_moved_between_own_accounts_cannot_be_split(ws):
    add(ws, "giden.xls", teb.account_export([("20/10/2026", "FAST GIDEN", "-500,00", "1.250,00")], number="111111111"))
    add(ws, "gelen.xls", teb.account_export([("20/10/2026", "FAST GELEN", "500,00", "500,00")], number="222222222"))
    client = signed_in(client_for(ws))
    [out, _] = client.get("/api/transactions", headers=bearer()).json()["rows"]
    assert client.get(f"/api/transactions/{out['fingerprint']}", headers=bearer()).json()["splittable"] is False
    halves = [{"minor": 25000, "category": "Giyim"}, {"minor": 25000, "category": "Giyim"}]
    moved = client.put(f"/api/transactions/{out['fingerprint']}/annotation", json={"parts": halves}, headers=OWN_PAGE)
    assert moved.status_code == 400 and "bölünür" in moved.json()["title"]


def test_views_are_kept_by_name_and_a_name_kept_again_replaces_its_view(own):
    assert own.get("/api/transactions/views", headers=bearer()).json() == []
    view = {"name": "Kahveler", "query": {"category": ["Kafe & Kahve"], "from": ["2026-01-01"]}}
    assert own.put("/api/transactions/views", json=view, headers=OWN_PAGE).json() == [view]
    again = {"name": "kahveler", "query": {"merchant": ["Ornek Kahve"]}}
    assert own.put("/api/transactions/views", json=again, headers=OWN_PAGE).json() == [again]
    assert own.delete("/api/transactions/views/kahveler", headers=OWN_PAGE).json() == []
    assert own.delete("/api/transactions/views/kahveler", headers=OWN_PAGE).status_code == 404


def test_a_statement_row_names_the_receipt_it_stands_for_and_an_own_transfer_its_pair(ws):
    day, paid = date(2026, 10, 15), Decimal("3250.00")
    add(ws, "kart-odeme.pdf", teb.card_payment_receipt(paid, day))
    add(ws, "teb.xls", teb.account_export([("15/10/2026", "KREDI KARTI ODEMESI", "-3.250,00", "1.750,00")]))
    add(ws, "giden.xls", teb.account_export([("20/10/2026", "FAST GIDEN", "-500,00", "1.250,00")], number="111111111"))
    add(ws, "gelen.xls", teb.account_export([("20/10/2026", "FAST GELEN", "500,00", "500,00")], number="222222222"))
    client = client_for(ws)
    rows = client.get("/api/transactions", headers=bearer()).json()["rows"]
    payment = next(r for r in rows if r["account"]["id"] == "teb-123456789")
    found = client.get(f"/api/transactions/{payment['fingerprint']}", headers=bearer()).json()
    assert [(t["status"], t["printed"]["kind"]) for t in found["told"]] == [("matched", "receipt")]
    out = next(r for r in rows if r["account"]["id"] == "teb-111111111")
    inc = next(r for r in rows if r["account"]["id"] == "teb-222222222")
    why = client.get(f"/api/transactions/{out['fingerprint']}", headers=bearer()).json()["why"]
    assert (why["transfer"], why["pair"]["fingerprint"]) == ("paired", inc["fingerprint"])
