"""The Değerlendirme screen's interpretation (F10): findings, steps, budget, habits, money in and out, what changed,
the regular income and the unusual movements. No filter changes it; every part says its window and numbers."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient

from iplikci import demo
from iplikci.analysis import Dataset
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import assessment
from iplikci.app.workspace import Workspace
from iplikci.domain.codes import TransactionKind, UnusualKind
from iplikci.domain.models import Transaction
from iplikci.insights import Insights

TOKEN = "deneme-belirteci"
TODAY = date(2026, 11, 15)


@pytest.fixture(scope="module")
def found(tmp_path_factory) -> dict:
    ws = Workspace.load(demo.build(tmp_path_factory.mktemp("demo") / "veri"))
    client = TestClient(
        create_app(Context(ws=ws, token=TOKEN, today=lambda: demo.AS_OF)), base_url="http://127.0.0.1:8643"
    )
    response = client.get("/api/insights", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    return response.json()


def test_the_interpretation_names_its_window_of_complete_months(found):
    window = found["window"]
    assert window["last_complete"] == "2026-10" and window["months"][-1] == "2026-10"
    assert "2026-07" not in window["months"]  # the month no document covers in full is no complete month


def test_findings_say_their_tone_and_lead_to_the_rows_they_rest_on(found):
    fees = next(f for f in found["findings"] if f["link"]["query"].get("kind") == "interest_fee")
    assert fees["tone"] == "attention" and "9 ayda" in fees["text"]
    assert {f["tone"] for f in found["findings"]} <= {"attention", "info", "good"}
    assert all(f["link"]["screen"] in ("transactions", "insights") for f in found["findings"])


def test_a_step_the_data_cannot_price_carries_no_monthly_amount(found):
    assert found["steps"] and all(s["monthly"] is None or s["monthly"]["minor"] > 0 for s in found["steps"])
    labels = [b["label"] for b in found["budget"]]
    assert labels[0] == "Düzenli gelir" and labels[-1] == "Ay sonunda kalan"


def test_habits_money_in_and_out_and_the_large_one_offs_come_with_their_numbers(found):
    fee = next(h for h in found["habits"] if h["by_category"])
    assert fee["status"] == "monthly" and fee["link"]["query"] == {"category": fee["category"]}
    flow = found["flow"]
    assert flow["income"]["minor"] == 4_000_000 and flow["months"] == found["window"]["months"]
    assert flow["left"]["minor"] == flow["income"]["minor"] - flow["expense"]["minor"]
    trend = found["trend"]
    assert [r["title"] for r in trend["large"]] == ["Teknosa"] and trend["threshold"]["minor"] >= 500_000
    assert [(i["name"], i["status"]) for i in found["income"]] == [("Örnek İşveren A.Ş.", "active")]


# --- the unusual movements -------------------------------------------------------------------------------------


def row(
    day: date, merchant: str, amount: str, kind=TransactionKind.PURCHASE, account="kart", category="Market"
) -> Transaction:
    t = Transaction(day, merchant, Decimal(amount), kind, account, merchant=merchant, category=category)
    t.fingerprint = f"{day:%Y%m%d}{merchant}{amount}{len(merchant)}"[:20].ljust(20, "0")
    return t


def flagged(*rows: Transaction) -> list[tuple[UnusualKind, str]]:
    ds = Dataset(accounts={}, statements=[], transactions=list(rows), documents=[], groups=[], categories={})
    ins = cast(Insights, SimpleNamespace(timeline=SimpleNamespace(window=[])))  # no window: large is 5.000 TL
    return [(u.kind, u.row.title) for u in assessment.unusual(ds, ins, TODAY)]


def test_an_amount_far_above_what_the_merchant_usually_takes_is_flagged_once_it_has_a_history():
    usual = [row(date(2026, m, 5), "ORNEKMARKET", "100") for m in range(5, 8)]  # three payments: a history
    assert flagged(*usual, row(date(2026, 10, 20), "ORNEKMARKET", "900")) == [
        (UnusualKind.UNUSUAL_AMOUNT, "ORNEKMARKET")
    ]
    assert flagged(*usual[:2], row(date(2026, 10, 20), "ORNEKMARKET", "900")) == []  # two are no history yet
    assert flagged(*usual, row(date(2026, 10, 20), "ORNEKMARKET", "550")) == []  # not 500 TL above the usual


def test_the_same_amount_at_the_same_merchant_on_the_same_day_is_a_possible_duplicate_never_dropped():
    twice = [row(date(2026, 10, 1), "ORNEKKAFE", "45"), row(date(2026, 10, 1), "ORNEKKAFE", "45")]
    assert flagged(*twice) == [(UnusualKind.POSSIBLE_DUPLICATE, "ORNEKKAFE")]
    old = [row(date(2026, 3, 1), "ORNEKKAFE", "45"), row(date(2026, 3, 1), "ORNEKKAFE", "45")]
    assert flagged(*old) == []  # older than the last three months: history


CARD_FEE = "Kart Aidatı & Ücretleri"


def fee(day: date, amount: str = "600", category: str = CARD_FEE, text: str = "YILLIK UYELIK") -> Transaction:
    return row(day, text, amount, kind=TransactionKind.INTEREST_FEE, category=category)


def test_a_large_amount_at_a_new_merchant_is_flagged_once_the_rows_go_back_far_enough_to_tell():
    history = row(date(2026, 5, 1), "ORNEKMARKET", "100")
    large = row(date(2026, 10, 3), "ORNEK MOBILYA", "6500")
    assert flagged(history, large) == [(UnusualKind.NEW_LARGE, "ORNEK MOBILYA")]
    assert flagged(large) == []  # the first weeks of data: every merchant is new


def test_a_fee_the_account_did_not_charge_in_twelve_months_is_flagged_and_a_card_fee_may_be_refunded():
    history = row(date(2026, 5, 1), "ORNEKMARKET", "100")
    small = fee(date(2026, 10, 11), "4.43", "Transfer & İşlem Ücretleri", "FAST UCRETI")
    [found] = assessment.unusual(
        Dataset({}, [], [history, fee(date(2026, 10, 10)), small], [], [], {}),
        cast(Insights, SimpleNamespace(timeline=SimpleNamespace(window=[]))),
        TODAY,
    )
    assert (found.kind, found.row.title) == (UnusualKind.UNEXPECTED_FEE, "YILLIK UYELIK")
    assert "son 12 ayda" in found.text and "iadesini isteyebilirsiniz" in found.text
    assert flagged(history, fee(date(2026, 1, 10)), fee(date(2026, 10, 10))) == []  # charged within the year
    year_ago = fee(date(2025, 9, 10))  # last year's: the yearly fee again, which may be refunded again
    assert flagged(year_ago, fee(date(2026, 10, 10))) == [(UnusualKind.UNEXPECTED_FEE, "YILLIK UYELIK")]
    assert flagged(fee(date(2026, 10, 10))) == []  # no history on the account: nothing to compare with
