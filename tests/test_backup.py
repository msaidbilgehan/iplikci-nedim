"""Backups (architecture §19, F20): what one holds, the originals copied once, 14 days kept, a restore in place that
can be undone or into a new folder, the monthly rehearsal, and the jobs, API and commands around them."""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from iplikci import cli
from iplikci.api.app import create_app
from iplikci.api.context import Context
from iplikci.app import annotate, background, backup, rebuild
from iplikci.app.analysis import analyze
from iplikci.app.workspace import Workspace
from iplikci.domain.codes import Actor, BackupReason, DocumentStatus, Necessity
from iplikci.fakes import teb
from iplikci.jobs import schedule
from iplikci.service import instance
from iplikci.settings import config
from iplikci.settings.config import SettingsError
from iplikci.storage import annotations, audit, db, documents, events
from iplikci.vault.store import sha256_of

from conftest import FEBRUARY, JANUARY, add

NOW = datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
TOKEN = "deneme-belirteci"
BASE = "http://127.0.0.1:8643"


@pytest.fixture
def kept(ws) -> Workspace:
    """ws with January's list, a note on its coffee and the user's settings."""
    add(ws, "ocak.xls", teb.account_export(JANUARY))
    [t] = [t for t in analyze(ws).dataset.transactions if t.merchant == "Kahveci Dukkan"]
    with ws.db() as database:
        annotations.change(database, t.fingerprint, annotate.subject(t, "TEB"), Actor.USER, note="arkadaşla")
    config.update(ws.layout.settings, "server", {"port": 8643})
    return ws


def notes(ws: Workspace) -> list[str]:
    with ws.db() as database:
        return [a.note for a in annotations.every(database).values()]


def test_a_backup_holds_the_database_its_primary_data_the_settings_the_rules_and_the_originals(kept):
    made = backup.take(kept, now=NOW)
    assert made.path == kept.layout.backups / made.name and made.name.startswith("yedek 2026-11-01 ")
    assert set(made.files) == {"iplikci.db", "birincil.json", "settings.toml", "rules/personal.yaml"}
    assert (made.documents, made.annotations, made.reason) == (1, 1, BackupReason.DAILY)
    assert not (made.path / "iplikci.db-wal").exists()  # one self-contained file
    with db.open_copy(made.path / "iplikci.db") as copy:
        assert len(documents.every(copy)) == 1
    primary = rebuild.load((made.path / "birincil.json").read_text(encoding="utf-8"))
    assert [a.note for a in primary.annotations] == ["arkadaşla"]
    [sha] = made.objects
    assert (kept.layout.backups / "vault" / "objects" / sha[:2] / sha[2:4] / sha).read_bytes() == kept.vault.read(sha)
    assert backup.verify(made) == [] and backup.every(kept) == [made]


def test_the_originals_are_copied_once(kept):
    first = backup.take(kept, now=NOW)
    [sha] = first.objects
    stored = kept.layout.backups / "vault" / "objects" / sha[:2] / sha[2:4] / sha
    before = stored.stat().st_mtime_ns
    add(kept, "subat.xls", FEBRUARY)
    second = backup.take(kept, now=NOW + timedelta(days=1))
    assert len(second.objects) == 2 and stored.stat().st_mtime_ns == before


def test_a_damaged_original_is_left_out_and_named(kept):
    with kept.db() as database:
        [doc] = documents.every(database)
    path = kept.vault.path(doc.sha256)
    os.chmod(path, 0o600)
    path.write_bytes(b"bozuk")
    made = backup.take(kept, now=NOW)
    assert made.objects == () and made.damaged == (doc.sha256,)


def test_fourteen_days_are_kept_and_the_newest_always_stays(kept):
    old = backup.take(kept, now=NOW - timedelta(days=20))
    with kept.db() as database:
        [doc] = documents.every(database)
        documents.set_status(database, doc.sha256, DocumentStatus.REMOVED, "kullanıcı kaldırdı")
    kept.vault.remove(doc.sha256)  # removed through the program, to the Trash: only the old backup needs it now
    recent = backup.take(kept, now=NOW - timedelta(days=3))
    assert backup.prune(kept, now=NOW) == [old.name]
    assert backup.every(kept) == [recent]
    assert list((kept.layout.backups / "vault" / "objects").rglob(doc.sha256)) == []
    assert backup.prune(kept, now=NOW + timedelta(days=30)) == []  # the newest stays, however old


def test_the_backups_keep_the_only_copy_of_an_original_the_archive_lost(kept):
    old = backup.take(kept, now=NOW - timedelta(days=20))
    with kept.db() as database:
        [doc] = documents.every(database)
    path = kept.vault.path(doc.sha256)
    os.chmod(path, 0o600)
    path.unlink()  # lost outside the program: the backups' copy is the only one left
    backup.take(kept, now=NOW - timedelta(days=3))
    assert backup.prune(kept, now=NOW) == [old.name]
    [copy] = (kept.layout.backups / "vault" / "objects").rglob(doc.sha256)
    assert sha256_of(copy.read_bytes()) == doc.sha256


