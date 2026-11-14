"""macOS's packaged app removed by dragging it to the Trash (ADR-0017's note of 2026-11-15): the running service takes
its own registration off the computer and ends, and an agent whose app has gone removes itself before its Python would
start, where launchd would otherwise try again for ever. The data folder stays where it is. The agent's guard runs in
/bin/sh here, with stand-ins for launchctl and logger first on its PATH: nothing reaches launchd, the user's
LaunchAgents or the system's log."""

import plistlib
import shutil
import subprocess
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path

import pytest

from iplikci.app import lifecycle
from iplikci.service import manager, runner
from iplikci.storage import audit
from iplikci.update import install

JOB = "gui/501/com.iplikci.service"
PYTHON = Path("Contents") / "Resources" / "python" / "bin" / "python3"  # inside the app


class Tools:
    """launchctl as the service manager's stand-in: every command recorded and answered with success."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> manager.Completed:
        self.calls.append(list(args))
        return manager.Completed(0, "", "")


class Ended:
    def __init__(self) -> None:
        self.codes: list[int] = []

    def end(self, code: int) -> None:
        self.codes.append(code)


def packaged(where: Path, home: Path, version: str = "1.2.2") -> manager.Program:
    """A stand-in for the packaged app at where, as update.install.detect knows it: by its place and its bundle. Its
    Python writes the arguments it was started with beside itself."""
    app = where / "İplikçi Nedim.app"
    python = app / PYTHON
    python.parent.mkdir(parents=True)
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$(dirname "$0")/calistirildi"\n', encoding="utf-8")
    python.chmod(0o755)
    info = {"CFBundleIdentifier": install.BUNDLE_ID, "CFBundleShortVersionString": version}
    (app / "Contents" / "Info.plist").write_bytes(plistlib.dumps(info))
    return manager.Program(python, home)


def app_of(program: manager.Program) -> Path:
    return program.python.parents[4]  # <app>/Contents/Resources/python/bin/python3


def registered(tmp_path: Path, home: Path, tools: Tools | None = None) -> tuple[manager.Launchd, manager.Program]:
    """The packaged app in a folder whose name has a space and Turkish letters, its service registered for home."""
    program = packaged(tmp_path / "Uygulama Klasörü", home)
    launchd = manager.Launchd(tmp_path / "ev", run=tools or Tools(), uid=501)
    launchd.install(program)
    return launchd, program


def command_of(launchd: manager.Launchd) -> list[str]:
    return [str(word) for word in plistlib.loads(launchd.path.read_bytes())["ProgramArguments"]]


@pytest.fixture
def stand_ins(tmp_path) -> Path:
    """launchctl and logger for the guard: each adds the words it was given to <name>.txt beside itself."""
    folder = tmp_path / "araclar"
    folder.mkdir()
    for name in ("launchctl", "logger"):
        (folder / name).write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$0.txt"\n', encoding="utf-8")
        (folder / name).chmod(0o755)
    return folder


def started(command: Sequence[str], stand_ins: Path) -> subprocess.CompletedProcess[str]:
    """What launchd does at a login: the agent's command line, the stand-ins first on its PATH."""
    path = f"{stand_ins}:/usr/bin:/bin"
    return subprocess.run(list(command), env={"PATH": path}, capture_output=True, text=True, timeout=30, check=False)


def asked(stand_ins: Path, name: str) -> list[str]:
    record = stand_ins / f"{name}.txt"
    return record.read_text(encoding="utf-8").splitlines() if record.exists() else []


def files_of(home: Path) -> set[Path]:
    """What the data folder holds, but for SQLite's own files beside the database, which come and go."""
    return {p.relative_to(home) for p in home.rglob("*") if not p.name.endswith(("-wal", "-shm"))}


# --- the agent's guard ------------------------------------------------------------------------------------------------


