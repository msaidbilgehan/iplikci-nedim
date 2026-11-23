"""The sync folder (ADR-0025, F22): two computers' data folders sharing one folder that a sync service would mirror.
Each test's computers are data folders beside each other; the "Google Drive" is a plain folder."""

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from iplikci.app import annotate, memory, sync
from iplikci.app.analysis import analyze
from iplikci.app.workspace import Workspace
from iplikci.domain.codes import Actor, Channel, DocumentStatus, MemoryKind
from iplikci.fakes import teb
from iplikci.settings import config
from iplikci.storage import aliases, annotations, audit, documents, memories
from iplikci.storage import db as database
from iplikci.sync import library, machine
from iplikci.sync.state import Kind, decode

from conftest import FEBRUARY, JANUARY, RULES, add


@pytest.fixture(autouse=True)
def one_machine(monkeypatch):
    """Every data folder of a test on one machine with a name, without asking the system."""
    monkeypatch.setattr(machine, "fingerprint", lambda: "makine-1")
    monkeypatch.setattr(machine, "computer_name", lambda: "Deneme Bilgisayarı")
    sync._peers.clear()
    sync._beats.clear()


@pytest.fixture
def drive(tmp_path) -> Path:
    """A sync service's folder; the sync folder is made in it."""
    root = tmp_path / "Google Drive" / "My Drive"
    root.mkdir(parents=True)
    return root / library.DEFAULT_NAME


def computer(tmp_path: Path, name: str) -> Workspace:
    ws = Workspace.load(tmp_path / name)
    ws.rules.write_text(RULES, encoding="utf-8")
    return ws


@pytest.fixture
def a(tmp_path) -> Workspace:
    return computer(tmp_path, "a")


@pytest.fixture
def b(tmp_path) -> Workspace:
    return computer(tmp_path, "b")


def coffee(ws: Workspace):
    [t] = [t for t in analyze(ws).dataset.transactions if t.merchant == "Kahveci Dukkan"]
    return t


def note_on_coffee(ws: Workspace, note: str) -> str:
    t = coffee(ws)
    with ws.db() as db:
        annotations.change(db, t.fingerprint, annotate.subject(t, "TEB"), Actor.USER, note=note)
    return t.fingerprint


def rounds(*computers: Workspace, times: int = 2) -> None:
    for _ in range(times):
        for ws in computers:
            while sync.run_round(ws).more:
                pass


def sends(ws: Workspace, channel: Channel) -> bool:
    with ws.db() as db:
        return sync.sends(db, config.load(ws.layout.settings), channel)


def ledger(ws: Workspace) -> set[tuple[object, ...]]:
    return {(t.fingerprint, t.date, t.amount, t.category, t.note) for t in analyze(ws).dataset.transactions}


def test_a_second_computer_gets_the_documents_notes_and_rules_and_reads_the_same_ledger(a, b, drive):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    fingerprint = note_on_coffee(a, "arkadaşla")
    with a.db() as db:
        memories.write(db, "kira-odemesi", MemoryKind.PROJECT, "Kira her ayın 5'inde", "Kira 5'inde çıkar.", Actor.MCP)
    sync.turn_on(a, str(drive))
    rounds(a)
    sync.turn_on(b, str(drive))
    rounds(b, a, b)

    with b.db() as db:
        [doc] = [d for d in documents.every(db) if d.name == "ocak.xls"]
        assert b.vault.has(doc.sha256)
        assert annotations.get(db, fingerprint).note == "arkadaşla"
        assert memories.get(db, "kira-odemesi").body == "Kira 5'inde çıkar."
    assert ledger(b) == ledger(a)
    assert [t.note for t in analyze(b).dataset.transactions if t.fingerprint == fingerprint] == ["arkadaşla"]
    status = sync.status(b)
    assert status.on and len(status.devices) == 2 and status.devices[0].me
    assert status.waiting_down == 0 and status.waiting_up == 0 and not status.problem


