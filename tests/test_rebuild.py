"""The archive check and the rebuild check (ADR-0003, ADR-0004): the vault is sound, and the database made again
from the vault and the primary data gives the same result."""

import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from iplikci import demo
from iplikci.app import annotate, checks, intake, memory, rebuild
from iplikci.app.analysis import analyze
from iplikci.app.workspace import Workspace
from iplikci.cli import main
from iplikci.domain.codes import Actor, DocumentStatus, MemoryKind, Necessity, RateSource
from iplikci.fakes import fx as fake_fx
from iplikci.fakes import garanti, teb
from iplikci.fx import tcmb
from iplikci.settings.paths import HOME_ENV
from iplikci.storage import annotations, documents, fx_rates, memories

from conftest import JANUARY, add


@pytest.fixture(scope="module")
def demo_home(tmp_path_factory) -> Path:
    return demo.build(tmp_path_factory.mktemp("demo") / "veri")


@pytest.fixture
def noted(ws) -> Workspace:
    """ws with January's list and a note, a tag and a corrected necessity on its coffee."""
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    [t] = [t for t in analyze(ws).dataset.transactions if t.merchant == "Kahveci Dukkan"]
    with ws.db() as db:
        annotations.change(
            db,
            t.fingerprint,
            annotate.subject(t, "TEB"),
            Actor.USER,
            note="arkadaşla",
            tags=("dışarıda",),
            necessity=Necessity.REQUIRED,
        )
    return ws


def test_the_demo_database_comes_out_the_same_when_made_again(demo_home):
    report = rebuild.check(Workspace.load(demo_home), today=demo.AS_OF)
    assert report.ok and report.documents == 10, report.differences


def test_notes_and_corrections_come_back_with_the_rebuilt_database(noted):
    report = rebuild.check(noted)
    assert report.ok and report.annotations == 1, report.differences


def test_a_split_row_comes_back_split_and_an_older_dump_without_parts_still_loads(noted):
    [t] = [t for t in analyze(noted).dataset.transactions if t.merchant == "Kahveci Dukkan"]
    parts = (annotations.Part(8000, "Kafe & Kahve"), annotations.Part(4000, "Market & Gıda", Necessity.OPTIONAL))
    with noted.db() as db:
        annotations.change(db, t.fingerprint, annotate.subject(t, "TEB"), Actor.USER, parts=parts)
        primary = rebuild.export(db)
    assert rebuild.load(rebuild.dump(primary)).annotations == primary.annotations
    report = rebuild.check(noted)
    assert report.ok, report.differences
    older = json.loads(rebuild.dump(primary))
    older["version"] = 4
    for a in older["annotations"]:
        del a["parts"]
    assert [a.parts for a in rebuild.load(json.dumps(older)).annotations] == [()]


def test_the_dump_carries_names_arrivals_annotations_and_the_logs(noted):
    add(noted, "ekstre.pdf", garanti.bonus_statement(total=Decimal("3900.00")))  # a format alarm for the event log
    with noted.db() as db:
        primary = rebuild.export(db)
    again = rebuild.load(rebuild.dump(primary))
    assert again.annotations == primary.annotations and again.audit == primary.audit
    kinds = [e.kind for e in again.events]
    assert again.events == primary.events and kinds.count("parser.format_alarm") == 1
    assert kinds.count("document.received") == 2 and {"document.processed"} <= set(kinds)
    assert [(k.row.sha256, k.row.name, k.row.added_at, k.sources) for k in again.documents] == [
        (k.row.sha256, k.row.name, k.row.added_at, k.sources) for k in primary.documents
    ]
    with pytest.raises(ValueError, match="dökümü değil"):
        rebuild.load('{"format": "baska"}')


def test_the_rebuilt_database_has_the_same_exchange_rates_and_asked_days(noted, tmp_path):
    friday, saturday = date(2026, 10, 30), date(2026, 10, 31)
    with noted.db() as db:
        fx_rates.put(
            db, friday, RateSource.TCMB, tcmb.parse(fake_fx.tcmb_xml(friday, fake_fx.tcmb_rates(friday))).quotes
        )
        fx_rates.put(db, saturday, RateSource.ECB, [])  # asked, nothing published
        kept, days = fx_rates.every(db), fx_rates.asked_days(db)
        primary = rebuild.load(rebuild.dump(rebuild.export(db)))
    assert (primary.rates, primary.rate_days) == (kept, days) and len(kept) == 3
    with rebuild.rebuild(noted, tmp_path, primary).db() as db:
        assert (fx_rates.every(db), fx_rates.asked_days(db)) == (kept, days)
        assert rebuild.rates_carried(primary, db) == []
    report = rebuild.check(noted)
    assert report.ok, report.differences


