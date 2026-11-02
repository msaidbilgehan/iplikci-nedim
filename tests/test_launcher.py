"""Opening the installed app (ADR-0017): the service registered for this copy and data folder, started or restarted
as needed, a login link for the browser, and every problem said in the system's own window. The service manager, the
health check and the windows are stand-ins; nothing reaches launchd, the network or the screen."""

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from iplikci import __version__
from iplikci.cli import main
from iplikci.service import dialog, instance, launcher, manager

APP = Path("/Applications/İplikçi Nedim.app/Contents/Resources/python/bin/python3")
SHOW_FOLDER = dialog.show_folder  # the real one: every test gets a stand-in that refuses (conftest)


class FakeService:
    """A service manager that remembers what it was asked to do, and the service that holds the data folder."""

    def __init__(self, registered: manager.Program | None = None, running: instance.Holder | None = None) -> None:
        self.program = registered
        self.running = running
        self.calls: list[str] = []

    def registered(self) -> manager.Program | None:
        return self.program

    def install(self, program: manager.Program) -> None:
        self.calls.append("install")
        self.program = program
        self._start()

    def restart(self) -> None:
        self.calls.append("restart")
        self._start()

    def _start(self) -> None:
        pid = (self.running.pid if self.running else 4000) + 1
        self.running = instance.Holder(pid, 8643, "2026-11-02T09:00:00+00:00", __version__)

    def serving(self, run: Path) -> instance.Holder | None:
        return self.running


@pytest.fixture
def installed(monkeypatch):
    """This program as an installed copy, its Python the app's."""
    monkeypatch.setattr(manager, "development_folder", lambda module=None: None)
    monkeypatch.setattr(manager.sys, "executable", str(APP))


def opened(ws, service, **options):
    return launcher.open_app(
        ws,
        service,
        "darwin",
        APP,
        healthy=lambda port: True,
        serving=service.serving,
        login=lambda ws: "http://127.0.0.1/giris",
        **options,
    )


def this_copy(ws) -> manager.Program:
    return manager.Program(APP, ws.home.resolve())


def running(version: str = __version__) -> instance.Holder:
    return instance.Holder(4321, 8643, "2026-11-01T08:00:00+00:00", version)


@pytest.mark.parametrize(
    "where",
    [
        "/Volumes/İplikçi Nedim/İplikçi Nedim.app/Contents/Resources/python/bin/python3",
        "/private/var/folders/xy/T/AppTranslocation/1234/d/İplikçi Nedim.app/Contents/Resources/python/bin/python3",
    ],
)
def test_an_app_opened_from_its_disk_image_or_where_it_was_downloaded_asks_to_be_moved_first(ws, installed, where):
    service = FakeService()
    with pytest.raises(launcher.LaunchError, match="Uygulamalar klasörüne taşıyın"):
        launcher.open_app(ws, service, "darwin", Path(where), healthy=lambda port: True, login=lambda ws: "")
    assert service.calls == []  # nothing was registered from a place that goes away


def test_the_first_opening_registers_the_service_for_this_copy_and_gives_a_login_link(ws, installed):
    service = FakeService()
    found = opened(ws, service)
    assert found == launcher.Opened("http://127.0.0.1/giris", registered=True, restarted=True)
    assert service.calls == ["install"] and service.program == this_copy(ws)


def test_a_running_service_of_this_copy_and_version_is_left_alone(ws, installed):
    service = FakeService(this_copy(ws), running())
    found = opened(ws, service)
    assert (found.registered, found.restarted, service.calls) == (False, False, [])


def test_a_stopped_service_is_started_and_an_older_version_restarted(ws, installed):
    service = FakeService(this_copy(ws))
    assert opened(ws, service).restarted and service.calls == ["restart"]  # not running
    service.running = running(version="0.0.1")
    assert opened(ws, service).restarted  # the update replaced the program under it
    assert service.calls == ["restart", "restart"]


def test_a_restart_waits_for_the_new_service_before_it_asks_for_a_login_link(ws, installed):
    older = running(version="0.0.1")
    service = FakeService(this_copy(ws), older)
    # The older service still holds the folder as it ends, then none does, then the new one before it says who it is.
    seen: list[instance.Holder | None] = [older, older, None, instance.UNKNOWN]
    links: list[int] = []

    def login(ws) -> str:
        links.append(len(seen))
        return "http://127.0.0.1/giris"

    found = launcher.open_app(
        ws,
        service,
        "darwin",
        APP,
        healthy=lambda port: True,  # the older one answers too, for a moment
        serving=lambda run: seen.pop(0) if seen else service.running,
        login=login,
        sleep=lambda seconds: None,
    )
    assert found.restarted and links == [0]  # asked of the new service only


