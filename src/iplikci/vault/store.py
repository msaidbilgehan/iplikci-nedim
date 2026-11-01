"""The object store: originals by content, vault/objects/ab/cd/<sha256> (ADR-0003).

An object is written once, through a temporary file in staging that is renamed into place, so a reader never
sees half a document and a crash leaves at most a stray temporary file. Objects are read-only. A file whose
content no longer matches its name is never replaced: the integrity check reports it.
"""

import hashlib
import os
import re
import shutil
import stat
import sys
import tempfile
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from ..settings.paths import Layout
from . import trash

_SHA256 = re.compile(r"[0-9a-f]{64}")
_CHUNK = 1 << 20
OBJECT_MODE = 0o400


class VaultError(Exception):
    """The archive is not as it should be; the message says what and where (Turkish)."""


@dataclass(slots=True)
class Integrity:
    """What the integrity check found among the objects."""

    checked: int = 0
    corrupt: list[str] = field(default_factory=list[str])  # content no longer matches the name
    misplaced: list[Path] = field(default_factory=list[Path])  # a sha256 in the wrong folder
    strays: list[Path] = field(default_factory=list[Path])  # files that are not objects (left-over temporary files)
    writable: list[str] = field(default_factory=list[str])  # objects someone made writable again

    @property
    def ok(self) -> bool:
        return not (self.corrupt or self.misplaced or self.strays)


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


class Vault:
    def __init__(self, layout: Layout):
        self.layout = layout

    def path(self, sha256: str) -> Path:
        if not _SHA256.fullmatch(sha256):
            raise ValueError(f"geçersiz sha256: {sha256!r}")
        return self.layout.objects / sha256[:2] / sha256[2:4] / sha256

    def has(self, sha256: str) -> bool:
        return self.path(sha256).is_file()

    def put(self, data: bytes) -> str:
        """Keep data and return its sha256; the same bytes are kept once."""
        sha256 = sha256_of(data)
        target = self.path(sha256)
        if target.exists():
            self._check(target, sha256)
            return sha256
        self.layout.staging.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".nesne-", dir=self.layout.staging)
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            self._install(tmp, target, sha256)
        finally:
            tmp.unlink(missing_ok=True)
        return sha256

    def put_file(self, source: Path) -> str:
        """Keep a file's bytes (copied, the file stays where it is) and return their sha256."""
        self.layout.staging.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".nesne-", dir=self.layout.staging)
        tmp = Path(tmp_name)
        try:
            digest = hashlib.sha256()
            with os.fdopen(fd, "wb") as out, source.open("rb") as f:
                for chunk in iter(lambda: f.read(_CHUNK), b""):
                    digest.update(chunk)
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            sha256 = digest.hexdigest()
            target = self.path(sha256)
            if target.exists():
                self._check(target, sha256)
            else:
                self._install(tmp, target, sha256)
        finally:
            tmp.unlink(missing_ok=True)
        return sha256

    def adopt(self, source: Path, sha256: str) -> bool:
        """Copy an object of another store under its name (the archive's into the backups' store, a backup's back
        into the archive); whether it was copied (False: it was here already). VaultError when the source's bytes do
        not match the name: a damaged copy is never spread."""
        target = self.path(sha256)
        if target.exists():
            return False
        self.layout.objects.mkdir(parents=True, exist_ok=True)
        self.layout.staging.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".nesne-", dir=self.layout.staging)
        tmp = Path(tmp_name)
        try:
            digest = hashlib.sha256()
            with os.fdopen(fd, "wb") as out, source.open("rb") as f:
                for chunk in iter(lambda: f.read(_CHUNK), b""):
                    digest.update(chunk)
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            if digest.hexdigest() != sha256:
                raise VaultError(f"{source} nesnesi bozulmuş: içeriği adıyla ({sha256}) uyuşmuyor")
            self._install(tmp, target, sha256)
        finally:
            tmp.unlink(missing_ok=True)
        return True

    def _install(self, tmp: Path, target: Path, sha256: str) -> None:
        for folder in (target.parent.parent, target.parent):
            folder.mkdir(exist_ok=True)
            if sys.platform != "win32":
                os.chmod(folder, 0o700)
        os.chmod(tmp, OBJECT_MODE)
        try:
            # A hard link fails when the name exists: two processes keeping the same bytes at once both succeed,
            # and no existing file is ever replaced.
            os.link(tmp, target)
        except FileExistsError:
            self._check(target, sha256)
        except OSError:  # a file system without hard links
            if target.exists():
                self._check(target, sha256)
            else:
                os.replace(tmp, target)

    def _check(self, path: Path, sha256: str) -> None:
        if _file_sha256(path) != sha256:
            raise VaultError(f"arşivdeki {sha256} nesnesi bozulmuş; iplikci dogrula --arsiv ile denetleyin")

    def read(self, sha256: str, verify: bool = True) -> bytes:
        try:
            data = self.path(sha256).read_bytes()
        except FileNotFoundError:
            raise VaultError(f"arşivde {sha256} nesnesi yok") from None
        if verify and sha256_of(data) != sha256:
            raise VaultError(f"arşivdeki {sha256} nesnesi bozulmuş; iplikci dogrula --arsiv ile denetleyin")
        return data

    def objects(self) -> Iterator[str]:
        """The sha256 of every object, in name order."""
        if not self.layout.objects.is_dir():
            return
        for path in sorted(self.layout.objects.glob("*/*/*")):
            if path.is_file() and _SHA256.fullmatch(path.name):
                yield path.name

    def verify(self) -> Integrity:
        """Hash every object again and look for anything else in the object folders."""
        found = Integrity()
        if not self.layout.objects.is_dir():
            return found
        for path in sorted(self.layout.objects.rglob("*")):
            if path.is_dir():
                continue
            relative = path.relative_to(self.layout.objects).parts
            if len(relative) != 3 or not _SHA256.fullmatch(path.name):
                found.strays.append(path)
                continue
            if relative[:2] != (path.name[:2], path.name[2:4]):
                found.misplaced.append(path)
                continue
            found.checked += 1
            if _file_sha256(path) != path.name:
                found.corrupt.append(path.name)
            if sys.platform != "win32" and path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
                found.writable.append(path.name)
        return found

    def remove(self, sha256: str) -> Path:
        """Move an object to the system Trash (never deleted); returns where it went."""
        source = self.path(sha256)
        if not source.exists():
            raise VaultError(f"arşivde {sha256} nesnesi yok")
        return trash.discard(source, self.layout.home)

    def derived(self, sha256: str) -> Path:
        """The folder of what is made from an object (page images, text); it can be emptied and made again."""
        folder = self.layout.derived / sha256
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def drop_derived(self, sha256: str) -> None:
        """Forget what was made from an object; it is made again on demand (not a document: removed outright)."""
        folder = self.layout.derived / self.path(sha256).name
        if folder.is_dir():
            shutil.rmtree(folder)

    @contextmanager
    def staging(self) -> Generator[Path]:
        """A private folder for a document being read before it is kept; emptied afterwards."""
        self.layout.staging.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="okuma-", dir=self.layout.staging))
        try:
            yield folder
        finally:
            shutil.rmtree(folder, ignore_errors=True)
