"""The user's notes and corrections: bound to fingerprints, kept across readings, never lost when their row goes."""

from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from iplikci import forecast, month_end, report
from iplikci.analysis import CONFIRMED, Dataset, ReceiptLine, payments
from iplikci.app import annotate
from iplikci.app.analysis import analyze
from iplikci.app.rows import Rows
from iplikci.app.workspace import Workspace
from iplikci.categorize import Categorizer
from iplikci.cli import main
from iplikci.domain.codes import AccountType, Actor, CategoryReason, Necessity, TransactionKind, TransferStep
from iplikci.domain.fingerprint import Fingerprints, fingerprint
from iplikci.domain.models import Account, Statement, Transaction
from iplikci.fakes import teb
from iplikci.insights import habits, interpret, regular_payments, timeline
from iplikci.parsers import registry
from iplikci.settings.paths import HOME_ENV
from iplikci.storage import annotations, audit

from conftest import JANUARY, add

TWO_COFFEES = [  # two rows alike in everything: both real
    ("20/01/2026", "KAHVECI DUKKAN", "-120,00", "760,00"),
    ("20/01/2026", "KAHVECI DUKKAN", "-120,00", "880,00"),
    ("05/01/2026", "ORNEK SIRKET den gelen havale", "1.000,00", "1.000,00"),
]


def coffee(ws: Workspace, n: int = 0) -> Transaction:
    return [t for t in analyze(ws).dataset.transactions if t.merchant == "Kahveci Dukkan"][n]


def note(ws: Workspace, t: Transaction, **changes) -> annotations.Annotation | None:
    with ws.db() as db:
        return annotations.change(db, t.fingerprint, annotate.subject(t, "TEB"), Actor.USER, **changes)


# --- the fingerprint -----------------------------------------------------------------------------------


def test_a_fingerprint_ignores_spacing_punctuation_case_and_the_lira_spelling():
    day = date(2026, 1, 20)
    tidy = fingerprint("teb-1", day, 12000, "TL", "Kahveci Dükkan", 0)
    assert fingerprint("teb-1", day, 12000, "TRY", "KAHVECI  DUKKAN.", 0) == tidy
    assert fingerprint("teb-1", day, 12000, "TRY", "KAHVECI DUKKAN", 1) != tidy  # the second of two alike
    assert fingerprint("teb-1", day, 12001, "TRY", "KAHVECI DUKKAN", 0) != tidy


rows = st.lists(
    st.tuples(st.sampled_from(["a", "b"]), st.integers(1, 3), st.integers(-500, 500), st.sampled_from(["X", "Y"])),
    max_size=30,
)


@given(rows)
def test_every_row_gets_its_own_fingerprint_and_alike_rows_keep_their_order(given_rows):
    def prints(seq):
        fp = Fingerprints()
        return [fp.next(a, date(2026, 1, d), m, "TRY", text) for a, d, m, text in seq]

    first = prints(given_rows)
    assert len(set(first)) == len(first)
    # The rows of other accounts, days, amounts or texts coming in between change nothing.
    by_key = sorted(range(len(given_rows)), key=lambda i: given_rows[i])
    regrouped = prints([given_rows[i] for i in by_key])
    assert sorted(regrouped) == sorted(first)


# --- kept across readings ------------------------------------------------------------------------------


def test_a_note_survives_reading_the_documents_again(ws, monkeypatch):
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    note(ws, coffee(ws), note="arkadaşla", tags=("dışarıda",))
    again = [t for t in analyze(ws, reread=True).dataset.transactions if t.note]
    assert [(t.merchant, t.note, t.tags) for t in again] == [("Kahveci Dukkan", "arkadaşla", ("dışarıda",))]
    for reader in registry.readers():  # new versions of every reader: every document is read again
        monkeypatch.setattr(reader, "version", reader.version + 1)
    a = analyze(ws)
    assert [t.note for t in a.dataset.transactions if t.note] == ["arkadaşla"] and a.orphans == []


def test_of_two_rows_alike_the_note_stays_on_the_one_it_was_given(ws):
    add(ws, "ocak.xls", teb.account_export(TWO_COFFEES))
    first, second = (coffee(ws, 0), coffee(ws, 1))
    assert first.fingerprint != second.fingerprint
    note(ws, second, note="ikincisi")
    rows = [t for t in analyze(ws, reread=True).dataset.transactions if t.merchant == "Kahveci Dukkan"]
    assert [t.note for t in rows] == ["", "ikincisi"]


