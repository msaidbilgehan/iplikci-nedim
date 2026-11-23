"""The sync folder (ADR-0025, F22): two computers' data folders sharing one folder that a sync service would mirror.
Each test's computers are data folders beside each other; the "Google Drive" is a plain folder."""

import json
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from iplikci.app import annotate, dashboard, memory, notify, sync, telegram
from iplikci.app import shared as shared_module
from iplikci.app.analysis import analyze
from iplikci.app.workspace import Workspace
from iplikci.domain.codes import Actor, Channel, DeliveryStatus, DocumentStatus, MemoryKind
from iplikci.fakes import teb
from iplikci.settings import config
from iplikci.storage import aliases, annotations, audit, documents, events, feed_state, memories, notifications
from iplikci.storage import db as database
from iplikci.storage import sync as stored
from iplikci.sync import library, machine, places
from iplikci.sync.clock import Clock, Stamp
from iplikci.sync.state import Entry, Kind, Published, StateError, decode, encode, merge

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


def test_a_document_from_another_computer_is_news_in_the_feed_as_it_came_in(a, b, drive):
    sync.turn_on(a, str(drive))
    rounds(a)
    sync.turn_on(b, str(drive))
    rounds(b)
    add(a, "ocak.xls", teb.account_export(JANUARY))
    rounds(a, b)
    with b.db() as db:
        [doc] = documents.every(db)
        received = [e for e in events.entries(db, "document.received") if e.target == doc.sha256]
    assert [e.detail for e in received] == [{"source": "import"}]


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


def test_a_sync_that_has_not_worked_for_hours_is_an_alert_and_told_once_a_day(a, tmp_path, drive):
    sync.turn_on(a, str(drive))
    (drive / library.MARKER).rename(tmp_path / "isaret-baska-yerde")
    began = datetime.now(UTC)
    sync.run_round(a, now=began)
    assert sync.trouble(a) is not None
    alerts = dashboard.alerts(a, analyze(a), began.date(), [], at=began + timedelta(hours=1)).items
    assert not [x for x in alerts if x.kind == dashboard.AlertKind.SYNC_FAILED]  # a passing problem: no alert yet
    later = began + sync.FAILED_AFTER + timedelta(minutes=1)
    sync.run_round(a, now=later)
    sync.run_round(a, now=later + timedelta(minutes=1))
    alerts = dashboard.alerts(a, analyze(a), later.date(), [], at=later).items
    [alert] = [x for x in alerts if x.kind == dashboard.AlertKind.SYNC_FAILED]
    assert "bulunamadı" in alert.text and alert.link.screen == "settings"
    with a.db() as db:
        assert len(events.entries(db, sync.FAILED)) == 1  # told once that day
    (tmp_path / "isaret-baska-yerde").rename(drive / library.MARKER)
    sync.run_round(a, now=later + timedelta(minutes=2))
    assert sync.trouble(a) is None


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
    assert result.ran and result.problem == sync.WAITING  # nothing merged until the others' data is read whole
    with b.db() as db:
        assert not documents.every(db)
    assert not (library.device_dir(drive, sync.status(b).device) / library.STATE_FILE).exists()
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


# --- the notifications leaving the computer ----------------------------------------------------------------


@dataclass
class Recorder:
    got: list[str] = field(default_factory=list)

    def send(self, message) -> None:
        self.got.append(message.title)


def test_a_computer_that_does_not_send_telegram_gives_up_what_waits_for_it_there(a, b, drive):
    sync.turn_on(a, str(drive))
    sync.run_round(a, channels=lambda: ("telegram",))
    sync.turn_on(b, str(drive))
    rounds(b)
    at = datetime.now(UTC)
    with b.db() as db:
        added = notifications.add(
            db,
            notifications.Notification(
                id=0,
                created_at=at.isoformat(),
                rule="Ay kapandı",
                event_id=1,
                kind="month.closed",
                key="2026-10",
                channel=Channel.TELEGRAM,
                detail="summary",
                title="Ekim kapandı",
                body="Ekim kapandı.",
                status=DeliveryStatus.PENDING,
            ),
        )
    telegram = Recorder()
    notify.deliver(b, at, senders={Channel.TELEGRAM: telegram})
    assert telegram.got == []
    with b.db() as db:
        [n] = [n for n in notifications.every(db) if n.id == added]
    assert n.status == DeliveryStatus.FAILED and n.error == notify.ELSEWHERE
    notify.deliver(a, at, senders={Channel.TELEGRAM: telegram})  # a has none waiting: nothing to send twice


