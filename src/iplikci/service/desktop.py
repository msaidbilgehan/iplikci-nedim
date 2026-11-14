"""The Linux app's entry in the desktop's application menu (K31, ADR-0017's note of 2026-11-15). An AppImage is a file
the user keeps wherever it was downloaded, and no menu lists it: the program writes a desktop entry (freedesktop's
Desktop Entry Specification) and its icons into the user's own share of the desktop's data ($XDG_DATA_HOME,
~/.local/share by default). The entry opens the app as AppRun does, with the Python copied to
~/.local/lib/iplikci/<version>. It is written when the app is opened and registers the service, and whenever an update
moves the service to a new copy, as the systemd unit is retargeted; removing the service removes it with its icons.
The desktop's own folders only: never the data folder. The menu is not the app: a failure to write or remove the
entry is logged and the work that asked for it goes on."""

import logging
import os
import re
import tempfile
from collections.abc import Mapping
from pathlib import Path

APP_ID = "com.iplikci.app"  # the entry's and the icon's name: reverse DNS, as the specification asks of a desktop ID
NAME = "İplikçi Nedim"
COMMENT = "Kişisel finans asistanı"
CATEGORIES = "Office;Finance;"
LAUNCH = ("-I", "-X", "utf8", "-m", "iplikci", "uygulama")  # what AppRun runs with the Python (packaging/build.py)
SIZES = (48, 128, 256)  # the icons the program carries, drawn from the logo by packaging/icons.py
ICONS = Path(__file__).resolve().parent / "icons"
FILE_MODE = 0o644  # the desktop's files, read by the menu and the icon theme: no secret in them
# The characters an Exec argument is quoted for (the specification's reserved ones), and those escaped inside quotes.
_RESERVED = re.compile(r"[\s\"'\\<>~|&;$*?#()`]")
_ESCAPED = re.compile(r'(["`$\\])')

log = logging.getLogger("iplikci.service")


def data_home(env: Mapping[str, str] | None = None, user_home: Path | None = None) -> Path:
    """The user's share of the desktop's data: $XDG_DATA_HOME, else ~/.local/share."""
    env = os.environ if env is None else env
    return Path(env.get("XDG_DATA_HOME") or (user_home or Path.home()) / ".local" / "share")


def entry_path(home: Path) -> Path:
    return home / "applications" / f"{APP_ID}.desktop"


def icon_path(home: Path, size: int) -> Path:
    return home / "icons" / "hicolor" / f"{size}x{size}" / "apps" / f"{APP_ID}.png"


def exec_argument(word: str) -> str:
    """One word of the Exec key: in double quotes, its `"`, `` ` ``, `$` and `\\` escaped there, when it holds a
    reserved character; `%` doubled, as a field code starts with it."""
    value = word.replace("%", "%%")
    if not _RESERVED.search(value):
        return value
    return '"' + _ESCAPED.sub(r"\\\1", value) + '"'


def _string(value: str) -> str:
    """A value of the string type, its escapes written: a reader undoes these first, before an Exec's quoting."""
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")


def entry(python: Path) -> str:
    """The desktop entry that opens the app with this copy's Python, as AppRun does. TryExec leaves it out of the menu
    once that copy is gone."""
    command = " ".join(exec_argument(word) for word in (str(python), *LAUNCH))
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={NAME}\n"
        f"Comment={COMMENT}\n"
        f"TryExec={_string(str(python))}\n"
        f"Exec={_string(command)}\n"
        f"Icon={APP_ID}\n"
        f"Categories={CATEGORIES}\n"
        "Terminal=false\n"
        "StartupNotify=false\n"  # the app opens the browser and no window of its own: no busy cursor waiting for one
    )


def present(home: Path | None = None) -> bool:
    return entry_path(home or data_home()).is_file()


def add(python: Path, home: Path | None = None) -> bool:
    """The entry for this copy's Python and its icons, each written where it differs from what is there. Whether
    anything was written; a failure is logged."""
    home = home or data_home()
    try:
        wanted = {entry_path(home): entry(python).encode("utf-8")}
        wanted |= {icon_path(home, size): (ICONS / f"iplikci-{size}.png").read_bytes() for size in SIZES}
        written = False
        for path, data in wanted.items():
            if _holds(path, data):
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            _replace(path, data)
            written = True
    except OSError as exc:
        log.warning("the app's menu entry could not be written: %s", exc)
        return False
    if written:
        log.info("the app's menu entry opens %s", python)
    return written


def remove(home: Path | None = None) -> bool:
    """The entry and its icons gone; whether there was any. The folders stay: they are the desktop's. A failure is
    logged."""
    home = home or data_home()
    found = False
    for path in (entry_path(home), *(icon_path(home, size) for size in SIZES)):
        try:
            path.unlink()  # a file this program wrote, not a document
        except FileNotFoundError:
            continue
        except OSError as exc:
            log.warning("the app's menu entry could not be removed: %s", exc)
            continue
        found = True
    return found


def _holds(path: Path, data: bytes) -> bool:
    try:
        return path.read_bytes() == data
    except OSError:
        return False


def _replace(path: Path, data: bytes) -> None:
    """data in place of the file at path at once: a menu reading the folder sees the old file or the new one."""
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".yeni")
    try:
        if hasattr(os, "fchmod"):  # mkstemp makes it the user's alone; Windows has no such modes
            os.fchmod(fd, FILE_MODE)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise
