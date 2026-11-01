"""The user's notes and corrections: bound to fingerprints, kept across readings, never lost when their row goes."""

from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from iplikci.analysis import CONFIRMED, Dataset, ReceiptLine
from iplikci.app import annotate
from iplikci.app.analysis import analyze
from iplikci.app.workspace import Workspace
from iplikci.categorize import Categorizer
from iplikci.cli import main
from iplikci.demo import teb_export
from iplikci.domain.codes import Actor, Necessity, TransactionKind
from iplikci.domain.fingerprint import Fingerprints, fingerprint
from iplikci.domain.models import Transaction
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
    add(ws, "ocak.xls", teb_export(JANUARY))
    note(ws, coffee(ws), note="arkadaşla", tags=("dışarıda",))
    again = [t for t in analyze(ws, reread=True).dataset.transactions if t.note]
    assert [(t.merchant, t.note, t.tags) for t in again] == [("Kahveci Dukkan", "arkadaşla", ("dışarıda",))]
    for reader in registry.readers():  # new versions of every reader: every document is read again
        monkeypatch.setattr(reader, "version", reader.version + 1)
    a = analyze(ws)
    assert [t.note for t in a.dataset.transactions if t.note] == ["arkadaşla"] and a.orphans == []


def test_of_two_rows_alike_the_note_stays_on_the_one_it_was_given(ws):
    add(ws, "ocak.xls", teb_export(TWO_COFFEES))
    first, second = (coffee(ws, 0), coffee(ws, 1))
    assert first.fingerprint != second.fingerprint
    note(ws, second, note="ikincisi")
    rows = [t for t in analyze(ws, reread=True).dataset.transactions if t.merchant == "Kahveci Dukkan"]
    assert [t.note for t in rows] == ["", "ikincisi"]


def test_a_corrected_category_brings_its_group_and_the_necessity_its_rules_give(ws):
    add(ws, "ocak.xls", teb_export(JANUARY))
    t = coffee(ws)
    assert (t.category, t.necessity) == ("Kafe & Kahve", Necessity.OPTIONAL)
    note(ws, t, category="Market & Gıda")
    t = coffee(ws)
    assert (t.category, t.group, t.necessity) == ("Market & Gıda", "Yeme & İçme", Necessity.REQUIRED)
    note(ws, t, necessity=Necessity.UNNECESSARY)
    assert (coffee(ws).category, coffee(ws).necessity) == ("Market & Gıda", Necessity.UNNECESSARY)
    note(ws, t, category="", necessity=None)  # back to the rules
    assert (coffee(ws).category, coffee(ws).necessity) == ("Kafe & Kahve", Necessity.OPTIONAL)


def test_an_annotation_left_empty_is_removed_and_the_log_names_fields_not_contents(ws):
    add(ws, "ocak.xls", teb_export(JANUARY))
    t = coffee(ws)
    kept = note(ws, t, note="gizli not", tags=("a", " a ", "", "b"))
    assert kept is not None and kept.tags == ("a", "b")
    assert note(ws, t, note="", tags=()) is None
    with ws.db() as db:
        assert annotations.every(db) == {}
        logged = [(e.action, e.detail) for e in audit.entries(db) if e.action.startswith("annotation.")]
    assert logged == [("annotation.set", {"fields": ["note", "tags"]}), ("annotation.removed", {})]


def test_an_annotation_whose_row_went_is_kept_as_an_orphan(ws):
    add(ws, "ocak.xls", teb_export(JANUARY, holder="ÖRNEK TEKNOLOJİ A.Ş."))
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


def test_a_receipts_note_moves_to_the_statement_row_that_confirmed_it():
    receipt, statement_row = _row("dekont", "FAST VELI"), _row("ekstre", "GIDEN FAST VELI ORNEKSOY")
    ds = Dataset(
        {}, [], [statement_row], [], [], {}, receipts=[ReceiptLine(receipt, "k", CONFIRMED, 500.0, statement_row)]
    )
    subject = annotate.subject(receipt, "TEB")
    found = {"dekont": annotations.Annotation("dekont", subject, note="kira")}
    assert annotate.apply(ds, found, Categorizer()) == [] and statement_row.note == "kira"
    # The statement's row has a note of its own: the user's word on that row wins, the receipt's is shown apart.
    own = annotations.Annotation("ekstre", subject, note="ekim kirası")
    assert annotate.apply(ds, found | {"ekstre": own}, Categorizer()) == [found["dekont"]]
    assert statement_row.note == "ekim kirası"


# --- the command line ----------------------------------------------------------------------------------


@pytest.fixture
def home(ws, monkeypatch):
    add(ws, "ocak.xls", teb_export(JANUARY))
    monkeypatch.setenv(HOME_ENV, str(ws.home))
    return ws


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
