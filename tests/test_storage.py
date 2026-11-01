"""The SQLite store (ADR-0004): migrations, transactions, the document tables, readings and search."""

import sqlite3
import stat
import sys
from datetime import date
from decimal import Decimal

import pytest

from iplikci.domain.codes import AccountType, Actor, DocumentKind, DocumentStatus, SourceKind, TransactionKind
from iplikci.domain.models import Account, ParseResult, Security, SourceRef, Statement, Transaction
from iplikci.storage import audit, db, documents, readings

SHA = "a" * 64
OTHER = "b" * 64


@pytest.fixture
def store(tmp_path):
    database = db.connect(tmp_path / "iplikci.db", tmp_path / "backups")
    yield database
    database.close()


def tables(database: db.Database) -> set[str]:
    return {r[0] for r in database.rows("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}


# --- the database ------------------------------------------------------------------------------------


def test_a_new_database_gets_the_whole_schema(store, tmp_path):
    assert {"documents", "document_sources", "statements", "transactions", "evidence", "annotations"} <= tables(store)
    assert {"audit_log", "search", "schema_migrations"} <= tables(store)
    assert store.scalar("PRAGMA journal_mode") == "wal"
    assert store.scalar("PRAGMA foreign_keys") == 1
    shipped = [n for n, _, _ in db.migrations()]
    assert [r["version"] for r in store.rows("SELECT version FROM schema_migrations ORDER BY version")] == shipped
    if sys.platform != "win32":
        assert stat.S_IMODE((tmp_path / "iplikci.db").stat().st_mode) == 0o600


def test_opening_again_changes_nothing(tmp_path):
    db.connect(tmp_path / "iplikci.db", tmp_path / "backups").close()
    with db.connect(tmp_path / "iplikci.db", tmp_path / "backups") as again:
        assert db.migrate(again, tmp_path / "backups") == []
    assert not (tmp_path / "backups").exists()


def test_a_new_migration_backs_the_database_up_first(tmp_path, monkeypatch):
    with db.connect(tmp_path / "iplikci.db", tmp_path / "backups") as first:
        documents.add(first, SHA, "ekstre.pdf", 10)
    shipped = db.migrations()
    new = (len(shipped) + 1, "deneme", "CREATE TABLE deneme (x INTEGER);\n")
    monkeypatch.setattr(db, "migrations", lambda: [*shipped, new])
    with db.connect(tmp_path / "iplikci.db", tmp_path / "backups") as second:
        assert "deneme" in tables(second)
    [copy] = (tmp_path / "backups").iterdir()
    assert copy.name.startswith(f"iplikci göç öncesi {len(shipped):04d} ")
    old = sqlite3.connect(copy)
    try:
        assert old.execute("SELECT name FROM documents").fetchall() == [("ekstre.pdf",)]
        assert "deneme" not in {r[0] for r in old.execute("SELECT name FROM sqlite_master")}
    finally:
        old.close()


def test_migration_numbers_have_no_gaps():
    assert [n for n, _, _ in db.migrations()] == list(range(1, len(db.migrations()) + 1))


def test_a_failed_write_leaves_nothing_behind(store):
    with pytest.raises(RuntimeError), store.transaction():
        documents.add(store, SHA, "ekstre.pdf", 10)  # joins the outer transaction
        raise RuntimeError("yarıda kaldı")
    assert documents.get(store, SHA) is None
    assert store.scalar("SELECT count(*) FROM search") == 0


def test_rows_must_belong_to_a_document(store):
    with pytest.raises(sqlite3.IntegrityError), store.transaction():
        store.execute(
            "INSERT INTO document_sources (sha256, kind, received_at) VALUES (?, 'upload', '2026-11-01')", (OTHER,)
        )


# --- documents and sources ----------------------------------------------------------------------------


def test_the_same_bytes_are_one_document_with_two_arrivals(store):
    assert documents.add(store, SHA, "HesapHareketleri.xls", 1200)
    assert not documents.add(store, SHA, "kopya.xls", 1200)
    first = documents.Source(SourceKind.IMPORT, "HesapHareketleri.xls", "Bankalar/TEB")
    assert documents.add_source(store, SHA, first)
    assert not documents.add_source(store, SHA, first)  # the same arrival is recorded once
    assert documents.add_source(store, SHA, documents.Source(SourceKind.UPLOAD, "kopya.xls"))
    assert documents.source_counts(store) == {SHA: 2}
    assert [s.original for s in documents.sources(store, SHA)] == ["HesapHareketleri.xls", "kopya.xls"]
    doc = documents.get(store, SHA)
    assert doc is not None
    assert (doc.name, doc.status, doc.ext) == ("HesapHareketleri.xls", DocumentStatus.UNPROCESSED, ".xls")


def test_a_reading_is_recorded_on_the_document(store):
    documents.add(store, SHA, "ekstre.pdf", 10)
    reading = documents.Reading(
        DocumentStatus.PROCESSED,
        kind=DocumentKind.CARD_STATEMENT,
        parser="garanti",
        parser_version="12",
        verified=True,
        period_start=date(2026, 9, 6),
        period_end=date(2026, 10, 5),
        display_name="2026-10-05 Garanti Bonus 1234 Ekstre.pdf",
    )
    documents.record_reading(store, SHA, reading)
    doc = documents.get(store, SHA)
    assert doc is not None
    assert (doc.status, doc.kind, doc.verified, doc.period_end) == (
        DocumentStatus.PROCESSED,
        DocumentKind.CARD_STATEMENT,
        True,
        date(2026, 10, 5),
    )
    assert doc.read_at
    assert [d.sha256 for d in documents.every(store, [DocumentStatus.PROCESSED])] == [SHA]
    assert documents.every(store, [DocumentStatus.UNREADABLE]) == []


# --- readings ---------------------------------------------------------------------------------------


def sample() -> ParseResult:
    card = Account(
        "garanti-bonus-1234", "Garanti BBVA Bonus •1234", "Garanti BBVA", AccountType.CREDIT_CARD, "TRY", "1234"
    )
    teb = Account("teb-123456789", "TEB Vadesiz TL 123456789", "TEB", AccountType.CURRENT, "TRY", "123456789")
    rows = [
        Transaction(
            date(2026, 9, 10),
            "MIGROS ORNEK SUBE ISTANBUL",
            Decimal(2150),
            TransactionKind.PURCHASE,
            card.id,
            ref=SourceRef(page=1, box=(40.0, 301.5, 412.25, 310.5)),
        ),
        Transaction(
            date(2026, 9, 10), "MIGROS ORNEK SUBE ISTANBUL", Decimal(2150), TransactionKind.PURCHASE, card.id
        ),  # both real; a row read before the readers kept their place has none
        Transaction(
            date(2026, 9, 12),
            "ODEMENIZ ICIN TESEKKUR",
            Decimal(-4300),
            TransactionKind.CARD_PAYMENT,
            card.id,
            installment="1/3",
        ),
    ]
    statement = Statement(card.id, date(2026, 10, 5), "TRY", "ekstre.pdf", Decimal(1000), Decimal(1000), rows)
    listing = Statement(
        teb.id,
        date(2026, 10, 31),
        "TRY",
        "liste.xls",
        Decimal(0),
        Decimal("39.99"),
        [
            Transaction(
                date(2026, 10, 1),
                "ÖRNEK İŞVEREN A.Ş.",
                Decimal(-40000),
                TransactionKind.TRANSFER_CANDIDATE,
                teb.id,
                counterparty="ÖRNEK İŞVEREN",
                ref=SourceRef(sheet="Hesap Hareketleri", row=12),
            )
        ],
        start=date(2026, 10, 1),
        checks_ok=1,
        checks_total=1,
        balances={"2026-10": Decimal("39.99")},
        securities=[Security("ORNEK", "ÖRNEK SANAYİ A.Ş.", Decimal(20), Decimal(1342), date(2026, 10, 30))],
        one_off=True,
    )
    receipt = [
        Transaction(
            date(2026, 9, 10),
            "AİDAT ÖDEMESİ",
            Decimal(1250),
            TransactionKind.TRANSFER_CANDIDATE,
            teb.id,
            ref=SourceRef(page=1, span=(120, 168)),
            balance=Decimal("-4321.10"),  # a notice's balance after the row
        )
    ]
    return ParseResult("deneme", [card, teb], [statement, listing], receipt, "dekont-1", "ÖRNEK KULLANICI", "Aidat")


def stored(store, result: ParseResult) -> documents.DocumentRow:
    documents.add(store, SHA, "ekstre.pdf", 10)
    documents.record_reading(
        store,
        SHA,
        documents.Reading(
            DocumentStatus.PROCESSED,
            parser=result.parser,
            receipt_key=result.receipt_key,
            holder=result.holder,
            title=result.title,
        ),
    )
    readings.save(store, SHA, result)
    doc = documents.get(store, SHA)
    assert doc is not None
    return doc


def test_a_reading_comes_back_as_the_reader_left_it(store):
    original = sample()
    doc = stored(store, original)
    assert readings.load(store, [doc]) == {SHA: original}


def test_saving_again_replaces_the_previous_reading(store):
    doc = stored(store, sample())
    readings.save(store, SHA, sample())
    assert store.scalar("SELECT count(*) FROM transactions") == 4
    assert store.scalar("SELECT count(*) FROM evidence") == 1
    assert readings.load(store, [doc])[SHA] == sample()
    readings.clear(store, SHA)
    assert readings.load(store, [doc])[SHA].statements == []
    assert store.scalar("SELECT count(*) FROM search WHERE kind != 'document'") == 0


def test_search_ignores_case_and_turkish_letters(store):
    stored(store, sample())
    found = readings.search(store, "örnek şube")
    assert {kind for kind, _, _ in found} == {"transaction"}
    assert len(found) == 2
    assert sorted(kind for kind, _, _ in readings.search(store, "aidat")) == ["document", "evidence"]  # its title
    assert [kind for kind, _, _ in readings.search(store, "EKSTRE")] == ["document"]
    assert readings.search(store, "işveren")[0][0] == "transaction"
    assert readings.search(store, '" OR 1') == []  # the query is words, never FTS syntax
    assert readings.search(store, "  ") == []


# --- the audit log ------------------------------------------------------------------------------------


def test_the_audit_log_only_grows(store):
    audit.record(store, Actor.SYSTEM, "document.business", SHA, stage="ingest")
    audit.record(store, Actor.SYSTEM, "document.business", SHA, stage="reread")
    audit.record(store, Actor.USER, "annotation.set", "abc")
    assert audit.targets(store, "document.business") == {SHA}
    [entry] = audit.entries(store, "annotation.set")
    assert (entry.actor, entry.target, entry.detail) == (Actor.USER, "abc", {})
    assert len(audit.entries(store)) == 3