def test_the_folder_holds_one_part_per_computer_with_its_state_and_originals(a, b, drive):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    sync.turn_on(a, str(drive))
    rounds(a)
    sync.turn_on(b, str(drive))
    rounds(b)
    assert (drive / library.MARKER).is_file() and (drive / library.README).is_file()
    ids = library.devices(drive)
    assert len(ids) == 2
    with a.db() as db:
        me = sync._me(db)
        [sha] = [d.sha256 for d in documents.every(db) if d.name == "ocak.xls"]
    assert library.object_path(drive, me.device, sha).is_file()  # the original went once, from the first computer
    other = next(i for i in ids if i != me.device)
    assert not library.objects(drive, other)
    published = decode((library.device_dir(drive, other) / library.STATE_FILE).read_bytes())
    assert any(e.kind == Kind.DOCUMENT and e.key == sha for e in published.entries)


def test_changes_on_either_computer_reach_the_other_and_the_later_one_wins(a, b, drive):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    fingerprint = note_on_coffee(a, "ilk")
    sync.turn_on(a, str(drive))
    rounds(a)
    sync.turn_on(b, str(drive))
    rounds(b, a, b)
    note_on_coffee(b, "ikinci")
    rounds(b, a)
    with a.db() as db:
        assert annotations.get(db, fingerprint).note == "ikinci"
    note_on_coffee(a, "üçüncü")
    rounds(a, b)
    with b.db() as db:
        assert annotations.get(db, fingerprint).note == "üçüncü"
    t = coffee(b)
    with b.db() as db:
        annotations.change(db, fingerprint, annotate.subject(t, "TEB"), Actor.USER, note="")  # taken away
    rounds(b, a)
    with a.db() as db:
        assert annotations.get(db, fingerprint) is None


def test_a_document_removed_on_one_computer_goes_to_the_trash_on_the_other_and_leaves_the_folder(
    a, b, drive, private_trash
):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    add(a, "subat.xls", FEBRUARY)
    sync.turn_on(a, str(drive))
    rounds(a)
    sync.turn_on(b, str(drive))
    rounds(b, a, b)
    with b.db() as db:
        [doc] = [d for d in documents.every(db) if d.name == "subat.xls"]
    from iplikci.app import documents as document_cases

    document_cases.remove(b, doc.sha256, Actor.USER)
    rounds(b, a)
    with a.db() as db:
        assert documents.get(db, doc.sha256).status is DocumentStatus.REMOVED
        assert any(e.action == "document.removed" and e.actor is Actor.SYNC for e in audit.entries(db))
    assert not a.vault.has(doc.sha256)
    assert doc.sha256 not in sync._listing(drive)
    assert ledger(a) == ledger(b)


def test_a_removal_is_never_undone_by_a_later_change_of_the_kept_document(a, b, drive):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    sync.turn_on(a, str(drive))
    rounds(a)
    sync.turn_on(b, str(drive))
    rounds(b, a, b)
    with a.db() as db:
        [doc] = documents.every(db)
    from iplikci.app import documents as document_cases

    document_cases.remove(a, doc.sha256, Actor.USER)
    with b.db() as db:  # meanwhile b's copy changes (the message it came in, say) before b hears of the removal
        documents.reparent(db, "", "f" * 64)
    rounds(b, a, b, a)
    for ws in (a, b):
        with ws.db() as db:
            assert documents.get(db, doc.sha256).status is DocumentStatus.REMOVED