def test_only_the_computer_sending_telegram_reads_the_bot(a, b, drive):
    for ws in (a, b):
        config.update(ws.layout.settings, "notify", {"telegram_chat": 42})
        with ws.db() as db:
            feed_state.save(db, notify.BOT, "deneme_bot")
    with b.db() as db:
        assert telegram._listening(db, config.load(b.layout.settings), datetime.now(UTC))  # no sync: on its own
    sync.turn_on(a, str(drive))
    sync.run_round(a, channels=lambda: ("telegram",))
    sync.turn_on(b, str(drive))
    rounds(b)
    for ws, reads in ((a, True), (b, False)):
        with ws.db() as db:
            assert telegram._listening(db, config.load(ws.layout.settings), datetime.now(UTC)) is reads


# --- the merge, the clock and the places ---------------------------------------------------------------------


def test_stamps_never_go_back_and_come_after_every_stamp_seen():
    wall = iter([1000, 1000, 999, 5000])
    clock = Clock("aaaaaaaaaaaa", wall=lambda: next(wall))
    first, second, third = clock.now(), clock.now(), clock.now()
    assert first < second < third  # the wall clock went back; the stamps did not
    clock.observe(Stamp(9000, 7, "bbbbbbbbbbbb"))
    assert clock.now() > Stamp(9000, 7, "bbbbbbbbbbbb")
    assert Stamp.parse(third.text) == third


entry_lists = st.lists(
    st.tuples(
        st.sampled_from([Kind.ANNOTATION, Kind.DOCUMENT]),
        st.sampled_from(["k1", "k2"]),
        st.integers(0, 50),
        st.sampled_from([None, '{"note":"x"}', '{"removed":false}', '{"removed":true}']),
    ),
    max_size=12,
)


def _entries(raw) -> list[Entry]:
    # A stamp is never given twice: the position stands for the counter.
    return [Entry(kind, key, Stamp(ms, i, "aaaaaaaaaaaa"), value) for i, (kind, key, ms, value) in enumerate(raw)]


@given(entry_lists, st.randoms())
def test_merging_gives_the_same_pieces_in_any_order_and_however_often(raw, random):
    entries = _entries(raw)
    shuffled = list(entries)
    random.shuffle(shuffled)
    assert merge(entries) == merge(shuffled) == merge(entries + entries)
    half = len(entries) // 2
    assert merge([*merge(entries[:half]).values(), *entries[half:]]) == merge(entries)


@given(entry_lists)
def test_a_documents_removal_wins_over_every_version_that_keeps_it(raw):
    for (kind, _), winner in merge(_entries(raw)).items():
        removed = [e for e in _entries(raw) if e.id == winner.id and e.value == '{"removed":true}']
        if kind == Kind.DOCUMENT and removed:
            assert winner.value == '{"removed":true}'


def test_the_state_file_reads_back_as_written():
    entries = (
        Entry(Kind.ANNOTATION, "parmak-izi", Stamp(1, 0, "aaaaaaaaaaaa"), '{"note":"çay","tags":["iş"]}'),
        Entry(Kind.MEMORY, "silinen", Stamp(2, 1, "bbbbbbbbbbbb"), None),
    )
    published = Published("kume", "aaaaaaaaaaaa", "1.1.0", "2026-11-24T10:00:00+00:00", entries)
    assert decode(encode(published)) == published
    with pytest.raises(StateError):
        decode(b'{"format": "baska"}')


def test_google_drive_is_found_under_the_users_cloud_storage_and_the_others_after_it(tmp_path):
    home = tmp_path / "ev"
    (home / "Library" / "CloudStorage" / "GoogleDrive-kisi@example.com" / "Drive'ım").mkdir(parents=True)
    (home / "Library" / "CloudStorage" / "GoogleDrive-kisi@example.com" / "Diğer bilgisayarlar").mkdir()
    (home / "Library" / "Mobile Documents" / "com~apple~CloudDocs").mkdir(parents=True)
    found = places.found(home, "darwin", {}, volumes=tmp_path / "yok")
    assert [(p.label, p.account, p.root.name) for p in found] == [
        ("Google Drive", "kisi@example.com", "Drive'ım"),
        ("iCloud Drive", "", "com~apple~CloudDocs"),
    ]
    assert places.kind_of(found[0].root / "İplikçi Nedim", found) == found[0]