def test_a_restore_in_place_can_be_undone(kept):
    made = backup.take(kept, now=NOW)
    with kept.db() as database:
        database.execute("DELETE FROM annotations")
    add(kept, "subat.xls", FEBRUARY)
    config.update(kept.layout.settings, "server", {"port": 9000})
    done = backup.restore(kept, made)
    assert notes(kept) == ["arkadaşla"] and config.load(kept.layout.settings).server.port == 8643
    assert done.unknown == 1  # February's original stays in the archive; the backup's database never knew it
    with kept.db() as database:
        assert audit.targets(database, "backup.restored") == {made.name}
    [safety] = [b for b in backup.every(kept) if b.reason is BackupReason.BEFORE_RESTORE]
    assert safety.name == done.safety and safety.documents == 2
    backup.restore(kept, safety)
    assert notes(kept) == [] and config.load(kept.layout.settings).server.port == 9000


def test_a_restore_stopped_half_way_puts_back_what_was_there(kept):
    made = backup.take(kept, now=NOW)
    [sha] = made.objects
    for path in (kept.vault.path(sha), kept.layout.backups / "vault" / "objects" / sha[:2] / sha[2:4] / sha):
        os.chmod(path, 0o600)
    kept.vault.path(sha).unlink()  # the archive lost the original, and the backups' copy of it is damaged
    (kept.layout.backups / "vault" / "objects" / sha[:2] / sha[2:4] / sha).write_bytes(b"bozuk")
    with kept.db() as database:
        database.execute("DELETE FROM annotations")
    config.update(kept.layout.settings, "server", {"port": 9000})
    with pytest.raises(backup.BackupError, match="geri yüklenemedi .* önceki hâline döndü"):
        backup.restore(kept, made)
    # Not the backup's note and port, nor half of them: the database and the settings as they were before.
    assert notes(kept) == [] and config.load(kept.layout.settings).server.port == 9000


def test_a_backup_is_restored_into_a_new_folder_whole(kept, tmp_path):
    made = backup.take(kept, now=NOW)
    done = backup.restore(kept, made, tmp_path / "yeni")
    copy = Workspace.load(tmp_path / "yeni")
    assert done.objects == 1 and done.safety == "" and done.unknown == 0
    assert notes(copy) == ["arkadaşla"] and list(copy.vault.objects()) == list(made.objects)
    with pytest.raises(backup.BackupError, match="boş değil"):
        backup.restore(kept, made, tmp_path / "yeni")


def test_a_changed_backup_is_not_restored(kept):
    made = backup.take(kept, now=NOW)
    (made.path / "settings.toml").write_text("[server]\nport = 1\n", encoding="utf-8")
    assert backup.verify(made) == ["settings.toml değişmiş"]
    with pytest.raises(backup.BackupError, match="bozuk: settings.toml değişmiş"):
        backup.restore(kept, made)