def test_a_corrected_category_brings_its_group_and_the_necessity_its_rules_give(ws):
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    t = coffee(ws)
    assert (t.category, t.necessity) == ("Kafe & Kahve", Necessity.OPTIONAL)
    note(ws, t, category="Market & Gıda")
    t = coffee(ws)
    assert (t.category, t.group, t.necessity) == ("Market & Gıda", "Yeme & İçme", Necessity.REQUIRED)
    assert (t.reason.category, t.reason.rule) == (CategoryReason.USER, "")
    note(ws, t, necessity=Necessity.UNNECESSARY)
    assert (coffee(ws).category, coffee(ws).necessity) == ("Market & Gıda", Necessity.UNNECESSARY)
    note(ws, t, category="", necessity=None)  # back to the rules
    assert (coffee(ws).category, coffee(ws).necessity) == ("Kafe & Kahve", Necessity.OPTIONAL)
    assert (coffee(ws).reason.category, coffee(ws).reason.rule) == (CategoryReason.TRANSFER_RULE, "KAHVE")


def test_an_annotation_left_empty_is_removed_and_the_log_names_fields_not_contents(ws):
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    t = coffee(ws)
    kept = note(ws, t, note="gizli not", tags=("a", " a ", "", "b"))
    assert kept is not None and kept.tags == ("a", "b")
    assert note(ws, t, note="", tags=()) is None
    with ws.db() as db:
        assert annotations.every(db) == {}
        logged = [(e.action, e.detail) for e in audit.entries(db) if e.action.startswith("annotation.")]
    assert logged == [("annotation.set", {"fields": ["note", "tags"]}), ("annotation.removed", {})]


def test_an_annotation_whose_row_went_is_kept_as_an_orphan(ws):
    add(ws, "ocak.xls", teb.account_export(JANUARY, holder="ÖRNEK TEKNOLOJİ A.Ş."))
    note(ws, coffee(ws), note="iş yemeği değil")
    ws.layout.settings.write_text('[identity]\nbusiness_names = ["Örnek Teknoloji"]\n', encoding="utf-8")
    ws = Workspace.load(ws.home)  # the list turns out to be a company's: it leaves the vault, and its rows
    [orphan] = analyze(ws).orphans
    assert (orphan.note, orphan.subject.description, orphan.subject.amount) == (
        "iş yemeği değil",
        "KAHVECI DUKKAN",
        12000,
    )
    with ws.db() as db:
        assert annotations.remove(db, orphan.fingerprint, Actor.USER)
    assert analyze(ws).orphans == []


def _row(fp: str, description: str) -> Transaction:
    t = Transaction(date(2026, 1, 20), description, 500.0, TransactionKind.P2P_TRANSFER, "teb-1", category="Kişilere")
    t.fingerprint = fp
    return t


def _transfer(fp: str, kind: TransactionKind, step: TransferStep | None, category: str, amount: str) -> Transaction:
    t = Transaction(date(2024, 1, 15), f"GIDEN FAST {fp.upper()}", Decimal(amount), kind, "teb-1", category=category)
    t.fingerprint, t.reason = fp, replace(t.reason, transfer=step)
    return t


def test_a_transfer_the_ledger_worked_out_counts_as_the_category_the_user_gives_it():
    rules = Categorizer.layered(None)
    deposit = _transfer("depozito", TransactionKind.PURCHASE, TransferStep.RULE, "Kira", "15000")  # the landlord's
    visit = _transfer("muayene", TransactionKind.P2P_TRANSFER, TransferStep.PERSON, "Kişilere Gönderilen", "1750")
    mine = _transfer("hesabim", TransactionKind.P2P_TRANSFER, TransferStep.PERSON, "Kişilere Gönderilen", "500")
    own = _transfer("kendim", TransactionKind.OWN_TRANSFER, TransferStep.OWN_NAME, "Hesaplar Arası Transfer", "900")
    card = _transfer("kart", TransactionKind.PURCHASE, None, "Market & Gıda", "100")
    given = {
        "depozito": "Kişilere Gönderilen",  # a deposit to the landlord: money to a person, no spending
        "muayene": "Sağlık Hizmetleri",  # a doctor's visit paid by transfer: spending
        "hesabim": "Hesaplar Arası Transfer",  # to the user's own account the ledger could not tell
        "kendim": "Kişilere Gönderilen",  # the ledger knows it is the user's own: it stays so
        "kart": "Kişilere Gönderilen",  # a card's purchase stays a purchase
    }
    rows = [deposit, visit, mine, own, card]
    ds = Dataset({}, [], rows, [], [], {})
    found = {
        t.fingerprint: annotations.Annotation(t.fingerprint, annotate.subject(t, "TEB"), category=given[t.fingerprint])
        for t in rows
    }
    annotate.apply(ds, found, rules)
    assert [(t.category, t.kind) for t in rows] == [
        ("Kişilere Gönderilen", TransactionKind.P2P_TRANSFER),
        ("Sağlık Hizmetleri", TransactionKind.PURCHASE),
        ("Hesaplar Arası Transfer", TransactionKind.OWN_TRANSFER),
        ("Kişilere Gönderilen", TransactionKind.OWN_TRANSFER),
        ("Kişilere Gönderilen", TransactionKind.PURCHASE),
    ]
    assert visit.necessity == Necessity.REQUIRED  # the category's, now that it is spending