def test_google_drive_is_found_on_its_own_drive_letter_on_windows(tmp_path):
    (tmp_path / "G" / "My Drive").mkdir(parents=True)
    found = places.found(tmp_path / "ev", "win32", {}, drive_root=lambda letter: tmp_path / letter)
    assert [(p.label, p.root) for p in found] == [("Google Drive", tmp_path / "G" / "My Drive")]


# --- many computers, any order: they end with the same data ----------------------------------------------------

operations = st.lists(
    st.tuples(
        st.integers(0, 2),  # the computer
        st.sampled_from(["note", "unnote", "memory", "forget", "alias", "names", "rules", "round"]),
        st.integers(0, 2),  # which piece
        st.integers(0, 3),  # which value
    ),
    min_size=1,
    max_size=25,
)


def _act(ws: Workspace, action: str, piece: int, value: int) -> None:
    subject = annotations.Subject("hesap", "Hesap", "2026-01-01", 100, "TRY", f"satır {piece}")
    with ws.db() as db:
        if action == "note":
            annotations.change(db, f"iz-{piece}", subject, Actor.USER, note=f"not {value}")
        elif action == "unnote":
            annotations.change(db, f"iz-{piece}", subject, Actor.USER, note="")
        elif action == "memory":
            memories.write(db, f"not-{piece}", MemoryKind.USER, f"açıklama {value}", f"metin {value}", Actor.MCP)
        elif action == "forget":
            memories.remove(db, f"not-{piece}", Actor.USER)
        elif action == "alias":
            aliases.change(db, f"hesap-{piece}", f"ad {value}" if value else "", Actor.USER)
    if action == "names":
        config.update(ws.layout.settings, "identity", {"names": [f"Kişi {value}"]})
    elif action == "rules":
        ws.rules.write_text(RULES + f"\nUlaşım:\n  Taksi {value}:\n    _: [TAKSI{value}]\n", encoding="utf-8")
    elif action == "round":
        sync.run_round(ws)


def _shared(ws: Workspace) -> dict[tuple[str, str], str]:
    from iplikci.app import shared

    with ws.db() as db:
        found = {k: v for k, v in shared.db_values(db).items() if k[0] != Kind.DOCUMENT and k[0] != Kind.SOURCE}
    return found | shared.file_kind_values(ws)


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(operations)
def test_computers_changing_the_same_pieces_in_any_order_end_with_the_same_data(steps):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / "drive").mkdir()
        computers = [computer(root, name) for name in ("a", "b", "c")]
        sync._peers.clear()
        sync._beats.clear()
        for ws in computers:
            sync.turn_on(ws, str(root / "drive" / library.DEFAULT_NAME))
            sync.run_round(ws)
        for who, action, piece, value in steps:
            _act(computers[who], action, piece, value)
        for _ in range(3):  # everyone hears of everything
            for ws in computers:
                sync.run_round(ws)
        first = _shared(computers[0])
        assert all(_shared(ws) == first for ws in computers[1:])


def _essence(ws: Workspace) -> dict[str, object]:
    """What the user sees of the shared pieces, without the times a computer wrote them at."""
    with ws.db() as db:
        found: dict[str, object] = {f"note {k}": a.note for k, a in annotations.every(db).items()}
        found |= {f"memory {m.name}": (m.kind, m.description, m.body) for m in memories.every(db)}
        found |= {f"alias {k}": a.alias for k, a in aliases.every(db).items()}
    found["names"] = config.load(ws.layout.settings).identity.names
    found["rules"] = ws.rules.read_text(encoding="utf-8")
    return found


@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(operations)
def test_changes_made_one_after_another_with_the_sync_between_them_keep_the_last_one(steps):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / "drive").mkdir()
        computers = [computer(root, name) for name in ("a", "b")]
        alone = computer(root, "tek")  # the same steps on one computer without the sync
        sync._peers.clear()
        sync._beats.clear()
        for ws in computers:
            sync.turn_on(ws, str(root / "drive" / library.DEFAULT_NAME))
            sync.run_round(ws)
        for who, action, piece, value in steps:
            if action == "round":
                continue
            _act(computers[who % 2], action, piece, value)
            _act(alone, action, piece, value)
            for _ in range(2):
                for ws in computers:
                    sync.run_round(ws)
        assert _essence(computers[0]) == _essence(computers[1]) == _essence(alone)


# --- what the review found (ADR-0025's failure cases) ----------------------------------------------------------


def _device(ws: Workspace) -> str:
    with ws.db() as db:
        return sync._me(db).device


