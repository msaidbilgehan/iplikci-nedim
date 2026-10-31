"""Collect documents from folders, mbox files and zip archives.

Everything is read into memory; nothing from an archive or an e-mail is ever
written to disk. Identical files (same SHA-256) are returned once.
"""

import hashlib
import io
import mailbox
import os
import zipfile
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import Message
from pathlib import Path

from .textutil import nfc

DOCUMENT_EXTENSIONS = {".pdf", ".html", ".htm", ".xls", ".xlsx"}
MAX_MEMBER_BYTES = 50 * 1024 * 1024  # skip suspiciously large archive members
ZIP_ENCRYPTED = "şifreli zip — açıp içindeki belgeleri ayrı ayrı ekleyin"
ZIP_DAMAGED = "zip açılamadı (bozuk ya da yarım inmiş)"


class UnreadableArchive(Exception):
    """A zip that is damaged or whose documents need a password: it is kept whole, as one unreadable
    document, instead of being set aside as an archive whose contents were taken out."""


@dataclass
class Document:
    name: str  # file name only, NFC-normalized
    origin: str  # where it came from, for the report
    data: bytes
    sha256: str

    @property
    def ext(self) -> str:
        return os.path.splitext(self.name)[1].lower()


def _decode_header(value: str | None) -> str:
    try:
        return str(make_header(decode_header(value or "")))
    except Exception:  # a malformed header of an untrusted message is kept as it is  # noqa: BLE001
        return value or ""


def _zip_member_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if not info.flag_bits & 0x800:  # name not flagged as UTF-8: zipfile decoded it as cp437
        try:
            name = name.encode("cp437").decode("utf-8")
        except UnicodeError:
            pass
    return nfc(name)


def _from_zip(data: bytes, origin: str) -> list[tuple[str, str, bytes]]:
    """(name, origin, bytes) of the documents and nested zips in a zip archive."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise UnreadableArchive(ZIP_DAMAGED) from exc
    members = []
    with zf:
        for info in zf.infolist():
            name = _zip_member_name(info)
            base = os.path.basename(name)
            if info.is_dir() or name.startswith("__MACOSX/") or base.startswith("."):
                continue
            if info.file_size > MAX_MEMBER_BYTES:
                continue
            ext = os.path.splitext(base)[1].lower()
            if ext not in DOCUMENT_EXTENSIONS and ext != ".zip":
                continue
            if info.flag_bits & 0x1:
                raise UnreadableArchive(ZIP_ENCRYPTED)
            try:
                members.append((base, f"{origin} › {name}", zf.read(info)))
            # A damaged member, or a compression method zipfile cannot unpack (NotImplementedError).
            except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError) as exc:
                raise UnreadableArchive(ZIP_DAMAGED) from exc
    return members


def attachments(msg: Message) -> Iterator[tuple[str, bytes]]:
    """(file name, bytes) of every attachment of an e-mail."""
    for part in msg.walk():
        filename = part.get_filename()
        if not filename:
            continue
        data = part.get_payload(decode=True)
        if data:
            yield nfc(_decode_header(filename)), data


def _from_mbox(path: Path):
    box = mailbox.mbox(str(path), create=False)
    for msg in box:
        subject = _decode_header(msg["Subject"])
        for name, data in attachments(msg):
            yield name, f"{path.name} › {subject} › {name}", data


def _is_mbox(path: Path) -> bool:
    if path.suffix.lower() == ".mbox":
        return True
    if path.suffix:
        return False
    with open(path, "rb") as f:
        return f.read(5) == b"From "


def _expand(name: str, origin: str, data: bytes):
    """Yield (name, origin, data) for a file, descending into zip archives. A zip that cannot be
    opened is yielded itself: the parsers report it as unreadable, so it is kept for a manual look."""
    if name.lower().endswith(".zip"):
        try:
            members = _from_zip(data, origin)
        except UnreadableArchive:
            yield name, origin, data
            return
        for member in members:
            yield from _expand(*member)
    elif os.path.splitext(name)[1].lower() in DOCUMENT_EXTENSIONS:
        yield name, origin, data


def _walk(path: Path):
    if path.is_dir():
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for fn in sorted(files):
                if fn.startswith("."):
                    continue
                yield from _walk(Path(root) / fn)
    elif path.is_file():
        if _is_mbox(path):
            for name, origin, data in _from_mbox(path):
                yield from _expand(name, origin, data)
        elif path.suffix.lower() in DOCUMENT_EXTENSIONS | {".zip"}:
            yield from _expand(nfc(path.name), nfc(str(path)), path.read_bytes())


def collect(paths: list[Path]) -> tuple[list[Document], int]:
    """Return unique documents under the given paths and the number of duplicates skipped."""
    seen: dict[str, Document] = {}
    duplicates = 0
    for path in paths:
        for name, origin, data in _walk(path):
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen:
                duplicates += 1
                continue
            seen[digest] = Document(name=name, origin=origin, data=data, sha256=digest)
    return list(seen.values()), duplicates