def test_the_pythons_of_older_versions_an_appimage_left_go_once_this_one_answers(ws, tmp_path, monkeypatch):
    folder = tmp_path / "share" / "iplikci" / "app"
    for version in ("0.6.0", "0.7.0", "0.6.0.yeni", "0.7.0.yeni"):
        (folder / version / "bin").mkdir(parents=True)
    python = folder / "0.7.0" / "bin" / "python3"
    monkeypatch.setattr(manager, "development_folder", lambda module=None: None)
    monkeypatch.setattr(manager.sys, "executable", str(python))
    assert launcher.older_copies(python, "darwin") == [] and launcher.older_copies(APP, "linux") == []
    service = FakeService()
    launcher.open_app(ws, service, "linux", python, healthy=lambda port: True, serving=service.serving, login=str)
    assert sorted(p.name for p in folder.iterdir()) == ["0.7.0", "0.7.0.yeni"]  # this one, and a copy AppRun makes


def test_a_service_registered_from_another_copy_or_folder_is_registered_again_from_this_one(ws, installed, tmp_path):
    for other in (manager.Program(tmp_path / "eski" / "python", ws.home), manager.Program(APP, tmp_path / "baska")):
        service = FakeService(other)
        assert opened(ws, service).registered and service.program == this_copy(ws)


def test_a_service_that_never_answers_is_said_with_where_its_log_is(ws, installed):
    with pytest.raises(launcher.LaunchError, match="yanıt vermedi") as found:
        service = FakeService()
        launcher.open_app(
            ws,
            service,
            "darwin",
            APP,
            healthy=lambda port: False,
            serving=service.serving,
            login=lambda ws: "",
            wait=0.0,
            sleep=lambda s: None,
        )
    assert str(ws.layout.logs) in str(found.value)


def test_a_development_copy_never_registers_the_service(ws):
    service = FakeService()
    with pytest.raises(manager.DevelopmentCopy):
        opened(ws, service)
    assert service.calls == []


def test_the_window_gets_the_text_as_an_argument_never_inside_a_script():
    text = 'Bir "sorun" var\nend run\ndo shell script "kötü"'
    mac = dialog.command(text, "darwin")
    assert mac is not None and mac[0] == "osascript" and mac[-2:] == [text, dialog.TITLE]
    assert all(text not in part for part in mac[:-2])
    assert dialog.command(text, "linux", which=lambda name: "/usr/bin/zenity" if name == "zenity" else None) == [
        "zenity", "--info", f"--title={dialog.TITLE}", f"--text={text}", "--no-markup"
    ]  # fmt: skip
    assert dialog.command(text, "linux", which=lambda name: None) is None


def test_a_window_that_cannot_be_shown_leaves_the_text_on_stderr(capsys):
    dialog.say("Bir sorun var.", "darwin", run=lambda args: 1)
    assert "Bir sorun var." in capsys.readouterr().err


def test_the_systems_windows_open_no_console_window_on_windows(monkeypatch, tmp_path):
    seen: list[tuple[str, object]] = []

    def run(args: Sequence[str], **options: object) -> subprocess.CompletedProcess[bytes]:
        seen.append((args[0], options["creationflags"]))
        return subprocess.CompletedProcess(args, 0, b"", b"")

    monkeypatch.setattr(dialog.subprocess, "run", run)  # nothing is shown
    monkeypatch.setattr(manager, "WINDOWS", True)
    dialog.say("Bir sorun var.", "darwin")
    assert SHOW_FOLDER(tmp_path, "win32")
    assert seen == [("osascript", manager.NO_WINDOW), ("explorer", manager.NO_WINDOW)]


def test_the_app_command_opens_the_browser_or_says_why_it_could_not(ws, monkeypatch):
    said: list[str] = []
    browsed: list[str] = []
    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    monkeypatch.setattr(dialog, "say", lambda text, *args, **kwargs: said.append(text))
    monkeypatch.setattr("webbrowser.open", lambda url: browsed.append(url) or True)
    monkeypatch.setattr(launcher, "open_app", lambda *args: launcher.Opened("http://127.0.0.1/giris", True, True))
    assert main(["uygulama"]) == 0 and browsed == ["http://127.0.0.1/giris"] and said == []

    def refused(*args):
        raise launcher.LaunchError("İplikçi Nedim'i önce Uygulamalar klasörüne taşıyın.")

    monkeypatch.setattr(launcher, "open_app", refused)
    assert main(["uygulama"]) == 1 and said == ["İplikçi Nedim'i önce Uygulamalar klasörüne taşıyın."]