def _hide(drive: Path, device: str, where: Path) -> Path:
    """A computer's part of the folder not here yet (the sync service still bringing it); where it is kept."""
    return library.device_dir(drive, device).rename(where / f"gizli-{device}")


def test_a_computer_joining_before_the_others_data_is_here_waits_and_then_lets_the_folder_win(a, b, drive, tmp_path):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    fingerprint = note_on_coffee(a, "a'nın notu")
    config.update(a.layout.settings, "identity", {"names": ["Klasördeki Ad"]})
    sync.turn_on(a, str(drive))
    rounds(a)
    hidden = _hide(drive, _device(a), tmp_path)
    add(b, "ocak.xls", teb.account_export(JANUARY))
    note_on_coffee(b, "b'nin daha yeni notu")
    config.update(b.layout.settings, "identity", {"names": ["Eski Ad"]})
    b.rules.write_text(RULES + "\nEski:\n  Kural:\n    _: [ESKI]\n", encoding="utf-8")
    sync.turn_on(b, str(drive))
    for _ in range(3):
        assert sync.run_round(b).problem == sync.WAITING
    assert not (library.device_dir(drive, _device(b)) / library.STATE_FILE).exists()  # nothing of b's goes out yet
    hidden.rename(library.device_dir(drive, _device(a)))
    rounds(b, a, b)
    for ws in (a, b):
        with ws.db() as db:
            assert annotations.get(db, fingerprint).note == "a'nın notu"
        assert config.load(ws.layout.settings).identity.names == ("Klasördeki Ad",)
        assert "ESKI" not in ws.rules.read_text(encoding="utf-8")
    assert not sync.status(b).problem


def test_a_state_file_that_could_not_be_read_is_read_again_in_the_next_round(a, b, drive):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    sync.turn_on(a, str(drive))
    rounds(a)
    state = library.device_dir(drive, _device(a)) / library.STATE_FILE
    sync.turn_on(b, str(drive))
    state.chmod(0)  # the sync service cannot give it now; its size and time stay as they are
    try:
        assert sync.run_round(b).problem
    finally:
        state.chmod(0o600)
    rounds(b)
    with b.db() as db:
        assert [d.name for d in documents.every(db)] == ["ocak.xls"]


def test_a_change_made_while_the_folder_is_away_keeps_its_time_and_a_later_one_wins(a, b, drive, tmp_path):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    fingerprint = note_on_coffee(a, "ilk")
    sync.turn_on(a, str(drive))
    rounds(a)
    sync.turn_on(b, str(drive))
    rounds(b, a, b)
    away = drive.rename(tmp_path / "drive-gitti")  # Google Drive not running on either computer
    note_on_coffee(b, "b'de önce")
    assert "bulunamadı" in sync.run_round(b).problem  # stamped all the same
    note_on_coffee(a, "a'da sonra")
    sync.run_round(a)
    away.rename(drive)
    rounds(b, a, b)
    for ws in (a, b):
        with ws.db() as db:
            assert annotations.get(db, fingerprint).note == "a'da sonra"


def test_a_change_made_while_the_sync_is_off_keeps_its_time(a, b, drive):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    fingerprint = note_on_coffee(a, "ilk")
    sync.turn_on(a, str(drive))
    rounds(a)
    sync.turn_on(b, str(drive))
    rounds(b, a, b)
    sync.turn_off(b)
    note_on_coffee(b, "kapalıyken")
    sync.run_round(b)
    note_on_coffee(a, "sonra")
    rounds(a)
    sync.turn_on(b, str(drive))
    rounds(b, a, b)
    for ws in (a, b):
        with ws.db() as db:
            assert annotations.get(db, fingerprint).note == "sonra"


def _forge(drive: Path, device: str, rows: list[list[object]]) -> None:
    """Pieces written into a computer's state file by someone else (a damaged or forged file)."""
    state = library.device_dir(drive, device) / library.STATE_FILE
    value = json.loads(state.read_bytes())
    value["entries"] += rows
    state.write_bytes(json.dumps(value, ensure_ascii=False).encode())


