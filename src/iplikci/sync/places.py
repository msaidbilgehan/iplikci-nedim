"""Where a sync folder can go: the folders the computer's sync services mirror (ADR-0025). Google Drive's desktop app
first, as the user asked for it; iCloud Drive, Dropbox and OneDrive work the same way. The program never talks to
these services: it writes into their folder and they carry it."""

import os
import string
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

GOOGLE_DRIVE = "google_drive"
ICLOUD = "icloud"
DROPBOX = "dropbox"
ONEDRIVE = "onedrive"

LABELS = {GOOGLE_DRIVE: "Google Drive", ICLOUD: "iCloud Drive", DROPBOX: "Dropbox", ONEDRIVE: "OneDrive"}

# The folders of a Google Drive account beside the user's own drive, in English and in Turkish.
_NOT_MY_DRIVE = {
    "Other computers",
    "Shared drives",
    "Computers",
    "Diğer bilgisayarlar",
    "Ortak Drive'lar",
    "Paylaşılan Drive'lar",
    "Bilgisayarlar",
}
_MY_DRIVE = ("My Drive", "Drive'ım", "Drive’ım")


@dataclass(frozen=True, slots=True)
class Place:
    kind: str  # GOOGLE_DRIVE, ICLOUD, DROPBOX, ONEDRIVE
    account: str  # the account the folder belongs to, when its name says one ("" otherwise)
    root: Path  # the folder the service mirrors: the sync folder is made in it

    @property
    def label(self) -> str:
        return LABELS[self.kind]


def _dirs(folder: Path) -> list[Path]:
    try:
        return sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        return []


def _my_drive(account_root: Path) -> Path | None:
    """The user's own drive inside a Google Drive account's folder: "My Drive", or its name in another language."""
    for name in _MY_DRIVE:
        if (account_root / name).is_dir():
            return account_root / name
    others = [p for p in _dirs(account_root) if p.name not in _NOT_MY_DRIVE]
    return others[0] if len(others) == 1 else None


def _mac(home: Path, volumes: Path) -> Iterable[Place]:
    cloud = home / "Library" / "CloudStorage"
    for folder in _dirs(cloud):
        if folder.name.startswith("GoogleDrive"):
            mine = _my_drive(folder)
            if mine is not None:
                yield Place(GOOGLE_DRIVE, folder.name.removeprefix("GoogleDrive").lstrip("-"), mine)
    for folder in _dirs(volumes):  # Google Drive's desktop app before it moved into CloudStorage
        if folder.name.startswith("GoogleDrive"):
            mine = _my_drive(folder)
            if mine is not None:
                yield Place(GOOGLE_DRIVE, "", mine)
    icloud = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    if icloud.is_dir():
        yield Place(ICLOUD, "", icloud)
    for folder in _dirs(cloud):
        if folder.name.startswith("Dropbox"):
            yield Place(DROPBOX, folder.name.removeprefix("Dropbox").lstrip("-"), folder)
        elif folder.name.startswith("OneDrive"):
            yield Place(ONEDRIVE, folder.name.removeprefix("OneDrive").lstrip("-"), folder)
    if (home / "Dropbox").is_dir():
        yield Place(DROPBOX, "", home / "Dropbox")


def _windows(home: Path, env: Mapping[str, str], drive_root: Callable[[str], Path]) -> Iterable[Place]:
    for letter in string.ascii_uppercase[3:]:  # Google Drive mounts a drive of its own, G: by default
        root = drive_root(letter)
        for name in _MY_DRIVE:
            try:
                if (root / name).is_dir():
                    yield Place(GOOGLE_DRIVE, "", root / name)
                    break
            except OSError:  # a drive that is not ready (an empty card reader)
                break
    if (home / "Google Drive").is_dir():
        yield Place(GOOGLE_DRIVE, "", home / "Google Drive")
    if (home / "iCloudDrive").is_dir():
        yield Place(ICLOUD, "", home / "iCloudDrive")
    if (home / "Dropbox").is_dir():
        yield Place(DROPBOX, "", home / "Dropbox")
    onedrive = env.get("OneDrive", "")
    if onedrive and Path(onedrive).is_dir():
        yield Place(ONEDRIVE, "", Path(onedrive))


def _linux(home: Path) -> Iterable[Place]:
    for name, kind in (("Dropbox", DROPBOX), ("GoogleDrive", GOOGLE_DRIVE), ("Google Drive", GOOGLE_DRIVE)):
        if (home / name).is_dir():
            yield Place(kind, "", home / name)


def found(
    home: Path | None = None,
    platform: str | None = None,
    env: Mapping[str, str] | None = None,
    volumes: Path = Path("/Volumes"),
    drive_root: Callable[[str], Path] = lambda letter: Path(f"{letter}:\\"),
) -> list[Place]:
    """The sync services' folders on this computer, Google Drive's first; each once."""
    home = home or Path.home()
    platform = platform or sys.platform
    env = os.environ if env is None else env
    if platform == "darwin":
        places = list(_mac(home, volumes))
    elif platform.startswith("win"):
        places = list(_windows(home, env, drive_root))
    else:
        places = list(_linux(home))
    seen: set[Path] = set()
    unique: list[Place] = []
    for p in sorted(places, key=lambda p: (p.kind != GOOGLE_DRIVE, p.kind, p.account)):
        if p.root not in seen:
            seen.add(p.root)
            unique.append(p)
    return unique


def kind_of(folder: Path, places: Iterable[Place]) -> Place | None:
    """The sync service whose folder holds folder; None for a folder no known service mirrors."""
    for p in places:
        if folder == p.root or folder.is_relative_to(p.root):
            return p
    return None