def test_a_receipts_note_moves_to_the_statement_row_that_confirmed_it():
    receipt, statement_row = _row("dekont", "FAST VELI"), _row("ekstre", "GIDEN FAST VELI ORNEKSOY")
    ds = Dataset(
        {}, [], [statement_row], [], [], {}, receipts=[ReceiptLine(receipt, "k", CONFIRMED, 500.0, statement_row)]
    )
    subject = annotate.subject(receipt, "TEB")
    found = {"dekont": annotations.Annotation("dekont", subject, note="kira")}
    assert annotate.apply(ds, found, Categorizer()).orphans == [] and statement_row.note == "kira"
    # The statement's row has a note of its own: the user's word on that row wins, the receipt's is shown apart.
    own = annotations.Annotation("ekstre", subject, note="ekim kirası")
    assert annotate.apply(ds, found | {"ekstre": own}, Categorizer()).orphans == [found["dekont"]]
    assert statement_row.note == "ekim kirası"


# --- split rows (F04) ----------------------------------------------------------------------------------


def split(ws: Workspace, t: Transaction, *shares: tuple[str, str]) -> None:
    given = [annotate.Share(Decimal(amount), category) for amount, category in shares]
    note(ws, t, parts=annotate.split(Categorizer.layered(ws.rules), t, given))


def test_a_split_row_counts_each_part_under_its_category_adding_up_to_the_kurus(ws):
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    before = analyze(ws).dataset
    t = coffee(ws)
    split(ws, t, ("80.00", "Kafe & Kahve"), ("40.00", "market & gıda"))
    ds = analyze(ws).dataset
    parts = [p for p in ds.transactions if p.split_of == t.fingerprint]
    assert [(p.fingerprint, p.amount, p.category, p.necessity) for p in parts] == [
        (f"{t.fingerprint}-1", Decimal("80.00"), "Kafe & Kahve", Necessity.OPTIONAL),
        (f"{t.fingerprint}-2", Decimal("40.00"), "Market & Gıda", Necessity.REQUIRED),
    ]
    assert parts[1].group == "Yeme & İçme" and {p.reason.category for p in parts} == {CategoryReason.SPLIT}
    assert {(p.date, p.account, p.kind, p.document) for p in parts} == {(t.date, t.account, t.kind, t.document)}
    assert t.fingerprint not in {p.fingerprint for p in ds.transactions}
    # The payments are as they were: the split row whole, in its place.
    assert [w.fingerprint for w in payments(ds)] == [w.fingerprint for w in before.transactions]
    assert ds.split[t.fingerprint].amount == Decimal("120.00")
    assert sum(p.amount for p in ds.transactions) == sum(p.amount for p in before.transactions)


def test_a_split_survives_reading_the_documents_again_and_no_parts_join_the_row(ws):
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    t = coffee(ws)
    split(ws, t, ("100.00", "Kafe & Kahve"), ("20.00", "Market & Gıda"))
    again = analyze(ws, reread=True).dataset
    assert [p.amount for p in again.transactions if p.split_of] == [Decimal("100.00"), Decimal("20.00")]
    assert note(ws, t, parts=()) is None  # nothing else was kept: the annotation goes
    assert coffee(ws).fingerprint == t.fingerprint and not analyze(ws).dataset.split
    with ws.db() as db:
        logged = [(e.action, e.detail) for e in audit.entries(db) if e.action.startswith("annotation.")]
    assert logged == [("annotation.set", {"fields": ["parts"]}), ("annotation.removed", {})]


