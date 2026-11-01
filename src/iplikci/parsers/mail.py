"""A kept e-mail as the readers of message bodies see it (Phase 4): who sent it, its subject and date, the visible
text of its body and whom its greeting names.

A message is kept whole (ADR-0015) and its attachments are documents of their own, read by the readers of their
formats; the body is what a reader of a bank's notices reads. Messages are untrusted input: a broken part or an
unknown character set gives less text, never an error.
"""

import email
import os
import re
import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from email.message import Message
from itertools import takewhile

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from ..ingest.archives import DOCUMENT_EXTENSIONS, decode_header_text, sender_domain, sent_at

# The attachments the intake keeps as documents of their own (app.intake): documents, zips and attached messages.
_DOCUMENTS = frozenset({*DOCUMENT_EXTENSIONS, ".zip", ".eml"})
_GREETING_WITHIN = 400  # characters of the body's text a greeting is looked for in

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
    addressee: str = ""  # whom the body's greeting names ("Sayın ÖRNEK KULLANICI,"); "" when it names nobody


def read_mail(data: bytes) -> Mail:
    msg = email.message_from_bytes(data)
    text, lines = _body(msg)
    return Mail(
        sender=sender_domain(msg),
        subject=collapse(decode_header_text(msg["Subject"])),
        sent=sent_at(msg),
        text=text,
        attached=_carries_documents(msg),
        addressee=_addressee(lines),
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


# A greeting at the start of a line of the body, and what follows it: "Sayın ÖRNEK KULLANICI,", "Merhaba ÖRNEK A.Ş.,".
_GREETING = re.compile(r"(?:Sayın|SAYIN|Merhaba|MERHABA|Değerli|DEĞERLİ)\s+(.*)")
_CONNECTORS = frozenset({"ve", "&", "-"})  # the small words inside a company's name ("San. ve Tic. Ltd. Şti.")


def _addressee(lines: Iterable[str]) -> str:
    """Whom a message is for, as a greeting at the start of one of the body's first lines names them: the words after
    it up to the comma or the end of the line, as far as they look like a name (each starts with a capital letter or
    is masked). A greeting run into a sentence ("Sayın Müşterimiz hesabınıza ÖRNEK A.Ş. …") ends at its first
    lowercase word, so a company the sentence names as the other side of a transfer is never taken for whom the
    message is for."""
    seen = 0
    for line in map(collapse, lines):
        if found := _GREETING.match(line):
            words = list(takewhile(_in_name, found[1].split(",", 1)[0].split()))
            return " ".join(words)
        seen += len(line)
        if seen > _GREETING_WITHIN:
            break
    return ""


def _in_name(word: str) -> bool:
    # A company's name may start with a digit ("3M"), a date or an amount never holds a capital letter.
    return (
        word[0].isupper()
        or word[0] == "*"
        or word in _CONNECTORS
        or (word[0].isdigit() and word.upper() != word.lower())
    )


def collapse(text: str) -> str:
    """text without its invisible characters and with every run of whitespace one space: the text a row's span
    (SourceRef.span) counts in."""
    return " ".join(text.translate(_INVISIBLE).split())


def _body(msg: Message) -> tuple[str, list[str]]:
    """The visible text of the body, and its lines as a browser breaks them: its first HTML part, else its first plain
    one. A part that names a file is an attachment, not the body. Styles and scripts are no text (BeautifulSoup leaves
    them out)."""
    parts = [p for p in msg.walk() if not p.is_multipart() and not p.get_filename()]
    html = next((p for p in parts if p.get_content_type() == "text/html"), None)
    if html is not None:
        soup = _soup(_decoded(html))
        return collapse(soup.get_text(" ")), _lines(soup)
    plain = next((p for p in parts if p.get_content_type() == "text/plain"), None)
    text = _decoded(plain) if plain is not None else ""
    return collapse(text), text.splitlines()


def _soup(html: str) -> BeautifulSoup:
    with warnings.catch_warnings():
        # Many templates are XHTML with an XML declaration; the HTML parser reads them well, but says so.
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        return BeautifulSoup(html, "html.parser")


# The elements a browser starts a line at; inline ones (b, span, a) run on in the line they are in.
_BLOCKS = ["p", "div", "td", "th", "tr", "li", "table", "center", "blockquote", "br", *(f"h{n}" for n in range(1, 7))]


def _lines(soup: BeautifulSoup) -> list[str]:
    """The text of soup line by line, broken where a browser breaks it. Changes soup: take its text first."""
    for tag in soup.find_all(_BLOCKS):
        tag.insert_before("\n")
        tag.insert_after("\n")
    return soup.get_text().split("\n")


def _decoded(part: Message) -> str:
    data = part.get_payload(decode=True)
    if not isinstance(data, bytes):
        return ""
    try:
        return data.decode(part.get_content_charset() or "utf-8", errors="replace")
    except LookupError:  # a character set Python does not know, which an untrusted message may name
        return data.decode("utf-8", errors="replace")
