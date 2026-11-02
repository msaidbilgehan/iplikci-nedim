"""Documents inside zip archives, mbox files and e-mails (ingest, architecture §6).

Everything is read into memory; nothing from an archive or an e-mail is ever written to disk.
"""

import io
import mailbox
import os
import re
import zipfile
import zlib
from collections.abc import Iterator
from datetime import datetime
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from ..domain.text import nfc

DOCUMENT_EXTENSIONS = {".pdf", ".html", ".htm", ".xls", ".xlsx", ".xml"}  # .xml: a Turkish e-invoice (UBL-TR)
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


def attachments_left_out(msg: Message) -> bool:
    """Whether a part names a file but carries nothing: Gmail's "Show original" leaves the contents of attachments
    out, and a message read there is incomplete (ADR-0016)."""
    for part in msg.walk():
        if not part.is_multipart() and part.get_filename() and not part.get_payload(decode=True):
            return True
    return False


def sender_domain(msg: Message) -> str:
    """The domain of the From address, lower case; "" when there is none."""
    return parseaddr(str(msg.get("From", "")))[1].rpartition("@")[2].strip().lower()


def sent_at(msg: Message) -> datetime | None:
    try:
        return parsedate_to_datetime(str(msg["Date"]))
    except (TypeError, ValueError, IndexError):
        return None


def message_fields(msg: Message) -> dict[str, str]:
    """What an e-mail says of itself, as a document source records it: its id, sender's domain, subject and date."""
    sent = sent_at(msg)
    return {
        "message_id": str(msg.get("Message-ID", "")).strip(),
        "sender": sender_domain(msg),
        "subject": decode_header_text(msg["Subject"])[:300],
        "sent_at": sent.isoformat() if sent else "",
    }


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


# --- what a file is by its bytes -------------------------------------------------------------------------------

HEAD_BYTES = 4096  # enough of a file to tell what it is
_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # the container of old Excel files
_MAIL_HEADER = re.compile(
    rb"(?:Received|Return-Path|Delivered-To|From|To|Subject|Date|Message-ID|MIME-Version|DKIM-Signature|"
    rb"Authentication-Results|ARC-[A-Za-z-]+|X-[A-Za-z0-9-]+):",
    re.IGNORECASE,
)


def may_be_document(head: bytes) -> bool:
    """Whether a file starting with head may be a document (sniffed_extension tells which); a picture, a text or a
    program never is."""
    return sniffed_extension(head, whole=False) is not None


def sniffed_extension(data: bytes, whole: bool = True) -> str | None:
    """The extension a file's bytes say it has, whatever its name says: a PDF, an Excel workbook (old or new), a zip,
    an HTML page or table, an XML document or an e-mail; None for anything else. A bank's download may come without
    an extension or with a wrong one. With whole=False data is only the file's start: a zip is then not told from a
    workbook (".zip")."""
    head = data[:HEAD_BYTES]
    # The containers first: a zip holding an uncompressed PDF shows the PDF's header too.
    if head.startswith(_OLE):
        return ".xls"
    if head.startswith(b"PK\x03\x04"):
        return ".xlsx" if whole and _is_workbook(data) else ".zip"
    if b"%PDF-" in head[:1024]:  # a PDF may carry a few bytes before its header
        return ".pdf"
    text = head.lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if text.startswith((b"<!doctype html", b"<html", b"<table", b"<meta")):
        return ".html"
    if text.startswith(b"<?xml"):
        return ".html" if b"<html" in text else ".xml"
    if _MAIL_HEADER.match(head.lstrip()):
        return ".eml"
    return None


def _is_workbook(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as found:
            return "xl/workbook.xml" in found.namelist()
    except (zipfile.BadZipFile, ValueError):  # a damaged zip: still a zip, read as one
        return False