def test_a_backup_of_a_newer_version_is_not_restored(kept):
    made = backup.take(kept, now=NOW)
    manifest = json.loads((made.path / "manifest.json").read_text(encoding="utf-8"))
    manifest["schema"] = db.schema_version() + 1
    (made.path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(backup.BackupError, match="daha yeni bir sürümle"):
        backup.restore(kept, backup.find(kept, made.name))


def test_the_rehearsal_restores_the_newest_backup_and_checks_it(kept):
    made = backup.take(kept, now=NOW)
    result = backup.rehearse(kept)
    assert result.ok and result.backup == made.name, (result.problems, result.differences)
    health = backup.health(kept, now=NOW)
    assert (health.count, health.rehearsal_ok, health.last) == (1, True, made.created_at)
    assert not list(kept.run.glob(".prova-*"))  # the temporary folder went


def test_the_rehearsal_finds_a_damaged_original(kept):
    made = backup.take(kept, now=NOW)
    [sha] = made.objects
    stored = kept.layout.backups / "vault" / "objects" / sha[:2] / sha[2:4] / sha
    os.chmod(stored, 0o600)
    stored.write_bytes(b"bozuk")
    result = backup.rehearse(kept)
    assert not result.ok and "nesnesi bozulmuş" in result.problems[0]
    assert backup.health(kept).rehearsal_ok is False


def test_the_next_daily_backup_is_due_at_once_then_after_half_past_three():
    morning = datetime(2026, 11, 1, 9, 0).astimezone()
    assert backup.next_due(None, morning) == morning.astimezone(UTC)
    done = morning - timedelta(hours=1)
    assert backup.next_due(done, morning) == datetime(2026, 11, 2, 3, 30).astimezone().astimezone(UTC)
    yesterday = morning - timedelta(days=1)
    assert backup.next_due(yesterday, morning) == morning.astimezone(UTC)


def test_a_monthly_period_begins_on_the_first_at_its_hour():
    period = schedule.monthly(datetime(2026, 1, 1, 4, 30).time())
    assert period(datetime(2026, 11, 1, 4, 0)) == "2026-10"
    assert period(datetime(2026, 11, 1, 4, 30)) == "2026-11"
    assert period(datetime(2026, 11, 30, 23, 0)) == "2026-11"


def test_a_failed_backup_is_told_once_a_day_and_tried_again(kept, monkeypatch):
    def full(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(backup, "take", full)
    for _ in range(2):
        with pytest.raises(OSError):
            background.back_up(kept, BackupReason.DAILY)
    with kept.db() as database:
        [failed] = events.entries(database, "backup.failed")
    assert failed.detail == {"stage": "backup", "error": "OSError"}


def test_the_night_job_makes_a_backup_and_deletes_the_expired_ones(kept):
    old = backup.take(kept, now=datetime.now(UTC) - timedelta(days=30))
    name = background.back_up(kept, BackupReason.DAILY)
    assert [b.name for b in backup.every(kept)] == [name] and old.name != name


def test_backups_are_listed_and_asked_for_through_the_api(kept):
    made = backup.take(kept, now=NOW)
    client = TestClient(create_app(Context(ws=kept, token=TOKEN)), base_url=BASE)
    bearer = {"Authorization": f"Bearer {TOKEN}"}
    [listed] = client.get("/api/backups", headers=bearer).json()
    assert (listed["name"], listed["reason"], listed["documents"]) == (made.name, "daily", 1)
    assert client.post("/api/backups", headers=bearer).json() == {"queued": True}
    with kept.db() as database:
        assert database.scalar("SELECT count(*) FROM jobs WHERE kind = ? AND status = 'queued'", ("backup.take",)) == 1
    health = client.get("/api/system", headers=bearer).json()["backup"]
    assert health["count"] == 1 and health["last"] == made.created_at and health["rehearsal_ok"] is None
    assert client.get("/api/backups").status_code == 401


def test_the_backup_folder_can_be_elsewhere_but_only_by_its_full_path(kept, tmp_path):
    with pytest.raises(SettingsError, match="tam yolu"):
        config.update(kept.layout.settings, "backup", {"folder": "goreli/klasor"})
    config.update(kept.layout.settings, "backup", {"folder": str(tmp_path / "harici")})
    made = backup.take(kept, now=NOW)
    assert made.path.parent == tmp_path / "harici" and (tmp_path / "harici" / "vault" / "objects").is_dir()


def test_the_commands_take_list_restore_and_rehearse(kept, monkeypatch, capsys):
    monkeypatch.setenv("IPLIKCI_HOME", str(kept.home))
    assert cli.main(["yedek", "al"]) == 0
    [made] = backup.every(kept)
    assert made.reason is BackupReason.MANUAL and "1 belge, 1 düzeltme" in capsys.readouterr().out
    assert cli.main(["yedek", "liste"]) == 0 and made.name in capsys.readouterr().out
    with kept.db() as database:
        database.execute("DELETE FROM annotations")
    assert cli.main(["yedek", "geri-yukle", made.name]) == 0  # the plan only
    assert "Hiçbir şeye dokunulmadı" in capsys.readouterr().out and notes(kept) == []
    with instance.held(kept.run, instance.Holder(111, 8643, "", "")):
        assert cli.main(["yedek", "geri-yukle", made.name, "--uygula"]) == 1
    assert "Servis çalışırken geri yüklenemez" in capsys.readouterr().err
    assert cli.main(["yedek", "geri-yukle", made.name, "--uygula"]) == 0
    assert notes(kept) == ["arkadaşla"] and "Önceki hâlin yedeği" in capsys.readouterr().out
    assert cli.main(["yedek", "prova"]) == 0 and "provası geçti" in capsys.readouterr().out
    assert cli.main(["yedek", "geri-yukle", "yok"]) == 1 and "adında bir yedek yok" in capsys.readouterr().err


def test_the_necessity_correction_survives_a_restore(kept, tmp_path):
    [t] = [t for t in analyze(kept).dataset.transactions if t.merchant == "Kahveci Dukkan"]
    with kept.db() as database:
        annotations.change(
            database, t.fingerprint, annotate.subject(t, "TEB"), Actor.USER, necessity=Necessity.REQUIRED
        )
    made = backup.take(kept, now=NOW)
    copy = Workspace.load(backup.restore(kept, made, tmp_path / "yeni").home)
    [again] = [t for t in analyze(copy).dataset.transactions if t.merchant == "Kahveci Dukkan"]
    assert again.necessity is Necessity.REQUIRED and Path(copy.home) == tmp_path / "yeni"