def test_the_packaged_apps_agent_starts_the_service_behind_its_guard(tmp_path):
    launchd, program = registered(tmp_path, tmp_path / "veri")
    agent = plistlib.loads(launchd.path.read_bytes())
    assert agent["ProgramArguments"] == manager.guarded(program.arguments(), launchd.path, JOB)
    assert agent["ProgramArguments"][:4] == ["/bin/sh", "-c", manager.GUARD, "iplikci-servis"]
    assert agent["AssociatedBundleIdentifiers"] == [install.BUNDLE_ID]  # what the background items list names
    assert launchd.registered() == program  # read past the guard
    by_hand = manager.Program(tmp_path / "araç" / "bin" / "python", tmp_path / "veri")  # a uv tool copy: no guard
    launchd.install(by_hand)
    assert command_of(launchd) == by_hand.arguments() and launchd.registered() == by_hand


def test_the_guard_starts_the_app_in_its_place_with_its_arguments_as_they_are(tmp_path, stand_ins):
    launchd, program = registered(tmp_path, tmp_path / 'Ali & Ayşe\'nin "verisi" $HOME *')
    done = started(command_of(launchd), stand_ins)
    assert done.returncode == 0, done.stderr
    assert (program.python.parent / "calistirildi").read_text(encoding="utf-8").splitlines() == program.arguments()[1:]
    assert launchd.path.exists() and asked(stand_ins, "launchctl") == []


@pytest.mark.parametrize("trash", ["çöp kutusuna sürüklendi", "çöp kutusu boşaltıldı"])
def test_an_agent_whose_app_has_gone_removes_itself_and_its_job_and_ends_cleanly(tmp_path, stand_ins, trash):
    launchd, program = registered(tmp_path, tmp_path / "veri")
    app = app_of(program)
    (tmp_path / ".Trash").mkdir()
    app.rename(tmp_path / ".Trash" / app.name)  # Finder moves the app to the user's Trash
    if trash == "çöp kutusu boşaltıldı":
        shutil.rmtree(tmp_path / ".Trash" / app.name)
    done = started(command_of(launchd), stand_ins)
    assert done.returncode == 0, done.stderr  # a clean exit, which launchd does not start again
    assert not launchd.path.exists() and asked(stand_ins, "launchctl") == ["bootout", JOB]
    assert "left its place" in " ".join(asked(stand_ins, "logger"))
    assert not list(tmp_path.rglob("calistirildi"))  # its Python never ran


def test_an_agent_whose_app_lies_in_a_trash_folder_takes_it_for_gone(tmp_path, stand_ins):
    program = packaged(tmp_path / "Harici Disk" / ".Trashes" / "501", tmp_path / "veri")  # another disk's Trash
    plist = tmp_path / "ajan.plist"
    plist.write_bytes(b"")
    assert started(manager.guarded(program.arguments(), plist, JOB), stand_ins).returncode == 0
    assert not plist.exists() and not (program.python.parent / "calistirildi").exists()


def test_an_agent_whose_app_is_on_a_disk_not_attached_now_waits_for_it(tmp_path, stand_ins):
    disk = Path("/Volumes") / f"iplikci-deneme-{uuid.uuid4().hex}"  # no such disk is attached
    away = manager.Program(disk / "Applications" / "İplikçi Nedim.app" / PYTHON, tmp_path / "veri")
    plist = tmp_path / "ajan.plist"
    plist.write_bytes(b"")
    assert started(manager.guarded(away.arguments(), plist, JOB), stand_ins).returncode == 0  # not again this login
    assert plist.exists() and asked(stand_ins, "launchctl") == []  # the next login looks again


