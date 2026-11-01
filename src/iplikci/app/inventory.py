"""The mailbox's inventory (Phase 4): which senders the kept e-mails come from and what kinds of message they are, so
the readers of e-mail bodies are written in the order the mailbox needs them. A kind is a sender's domain with a
subject template: the subject with what changes from message to message (numbers, month names) masked.

The messages are the user's data: the inventory is only shown, or written inside the data folder."""

import csv
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from ..domain.codes import DocumentStatus
from ..domain.text import fold
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


def write_csv(kinds: Iterable[MailKind], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["Gönderen", "Konu kalıbı", "İleti", "İlk", "Son", "Ekli", "Ne oldu"])
        for k in kinds:
            states = "; ".join(f"{state} ({n})" for state, n in k.states.most_common())
            writer.writerow([k.domain, k.template, k.count, k.first_day, k.last_day, k.with_files, states])
