"""The program's own updates in the service (ADR-0022, F21): the daily check, installing a new version, and how the
next start tells it. GitHub is a fake that serves a release signed with a key the test makes; nothing leaves."""

import base64
import hashlib
import json
import tempfile
from datetime import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from iplikci import __version__, egress
from iplikci.app import background, backup, kinds, lifecycle, update
from iplikci.domain.codes import Actor, BackupReason
from iplikci.service import manager
from iplikci.settings import config
from iplikci.storage import audit, jobs
from iplikci.update import install, keys, manifest, source
from iplikci.update.install import Installation, Kind
from iplikci.update.manifest import Entry, Manifest

NEXT = "99.0.0"  # newer than whatever the program is
PLATFORM = manifest.platform_key() or "linux-x86_64"
PAYLOAD = b"yeni program"


class FakeGitHub:
    """github.com as egress.https_download reaches it: the files of one release by name, the latest and by tag."""

    def __init__(self) -> None:
        self.tag = ""
        self.files: dict[str, bytes] = {}
        self.asked: list[str] = []
        self.status = 200
        self.down = False

    def __call__(self, host, path, settings, into, *, follow, limit, timeout=60.0) -> egress.Downloaded:
        egress.check(host, settings)
        assert host == egress.GITHUB and follow == egress.GITHUB_FILES
        self.asked.append(path)
        if self.down:
            raise egress.Unreachable("github.com adresine ulaşılamadı (URLError)")
        name = path.rsplit("/", 1)[-1]
        prefixes = (source.latest("", source.REPO), source.tagged(self.tag, "", source.REPO))
        if self.status != 200 or not path.startswith(prefixes) or name not in self.files:
            return egress.Downloaded(self.status if self.status != 200 else 404, 0, "")
        body = self.files[name]
        if len(body) > limit:
            raise egress.TooLarge("büyük")
        into.write(body)
        return egress.Downloaded(200, len(body), hashlib.sha256(body).hexdigest())

    def latest_asked(self) -> int:
        return sum(1 for p in self.asked if p.endswith(source.MANIFEST))


@pytest.fixture
def private_key(monkeypatch) -> bytes:
    """The release key for the test: the program trusts it alone."""
    key = Ed25519PrivateKey.generate()
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    monkeypatch.setattr(keys, "TRUSTED", {"deneme": base64.b64encode(raw).decode()})
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


@pytest.fixture
def github(monkeypatch, private_key, tmp_path) -> FakeGitHub:
    fake = FakeGitHub()
    monkeypatch.setattr(egress, "https_download", fake)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "gecici"))  # the downloads' folder, the test's own
    (tmp_path / "gecici").mkdir()
    fake.publish = lambda version=NEXT, payload=PAYLOAD, **kw: publish(fake, private_key, version, payload, **kw)  # type: ignore[attr-defined] - a test's helper
    return fake


def publish(fake: FakeGitHub, key: bytes, version: str, payload: bytes, signed_by: bytes | None = None) -> None:
    name = f"iplikci-nedim-{version}-{PLATFORM}.bin"
    release = Manifest(
        version=version,
        tag=f"v{version}",
        date="2026-11-11",
        notes="### Eklendi\n\n- Güncellemeler.",
        updates={PLATFORM: Entry(name, len(payload), hashlib.sha256(payload).hexdigest())},
    )
    data = manifest.render(release)
    fake.tag = release.tag
    fake.files = {
        source.MANIFEST: data,
        source.SIGNATURE: manifest.sign(data, signed_by or key, "deneme"),
        name: payload,
    }


@pytest.fixture
def registered(monkeypatch) -> None:
    monkeypatch.setattr(lifecycle, "registration", lambda ws: lifecycle.Registration(True, "launchd"))


def mode(ws, value: str) -> None:
    config.update(ws.layout.settings, "updates", {"mode": value})


def queued(ws, kind: str) -> list[dict]:
    with ws.db() as db:
        rows = db.rows("SELECT payload FROM jobs WHERE kind = ? AND status = 'queued'", (kind,))
    return [json.loads(r["payload"]) for r in rows]


