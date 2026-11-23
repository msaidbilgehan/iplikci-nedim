"""The sync folder on disk (ADR-0025):

    <folder>/                       the user's choice; "İplikçi Nedim" in their Google Drive by default
      iplikci-esitleme.json         which set of data this is; written once, by the computer that began it
      BENİOKU.txt                   what the folder is, for a person who opens it
      cihaz-<id>/                   one per computer; only that computer writes in it
        cihaz.json                  its name, version, when it was last seen, the channels it could send on
        durum.json                  every piece of the shared data it knows (sync.state)
        belgeler/ab/<sha256>        the originals it brought in that no other computer had put in the folder

Each file has one writer, so the sync service never meets two computers changing one file. A file is written beside
its place under a name of its own and moved over it: a computer reading it gets the old file or the new one, never
half (and one the sync service brought only halfway is refused by its reader and read again in the next round). The
originals are named by their content and never change; a copy is checked against its name before it is used.
"""

import hashlib
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..vault import trash

MARKER = "iplikci-esitleme.json"
README = "BENİOKU.txt"
DEVICE_PREFIX = "cihaz-"
DEVICE_FILE = "cihaz.json"
STATE_FILE = "durum.json"
OBJECTS = "belgeler"
DEFAULT_NAME = "İplikçi Nedim"  # the folder made in the place the user picks
FORMAT = "iplikci-esitleme"
DEVICE_FORMAT = "iplikci-esitleme-cihazi"
VERSION = 1