def _purchase(amount: str, day: date = date(2026, 1, 20), fp: str = "f" * 20) -> Transaction:
    t = Transaction(day, "ORNEK MAGAZA", Decimal(amount), TransactionKind.PURCHASE, "card", merchant="Ornek Magaza")
    t.fingerprint = fp
    return t


def _split_alone(t: Transaction, *parts: annotations.Part) -> Dataset:
    ds = Dataset({}, [], [t], [], [], {})
    found = {t.fingerprint: annotations.Annotation(t.fingerprint, annotate.subject(t, "Kart"), parts=parts)}
    applied = annotate.apply(ds, found, Categorizer())
    assert applied.orphans == []
    assert applied.unsplit == ([] if ds.split else [annotate.Unsplit(t, len(parts))])  # a split it could not make
    return ds


def test_a_row_valued_at_another_rate_since_its_split_is_shared_out_as_its_parts_were():
    t = _purchase("1000.01")  # a foreign row, split when the rate made it 950,00 TL
    ds = _split_alone(t, annotations.Part(60000, "Giyim"), annotations.Part(35000, "Hediye"))
    assert [p.amount for p in ds.transactions] == [Decimal("631.59"), Decimal("368.42")]


@given(st.integers(1, 10**9), st.lists(st.integers(1, 10**6), min_size=2, max_size=6))
def test_the_parts_always_add_up_to_their_row_or_it_stays_whole(minor, weights):
    t = _purchase(str(Decimal(minor) / 100))
    ds = _split_alone(t, *(annotations.Part(w, "Giyim") for w in weights))
    if ds.split:
        assert sum(p.amount for p in ds.transactions) == t.amount and all(p.amount > 0 for p in ds.transactions)
    else:  # too small to share out among so many
        assert ds.transactions == [t]


def test_a_row_whose_amount_moved_too_far_for_its_parts_counts_whole_and_says_so():
    t = _purchase("0.02")  # split at 100,00 TL into 99,99 and 0,01; a new rate makes it 0,02 TL
    ds = Dataset({}, [], [t], [], [], {})
    note = annotations.Annotation(t.fingerprint, annotate.subject(t, "Kart"), parts=(_part(9999), _part(1), _part(1)))
    applied = annotate.apply(ds, {t.fingerprint: note}, Categorizer())
    assert ds.transactions == [t] and not ds.split and applied.unsplit == [annotate.Unsplit(t, 3)]


def _part(minor: int, category: str = "Giyim", necessity: Necessity | None = None) -> annotations.Part:
    return annotations.Part(minor, category, necessity)


@pytest.mark.parametrize(
    ("shares", "error"),
    [
        ([("120.00", "Kafe & Kahve")], "en az 2"),
        ([("100.00", "Kafe & Kahve"), ("10.00", "Market & Gıda")], "120,00 TL"),
        ([("100.00", "Kafe & Kahve"), ("20.00", "Kahve Yok")], "diye bir kategori yok"),
        ([("119.995", "Kafe & Kahve"), ("0.005", "Market & Gıda")], "iki ondalıklı"),
        ([("130.00", "Kafe & Kahve"), ("-10.00", "Market & Gıda")], "sıfırdan büyük"),
    ],
)
def test_a_split_must_add_up_to_its_row_in_categories_the_rules_know(ws, shares, error):
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    rules = Categorizer.layered(ws.rules)
    with pytest.raises(ValueError, match=error):
        annotate.split(rules, coffee(ws), [annotate.Share(Decimal(a), c) for a, c in shares])


def test_a_row_moving_money_between_own_accounts_is_not_split():
    own = Transaction(date(2026, 1, 20), "HESAPLAR ARASI", Decimal(100), TransactionKind.OWN_TRANSFER, "a")
    with pytest.raises(ValueError, match="bölünür"):
        annotate.split(Categorizer(), own, [annotate.Share(Decimal(50), "Giyim"), annotate.Share(Decimal(50), "Giyim")])
    assert _split_alone(own, annotations.Part(5000, "Giyim"), annotations.Part(5000, "Giyim")).transactions == [own]