def place(tmp_path: Path, where: str) -> Path:
    """The Python of an app at a place of each kind."""
    if where == "yerinde":
        return packaged(tmp_path / "Uygulamalar", tmp_path / "veri").python
    if where == "silindi":
        return tmp_path / "Uygulamalar" / "İplikçi Nedim.app" / PYTHON
    if where == "çöp kutusunda":
        return packaged(tmp_path / ".Trash", tmp_path / "veri").python
    if where == "takılı olmayan diskte":
        return Path("/Volumes") / f"iplikci-deneme-{uuid.uuid4().hex}" / "İplikçi Nedim.app" / PYTHON
    volumes = Path("/Volumes")
    disk = next((p for p in sorted(volumes.iterdir()) if p.is_dir()), None) if volumes.is_dir() else None
    if disk is None:
        pytest.skip("this system attaches no disk under /Volumes")
    return disk / f"iplikci-deneme-{uuid.uuid4().hex}" / "İplikçi Nedim.app" / PYTHON  # gone from a disk that is here


@pytest.mark.parametrize(
    ("where", "left"),
    [
        ("yerinde", False),
        ("silindi", True),
        ("çöp kutusunda", True),
        ("takılı olmayan diskte", False),
        ("takılı diskten silindi", True),
    ],
)
def test_the_service_and_its_agents_guard_agree_on_when_the_app_has_left_its_place(tmp_path, stand_ins, where, left):
    python = place(tmp_path, where)
    assert manager.left_its_place(python) is left
    plist = tmp_path / "ajan.plist"
    plist.write_bytes(b"")
    started(manager.guarded(manager.Program(python, tmp_path / "veri").arguments(), plist, JOB), stand_ins)
    assert (not plist.exists()) is left


# --- the running service ----------------------------------------------------------------------------------------------


def test_a_service_whose_app_went_to_the_trash_takes_its_registration_off_and_the_data_stays(ws, tmp_path, monkeypatch):
    tools = Tools()
    launchd, program = registered(tmp_path, ws.home, tools)
    monkeypatch.setattr(manager, "for_platform", lambda: launchd)
    assert lifecycle.gone_program(ws, program.python) is None  # in its place
    (tmp_path / ".Trash").mkdir()
    app_of(program).rename(tmp_path / ".Trash" / app_of(program).name)
    found = lifecycle.gone_program(ws, program.python)
    assert found == program
    kept = files_of(ws.home)
    tools.calls.clear()
    assert lifecycle.remove_gone(ws, found)
    assert not launchd.path.exists() and tools.calls == []  # no bootout: the service ends by itself, cleanly
    assert kept <= files_of(ws.home)  # nothing of the data folder goes
    with ws.db() as db:
        removed = [e.detail for e in audit.entries(db, lifecycle.REMOVED)]
    assert removed == [{"data_to_trash": False, "program_gone": True}]


def test_only_the_services_own_registration_is_taken_for_gone(ws, tmp_path, monkeypatch):
    launchd, program = registered(tmp_path, ws.home)
    monkeypatch.setattr(manager, "for_platform", lambda: launchd)
    shutil.rmtree(app_of(program))  # the Trash emptied
    assert lifecycle.gone_program(ws, program.python) == program
    assert lifecycle.gone_program(ws, tmp_path / "baska" / "python3") is None  # another copy runs this service
    launchd.install(manager.Program(program.python, tmp_path / "baska-veri"))
    assert lifecycle.gone_program(ws, program.python) is None  # the computer starts another data folder's
    launchd.path.unlink()
    assert lifecycle.gone_program(ws, program.python) is None  # nothing registered


def test_a_copy_opened_since_keeps_the_registration_it_made(ws, tmp_path, monkeypatch):
    launchd, program = registered(tmp_path, ws.home)
    monkeypatch.setattr(manager, "for_platform", lambda: launchd)
    shutil.rmtree(app_of(program))
    moved = packaged(tmp_path / "Yeni Yer", ws.home)
    launchd.install(moved)  # the app, put somewhere else, was opened and registered itself
    assert lifecycle.remove_gone(ws, program) is False
    assert launchd.registered() == moved


