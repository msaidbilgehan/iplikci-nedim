"""Putting a new version of the installed program in place (ADR-0022), where ADR-0017's installers put it:

- macOS: "İplikçi Nedim.app" in an Applications folder. The new app is unpacked inside the old one and its Contents
  takes the old Contents' place in one step, so the app keeps its path and the service its registration.
- Linux: the AppImage's Python copied to ~/.local/lib/iplikci/<version>. The new version is unpacked beside the
  others, as AppRun would copy it; the service is then registered with the new Python.
- Windows: the setup program in the user's own Programs folder. It is run without a window: it takes the service off,
  replaces the files and opens the app, which registers the service again.

Any other copy (uv tool install, a development folder) is the user's to update. Before a new version takes the old
one's place it is started with its own Python and must say its version: an archive that unpacked badly never runs
the service."""

import ctypes
import os
import plistlib
import re
import shutil
import subprocess
import tarfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import cast

BUNDLE_ID = "com.iplikci.app"
STAGING = ".guncelleme"  # inside the .app: the new version unpacked, beside what it replaces
OLD = ".eski-surum"  # inside the .app: the Contents it replaced, until the new version runs
PROBE = "import iplikci; print(iplikci.__version__)"
PROBE_SECONDS = 180.0  # a Python's first start after unpacking is slow on macOS: its files are checked once
RENAME_SWAP = 0x00000002  # renamex_np's flag: two paths trade places atomically (APFS, HFS+)
_VERSION_FOLDER = re.compile(r"\d+(?:\.\d+)*")
_SETUP_FLAGS = ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-")

type Probe = Callable[[Path], str]
type Unpack = Callable[[Path, Path], None]
type Swap = Callable[[Path, Path], None]


class Kind(StrEnum):
    MACOS_APP = "macos_app"
    LINUX_COPY = "linux_copy"
    WINDOWS_SETUP = "windows_setup"
    MANUAL = "manual"  # installed by hand: only told of a new version


class InstallError(Exception):
    """The new version could not be put in place; the running one is as it was. The message says why (Turkish)."""


@dataclass(frozen=True, slots=True)
class Installation:
    kind: Kind
    root: Path | None  # the .app, the folder of the Linux copies, the Windows program's folder; None by hand

    @property
    def automatic(self) -> bool:
        """Whether this program can install a new version of itself here."""
        return self.kind is not Kind.MANUAL


MANUAL = Installation(Kind.MANUAL, None)


def detect(executable: Path, system: str, development: bool = False) -> Installation:
    """Which installer put the Python running this program (sys.executable, as it was started) on the computer."""
    if development:
        return MANUAL
    up = executable.parents
    if system == "darwin" and len(up) > 4:
        app = up[4]  # <app>/Contents/Resources/python/bin/python3
        names = (up[0].name, up[1].name, up[2].name, up[3].name)
        if names == ("bin", "python", "Resources", "Contents") and app.suffix == ".app" and _bundle(app) == BUNDLE_ID:
            return Installation(Kind.MACOS_APP, app)
    elif system.startswith("linux") and len(up) > 3:
        copies = up[2]  # ~/.local/lib/iplikci/<version>/bin/python3
        if (
            up[0].name == "bin"
            and _VERSION_FOLDER.fullmatch(up[1].name)
            and (copies.name, copies.parent.name) == ("iplikci", "lib")
        ):
            return Installation(Kind.LINUX_COPY, copies)
    elif system == "win32" and len(up) > 1:
        program = up[1]  # <program>\python\pythonw.exe
        if up[0].name.lower() == "python" and (program / "unins000.exe").is_file():
            return Installation(Kind.WINDOWS_SETUP, program)
    return MANUAL


def _bundle(app: Path) -> str:
    return _info(app).get("CFBundleIdentifier", "")


def _bundle_version(app: Path) -> str:
    return _info(app).get("CFBundleShortVersionString", "")


def _info(app: Path) -> dict[str, str]:
    """The app's Info.plist, its text values only; empty when it has none that reads."""
    try:
        found: object = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    except (OSError, plistlib.InvalidFileException, ValueError):
        return {}
    if not isinstance(found, dict):
        return {}
    return {str(k): v for k, v in cast(dict[object, object], found).items() if isinstance(v, str)}


