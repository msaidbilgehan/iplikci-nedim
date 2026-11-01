"""The mailbox's inventory (Phase 4): which senders the kept e-mails come from and what kinds of message they are, so
the readers of e-mail bodies are written in the order the mailbox needs them. A kind is a sender's domain with a
subject template: the subject with what changes from message to message (numbers, month names) masked. The coverage
of F01 says how many bank messages were read or knowingly classified.

The messages are the user's data: the inventory is only shown, or written inside the data folder."""

import csv
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from ..domain.codes import DocumentStatus
from ..domain.text import fold
from ..ingest.mail.trust import listed
from ..parsers.common import BUSINESS_REASON
from ..parsers.messages import ATTACHED, NO_MONEY
from ..storage import documents
from ..storage.db import Database
from .bridge import INCOMPLETE_REASON
from .workspace import Workspace

_NUMBER = re.compile(r"\d+")
_MONTH = re.compile(r"OCAK|SUBAT|MART|NISAN|MAYIS|HAZIRAN|TEMMUZ|AGUSTOS|EYLUL|EKIM|KASIM|ARALIK")
# A word's name between the punctuation around it, with a suffix after an apostrophe ("Şubat'ta", "Mart:").
_NAME = re.compile(r"[\"“(\[]*(?P<name>[^\s'’.,:;!?\"”)\]]+)")


def subject_template(subject: str) -> str:
    """A subject with what changes from message to message masked: every run of digits becomes "#" and every month
    name "<ay>", its suffix kept ("1234 **** 5678 - Ocak 2026 Hesap Özeti" → "# **** # - <ay> # Hesap Özeti")."""
    return _NUMBER.sub("#", " ".join(_mask_month(word) for word in subject.split()))


def _mask_month(word: str) -> str:
    found = _NAME.match(word)
    if found is None or not _MONTH.fullmatch(fold(found["name"])):
        return word
    return word[: found.start("name")] + "<ay>" + word[found.end("name") :]


@dataclass(slots=True)
class MailKind:
    """The kept messages of one sender domain whose subjects share a template."""

    domain: str
    template: str
    count: int = 0
    first_day: str = ""
    last_day: str = ""
    with_files: int = 0  # messages that came with attachments of their own
    states: Counter[str] = field(default_factory=Counter[str])  # what became of the messages: status, and reason

    def add(self, day: str, files: bool, state: str) -> None:
        self.count += 1
        if day and (not self.first_day or day < self.first_day):
            self.first_day = day
        self.last_day = max(self.last_day, day)
        self.with_files += files
        self.states[state] += 1


def mail_inventory(ws: Workspace) -> list[MailKind]:
    """Every kind of e-mail the archive holds, by sender domain and then the most frequent first. A copy that its
    whole message replaced is not counted; a company's message is, as what became of it says."""
    with ws.db() as db:
        return _inventory(db, documents.every(db))


def _inventory(db: Database, docs: Iterable[documents.DocumentRow]) -> list[MailKind]:
    every = list(docs)
    parents = Counter(d.parent for d in every if d.parent)
    kinds: dict[tuple[str, str], MailKind] = {}
    for doc in every:
        if doc.parent or doc.ext != ".eml" or doc.reason == INCOMPLETE_REASON:
            continue
        found = documents.sources(db, doc.sha256)
        source = found[0] if found else None
        domain = source.sender.lower() if source else ""  # the intake keeps only the sender's domain
        template = subject_template(source.subject) if source else ""
        kind = kinds.setdefault((domain, template), MailKind(domain, template))
        kind.add(source.sent_at[:10] if source else "", parents[doc.sha256] > 0, _state(doc))
    return sorted(kinds.values(), key=lambda k: (k.domain, -k.count, k.template))


def _state(doc: documents.DocumentRow) -> str:
    """What became of a message, in a few words: "işlendi", or its status with the reason."""
    if doc.status is DocumentStatus.PROCESSED:
        return "işlendi"
    word = "kaldırıldı" if doc.status is DocumentStatus.REMOVED else "işlenmedi"
    return f"{word}: {doc.reason}" if doc.reason else word


@dataclass(slots=True)
class Coverage:
    """F01's measure over the kept bank messages: how many were read, read through the documents they carry, known
    to move no money, or a company's (gone to the Trash); the rest is what no reader or rule knows yet, or what could
    not be read. A copy that its whole message replaced is not counted."""

    read: int = 0  # a reader read the body: a bank's notice
    attached: int = 0  # read through its documents, none of which was left unreadable
    no_money: int = 0  # knowingly a campaign, an announcement, a security or a card notice
    business: int = 0
    unknown: int = 0
    left: Counter[tuple[str, str]] = field(default_factory=Counter[tuple[str, str]])  # unknown: domain, template

    @property
    def total(self) -> int:
        return self.read + self.attached + self.no_money + self.business + self.unknown

    @property
    def share(self) -> float:
        """The covered share of the bank messages; 1.0 when there are none."""
        return (self.total - self.unknown) / self.total if self.total else 1.0


def mail_coverage(db: Database, bank_senders: tuple[str, ...]) -> Coverage:
    """The coverage of the messages from bank_senders (settings: mail.bank_senders)."""
    every = list(documents.every(db))
    children: dict[str, list[DocumentStatus]] = {}
    for doc in every:
        if doc.parent:
            children.setdefault(doc.parent, []).append(doc.status)
    found = Coverage()
    for doc in every:
        if doc.parent or doc.ext != ".eml" or doc.reason == INCOMPLETE_REASON:
            continue
        sources = documents.sources(db, doc.sha256)
        domain = sources[0].sender.lower() if sources else ""
        if not listed(domain, bank_senders):
            continue
        if doc.status is DocumentStatus.REMOVED:
            if doc.reason == BUSINESS_REASON:  # one the user removed is no longer the mailbox's
                found.business += 1
            continue
        kids = children.get(doc.sha256, [])
        if doc.status is DocumentStatus.PROCESSED:
            found.read += 1
        elif doc.reason == ATTACHED and kids and DocumentStatus.UNREADABLE not in kids:
            found.attached += 1
        elif doc.status is DocumentStatus.UNPROCESSED and doc.reason in NO_MONEY:
            found.no_money += 1
        else:
            found.unknown += 1
            found.left[(domain, subject_template(sources[0].subject) if sources else "")] += 1
    return found


def write_csv(kinds: Iterable[MailKind], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["Gönderen", "Konu kalıbı", "İleti", "İlk", "Son", "Ekli", "Ne oldu"])
        for k in kinds:
            states = "; ".join(f"{state} ({n})" for state, n in k.states.most_common())
            writer.writerow([k.domain, k.template, k.count, k.first_day, k.last_day, k.with_files, states])
