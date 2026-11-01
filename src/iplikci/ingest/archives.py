"""Documents inside zip archives, mbox files and e-mails (ingest, architecture §6).

Everything is read into memory; nothing from an archive or an e-mail is ever written to disk.
"""

import io
import mailbox
import os
import zipfile
import zlib
from collections.abc import Iterator
from email.header import decode_header, make_header
from email.message import Message
from pathlib import Path

from ..domain.text import nfc

DOCUMENT_EXTENSIONS = {".pdf", ".html", ".htm", ".xls", ".xlsx"}
MAX_MEMBER_BYTES = 50 * 1024 * 1024  # skip suspiciously large archive members
ZIP_ENCRYPTED = "şifreli zip — açıp içindeki belgeleri ayrı ayrı ekleyin"
ZIP_DAMAGED = "zip açılamadı (bozuk ya da yarım inmiş)"


class UnreadableArchive(Exception):
    """A zip that is damaged or whose documents need a password: it is kept whole, as one unreadable
    document, instead of being set aside as an archive whose contents were taken out."""


def decode_header_text(value: str | None) -> str:
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


def from_zip(data: bytes, origin: str) -> list[tuple[str, str, bytes]]:
    """(name, origin, bytes) of the documents and nested zips in a zip archive."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise UnreadableArchive(ZIP_DAMAGED) from exc
    members: list[tuple[str, str, bytes]] = []
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
        if isinstance(data, bytes) and data:  # decode=True gives bytes for a leaf part
            yield nfc(decode_header_text(filename)), data


def from_mbox(path: Path) -> Iterator[tuple[str, str, bytes]]:
    """(name, origin, bytes) of the attachments of every e-mail in an mbox file."""
    box = mailbox.mbox(str(path), create=False)
    for msg in box:
        subject = decode_header_text(msg["Subject"])
        for name, data in attachments(msg):
            yield name, f"{path.name} › {subject} › {name}", data


def is_mbox(path: Path) -> bool:
    if path.suffix.lower() == ".mbox":
        return True
    if path.suffix:
        return False
    with open(path, "rb") as f:
        return f.read(5) == b"From "