def test_the_service_leaves_only_once_its_app_is_found_gone_twice_in_a_row():
    gone = manager.Program(Path("/Applications/İplikçi Nedim.app") / PYTHON, Path("/veri"))
    seen = iter([None, gone, None, gone, None, gone, gone])  # a trade of the app's Contents seen half way, once
    left: list[manager.Program] = []
    life = Ended()
    watch = runner.PlaceWatch(life, gone=lambda: next(seen), leave=left.append, every=0.001)  # pyright: ignore[reportArgumentType] - a stand-in
    watch._run()  # the watch's loop, run here rather than in its thread
    assert left == [gone] and life.codes == [lifecycle.STOP]  # a clean exit: launchd does not start it again


def test_the_service_ends_even_when_its_registration_could_not_be_taken_off():
    gone = manager.Program(Path("/Applications/İplikçi Nedim.app") / PYTHON, Path("/veri"))

    def refuse(found: manager.Program) -> None:
        raise OSError("veritabanı yazılamadı")

    life = Ended()
    watch = runner.PlaceWatch(life, gone=lambda: gone, leave=refuse, every=0.001)  # pyright: ignore[reportArgumentType] - a stand-in
    with pytest.raises(OSError, match="yazılamadı"):
        watch._run()
    assert life.codes == [lifecycle.STOP]


def test_an_update_trading_the_apps_contents_leaves_its_python_in_place(ws, tmp_path, monkeypatch):
    launchd, program = registered(tmp_path, ws.home)
    monkeypatch.setattr(manager, "for_platform", lambda: launchd)
    seen: list[object] = []

    def unpack(archive: Path, into: Path) -> None:  # the new version's app, as ditto unpacks it
        packaged(into, ws.home, "9.9.9")

    def trade(new: Path, old: Path) -> None:
        install.swap(new, old)
        seen.append(lifecycle.gone_program(ws, program.python))

    archive = tmp_path / "guncelleme.zip"
    install.apply_macos(app_of(program), archive, "9.9.9", unpack=unpack, run=lambda python: "9.9.9", trade=trade)
    assert seen == [None] and launchd.registered() == program  # in place the moment the trade is done


def test_an_agent_an_older_version_wrote_gets_its_guard_at_the_start_and_the_job_goes_on(ws, tmp_path, monkeypatch):
    tools = Tools()
    launchd = manager.Launchd(tmp_path / "ev", run=tools, uid=501)
    program = packaged(tmp_path / "Uygulamalar", ws.home)
    older = {**launchd.agent(program), "ProgramArguments": program.arguments()}  # as 0.11 wrote it
    del older["AssociatedBundleIdentifiers"]
    launchd.path.parent.mkdir(parents=True)
    launchd.path.write_bytes(plistlib.dumps(older))
    monkeypatch.setattr(manager, "for_platform", lambda: launchd)
    assert lifecycle.refresh_registration(ws, tmp_path / "baska" / "python3") is False  # another copy's service
    assert plistlib.loads(launchd.path.read_bytes()) == older
    assert lifecycle.refresh_registration(ws, program.python)
    assert plistlib.loads(launchd.path.read_bytes()) == launchd.agent(program)
    assert tools.calls == []  # the job loaded now goes on; the next login reads the new agent
    assert lifecycle.refresh_registration(ws, program.python) is False  # once


def test_only_the_packaged_app_watches_its_place_and_refreshes_its_agent(ws, monkeypatch):
    life = Ended()
    assert runner.place_watch(ws, life) is None  # pyright: ignore[reportArgumentType] - these tests run from a development folder
    monkeypatch.setattr(runner, "packaged", lambda: True)
    assert isinstance(runner.place_watch(ws, life), runner.PlaceWatch)  # pyright: ignore[reportArgumentType] - a stand-in
    refreshed: list[Path] = []
    monkeypatch.setattr(lifecycle, "refresh_registration", lambda found, own: refreshed.append(own) or False)
    monkeypatch.setattr(runner, "_serve", lambda found, announce: lifecycle.STOP)
    assert runner.run(ws, lambda _: None) == lifecycle.STOP
    assert refreshed == [Path(sys.executable).absolute()]
