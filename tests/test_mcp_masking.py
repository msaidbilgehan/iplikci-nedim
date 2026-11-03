"""What the model sees with masking on (ADR-0011, `[privacy] mcp_masking`): no account number, IBAN or, on the second
level, person's name in any answer; the numbers and the identifiers stay exact."""

import json

import pytest

from iplikci.fakes import teb
from iplikci.mcp import masking
from iplikci.mcp.tools import TOOLS, Session

from conftest import add

ROWS = [
    ("25/01/2026", "VELİ ÖRNEKSOY Hesaba Havale TR330006100519786457841326", "-500,00", "380,00"),
    ("22/01/2026", "AYŞE YILMAZ den gelen havale", "200,00", "880,00"),
    ("20/01/2026", "KAHVECI DUKKAN", "-120,00", "680,00"),
    ("05/01/2026", "ORNEK SIRKET den gelen havale", "800,00", "800,00"),
]
NUMBERS = ("123456789", "TR33", "0006100519786457841326")
NAMES = ("VELİ", "Veli", "ÖRNEKSOY", "Örneksoy", "AYŞE", "Ayşe", "YILMAZ", "Yilmaz", "Yılmaz", "Kullanıcı", "KULLANICI")


def settings(ws, level: str) -> None:
    ws.layout.settings.write_text(
        f'[identity]\nnames = ["Örnek Kullanıcı"]\n\n[privacy]\nmcp_masking = "{level}"\n', encoding="utf-8"
    )


@pytest.fixture
def session(ws):
    add(ws, "ocak.xls", teb.account_export(ROWS))
    return Session(ws)


def every_answer(session) -> dict[str, str]:
    """What each tool that only reads answers when asked with no arguments."""
    return {tool.name: session.call(tool.name, {}).text for tool in TOOLS if tool.read_only}


def test_with_accounts_and_names_masked_no_answer_names_an_account_an_iban_or_a_person(session, ws):
    settings(ws, masking.NAMES)
    for tool, text in every_answer(session).items():
        for secret in (*NUMBERS, *NAMES):
            assert secret not in text, (tool, secret)
    rows = json.loads(session.call("transactions", {}).text)["rows"]
    assert {r["account"] for r in rows} == {"TEB Vadesiz TL •••A"}
    assert {r["merchant"] for r in rows} >= {"Kişi 1", "Ornek Sirket", "Kahveci Dukkan"}  # a company's name stays
    assert any(r.get("counterparty", "").startswith("Kişi ") for r in rows)


def test_with_accounts_masked_the_names_stay_and_with_masking_off_everything_does(session, ws):
    settings(ws, masking.ACCOUNTS)
    masked = every_answer(session)
    assert not any(number in text for text in masked.values() for number in NUMBERS)
    assert "AYŞE YILMAZ" in masked["transactions"] and "[IBAN]" in masked["transactions"]
    settings(ws, masking.OFF)
    plain = every_answer(session)["transactions"]
    assert "123456789" in plain and "TR330006100519786457841326" in plain


def test_masking_leaves_the_amounts_and_the_fingerprints_exact(session, ws):
    plain = json.loads(session.call("transactions", {}).text)["rows"]
    settings(ws, masking.NAMES)
    masked = json.loads(session.call("transactions", {}).text)["rows"]
    assert [(r["amount"], r["fingerprint"], r["date"]) for r in masked] == [
        (r["amount"], r["fingerprint"], r["date"]) for r in plain
    ]


def test_the_programs_own_identifiers_stay_whole_even_when_their_hex_digits_are_all_digits():
    mask = masking.Mask(masking.ACCOUNTS)
    digits = "12345678901234567890"  # a row's fingerprint, its twenty hex digits all of them digits
    sha = "1" * 64
    found = mask.apply(
        {
            "fingerprint": digits,
            "splitOf": digits,
            "fingerprints": [digits],
            "plan_id": digits[:16],
            "document": {"id": sha, "resource": f"iplikci://documents/{sha}/pages/2"},
            "description": f"EFT {digits}",
            "id": "1234567890",  # an identifier's field holding no identifier of the program's
        }
    )
    assert found["fingerprint"] == found["splitOf"] == digits and found["fingerprints"] == [digits]
    assert found["plan_id"] == digits[:16] and found["document"]["id"] == sha
    assert found["document"]["resource"] == f"iplikci://documents/{sha}/pages/2"
    assert found["description"] == f"EFT {masking.NUMBER}" and found["id"] == masking.NUMBER


def test_a_documents_text_is_masked_as_every_answer_is(session, ws):
    settings(ws, masking.NAMES)
    found = json.loads(session.call("search", {"text": "kahveci"}).text)
    sha = found["transactions"]["rows"][0]["document"]
    text = session.call("get_document", {"id": sha}).text
    for secret in (*NUMBERS, *NAMES):
        assert secret not in text, secret
    document = json.loads(text)
    assert document["document"]["id"] == sha and "[IBAN]" in document["text"]["pages"][0]["text"]


def test_an_error_the_model_reads_is_masked_too(session, ws):
    settings(ws, masking.NAMES)
    found = session.call("mark_ended", {"merchant": "Ayse Yilmazz", "month": "2026-01"})
    assert found.error and "Yılmaz" not in found.text and "YILMAZ" not in found.text


@pytest.mark.parametrize(
    ("name", "text", "masked"),
    [
        ("Ayşe Yılmaz", "AYŞE YILMAZ den gelen", "Kişi 1 den gelen"),
        ("Ayşe Yılmaz", "ayşe yılmaz'a", "Kişi 1'a"),
        ("Ali Er", "ALİŞVERİŞ ALİ ER", "ALİŞVERİŞ Kişi 1"),  # only whole words
    ],
)
def test_a_persons_name_is_found_whatever_its_letters_case(name, text, masked):
    from iplikci.analysis import Dataset

    ds = Dataset(accounts={}, statements=[], transactions=[], documents=[], groups=[], categories={})
    assert masking.mask_for(masking.NAMES, ds, [name]).text(text) == masked