_ID = re.compile(r"[0-9a-f]{12}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_CHUNK = 1 << 20
_WRITING = ".yaziliyor"

README_TEXT = """\
Bu klasörü İplikçi Nedim yazar. Kişisel finans programınızın belgeleri ve kararları burada
bilgisayarlarınız arasında eşitlenir; bilgisayarınızın dışında da bir kopyaları durur.

- Klasördeki dosyaları değiştirmeyin, taşımayın, silmeyin.
- Her bilgisayarın kendi klasörü vardır (cihaz-...); her bilgisayar yalnızca kendininkine yazar.
- Verilerinizi yeni bir bilgisayara getirmek için İplikçi Nedim'i kurun ve
  Ayarlar > Eşitleme ve yedek bölümünden bu klasörü seçin.
"""


class LibraryError(Exception):
    """The folder is not a sync folder this program can use; the message says why (Turkish)."""


@dataclass(frozen=True, slots=True)
class Device:
    """What a computer says of itself in its cihaz.json."""

    id: str
    name: str  # the name the user gave it, or the computer's own
    app: str  # the program's version it runs
    system: str  # macOS, Windows, Linux
    seen_at: str  # UTC, ISO 8601: when it last wrote the file
    channels: tuple[str, ...] = ()  # the channels leaving the app it could send notifications on (telegram, email)
    left: bool = False  # its user turned the sync off there


def new_device_id() -> str:
    return secrets.token_hex(6)


def valid_id(text: str) -> bool:
    return bool(_ID.fullmatch(text))


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


# --- the folder itself --------------------------------------------------------------------------------------


def marker(folder: Path) -> str | None:
    """The id of the set of data in folder; None when folder holds none (LibraryError when its mark is damaged)."""
    path = folder / MARKER
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise LibraryError(f"eşitleme klasörünün işareti okunamadı: {exc.strerror or exc}") from exc
    try:
        value: Any = json.loads(data.decode("utf-8"))
        library = value["library"]
        if value.get("format") != FORMAT or not isinstance(library, str) or not library:
            raise ValueError(library)
    except (UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        raise LibraryError(f"{MARKER} bir İplikçi Nedim eşitleme klasörü işareti değil") from exc
    return library


def create(folder: Path) -> str:
    """Begin a set of data in folder (made if missing; its parent must exist); the new set's id. A folder holding
    other files is refused: the program never writes among the user's own files."""
    if folder.exists() and not folder.is_dir():
        raise LibraryError(f"{folder.name} bir klasör değil")
    if folder.is_dir() and any(not p.name.startswith(".") for p in folder.iterdir()):
        raise LibraryError(f"{folder.name} klasörü boş değil; İplikçi Nedim için boş ya da yeni bir klasör seçin")
    if not folder.parent.is_dir():
        raise LibraryError(f"{folder.parent} bulunamadı")
    folder.mkdir(exist_ok=True)
    library = secrets.token_hex(8)
    value = {"format": FORMAT, "version": VERSION, "library": library, "created_at": _now()}
    write_file(folder / README, README_TEXT.encode("utf-8"))
    write_file(folder / MARKER, (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    return library


def device_dir(folder: Path, device: str) -> Path:
    if not valid_id(device):
        raise ValueError(f"geçersiz cihaz kimliği: {device!r}")
    return folder / f"{DEVICE_PREFIX}{device}"


def devices(folder: Path) -> list[str]:
    """The ids of the computers that have a part in folder."""
    try:
        names = [p.name for p in folder.iterdir() if p.is_dir()]
    except OSError:
        return []
    found = [n.removeprefix(DEVICE_PREFIX) for n in names if n.startswith(DEVICE_PREFIX)]
    return sorted(i for i in found if valid_id(i))


# --- files ------------------------------------------------------------------------------------------------------


def write_file(path: Path, data: bytes) -> None:
    """Put data at path at once: written beside it under a name of its own, then moved over it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=_WRITING)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if sys.platform != "win32":
            os.chmod(name, 0o600)
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def stat_key(path: Path) -> tuple[int, int] | None:
    """The size and time of the file at path, to tell a changed file without reading it; None when there is none."""
    try:
        st = path.stat()
    except OSError:
        return None
    return st.st_size, st.st_mtime_ns


# --- what a computer says of itself -----------------------------------------------------------------------


def write_device(folder: Path, d: Device) -> None:
    value = {
        "format": DEVICE_FORMAT,
        "version": VERSION,
        "device": d.id,
        "name": d.name,
        "app": d.app,
        "system": d.system,
        "seen_at": d.seen_at,
        "channels": list(d.channels),
        "left": d.left,
    }
    write_file(device_dir(folder, d.id) / DEVICE_FILE, json.dumps(value, ensure_ascii=False, indent=1).encode("utf-8"))


def read_device(folder: Path, device: str) -> Device | None:
    """A computer's cihaz.json; None while it cannot be read (not there yet, being brought, another program's)."""
    try:
        value: Any = json.loads((device_dir(folder, device) / DEVICE_FILE).read_bytes().decode("utf-8"))
        fields: Mapping[str, Any] = value
        if fields.get("format") != DEVICE_FORMAT or fields.get("device") != device:
            return None
        channels: list[Any] = list(fields.get("channels", []))
        return Device(
            device,
            str(fields.get("name", "")),
            str(fields.get("app", "")),
            str(fields.get("system", "")),
            str(fields.get("seen_at", "")),
            tuple(str(c) for c in channels),
            bool(fields.get("left", False)),
        )
    except (OSError, UnicodeDecodeError, ValueError, TypeError, AttributeError):
        return None


# --- the originals ------------------------------------------------------------------------------------------


def object_path(folder: Path, device: str, sha256: str) -> Path:
    if not _SHA256.fullmatch(sha256):
        raise ValueError(f"geçersiz sha256: {sha256!r}")
    return device_dir(folder, device) / OBJECTS / sha256[:2] / sha256


def objects(folder: Path, device: str) -> dict[str, Path]:
    """The originals a computer put in the folder, by sha256 (by their names; a copy is checked when it is used)."""
    root = device_dir(folder, device) / OBJECTS
    found: dict[str, Path] = {}
    try:
        groups = [p for p in root.iterdir() if p.is_dir()]
    except OSError:
        return found
    for group in groups:
        try:
            entries = list(group.iterdir())
        except OSError:
            continue
        for path in entries:
            if _SHA256.fullmatch(path.name) and path.name.startswith(group.name):
                found[path.name] = path
    return found


def publish(folder: Path, device: str, sha256: str, source: Path) -> int:
    """Copy an original into the computer's part of the folder, checked against its name; the bytes copied. A
    damaged original is never spread (ValueError)."""
    target = object_path(folder, device, sha256)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=target.parent, prefix=f".{sha256[:12]}.", suffix=_WRITING)
    size = 0
    try:
        digest = hashlib.sha256()
        with os.fdopen(fd, "wb") as out, source.open("rb") as f:
            for chunk in iter(lambda: f.read(_CHUNK), b""):
                digest.update(chunk)
                out.write(chunk)
                size += len(chunk)
            out.flush()
            os.fsync(out.fileno())
        if digest.hexdigest() != sha256:
            raise ValueError(f"{sha256[:12]} belgesinin aslı adıyla uyuşmuyor; klasöre konmadı")
        os.replace(name, target)
    finally:
        Path(name).unlink(missing_ok=True)
    return size


def withdraw(path: Path, home: Path) -> None:
    """An original of a removed document out of the computer's part of the folder: to the system Trash, never
    deleted (ADR-0003); the sync service then keeps it in its own trash for a while."""
    if path.exists():
        trash.discard(path, home)


def leftovers(folder: Path, device: str) -> Iterator[Path]:
    """Half-written files a stop left in the computer's part of the folder."""
    root = device_dir(folder, device)
    if not root.is_dir():
        return
    for path in root.rglob(f"*{_WRITING}"):
        if path.is_file():
            yield path


def remove_leftover(path: Path) -> None:
    """A half-written copy this program made: removed outright, like a backup's own half-made folder."""
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)
