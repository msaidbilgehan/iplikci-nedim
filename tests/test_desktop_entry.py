"""The Linux app's entry in the desktop's application menu (K31, service/desktop): written for the copy AppRun runs as
the app registers the service and as an update moves the service to a new copy, and removed with the service. Every
test writes into a temporary $XDG_DATA_HOME (conftest gives each one its own), never the user's; systemctl is a
stand-in."""

import json
import re
import stat
import tempfile
from collections.abc import Sequence
from pathlib import Path

import pytest
from PIL import Image

from iplikci import __version__, cli
from iplikci.app import lifecycle, setup, update
from iplikci.domain.codes import Actor
from iplikci.service import desktop, instance, launcher, manager
from iplikci.update import install
from iplikci.update.install import Installation, Kind

LAUNCH = ["-I", "-X", "utf8", "-m", "iplikci", "uygulama"]


class Tools:
    def __call__(self, args: Sequence[str]) -> manager.Completed:
        return manager.Completed(0, "", "")


def copy_of(root: Path, version: str = "1.2.3") -> Path:
    """The Python AppRun copied for a version, as update.install.detect knows it."""
    return root / ".local" / "lib" / "iplikci" / version / "bin" / "python3"


def keys_of(entry: Path) -> dict[str, str]:
    lines = entry.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "[Desktop Entry]"
    return dict(line.split("=", 1) for line in lines[1:] if line)


def unescaped(value: str) -> str:
    """A string value as a desktop reads it: the specification's escapes undone first."""
    return re.sub(r"\\(.)", lambda m: {"s": " ", "n": "\n", "t": "\t", "r": "\r"}.get(m[1], m[1]), value)


def words(value: str) -> list[str]:
    """An Exec value as a desktop reads it (GLib, KDE): the string's escapes, %% for %, then the words as a POSIX shell
    splits them, where inside double quotes a backslash escapes only $, `, " and itself."""
    text = unescaped(value).replace("%%", "%")
    found: list[str] = []
    word: list[str] | None = None
    quoted = False
    at = 0
    while at < len(text):
        char = text[at]
        if quoted and char == "\\" and text[at + 1 : at + 2] in ("$", "`", '"', "\\"):
            word = [*(word or []), text[at + 1]]
            at += 1
        elif char == '"':
            quoted, word = not quoted, word or []
        elif char == " " and not quoted:
            if word is not None:
                found.append("".join(word))
            word = None
        else:
            word = [*(word or []), char]
        at += 1
    if word is not None:
        found.append("".join(word))
    return found


# --- the entry --------------------------------------------------------------------------------------------------------


def test_the_menu_entry_opens_the_app_as_apprun_does_and_shows_its_icon(tmp_path):
    home = tmp_path / "xdg"
    python = copy_of(tmp_path)
    assert desktop.add(python, home)
    entry = home / "applications" / "com.iplikci.app.desktop"
    keys = keys_of(entry)
    assert keys["Type"] == "Application" and keys["Name"] == "İplikçi Nedim" and keys["Terminal"] == "false"
    assert keys["Icon"] == "com.iplikci.app"  # the icons below, in the user's icon theme
    assert words(keys["Exec"]) == [str(python), *LAUNCH] and keys["TryExec"] == str(python)
    assert stat.S_IMODE(entry.stat().st_mode) == 0o644
    for size in (48, 128, 256):
        icon = home / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "com.iplikci.app.png"
        with Image.open(icon) as image:
            assert image.size == (size, size)
        assert stat.S_IMODE(icon.stat().st_mode) == 0o644
    assert desktop.add(python, home) is False  # nothing differs: nothing written again
    assert not [p for p in home.rglob("*") if p.name.endswith(".yeni")]  # no file half written stays


@pytest.mark.parametrize(
    "folder",
    [
        "Uygulama Klasörü",
        "Ali'nin $HOME klasörü",
        'tırnak "içinde"',
        "ters\\bölü",
        "yüzde %u %%",
        "`komut` (ayraç) #; & | > < * ? ~",
    ],
)
def test_the_menu_entry_gives_the_copys_path_back_whatever_its_letters(tmp_path, folder):
    python = copy_of(tmp_path / folder)
    home = tmp_path / "xdg"
    desktop.add(python, home)
    keys = keys_of(desktop.entry_path(home))
    assert words(keys["Exec"]) == [str(python), *LAUNCH]
    assert unescaped(keys["TryExec"]) == str(python)


def test_an_exec_word_is_quoted_only_when_the_specification_asks():
    assert desktop.exec_argument("/home/ali/.local/lib/iplikci/1.2.3/bin/python3") == (
        "/home/ali/.local/lib/iplikci/1.2.3/bin/python3"
    )
    assert desktop.exec_argument("/home/Ayşe Kaya/python3") == '"/home/Ayşe Kaya/python3"'
    assert desktop.exec_argument('a"b$c`d\\e f') == '"a\\"b\\$c\\`d\\\\e f"'
    assert desktop.exec_argument("yüzde%u") == "yüzde%%u"


def test_the_menu_entry_and_its_icons_go_and_the_desktops_folders_stay(tmp_path):
    home = tmp_path / "xdg"
    assert desktop.remove(home) is False  # nothing to remove
    desktop.add(copy_of(tmp_path), home)
    assert desktop.remove(home)
    assert not desktop.present(home) and not list((home / "icons").rglob("*.png"))
    assert (home / "applications").is_dir()  # the desktop's own


def test_a_menu_entry_that_cannot_be_written_leaves_the_work_that_asked_for_it_alone(tmp_path, caplog):
    home = tmp_path / "xdg"
    home.write_text("bir dosya, klasör değil", encoding="utf-8")
    assert desktop.add(copy_of(tmp_path), home) is False
    assert "menu entry could not be written" in caplog.text