def test_a_malformed_or_forged_piece_is_left_out_and_the_rounds_go_on(a, b, drive):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    sync.turn_on(a, str(drive))
    rounds(a)
    stamp = "0000000000001.00000.aaaaaaaaaaaa"
    _forge(
        drive,
        _device(a),
        [
            [
                "document",
                "../../disari",
                stamp,
                {"name": "x", "size": 1, "added_at": "", "parent": "", "removed": True, "reason": ""},
            ],
            ["source", "bir anahtar değil", stamp, {"sender": "", "subject": "", "sent_at": "", "received_at": ""}],
            ["alias", "hesap-1", stamp, {"alias": ["liste"], "updated_at": "", "actor": "user"}],
            ["memory", "gelecek", "9999999999999.99999.aaaaaaaaaaaa", None],
            ["setting", "mail.verify_sender", stamp, False],
            ["rate", "2026-01-01 tcmb USD", stamp, {"buying": "1"}],  # a newer version's kind passes through
        ],
    )
    sync.turn_on(b, str(drive))
    result = sync.run_round(b)
    assert result.ran and "5 kayıt atlandı" in result.problem
    rounds(b)
    with b.db() as db:
        assert [d.name for d in documents.every(db)] == ["ocak.xls"]
        assert not aliases.every(db)
        assert stored.get(db, "rate", "2026-01-01 tcmb USD") is not None
        assert stored.load(db, sync.CLOCK) < "9"  # the clock took no stamp from 2286
    assert config.load(b.layout.settings).mail.verify_sender  # never another computer's to turn off


def test_a_piece_that_cannot_be_put_in_place_holds_up_no_other(a, b, drive, monkeypatch):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    with a.db() as db:
        memories.write(db, "bir-not", MemoryKind.USER, "bir not", "bir", Actor.MCP)
    sync.turn_on(a, str(drive))
    rounds(a)
    real = shared_module.put_db

    def failing(ws, db, kind, key, value, applied):
        if kind == Kind.DOCUMENT:
            raise sqlite3.ProgrammingError("bu sürümün okuyamadığı bir değer")
        return real(ws, db, kind, key, value, applied)

    monkeypatch.setattr(shared_module, "put_db", failing)
    sync.turn_on(b, str(drive))
    result = sync.run_round(b)
    assert result.ran and not result.problem
    with b.db() as db:
        assert memories.get(db, "bir-not") is not None  # put in place beside the document that could not be
        assert not documents.every(db)
    monkeypatch.setattr(shared_module, "put_db", real)
    rounds(b)
    with b.db() as db:
        assert [d.name for d in documents.every(db)] == ["ocak.xls"]


def test_bytes_brought_in_before_their_removal_came_go_to_the_trash(a, b, drive, monkeypatch):
    sync.turn_on(a, str(drive))
    rounds(a)
    sync.turn_on(b, str(drive))
    rounds(b)
    add(a, "subat.xls", FEBRUARY)
    rounds(a)
    with a.db() as db:
        [doc] = documents.every(db)
    real = sync._merge
    monkeypatch.setattr(sync, "_merge", lambda *args: (_ for _ in ()).throw(sync.Busy("okuma sürüyor")))
    sync.run_round(b)  # the bytes come in; a long reading holds the documents, so nothing is merged
    assert b.vault.has(doc.sha256)
    monkeypatch.setattr(sync, "_merge", real)
    from iplikci.app import documents as document_cases

    document_cases.remove(a, doc.sha256, Actor.USER)
    rounds(a, b)
    with b.db() as db:
        assert documents.get(db, doc.sha256).status is DocumentStatus.REMOVED
    assert not b.vault.has(doc.sha256)  # to the Trash, never kept


def test_a_joining_computers_old_removal_never_removes_what_the_others_keep(a, b, drive):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    sync.turn_on(a, str(drive))
    rounds(a)
    add(b, "ocak.xls", teb.account_export(JANUARY))
    with b.db() as db:
        [doc] = documents.every(db)
    from iplikci.app import documents as document_cases

    document_cases.remove(b, doc.sha256, Actor.USER)  # long before b joined
    sync.turn_on(b, str(drive))
    rounds(b, a, b)
    for ws in (a, b):
        with ws.db() as db:
            assert documents.get(db, doc.sha256).status is not DocumentStatus.REMOVED
        assert ws.vault.has(doc.sha256)
    assert ledger(a) == ledger(b)


def test_a_removal_not_in_place_here_leaves_this_computers_original_in_the_folder(a, b, drive, monkeypatch):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    sync.turn_on(a, str(drive))
    rounds(a)
    sync.turn_on(b, str(drive))
    rounds(b, a, b)
    with b.db() as db:
        [doc] = documents.every(db)
    from iplikci.app import documents as document_cases

    document_cases.remove(b, doc.sha256, Actor.USER)
    rounds(b)
    real = shared_module.put_db
    monkeypatch.setattr(shared_module, "put_db", lambda *args: (_ for _ in ()).throw(ValueError("okunamadı")))
    sync.run_round(a)  # a merges the removal but cannot put it in place
    assert library.object_path(drive, _device(a), doc.sha256).exists()
    monkeypatch.setattr(shared_module, "put_db", real)
    rounds(a)
    assert not library.object_path(drive, _device(a), doc.sha256).exists()


