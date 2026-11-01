"""A kept e-mail as the readers of message bodies see it (Phase 4): who sent it, its subject and date, and the visible
text of its body.

A message is kept whole (ADR-0015) and its attachments are documents of their own, read by the readers of their
formats; the body is what a reader of a bank's notices reads. Messages are untrusted input: a broken part or an
unknown character set gives less text, never an error.
"""

import email
import os
import warnings
from dataclasses import dataclass
from datetime import datetime
from email.message import Message

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from ..ingest.archives import DOCUMENT_EXTENSIONS, decode_header_text, sender_domain, sent_at

# The attachments the intake keeps as documents of their own (app.intake): documents, zips and attached messages.
_DOCUMENTS = frozenset({*DOCUMENT_EXTENSIONS, ".zip", ".eml"})

# Characters that take no room yet split a word for a pattern: zero-width spaces and joiners, the byte-order mark and
# the soft hyphen, which some e-mail templates put inside words.
_INVISIBLE = str.maketrans(dict.fromkeys("\u200b\u200c\u200d\u2060\ufeff\xad"))


@dataclass(frozen=True, slots=True)
class Mail:
    sender: str  # the domain of the From address, lower case
    subject: str
    sent: datetime | None  # the Date header, in the sender's time zone
    text: str  # the body's visible text, its whitespace collapsed: the HTML part's when there is one
    attached: bool  # the message carries documents of its own (a PDF, a sheet, a zip), kept and read on their own


def read_mail(data: bytes) -> Mail:
    msg = email.message_from_bytes(data)
    return Mail(
        sender=sender_domain(msg),
        subject=collapse(decode_header_text(msg["Subject"])),
        sent=sent_at(msg),
        text=_body(msg),
        attached=_carries_documents(msg),
    )


def _carries_documents(msg: Message) -> bool:
    """Whether an attachment is one the intake keeps as a document of its own: a logo or a signature image is not,
    nor a file whose contents Gmail's "Show original" left out (ADR-0016)."""
    for part in msg.walk():
        name = part.get_filename()
        if not name or part.is_multipart() or os.path.splitext(decode_header_text(name))[1].lower() not in _DOCUMENTS:
            continue
        if part.get_payload(decode=True):
            return True
    return False


def collapse(text: str) -> str:
    """text without its invisible characters and with every run of whitespace one space: the text a row's span
    (SourceRef.span) counts in."""
    return " ".join(text.translate(_INVISIBLE).split())


def _body(msg: Message) -> str:
    """The visible text of the body: its first HTML part, else its first plain one. A part that names a file is an
    attachment, not the body. Styles and scripts are no text (BeautifulSoup leaves them out)."""
    parts = [p for p in msg.walk() if not p.is_multipart() and not p.get_filename()]
    for kind in ("text/html", "text/plain"):
        part = next((p for p in parts if p.get_content_type() == kind), None)
        if part is not None:
            return collapse(_visible(_decoded(part)) if kind == "text/html" else _decoded(part))
    return ""


def _visible(html: str) -> str:
    with warnings.catch_warnings():
        # Many templates are XHTML with an XML declaration; the HTML parser reads them well, but says so.
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        return BeautifulSoup(html, "html.parser").get_text(" ")


def _decoded(part: Message) -> str:
    data = part.get_payload(decode=True)
    if not isinstance(data, bytes):
        return ""
    try:
        return data.decode(part.get_content_charset() or "utf-8", errors="replace")
    except LookupError:  # a character set Python does not know, which an untrusted message may name
        return data.decode("utf-8", errors="replace")