def test_an_older_dump_has_no_rates_and_rates_lost_on_the_way_are_a_difference(noted, tmp_path):
    friday = date(2026, 10, 30)
    with noted.db() as db:
        fx_rates.put(
            db, friday, RateSource.TCMB, tcmb.parse(fake_fx.tcmb_xml(friday, fake_fx.tcmb_rates(friday))).quotes
        )
        primary = rebuild.export(db)
    older = json.loads(rebuild.dump(primary))
    older["version"] = 5
    del older["rates"], older["rate_days"]
    without = rebuild.load(json.dumps(older))
    assert (without.rates, without.rate_days) == ([], [])
    with rebuild.rebuild(noted, tmp_path, without).db() as db:
        assert rebuild.rates_carried(primary, db) == [
            "kurlar: dökümde 3 kur ve 1 gün, yeniden kurulanda 0 kur ve 0 gün"
        ]


def test_claudes_notes_come_back_with_the_rebuilt_database_and_an_older_dump_has_none(noted, tmp_path):
    memory.write(noted, "kira-odemesi", Actor.MCP, kind=MemoryKind.REFERENCE, description="Kira", body="Ayın 5'i.")
    memory.write(noted, "ozet-bicimi", Actor.MCP, kind=MemoryKind.FEEDBACK, description="Tablo", body="Neden: …")
    with noted.db() as db:
        kept = memories.every(db)
        primary = rebuild.load(rebuild.dump(rebuild.export(db)))
    assert primary.memories == kept and len(kept) == 2
    with rebuild.rebuild(noted, tmp_path, primary).db() as db:
        assert memories.every(db) == kept  # with their own times and who wrote them
        assert rebuild.notes_carried(kept, db) == []
    report = rebuild.check(noted)
    assert report.ok and report.memories == 2, report.differences
    older = json.loads(rebuild.dump(primary))
    older["version"] = 6
    del older["memories"]
    without = rebuild.load(json.dumps(older))
    assert without.memories == []
    (folder := tmp_path / "eski").mkdir()
    with rebuild.rebuild(noted, folder, without).db() as db:
        assert rebuild.notes_carried(kept, db) == ["hafıza: 2 not yeniden kurulanda aynı değil"]


def test_a_changed_reading_in_the_database_is_found(noted):
    with noted.db() as db:  # as if the database had been tampered with or damaged
        db.execute("UPDATE transactions SET amount = amount + 100 WHERE description = 'KAHVECI DUKKAN'")
    report = rebuild.check(noted)
    assert not report.ok
    assert "işlemler: 1 işlem yalnızca gerçek veritabanında, 1 işlem yalnızca yeniden kurulanda" in report.differences
    assert any(d.startswith("yetim düzeltmeler: 1 → 0") for d in report.differences)  # the note's row moved


def test_the_rebuild_only_reads_the_vault(noted, private_trash):
    with noted.db() as db:
        primary = rebuild.export(db)
    noted.layout.settings.write_text('[identity]\nbusiness_names = ["Örnek Kullanıcı"]\n', encoding="utf-8")
    ws = Workspace.load(noted.home)  # the list now reads as a company's
    shadow = rebuild.rebuild(ws, ws.run, primary)
    with shadow.db() as db:
        [doc] = documents.every(db)
    assert doc.status is DocumentStatus.REMOVED  # marked in the new database...
    assert ws.vault.has(doc.sha256) and not any(private_trash.iterdir())  # ...never moved
    with pytest.raises(PermissionError):
        intake.apply(shadow, intake.plan_documents(shadow, []))


# --- the archive check -------------------------------------------------------------------------------


def test_a_sound_archive_passes(noted):
    report = checks.archive(noted)
    assert report.ok and report.integrity.checked == report.documents == 1
    assert (report.missing, report.unknown, report.lingering, report.database, report.stale) == ([], [], [], [], 0)


def test_the_archive_check_finds_damage_loss_and_leftovers(noted):
    vault = noted.vault
    [kept] = list(vault.objects())
    os.chmod(vault.path(kept), 0o600)
    vault.path(kept).write_bytes(b"bozuk")
    stray = vault.put(b"yarim kalan bir alim")  # kept in the vault, never recorded: harmless, worth a look
    report = checks.archive(noted)
    assert not report.ok and report.integrity.corrupt == [kept] and report.unknown == [stray]
    vault.path(kept).unlink()  # lost altogether
    report = checks.archive(noted)
    assert report.missing == [kept] and not report.ok


def test_the_commands_answer_with_their_exit_code(noted, monkeypatch, capsys):
    monkeypatch.setenv(HOME_ENV, str(noted.home))
    assert main(["dogrula", "--arsiv"]) == 0
    assert "Arşiv sağlam" in capsys.readouterr().out
    assert main(["dogrula", "--yeniden-kur"]) == 0
    assert "Birincil veriler: 1 belge, 1 düzeltme" in capsys.readouterr().out
    [kept] = list(noted.vault.objects())
    noted.vault.path(kept).unlink()
    assert main(["dogrula", "--arsiv"]) == 1
    assert f"arşivde olmayan belge: {kept}" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["dogrula", "--arsiv", "--taban"])
