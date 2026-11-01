"""Files the user drops into the inbox, through the panel or the file manager.

An upload is written under a hidden name first and gets its real name only when complete, so a plan or the
automatic run never sees half a file. Nothing in the inbox is ever replaced: a second file with a taken name
gets "(2)" and so on.
"""

import hashlib
import os
import re
import shutil
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from ..domain.text import nfc
from ..ingest.archives import DOCUMENT_EXTENSIONS
from .workspace import Workspace

UPLOAD_EXTENSIONS = frozenset(DOCUMENT_EXTENSIONS | {".zip", ".mbox"})
MAX_UPLOAD_BYTES = 1 << 30  # an e-mail archive can be large; a statement is a few hundred KB
PARTIAL_PREFIX = ".yukleniyor-"  # hidden: no reader picks up a file that is still being written
_MAX_FOLDERS = 3  # folder levels kept from an uploaded tree
_UNSAFE = re.compile(r"[\x00-\x1f\x7f:]")
_upload_lock = threading.Lock()
_hashes: dict[tuple[str, int, int], str] = {}  # (path, size, mtime) -> sha256 of inbox files


@dataclass(frozen=True)
class Upload:
    status: str  # "eklendi", "zaten-var" (same bytes already waiting), "reddedildi"
    name: str  # path inside the inbox, or the name that was refused
    reason: str = ""


def safe_upload_path(name: str) -> PurePosixPath | None:
    """An uploaded file's relative path made safe: no "..", no absolute path, no control characters, at most a
    few folders; None for a hidden file or when nothing usable is left."""
    parts: list[str] = []
    for part in PurePosixPath(nfc(name).replace("\\", "/")).parts:
        part = _UNSAFE.sub("", part).strip()
        if part in ("", "/", ".", ".."):
            continue
        if part.startswith("."):
            return None  # .DS_Store and friends are never documents
        parts.append(part[:150])
    if not parts:
        return None
    return PurePosixPath(*parts[:-1][-_MAX_FOLDERS:], parts[-1])


def inbox_files(ws: Workspace) -> list[Path]:
    """Files waiting in the inbox (hidden files and folders, i.e. unfinished uploads, left out)."""
    if not ws.inbox.is_dir():
        return []
    found: list[Path] = []
    for folder, dirs, files in os.walk(ws.inbox):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        found += [Path(folder) / f for f in sorted(files) if not f.startswith(".")]
    return found


def file_sha256(path: Path) -> str:
    st = path.stat()
    key = (str(path), st.st_size, st.st_mtime_ns)
    if len(_hashes) > 10_000:
        _hashes.clear()
    if key not in _hashes:
        digest = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        _hashes[key] = digest.hexdigest()
    return _hashes[key]


def _place(src: Path, dest: Path) -> None:
    """Make src's bytes appear under dest; FileExistsError if dest exists (nothing is replaced)."""
    try:
        os.link(src, dest)
        return
    except FileExistsError:
        raise
    except OSError:  # a file system without hard links (FAT, exFAT, some network shares): copy
        pass
    with open(dest, "xb") as out:
        try:
            with open(src, "rb") as f:
                shutil.copyfileobj(f, out)
        except BaseException:
            out.close()
            dest.unlink(missing_ok=True)  # our half-written copy, never someone's file
            raise


def link_free(src: Path, dest: Path) -> Path:
    """Give src the name dest, or "dest (2)" and so on: never replaces an existing file."""
    candidate, n = dest, 2
    while True:
        try:
            _place(src, candidate)
            return candidate
        except FileExistsError:
            candidate = dest.with_name(f"{dest.stem} ({n}){dest.suffix}")
            n += 1


def save_upload(ws: Workspace, name: str, stream: BinaryIO, length: int) -> Upload:
    """Store one uploaded file in the inbox."""
    rel = safe_upload_path(name)
    if rel is None or rel.suffix.lower() not in UPLOAD_EXTENSIONS:
        kinds = ", ".join(sorted(e.lstrip(".").upper() for e in UPLOAD_EXTENSIONS))
        return Upload("reddedildi", name, f"desteklenmeyen dosya türü (kabul edilenler: {kinds})")
    if length > MAX_UPLOAD_BYTES:
        return Upload(
            "reddedildi",
            name,
            f"dosya {MAX_UPLOAD_BYTES >> 20} MB sınırından büyük; büyük arşivleri doğrudan gelen klasörüne kopyalayın",
        )
    ws.inbox.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=PARTIAL_PREFIX, dir=ws.inbox)
    tmp = Path(tmp_name)
    try:
        digest = hashlib.sha256()
        with os.fdopen(fd, "wb") as f:
            left = length
            while left > 0:
                chunk = stream.read(min(left, 1 << 20))
                if not chunk:
                    raise ConnectionError("yükleme yarıda kesildi")
                f.write(chunk)
                digest.update(chunk)
                left -= len(chunk)
        sha = digest.hexdigest()
        with _upload_lock:
            twin = next((p for p in inbox_files(ws) if file_sha256(p) == sha), None)
            if twin:
                return Upload("zaten-var", str(twin.relative_to(ws.inbox)), "aynı dosya gelen kutusunda zaten var")
            dest = ws.inbox / rel
            existing = dest.parent
            while not existing.exists():
                existing = existing.parent
            if not existing.resolve().is_relative_to(ws.inbox.resolve()):  # a symlinked folder
                return Upload("reddedildi", name, "gelen kutusunun dışına yazılamaz")
            dest.parent.mkdir(parents=True, exist_ok=True)
            final = link_free(tmp, dest)
        return Upload("eklendi", str(final.relative_to(ws.inbox)))
    finally:
        tmp.unlink(missing_ok=True)  # our own partial file, never a document
