from datetime import date
from decimal import Decimal

from openpyxl import load_workbook

from iplikci import month_end
from iplikci.analysis import Dataset
from iplikci.domain.codes import AccountType, Necessity, TransactionKind
from iplikci.domain.models import Account, Statement, Transaction
from iplikci.insights import interpret
from iplikci.report import build_payload, write_html, write_xlsx


def dataset() -> Dataset:
    account = Account("teb-2468", "TEB Bonus •2468", "TEB", AccountType.CREDIT_CARD, number="2468")
    t = Transaction(
        date=date(2026, 1, 5),
        description="</script><script>alert(1)</script>",
        amount=Decimal(100),
        kind=TransactionKind.PURCHASE,
        account="teb-2468",
        merchant="Kötü <b>",
        category="Diğer Harcamalar",
        group="Diğer",
        necessity=Necessity.UNKNOWN,
        source="a.pdf",
    )
    s = Statement(
        account="teb-2468",
        cut_date=date(2026, 1, 10),
        currency="TRY",
        source="a.pdf",
        previous=Decimal(0),
        total=Decimal(100),
        transactions=[t],
    )
    return Dataset(
        accounts={"teb-2468": account},
        statements=[s],
        transactions=[t],
        documents=[],
        groups=["Yeme & İçme", "Diğer"],
        categories={"Diğer Harcamalar": "Diğer"},
        coverage={"teb-2468": {"2026-01": 0.33}},
        warnings=[],
    )


def test_payload_shape():
    payload = build_payload(dataset(), {"documents": 1, "duplicates": 0})
    assert [lvl["name"] for lvl in payload["levels"]] == ["Gerekli", "İsteğe bağlı", "Gereksiz", "Belirsiz"]
    tx = payload["tx"][0]
    assert (tx["n"], tx["v"]) == (3, Decimal(100))  # Necessity.UNKNOWN
    assert payload["statements"][0]["ok"] and payload["statements"][0]["checks"] is None
    assert payload["groups"][-1] == {"name": "Diğer", "slot": 0}  # "Diğer" takes the neutral color
    ins = payload["insights"]
    assert ins["lastComplete"] and ins["window"] and isinstance(ins["findings"], list)
    assert (tx["r"], tx["x"]) == (None, None)  # not a regular payment, merchant not listed as ended


def test_statement_text_cannot_break_out_of_the_data_block(tmp_path):
    out = tmp_path / "rapor.html"
    write_html(build_payload(dataset(), {"documents": 1, "duplicates": 0}), out)
    html = out.read_text(encoding="utf-8")
    assert "<script>alert(1)" not in html
    assert html.count("</script>") == 2  # the data block and the report script, nothing from the data
    assert "default-src 'none'" in html  # no network access from the report


def test_the_closing_card_and_the_exports_carry_the_month_end(tmp_path):
    ds = dataset()
    ds.transactions[0].provisional = True
    ins = interpret(ds)
    months = month_end.build(ds, ins, today=date(2026, 2, 10))
    payload = build_payload(ds, {"documents": 1, "duplicates": 0}, ins, months)
    january, february = payload["closing"]
    assert (january["m"], january["status"], january["file"]) == ("2026-01", "bekleniyor", "ay-sonu/2026-01.html")
    assert january["open"] == ["TEB Bonus •2468: 11–31 Ocak ekstresi, kesim ~10.02"]
    assert february["status"] == "suruyor" and payload["tx"][0]["p"] == 1
    write_xlsx(ds, tmp_path / "islemler.xlsx", ins, months)
    wb = load_workbook(tmp_path / "islemler.xlsx")
    assert {"Ay Sonu", "Kapanış"} <= set(wb.sheetnames)
    assert wb["İşlemler"]["P1"].value == "Durum" and wb["İşlemler"]["P2"].value == "Geçici (ekstre bekleniyor)"
    assert [c.value for c in wb["Ay Sonu"]["A"][1:]] == ["2026-02", "2026-01"]