APP = Installation(Kind.MACOS_APP, Path("/Applications/İplikçi Nedim.app"))
BY_HAND = install.MANUAL


# --- the check ------------------------------------------------------------------------------------------------------


def test_with_updates_off_github_is_never_asked(ws, github):
    github.publish()
    mode(ws, "off")
    found = update.check(ws, here=APP)
    assert github.asked == [] and found.available is None and found.checked_at == ""


def test_a_check_the_user_asks_for_asks_github_even_when_updates_are_off(ws, github):
    github.publish()
    mode(ws, "off")
    found = update.check(ws, forced=True, here=APP)
    assert github.latest_asked() == 1
    assert found.available is not None and found.available.version == NEXT and found.available.size == len(PAYLOAD)
    assert found.available.page == source.page(f"v{NEXT}") and found.check_error == ""
    assert queued(ws, update.INSTALL_JOB) == []  # off never installs by itself


def test_a_newer_version_is_installed_by_itself_only_when_the_mode_says_auto(ws, github):
    github.publish()
    mode(ws, "ask")
    update.check(ws, here=APP)
    assert queued(ws, update.INSTALL_JOB) == []
    mode(ws, "auto")
    update.check(ws, here=APP)
    assert queued(ws, update.INSTALL_JOB) == [{"version": NEXT}]


def test_a_copy_installed_by_hand_is_only_told(ws, github):
    github.publish()
    found = update.check(ws, here=BY_HAND)
    assert found.available is not None and not found.automatic and found.installation == "manual"
    assert queued(ws, update.INSTALL_JOB) == []


def test_the_running_version_or_an_older_one_is_nothing_to_install(ws, github):
    github.publish(version=__version__)
    assert update.check(ws, here=APP).available is None
    github.publish(version="0.0.1")
    assert update.check(ws, here=APP).available is None
    assert queued(ws, update.INSTALL_JOB) == []