def test_names_and_shared_settings_and_rules_reach_the_other_computer_but_its_own_settings_stay(a, b, drive):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    sync.turn_on(a, str(drive))
    rounds(a)
    sync.turn_on(b, str(drive))
    config.update(b.layout.settings, "server", {"port": 9000})
    rounds(b, a, b)
    [account] = {t.account for t in analyze(a).dataset.transactions}
    with a.db() as db:
        aliases.change(db, account, "Maaş hesabı", Actor.USER)
    config.update(a.layout.settings, "identity", {"names": ["Deneme Kişi"]})
    config.update(a.layout.settings, "server", {"port": 9100})
    a.rules.write_text(RULES + "\nUlaşım:\n  Taksi:\n    _: [TAKSI]\n", encoding="utf-8")
    rounds(a, b)
    with b.db() as db:
        assert aliases.every(db)[account].alias == "Maaş hesabı"
    settings = config.load(b.layout.settings)
    assert settings.identity.names == ("Deneme Kişi",)
    assert settings.server.port == 9000  # the computer's own
    assert "TAKSI" in b.rules.read_text(encoding="utf-8")
    assert any(p.name.startswith("personal ") for p in b.rules_history.iterdir())  # b's rules before, kept


def test_a_computer_joining_with_data_of_its_own_keeps_what_the_others_lack_and_takes_what_they_decided(a, b, drive):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    fingerprint = note_on_coffee(a, "a'nın notu")
    sync.turn_on(a, str(drive))
    rounds(a)
    add(b, "ocak.xls", teb.account_export(JANUARY))  # b read the same list on its own, and the February one
    add(b, "subat.xls", FEBRUARY)
    note_on_coffee(b, "b'nin notu")  # later than a's, but b joins: what the set of data decided wins
    with b.db() as db:
        memories.write(db, "b-notu", MemoryKind.USER, "b'de yazılan not", "b'de yazıldı.", Actor.MCP)
    sync.turn_on(b, str(drive))
    rounds(b, a, b)
    for ws in (a, b):
        with ws.db() as db:
            assert annotations.get(db, fingerprint).note == "a'nın notu"
            assert memories.get(db, "b-notu") is not None
            assert {d.name for d in documents.every(db)} == {"ocak.xls", "subat.xls"}
    assert ledger(a) == ledger(b)


def test_one_computer_sends_telegram_and_another_takes_over_when_it_goes_silent(a, b, drive):
    sync.turn_on(a, str(drive))
    sync.run_round(a, channels=lambda: ("telegram",))
    sync.turn_on(b, str(drive))
    rounds(b)
    sync.run_round(b, channels=lambda: ("telegram",))
    assert sends(a, Channel.TELEGRAM)
    assert not sends(b, Channel.TELEGRAM)
    assert sends(b, Channel.DESKTOP)  # every computer's own
    later = datetime.now(UTC) + sync.TAKEOVER_AFTER + timedelta(minutes=1)
    sync.run_round(b, channels=lambda: ("telegram",), now=later)
    sync.run_round(a, channels=lambda: ("telegram",), now=later)
    assert sends(b, Channel.TELEGRAM)
    assert not sends(a, Channel.TELEGRAM)


def test_the_user_moves_the_notifications_to_this_computer(a, b, drive):
    sync.turn_on(a, str(drive))
    sync.run_round(a, channels=lambda: ("telegram", "email"))
    sync.turn_on(b, str(drive))
    sync.run_round(b, channels=lambda: ("telegram",))
    sync.claim(b, ["telegram"])
    sync.run_round(b, channels=lambda: ("telegram",))
    sync.run_round(a, channels=lambda: ("telegram", "email"))
    assert sends(b, Channel.TELEGRAM) and not sends(a, Channel.TELEGRAM)
    assert sends(a, Channel.EMAIL) and not sends(b, Channel.EMAIL)
    with pytest.raises(sync.SyncError):
        sync.claim(b, [])


def test_turning_it_off_leaves_the_folder_and_lets_the_channels_go(a, b, drive):
    sync.turn_on(a, str(drive))
    sync.run_round(a, channels=lambda: ("telegram",))
    sync.turn_off(a)
    assert not config.load(a.layout.settings).sync.folder
    with a.db() as db:
        me = sync._me(db)
    told = library.read_device(drive, me.device)
    assert told is not None and told.left
    sync.turn_on(b, str(drive))
    rounds(b)
    sync.run_round(b, channels=lambda: ("telegram",))
    assert sends(b, Channel.TELEGRAM)