def test_a_channel_just_taken_is_not_let_go_on_an_old_word_that_it_cannot_send(a, b, drive):
    sync.turn_on(a, str(drive))
    sync.run_round(a, channels=lambda: ("telegram",))
    sync.turn_on(b, str(drive))
    rounds(b)
    sync.claim(b, ["telegram"])
    sync.run_round(b, channels=lambda: ())  # the service's list from before the bot was paired here
    assert sends(b, Channel.TELEGRAM)
    later = datetime.now(UTC) + sync.CLAIM_GRACE + timedelta(minutes=1)
    sync.run_round(b, channels=lambda: (), now=later)
    assert not sends(b, Channel.TELEGRAM)


def test_the_computer_taking_telegram_over_sends_what_the_silent_one_missed(a, b, drive, monkeypatch):
    for ws in (a, b):
        config.update(ws.layout.settings, "notify", {"telegram_chat": 42, "quiet_hours": ""})
        with ws.db() as db:
            feed_state.save(db, notify.BOT, "deneme_bot")
    monkeypatch.setattr(notify, "telegram_token", lambda: "belirtec")
    sync.turn_on(a, str(drive))
    sync.run_round(a, channels=lambda: ("telegram",))
    sync.turn_on(b, str(drive))
    rounds(b)
    sync.run_round(b, channels=lambda: ("telegram",))
    notify.take_events(b)  # b's first run: what happened before is no news
    with b.db() as db:
        events.append(db, "month.closed", "2026-10")  # a went silent (asleep) and told nobody
    notify.take_events(b)
    with b.db() as db:
        assert not [n for n in notifications.every(db) if n.channel == Channel.TELEGRAM]
    later = datetime.now(UTC) + sync.TAKEOVER_AFTER + timedelta(minutes=1)
    sync.run_round(b, channels=lambda: ("telegram",), now=later)
    assert sends(b, Channel.TELEGRAM)
    notify.take_events(b)
    with b.db() as db:
        told = [n for n in notifications.every(db) if n.channel == Channel.TELEGRAM]
        assert [n.key for n in told] == ["2026-10"]
        assert not sync.catch_ups(db)
    notify.take_events(b)
    with b.db() as db:
        assert len([n for n in notifications.every(db) if n.channel == Channel.TELEGRAM]) == 1  # once


def test_a_copied_data_folder_says_nothing_for_the_computer_it_was_copied_from(a, drive, tmp_path, monkeypatch):
    sync.turn_on(a, str(drive))
    sync.run_round(a, channels=lambda: ("telegram",))
    state = library.device_dir(drive, _device(a)) / library.STATE_FILE
    before = state.read_bytes()
    copy = Workspace.load(Path(shutil.copytree(a.home, tmp_path / "kopya")))
    monkeypatch.setattr(machine, "fingerprint", lambda: "makine-2")
    assert not sends(copy, Channel.TELEGRAM)  # the original holds it
    sync.turn_off(copy)
    assert state.read_bytes() == before
    told = library.read_device(drive, _device(a))
    assert told is not None and not told.left


def test_the_sync_turned_on_in_another_folder_puts_the_originals_there(a, tmp_path, drive):
    add(a, "ocak.xls", teb.account_export(JANUARY))
    sync.turn_on(a, str(drive))
    rounds(a)
    other = tmp_path / "Dropbox" / library.DEFAULT_NAME
    other.parent.mkdir()
    sync.turn_on(a, str(other))
    rounds(a)
    [sha] = list(a.vault.objects())
    assert library.object_path(other, _device(a), sha).exists()
    assert sync.status(a).waiting_up == 0


def test_a_settings_change_waits_when_the_file_changed_since_it_was_compared(a):
    config.update(a.layout.settings, "notify", {"quiet_hours": "22:00-07:00"})
    with pytest.raises(config.Changed):
        config.update(a.layout.settings, "notify", {"quiet_hours": "23:00-08:00"}, guard=lambda tables: False)
    assert config.load(a.layout.settings).notify.quiet_hours == "22:00-07:00"
    with pytest.raises(shared_module.Waits):
        shared_module.put_file(a, Kind.SETTING, "notify.quiet_hours", '"23:00-08:00"', expected="eski bir özet")