def probe(python: Path) -> str:
    """The version the program installed with this Python says it is; InstallError when it does not start."""
    try:
        done = subprocess.run(
            [str(python), "-I", "-c", PROBE], capture_output=True, text=True, timeout=PROBE_SECONDS, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise InstallError(f"yeni sürüm açılamadı ({type(exc).__name__})") from None
    if done.returncode != 0:
        raise InstallError(f"yeni sürüm açılamadı (çıkış kodu {done.returncode})")
    return done.stdout.strip()


# --- macOS ------------------------------------------------------------------------------------------------------------


def unpack_app(archive: Path, into: Path) -> None:
    """The app archived by ditto (with its extended attributes and the bundle's seal) unpacked into a folder."""
    done = subprocess.run(
        ["/usr/bin/ditto", "-x", "-k", str(archive), str(into)], capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise InstallError(f"güncelleme dosyası açılamadı: {(done.stderr or done.stdout).strip()[:200]}")


def swap(new: Path, old: Path) -> None:
    """new and old trade places: in one step where the file system can (renamex_np on APFS and HFS+), otherwise in
    three renames."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renamex = libc.renamex_np
    except (OSError, AttributeError):
        renamex = None
    if renamex is not None:
        renamex.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
        renamex.restype = ctypes.c_int
        if renamex(os.fsencode(new), os.fsencode(old), RENAME_SWAP) == 0:
            return
    aside = old.with_name(f"{old.name}.takas")
    old.rename(aside)
    try:
        new.rename(old)
    except OSError:
        aside.rename(old)
        raise
    aside.rename(new)


def apply_macos(
    app: Path, archive: Path, version: str, *, unpack: Unpack = unpack_app, run: Probe = probe, trade: Swap = swap
) -> None:
    """The app in archive takes the place of `app`'s Contents. The replaced Contents waits in OLD until the new
    version has started (leftovers); the app's own path never changes."""
    for place in (app, app / "Contents"):
        if not os.access(place, os.W_OK):
            raise InstallError(f"{app} değiştirilemiyor: bu kullanıcı oraya yazamıyor. Yeni sürümü elle kurun.")
    staging = app / STAGING
    shutil.rmtree(staging, ignore_errors=True)  # an earlier attempt's
    staging.mkdir()
    try:
        unpack(archive, staging)
        found = [p for p in staging.iterdir() if p.suffix == ".app" and p.is_dir()]
        if len(found) != 1:
            raise InstallError("güncelleme dosyasında uygulama yok")
        [new] = found
        if _bundle(new) != BUNDLE_ID or _bundle_version(new) != version:
            raise InstallError(f"güncelleme dosyasındaki uygulama İplikçi Nedim {version} değil")
        said = run(new / "Contents" / "Resources" / "python" / "bin" / "python3")
        if said != version:
            raise InstallError(f"yeni sürüm kendini {said or '?'} diye tanıttı, {version} değil")
        old = app / OLD
        shutil.rmtree(old, ignore_errors=True)  # an earlier update's, the program files of a version gone
        trade(new / "Contents", app / "Contents")
        (new / "Contents").rename(old)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    os.utime(app)  # Finder and Launch Services read the new version


# --- Linux ------------------------------------------------------------------------------------------------------------


def unpack_copy(archive: Path, into: Path) -> None:
    """The Python folder of a Linux release unpacked into a folder: only files, folders and links inside it."""
    try:
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(into, filter="data")
    except (tarfile.TarError, OSError) as exc:
        raise InstallError(f"güncelleme dosyası açılamadı: {exc}") from None


def apply_linux(copies: Path, archive: Path, version: str, *, unpack: Unpack = unpack_copy, run: Probe = probe) -> Path:
    """The new version's copy in copies/<version>, as AppRun would make it; its Python, which the service is then
    registered with. A whole copy of the version already there (an AppImage of it opened) is kept."""
    target = copies / version
    python = target / "bin" / "python3"
    if python.is_file() and os.access(python, os.X_OK) and run(python) == version:
        return python
    temp = copies / f"{version}.yeni.{os.getpid()}"
    shutil.rmtree(temp, ignore_errors=True)
    temp.mkdir(parents=True)
    try:
        unpack(archive, temp)
        said = run(temp / "bin" / "python3")
        if said != version:
            raise InstallError(f"yeni sürüm kendini {said or '?'} diye tanıttı, {version} değil")
        shutil.rmtree(target, ignore_errors=True)  # a copy without its Python, as AppRun makes it again
        temp.rename(target)
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return python


# --- Windows ----------------------------------------------------------------------------------------------------------


def windows_command(setup: Path, log: Path) -> list[str]:
    """How the setup program runs for an update: no window, no question, no restart of the computer; its log kept.
    It takes the service off itself and opens the app at the end without a browser (packaging/build.py)."""
    return [str(setup), *_SETUP_FLAGS, f"/LOG={log}"]


def leftovers(installation: Installation) -> list[Path]:
    """What an update on macOS left inside the app once the new version runs: the replaced Contents and an unpacking
    cut short. Program files, never documents."""
    if installation.kind is not Kind.MACOS_APP or installation.root is None:
        return []
    return [path for path in (installation.root / OLD, installation.root / STAGING) if path.exists()]