def test_a_split_payment_stays_one_payment_of_its_series():
    card = Account("card", "Test Kart •1234", "TEB", AccountType.CREDIT_CARD, number="1234")
    days = [date(2026, month, 10) for month in range(1, 7)]
    rows = [_purchase("200.00", day, f"{n:020d}") for n, day in enumerate(days)]
    for t in rows:
        t.category = "İnternet & Telefon"
    cuts = [Statement("card", day + timedelta(days=5), "TRY", "e.pdf", Decimal(0), Decimal(0)) for day in days]
    ds = Dataset({"card": card}, cuts, rows, [], [], {}, regular={"İnternet & Telefon"})
    last = rows[-1]
    parts = (annotations.Part(15000, "İnternet & Telefon"), annotations.Part(5000, "Elektronik"))
    annotate.apply(
        ds,
        {last.fingerprint: annotations.Annotation(last.fingerprint, annotate.subject(last, "Kart"), parts=parts)},
        Categorizer(),
    )
    [series], _ = regular_payments(ds, timeline(ds))
    assert len(series.payments) == 6 and series.payments[-1] is last and series.price_change() is None


def test_a_split_receipts_parts_are_found_on_the_statement_row_that_confirmed_it():
    receipt, statement_row = (_purchase("500.00", fp=fp * 20) for fp in "de")
    line = ReceiptLine(receipt, "k", CONFIRMED, Decimal(500), statement_row)
    ds = Dataset({}, [], [statement_row], [], [], {}, receipts=[line])
    note = annotations.Annotation(
        receipt.fingerprint, annotate.subject(receipt, "TEB"), parts=(_part(40000), _part(10000))
    )
    annotate.apply(ds, {receipt.fingerprint: note}, Categorizer())
    rows = Rows(ds)
    moved = rows.find(f"{receipt.fingerprint}-2")  # the address the part had while only the receipt told the row
    assert moved is not None and (moved.row.fingerprint, moved.row.amount) == (f"{'e' * 20}-2", Decimal(100))
    gone = rows.find(f"{'e' * 20}-3")  # a part no more: its row, whole
    assert gone is not None and gone.row is ds.split["e" * 20]


def test_a_split_purchase_is_one_purchase_in_the_month_end_and_the_habits():
    cash = Account("cash", "Test Vadesiz TL", "TEB", AccountType.CURRENT, number="111222333")
    months = range(1, 5)
    rows: list[Transaction] = []
    for m in months:
        for n, day in enumerate((5, 15)):  # a shop visited twice a month, for a different sum each time
            t = _purchase(f"{150 + 50 * (2 * m + n)}.00", date(2026, m, day), f"{m:02d}{n}".ljust(20, "0"))
            t.account, t.category, t.group, t.necessity = "cash", "Giyim", "Alışveriş", Necessity.OPTIONAL
            rows.append(t)
    big = _purchase("9000.00", date(2026, 4, 20), "9" * 20)
    big.account, big.merchant, big.category, big.group = "cash", "Ornek Teknoloji", "Elektronik", "Alışveriş"
    shop = rows[-1]  # April's second visit (600,00), split in two: one purchase still
    spent = sum((t.amount for t in rows), Decimal(0))
    cuts = [
        Statement("cash", date(2026, m, 28), "TRY", "h.xls", Decimal(0), Decimal(0), start=date(2026, m, 1))
        for m in months
    ]
    coverage = {"cash": {f"2026-{m:02d}": 1.0 for m in months}}
    ds = Dataset({"cash": cash}, cuts, [*rows, big], [], [], {}, coverage=coverage)
    notes = {
        t.fingerprint: annotations.Annotation(t.fingerprint, annotate.subject(t, "TEB"), parts=parts)
        for t, parts in (
            (big, (_part(450000, "Elektronik"), _part(450000, "Giyim"))),
            (shop, (_part(50000, "Giyim", Necessity.OPTIONAL), _part(10000, "Giyim", Necessity.OPTIONAL))),
        )
    }
    annotate.apply(ds, notes, Categorizer())
    ins = interpret(ds)
    april = next(m for m in month_end.build(ds, ins, date(2026, 5, 15)) if m.month == "2026-04")
    assert april.count == 3  # two visits and the large purchase, whatever their parts
    assert [t.fingerprint for t in april.big] == [big.fingerprint]  # large as a whole (each half is not), once
    assert {(m, n) for m, _, _, n in april.merchants} == {("Ornek Teknoloji", 1), ("Ornek Magaza", 2)}
    [shopping] = [h for h in habits(ds, timeline(ds), ins.series) if h.name == "Ornek Magaza"]
    assert (shopping.count, shopping.total, shopping.high) == (8, spent, Decimal("600.00"))  # the split one whole


def test_a_split_series_payment_stays_with_its_series_in_the_forecast_and_the_report():
    cash = Account("cash", "Test Vadesiz TL", "TEB", AccountType.CURRENT, number="111222333")
    months = range(1, 9)
    rows = [_purchase("1000.00", date(2026, m, 5), f"{m:020d}") for m in months]
    for t in rows:
        t.account, t.merchant, t.category = "cash", "Ornek Kira", "Kira"
    cuts = [
        Statement("cash", date(2026, m, 28), "TRY", "h.xls", Decimal(0), Decimal(0), start=date(2026, m, 1))
        for m in months
    ]
    ds = Dataset({"cash": cash}, cuts, rows, [], [], {}, coverage={"cash": {f"2026-{m:02d}": 1.0 for m in months}})
    parts = (annotations.Part(90000, "Kira"), annotations.Part(10000, "Aidat"))
    notes = {
        t.fingerprint: annotations.Annotation(t.fingerprint, annotate.subject(t, "TEB"), parts=parts) for t in rows[-5:]
    }
    annotate.apply(ds, notes, Categorizer())
    assert {(p.split_of[-1:], p.split_parts) for p in ds.transactions if p.split_of} >= {("8", 2)}
    ins = interpret(ds)
    # The spending spread over the days ahead leaves the series out, its split payments' parts too.
    spending, _ = forecast.spreads(ds, ins, "cash")
    assert spending is not None and spending.monthly == 0
    # The report marks every row of the series, parts and all.
    assert {row["r"] for row in report.build_payload(ds, {"documents": 0, "duplicates": 0}, ins)["tx"]} == {0}


# --- the command line ----------------------------------------------------------------------------------


@pytest.fixture
def home(ws, monkeypatch):
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    monkeypatch.setenv(HOME_ENV, str(ws.home))
    return ws


def test_the_command_line_shows_a_split_rows_parts_and_keeps_their_category_to_them(home, capsys):
    t = coffee(home)
    split(home, t, ("80.00", "Kafe & Kahve"), ("40.00", "Market & Gıda"))
    assert main(["islem", "ara", "kahveci"]) == 0
    shown = [line.split("  [")[0].rsplit(" · ", 1)[1] for line in capsys.readouterr().out.splitlines()]
    assert shown == ["parça 2/2", "parça 1/2"]  # newest first, as every row
    assert main(["islem", "duzelt", f"{t.fingerprint}-2", "--not", "ikiye bölündü"]) == 0  # a part names its row
    assert "Kaydedildi — not: ikiye bölündü" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["islem", "duzelt", t.fingerprint[:8], "--kategori", "Market & Gıda"])
    assert "bu işlem bölünmüş" in capsys.readouterr().err


def test_the_command_line_finds_a_row_and_corrects_it(home, capsys):
    assert main(["islem", "ara", "kahveci"]) == 0
    line = capsys.readouterr().out.splitlines()[0]
    fp = line.split()[0]
    assert len(fp) == 10 and "Kafe & Kahve" in line
    assert (
        main(["islem", "duzelt", fp[:6], "--not", "arkadaşla", "--etiket", "dışarıda", "--kategori", "market & gıda"])
        == 0
    )
    assert "Kaydedildi — not: arkadaşla; etiketler: dışarıda; kategori: Market & Gıda" in capsys.readouterr().out
    assert main(["islem", "ara", "arkadaşla"]) == 0  # notes and tags are searched too
    found = capsys.readouterr().out
    assert "Market & Gıda · Gerekli" in found and "not: arkadaşla" in found and "#dışarıda" in found
    assert main(["islem", "yetimler"]) == 0
    assert "Eşi bulunamayan düzeltme yok." in capsys.readouterr().out


@pytest.mark.parametrize(
    "args, error",
    [
        (["kisa", "--not", "x"], "en az ilk 6"),
        (["000000", "--not", "x"], "ile başlayan bir işlem yok"),
        (["KEY", "--kategori", "Market & Gda"], "bunu mu demek istediniz: Market & Gıda"),
        (["KEY", "--gereklilik", "çok gerekli"], "gereklilik şunlardan biri olmalı"),
        (["KEY"], "neyin değişeceğini yazın"),
    ],
)
def test_the_command_line_refuses_what_it_cannot_do(home, capsys, args, error):
    key = coffee(home).fingerprint
    with pytest.raises(SystemExit):
        main(["islem", "duzelt", *[key if a == "KEY" else a for a in args]])
    assert error in capsys.readouterr().err