def test_a_manifest_another_key_signed_is_not_believed(ws, github):
    github.publish(
        signed_by=Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    found = update.check(ws, here=APP)
    assert found.available is None and "güvenilmedi" in found.check_error and found.checked_at
    assert queued(ws, update.INSTALL_JOB) == []


def test_releases_github_does_not_show_say_where_they_must_be(ws, github):
    found = update.check(ws, here=APP)  # nothing published: 404, as a private repository answers
    assert "herkese açık" in found.check_error
    github.down = True
    assert "ulaşılamadı" in update.check(ws, here=APP).check_error


def test_the_check_runs_daily_from_five_and_the_worker_knows_both_jobs(ws):
    [job] = [p for p in background.PERIODIC if p.kind == update.CHECK_JOB]
    assert job.period.__qualname__.startswith("daily") and update.DAILY_AT == time(5, 0)
    assert {update.CHECK_JOB, update.INSTALL_JOB} <= set(background.handlers(ws))
    assert kinds.LABELS[update.CHECK_JOB] == "Yeni sürüm denetimi"


# --- installing -----------------------------------------------------------------------------------------------------


class Applied:
    def __init__(self) -> None:
        self.calls: list[tuple[Installation, bytes, str]] = []

    def __call__(self, ws, found: Installation, file: Path, version: str) -> None:
        self.calls.append((found, file.read_bytes(), version))


def test_an_install_downloads_checks_backs_up_puts_in_place_and_starts_again(ws, github, registered):
    github.publish()
    applied, restarts = Applied(), []
    found = update.install_update(ws, lambda: restarts.append(1), here=APP, apply=applied)
    assert applied.calls == [(APP, PAYLOAD, NEXT)] and restarts == [1]
    assert found.installing == NEXT
    assert [b.reason for b in backup.every(ws)] == [BackupReason.BEFORE_UPDATE]
    assert list((Path(tempfile.gettempdir())).iterdir()) == []  # the download went once it was in place


def test_a_download_that_is_not_the_manifests_file_is_never_put_in_place(ws, github, registered):
    github.publish()
    name = next(n for n in github.files if n.endswith(".bin"))
    github.files[name] = PAYLOAD.upper()  # as long as the manifest says, another SHA-256
    applied, restarts = Applied(), []
    found = update.install_update(ws, lambda: restarts.append(1), here=APP, apply=applied)
    assert applied.calls == [] and restarts == []
    assert found.last is not None and not found.last.ok and "aynı değil" in found.last.error
    assert found.installing == "" and backup.every(ws) == []
    assert list(Path(tempfile.gettempdir()).iterdir()) == []


def test_a_service_run_by_hand_does_not_update_itself(ws, github, monkeypatch):
    github.publish()
    monkeypatch.setattr(lifecycle, "registration", lambda ws: lifecycle.Registration(False, "launchd"))
    applied = Applied()
    found = update.install_update(ws, lambda: None, here=APP, apply=applied)
    assert applied.calls == [] and "kayıtlı değil" in found.check_error


def test_a_version_that_did_not_come_up_is_not_tried_by_itself_again(ws, github, registered, monkeypatch):
    github.publish()

    def broken(ws, found, file, version):
        raise install.InstallError("yeni sürüm açılamadı (çıkış kodu 1)")

    for attempt in range(1, update.TRIES + 1):
        found = update.install_update(ws, lambda: None, here=APP, apply=broken)
        assert found.last is not None and found.last.tries == attempt and not found.last.ok
    update.check(ws, here=APP)
    assert queued(ws, update.INSTALL_JOB) == []  # the check no longer queues it
    applied = Applied()
    update.install_update(ws, lambda: None, here=APP, apply=applied)
    assert applied.calls == []  # nor does a queued one run by itself
    update.install_update(ws, lambda: None, asked=True, here=APP, apply=applied)
    assert len(applied.calls) == 1  # the user may still ask


def test_on_windows_the_setup_program_runs_and_ends_the_service_itself(ws, github, monkeypatch):
    github.publish()
    program = ws.home.parent / "Programs" / "İplikçi Nedim"
    started: list[list[str]] = []
    monkeypatch.setattr(manager, "spawn_detached", lambda args: started.append(list(args)))
    restarts: list[int] = []
    update.install_update(ws, lambda: restarts.append(1), here=Installation(Kind.WINDOWS_SETUP, program))
    [command] = started
    assert command[1:5] == ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"]
    assert Path(command[0]).read_bytes() == PAYLOAD and command[-1] == f"/LOG={ws.logs / update.SETUP_LOG}"
    assert restarts == []


def test_on_linux_the_new_copy_is_unpacked_and_the_unit_starts_it_next(ws, github, registered, monkeypatch, tmp_path):
    github.publish()
    copies = tmp_path / ".local" / "lib" / "iplikci"
    python = copies / NEXT / "bin" / "python3"
    monkeypatch.setattr(install, "apply_linux", lambda root, archive, version: python)
    ran: list[list[str]] = []
    unit = manager.Systemd(
        user_home=tmp_path, run=lambda a: ran.append(list(a)) or manager.Completed(0, "", ""), env={}
    )
    monkeypatch.setattr(manager, "for_platform", lambda: unit)
    restarts: list[int] = []
    update.install_update(ws, lambda: restarts.append(1), here=Installation(Kind.LINUX_COPY, copies))
    assert unit.registered() == manager.Program(python, ws.home.resolve())
    assert ran == [["systemctl", "--user", "daemon-reload"]] and restarts == [1]


# --- the start after an install -------------------------------------------------------------------------------------


def started_install(ws, to: str) -> None:
    (ws.run).mkdir(parents=True, exist_ok=True)
    (ws.run / update.STATE).write_text(
        json.dumps({"installing": {"from": "0.0.1", "to": to, "at": "2026-11-11T05:00:00+00:00", "tries": 1}}),
        encoding="utf-8",
    )


def test_the_new_version_says_at_its_start_that_the_update_worked(ws, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    started_install(ws, __version__)
    outcome = update.finish(ws, here=BY_HAND)
    assert outcome is not None and outcome.ok and outcome.to_version == __version__
    found = update.state(ws, BY_HAND)
    assert found.installing == "" and found.last == outcome
    with ws.db() as db:
        assert [e.action for e in audit.entries(db)] == [update.INSTALLED]


def test_a_start_of_another_version_says_the_update_did_not_come_up(ws, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    started_install(ws, NEXT)
    outcome = update.finish(ws, here=BY_HAND)
    assert outcome is not None and not outcome.ok and "başlayamadı" in outcome.error
    assert update.finish(ws, here=BY_HAND) is None  # told once


def test_the_start_removes_what_the_old_version_left(ws, tmp_path, monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "gecici"))
    download = tmp_path / "gecici" / f"{update.TEMP_PREFIX}abc"
    download.mkdir(parents=True)
    app = tmp_path / "İplikçi Nedim.app"
    (app / install.OLD / "Resources").mkdir(parents=True)
    other = tmp_path / "gecici" / "baska-bir-program"
    other.mkdir()
    update.finish(ws, here=Installation(Kind.MACOS_APP, app))
    assert not (app / install.OLD).exists() and not download.exists() and other.exists()


# --- the user's side ----------------------------------------------------------------------------------------------


def test_the_user_asks_for_an_install_only_of_a_version_the_check_found(ws, github):
    with pytest.raises(update.UpdateError, match="yeni bir sürüm yok"):
        update.request_install(ws, Actor.USER, here=APP)
    github.publish()
    mode(ws, "ask")
    update.check(ws, here=APP)
    with pytest.raises(update.UpdateError, match="elle kuruldu"):
        update.request_install(ws, Actor.USER, here=BY_HAND)
    assert update.request_install(ws, Actor.USER, here=APP) == NEXT
    assert queued(ws, update.INSTALL_JOB) == [{"version": NEXT, "asked": True}]


def test_the_mode_is_a_setting_the_user_changes(ws):
    assert update.state(ws, APP).mode == "auto"
    assert update.set_mode(ws, "ask", Actor.USER).mode == "ask"
    assert config.load(ws.layout.settings).updates.mode == "ask"
    with pytest.raises(update.UpdateError):
        update.set_mode(ws, "bazen", Actor.USER)


def test_a_check_the_user_asks_for_is_queued(ws):
    update.request_check(ws)
    assert queued(ws, update.CHECK_JOB) == [{"forced": True}]


def test_the_state_knows_this_system_and_where_the_releases_are(ws):
    found = update.state(ws, BY_HAND)
    assert found.version == __version__ and found.platform == PLATFORM
    assert found.page == source.page() and found.available is None and found.last is None


def test_an_unreadable_state_file_reads_as_none(ws):
    ws.run.mkdir(parents=True, exist_ok=True)
    (ws.run / update.STATE).write_text("{bozuk", encoding="utf-8")
    assert update.state(ws, BY_HAND).checked_at == ""


def test_the_jobs_queue_keeps_one_waiting_check(ws):
    update.request_check(ws)
    update.request_check(ws)
    with ws.db() as db:
        assert jobs.counts(db).get("queued", 0) == 1


# --- the command line -----------------------------------------------------------------------------------------------


def test_the_command_checks_here_when_no_service_runs(ws, github, monkeypatch, capsys):
    from iplikci import cli

    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    github.publish()
    assert cli.main(["guncelleme", "denetle"]) == 0
    out = capsys.readouterr().out
    assert f"Sürüm: {__version__}" in out and f"Yeni sürüm: {NEXT} (2026-11-11)" in out
    assert cli.main(["guncelleme", "mod", "kapali"]) == 0
    assert "yeni sürüm denetlenmez" in capsys.readouterr().out
    assert config.load(ws.layout.settings).updates.mode == "off"


def test_the_command_asks_the_running_service(ws, monkeypatch, capsys):
    from iplikci import cli
    from iplikci.service import client, instance

    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    asked: list[tuple[str, str]] = []
    monkeypatch.setattr(client, "call", lambda ws, method, path, body=None: asked.append((method, path)) or {})
    with instance.held(ws.run, instance.Holder(111, ws.port, "", "")):
        assert cli.main(["guncelleme", "denetle"]) == 0
        assert cli.main(["guncelleme", "kur"]) == 0
    assert asked == [("POST", "/api/update/check"), ("POST", "/api/update/install")]
    assert "Servis yeni sürümü kuruyor" in capsys.readouterr().out