def test_a_folder_that_holds_other_files_is_refused_and_a_missing_one_is_a_problem(a, tmp_path, drive):
    busy = tmp_path / "dolu"
    busy.mkdir()
    (busy / "tatil.jpg").write_bytes(b"resim")
    assert not sync.inspect(busy).usable
    with pytest.raises(sync.SyncError):
        sync.turn_on(a, str(busy))
    assert not any(p.name == library.MARKER for p in busy.iterdir())
    sync.turn_on(a, str(drive))
    (drive / library.MARKER).rename(tmp_path / "isaret-baska-yerde")
    result = sync.run_round(a)
    assert not result.ran and "bulunamadı" in result.problem
    assert not (drive / library.MARKER).exists()  # never made again behind the user's back
    assert sync.status(a).problem


def test_inspect_tells_a_new_folder_from_one_another_computer_began(a, b, drive):
    place = sync.inspect(drive)
    assert place.usable and not place.exists
    sync.turn_on(a, str(drive))
    sync.run_round(a)
    place = sync.inspect(drive)
    assert place.exists and [d.name for d in place.devices] == ["Deneme Bilgisayarı"]


def test_a_state_file_half_brought_or_from_a_newer_version_is_left_for_later(a, b, drive):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    sync.turn_on(a, str(drive))
    rounds(a)
    with a.db() as db:
        me = sync._me(db)
    state = library.device_dir(drive, me.device) / library.STATE_FILE
    whole = state.read_bytes()
    state.write_bytes(whole[: len(whole) // 2])
    sync.turn_on(b, str(drive))
    result = sync.run_round(b)
    assert result.ran and not result.problem  # read again in the next round
    with b.db() as db:
        assert not documents.every(db)
    newer = json.loads(whole)
    newer["version"] = 99
    state.write_bytes(json.dumps(newer).encode())
    result = sync.run_round(b)
    assert "güncelleyin" in result.problem
    state.write_bytes(whole)
    rounds(b)
    with b.db() as db:
        assert [d.name for d in documents.every(db)] == ["ocak.xls"]


def test_a_data_folder_copied_to_another_machine_takes_a_new_id(a, drive, monkeypatch):
    sync.turn_on(a, str(drive))
    sync.run_round(a)
    with a.db() as db:
        before = sync._me(db).device
    monkeypatch.setattr(machine, "fingerprint", lambda: "makine-2")
    sync.run_round(a)
    with a.db() as db:
        after = sync._me(db).device
    assert after != before and sorted(library.devices(drive)) == sorted([before, after])


def test_a_restored_older_database_catches_up_from_the_folder(a, drive, tmp_path):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    sync.turn_on(a, str(drive))
    rounds(a)
    older = tmp_path / "eski.db"
    with a.db() as db:
        database.backup(db, older)
    with a.db() as db:
        memories.write(db, "sonra", MemoryKind.USER, "sonradan yazılan", "sonradan", Actor.MCP)
    rounds(a)
    for side in ("-wal", "-shm"):  # as a restore puts a backup's database back
        a.layout.database.with_name(a.layout.database.name + side).unlink(missing_ok=True)
    shutil.copyfile(older, a.layout.database)
    rounds(a)
    with a.db() as db:
        assert memories.get(db, "sonra") is not None  # back from what this computer wrote into the folder


def test_claude_notes_written_through_mcp_reach_the_other_computer(a, b, drive):
    sync.turn_on(a, str(drive))
    rounds(a)
    sync.turn_on(b, str(drive))
    rounds(b)
    memory.write(
        a, "ev-kirasi", Actor.MCP, kind=MemoryKind.PROJECT, description="Kira 5'inde", body="Kira 5'inde çıkar."
    )
    rounds(a, b)
    with b.db() as db:
        assert memories.get(db, "ev-kirasi") is not None
