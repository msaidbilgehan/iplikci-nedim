"""The system Trash: where a removed document or a set-aside file goes. Nothing is ever deleted (ADR-0003); a
file in the Trash can be put back with the file manager.

macOS: a folder created inside ~/.Trash when the process may (a background job without Full Disk Access may
not), else Finder's own "move to Trash". Linux desktops: the freedesktop.org Trash with its .trashinfo note.
Windows: the Recycle Bin through the shell. Tests point MAC_TRASH at a temporary folder.
"""

import importlib
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

MAC_TRASH = Path.home() / ".Trash"


def can_create_in(folder: Path) -> bool:
    """macOS may refuse a background job inside the Trash; only creating something there tells."""
    if not folder.is_dir():
        return False
    try:
        probe = Path(tempfile.mkdtemp(prefix=".iplikci-", dir=folder))
    except OSError:
        return False
    probe.rmdir()
    return True


def default_folder(fallback: Path) -> Path:
    """A fresh folder for the files one operation sets aside: inside the macOS Trash when possible, else in
    fallback (handed to the system Trash afterwards with move_to_system_trash)."""
    stamp = datetime.now().strftime("%Y-%m-%d %H.%M.%S")
    base = MAC_TRASH if can_create_in(MAC_TRASH) else fallback
    return base / f"iplikci silinenler {stamp}"


def move_to_system_trash(path: Path) -> Path:
    """Where path (a file or a folder) ended up. Something already inside the macOS Trash stays; elsewhere it
    goes to the desktop's own Trash. When that is impossible it stays where it is and that path is returned."""
    if not path.exists() or path.resolve().is_relative_to(MAC_TRASH.resolve()):
        return path
    if sys.platform.startswith("linux"):
        return freedesktop_trash(path)
    if sys.platform == "win32":
        return _recycle(path)
    try:
        foundation = importlib.import_module("Foundation")  # macOS only (pyobjc), without type stubs
    except ImportError:
        return path
    ok, url, _ = foundation.NSFileManager.defaultManager().trashItemAtURL_resultingItemURL_error_(
        foundation.NSURL.fileURLWithPath_(str(path)), None, None
    )
    return Path(str(url.path())) if ok and url is not None else path


def discard(path: Path, fallback: Path) -> Path:
    """Move one file to the Trash, inside a dated "iplikci silinenler" folder; returns where it went. When the
    system Trash cannot take the folder it stays in fallback, still recoverable (as the MVP did on Windows)."""
    folder = default_folder(fallback)
    folder.mkdir(parents=True, exist_ok=True)
    moved = Path(shutil.move(path, folder / path.name))
    return move_to_system_trash(folder) / moved.name


def freedesktop_trash(path: Path) -> Path:
    """Move path into the Trash of Linux desktops (freedesktop.org Trash specification): Trash/files with a
    Trash/info note of where it came from, so the file manager can put it back. If it cannot be made, path stays
    where it is."""
    trash = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "Trash"
    try:
        (trash / "files").mkdir(parents=True, exist_ok=True)
        (trash / "info").mkdir(parents=True, exist_ok=True)
        name, n = path.name, 2
        while True:
            note = trash / "info" / f"{name}.trashinfo"
            try:
                fd = os.open(note, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                name, n = f"{path.name} {n}", n + 1
                continue
            if not (trash / "files" / name).exists():
                break
            os.close(fd)  # the name is taken by an item without a note: take back ours, try the next
            note.unlink()
            name, n = f"{path.name} {n}", n + 1
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(
                f"[Trash Info]\nPath={quote(str(path.resolve()))}\nDeletionDate={datetime.now():%Y-%m-%dT%H:%M:%S}\n"
            )
        try:
            return Path(shutil.move(path, trash / "files" / name))
        except OSError:
            note.unlink(missing_ok=True)
            raise
    except OSError:
        return path


def _recycle(path: Path) -> Path:
    """The Windows Recycle Bin, through SHFileOperationW with undo allowed; path stays where it is on failure."""
    import ctypes
    from ctypes import wintypes

    class _FileOp(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", ctypes.c_uint16),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    fo_delete, allow_undo, silent, no_confirmation, no_error_ui = 3, 0x40, 0x4, 0x10, 0x400
    # What the Recycle Bin cannot take (too big, a bin set to delete at once, a drive without one) Windows would delete
    # for good without a word under no_confirmation; this flag makes it ask first, and a no keeps the file (ADR-0003).
    want_nuke_warning = 0x4000
    flags = allow_undo | silent | no_confirmation | no_error_ui | want_nuke_warning
    op = _FileOp(None, fo_delete, str(path.resolve()) + "\0", None, flags, 0)
    shell: Any = getattr(ctypes, "windll").shell32  # noqa: B009 - windll exists only on Windows
    if shell.SHFileOperationW(ctypes.byref(op)) == 0 and not path.exists():
        return Path("$Recycle.Bin") / path.name  # the Recycle Bin keeps it under a name of its own
    return path