# --- when it is written and removed -----------------------------------------------------------------------------------


class FakeService:
    """A service manager whose service starts as soon as it is registered."""

    def __init__(self) -> None:
        self.program: manager.Program | None = None
        self.running: instance.Holder | None = None

    def registered(self) -> manager.Program | None:
        return self.program

    def install(self, program: manager.Program) -> None:
        self.program = program
        self.running = instance.Holder(4001, 8643, "2026-11-15T09:00:00+00:00", "1.2.3")

    def restart(self) -> None:
        if self.program is not None:
            self.install(self.program)

    def serving(self, run: Path) -> instance.Holder | None:
        return self.running


def test_the_app_puts_itself_in_the_menu_as_it_registers_the_service(ws, tmp_path, monkeypatch):
    python = copy_of(tmp_path)
    monkeypatch.setattr(manager, "development_folder", lambda module=None: None)
    monkeypatch.setattr(manager.sys, "executable", str(python))
    service = FakeService()
    found = launcher.open_app(
        ws, service, "linux", python, healthy=lambda port: True, serving=service.serving, login=str
    )
    assert found.registered and words(keys_of(desktop.entry_path(desktop.data_home()))["Exec"])[0] == str(python)


def test_an_entry_already_in_the_menu_is_left_as_the_user_changed_it_until_a_new_copy_registers(tmp_path):
    python = copy_of(tmp_path)
    entry = desktop.entry_path(desktop.data_home())
    assert launcher.in_menu(python, "linux", registered=False)  # none yet: a copy from before the entry
    entry.write_text(entry.read_text(encoding="utf-8") + "NoDisplay=true\n", encoding="utf-8")  # a menu editor's
    assert launcher.in_menu(python, "linux", registered=False) is False
    assert keys_of(entry)["NoDisplay"] == "true"
    newer = copy_of(tmp_path, "1.3.0")
    assert launcher.in_menu(newer, "linux", registered=True)  # a new version's AppImage was opened
    assert words(keys_of(entry)["Exec"])[0] == str(newer)


def test_only_the_linux_copy_goes_into_the_menu(tmp_path):
    mac = tmp_path / "İplikçi Nedim.app" / "Contents" / "Resources" / "python" / "bin" / "python3"
    assert launcher.in_menu(mac, "darwin", registered=True) is False
    by_hand = tmp_path / ".local" / "share" / "uv" / "tools" / "iplikci-nedim" / "bin" / "python3"  # uv tool install
    assert launcher.in_menu(by_hand, "linux", registered=True) is False
    assert not desktop.present()


def test_an_update_moves_the_menu_entry_to_the_new_copy_as_it_retargets_the_unit(ws, tmp_path, monkeypatch):
    copies = tmp_path / ".local" / "lib" / "iplikci"
    old, new = copy_of(tmp_path, "1.2.3"), copy_of(tmp_path, "1.3.0")
    unit = manager.Systemd(tmp_path, run=Tools(), env={"XDG_DATA_HOME": str(tmp_path / "xdg")})
    desktop.add(old, unit.menu)
    monkeypatch.setattr(install, "apply_linux", lambda root, archive, version: new)
    monkeypatch.setattr(manager, "for_platform", lambda: unit)
    update._apply(ws, Installation(Kind.LINUX_COPY, copies), tmp_path / "guncelleme.tar.gz", "1.3.0")
    assert unit.registered() == manager.Program(new, ws.home.resolve())
    assert words(keys_of(desktop.entry_path(unit.menu))["Exec"])[0] == str(new)


def test_the_first_start_after_an_update_puts_the_new_copy_in_the_menu(ws, tmp_path, monkeypatch):
    """An update installed by a version from before the entry: the new version writes it."""
    python = copy_of(tmp_path, __version__)
    monkeypatch.setattr(update.sys, "executable", str(python))
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "gecici"))  # where the start looks for old downloads
    ws.run.mkdir(parents=True, exist_ok=True)
    started = {"installing": {"from": "0.11.1", "to": __version__, "at": "2026-11-15T05:00:00+00:00", "tries": 1}}
    (ws.run / update.STATE).write_text(json.dumps(started), encoding="utf-8")
    here = Installation(Kind.LINUX_COPY, python.parents[2])
    assert update.finish(ws, here=here) is not None
    assert words(keys_of(desktop.entry_path(desktop.data_home()))["Exec"])[0] == str(python)
    desktop.remove()
    assert update.finish(ws, here=here) is None and not desktop.present()  # an ordinary start writes nothing


def test_removing_the_service_from_the_settings_or_the_command_line_takes_the_menu_entry_along(
    ws, tmp_path, monkeypatch
):
    unit = manager.Systemd(tmp_path, run=Tools(), env={"XDG_DATA_HOME": str(tmp_path / "xdg")})
    monkeypatch.setattr(manager, "for_platform", lambda: unit)
    monkeypatch.setattr(setup, "registered_home", lambda: ws.home)
    program = manager.Program(copy_of(tmp_path), ws.home.resolve())
    unit.install(program)
    desktop.add(program.python, unit.menu)
    assert lifecycle.remove(ws, False, Actor.USER)  # Ayarlar → Servisi kaldır
    assert not desktop.present(unit.menu) and not list((unit.menu / "icons").rglob("*.png"))
    unit.install(program)
    desktop.add(program.python, unit.menu)
    monkeypatch.setenv("IPLIKCI_HOME", str(ws.home))
    assert cli.main(["servis", "kaldir"]) == 0  # iplikci servis kaldir
    assert not desktop.present(unit.menu)
