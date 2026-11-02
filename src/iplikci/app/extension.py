"""The browser extension's files for the browser to load (ADR-0016, K20). Until the extension is in a store, the
browser loads it unpacked, from a folder that must stay where it is. The program carries the built extension; when
the user asks, the service copies it into the data folder's extension/ and shows that folder in the system's file
manager. The copy keeps up with the program: a newer program rewrites it at the service's next start, and the browser
runs the new version once it starts again."""

import hashlib
import json
import logging
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..service import dialog
from .workspace import Workspace

BUILT = Path(__file__).resolve().parent.parent / "browser_extension"  # written by `npm run build` in extension/
MANIFEST = "manifest.json"

log = logging.getLogger("iplikci.extension")


class ExtensionError(Exception):
    """The extension's folder cannot be made here; the message says why (Turkish)."""


@dataclass(frozen=True, slots=True)
class ExtensionState:
    available: bool  # this installation carries the built extension
    version: str  # the carried extension's version; "" when there is none
    folder: Path | None  # the data folder's copy, once made
    current: bool  # the copy holds the carried files


@dataclass(frozen=True, slots=True)
class Shown:
    folder: Path
    version: str
    opened: bool  # the system's file manager shows the folder


def _carried(built: Path | None) -> Path:
    return BUILT if built is None else built


def state(ws: Workspace, built: Path | None = None) -> ExtensionState:
    built = _carried(built)
    available = (built / MANIFEST).is_file()
    folder = ws.layout.extension
    made = (folder / MANIFEST).is_file()
    return ExtensionState(
        available=available,
        version=_version(built) if available else "",
        folder=folder if made else None,
        current=available and made and _digest(folder) == _digest(built),
    )


def prepare(ws: Workspace, built: Path | None = None) -> Path:
    """The data folder's copy of the extension, made or brought up to date now."""
    built = _carried(built)
    if not (built / MANIFEST).is_file():
        raise ExtensionError(
            "Bu kurulum tarayıcı eklentisini taşımıyor. Kurulum paketiyle gelen uygulamayı kullanın; geliştirme "
            "kopyasında önce extension/ klasöründe eklentiyi derleyin."
        )
    folder = ws.layout.extension
    if not ((folder / MANIFEST).is_file() and _digest(folder) == _digest(built)):
        _copy(built, folder)
        log.info("the extension's folder holds version %s", _version(built))
    return folder


def show(ws: Workspace, built: Path | None = None, opener: Callable[[Path], bool] | None = None) -> Shown:
    """Make the copy and show it in the system's file manager, for the browser's "Load unpacked"."""
    folder = prepare(ws, built)
    return Shown(folder, _version(_carried(built)), (opener or dialog.show_folder)(folder))


def refresh(ws: Workspace, built: Path | None = None) -> bool:
    """At the service's start: a copy made before is brought up to date with the program; one the user never asked
    for is not made. Whether it was rewritten. A copy the system keeps busy is tried again at the next start."""
    built = _carried(built)
    folder = ws.layout.extension
    if not ((folder / MANIFEST).is_file() and (built / MANIFEST).is_file()):
        return False
    if _digest(folder) == _digest(built):
        return False
    try:
        _copy(built, folder)
    except OSError as exc:
        log.warning("the extension's folder could not be brought up to date: %s", exc)
        return False
    log.info("the extension's folder was brought up to date: version %s", _version(built))
    return True


def _version(root: Path) -> str:
    try:
        return str(json.loads((root / MANIFEST).read_text(encoding="utf-8"))["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def _files(root: Path) -> dict[str, Path]:
    """The extension's files by their path inside root; hidden ones (a file manager's own, a half-written copy) are
    not the extension's."""
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if path.is_file() and not any(part.startswith(".") for part in path.relative_to(root).parts)
    }


def _digest(root: Path) -> str:
    found = hashlib.sha256()
    for name, path in _files(root).items():
        found.update(name.encode())
        found.update(hashlib.sha256(path.read_bytes()).digest())
    return found.hexdigest()


def _copy(built: Path, folder: Path) -> None:
    """Every carried file into folder, each replaced whole, and an older version's other files removed: the folder
    stays where the browser loads it from. Only the user can read the copy, as everything in the data folder."""
    folder.mkdir(mode=0o700, exist_ok=True)
    wanted = _files(built)
    for name, source in wanted.items():
        target = folder / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=target.parent, prefix=".yeni-")  # 0600
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(source.read_bytes())
            os.replace(temp, target)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise
    for name, path in _files(folder).items():
        if name not in wanted:
            path.unlink()  # our own copy of an older version's file
    for path in sorted((p for p in folder.rglob("*") if p.is_dir()), reverse=True):
        if not any(path.iterdir()):
            path.rmdir()
