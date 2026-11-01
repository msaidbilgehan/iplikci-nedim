"""Taking one e-mail in, whichever connector fetched it (ADR-0015, ADR-0016).

The trust rule first (ingest.mail.trust): a message that fails it is counted and dropped, nothing of it is kept, so
a mail imitating a bank leaves no trace. Then the company check: a message whose subject marks a company, or one of
whose attachments is a company document, is not kept at all. Every other message is kept whole as .eml, and each
attachment, zip members included, as a document of its own with the message as its parent.
"""

import email
from dataclasses import dataclass
from enum import StrEnum

from ..domain.codes import Actor, SourceKind
from ..ingest.archives import message_fields, sender_domain
from ..ingest.mail.trust import MAX_MESSAGE_BYTES, listed, message_name, verified
from ..parsers.common import is_business
from ..storage import audit
from ..storage.documents import Source
from ..vault.store import sha256_of
from . import intake
from .workspace import Workspace


class Taken(StrEnum):
    """What became of one message."""

    STORED = "stored"  # kept, with its attachments
    KNOWN = "known"  # the vault had it already
    UNLISTED = "unlisted"  # its sender is on no list
    UNVERIFIED = "unverified"  # from a listed domain, but the receiving server did not verify the sender
    BUSINESS = "business"  # carries company content: not kept
    TOO_LARGE = "too_large"


@dataclass(frozen=True)
class MailOutcome:
    taken: Taken
    domain: str = ""
    sha256: str = ""  # the message's, when it was kept or known
    documents: int = 0  # new documents kept: the message and its attachments


def take(
    ws: Workspace, raw: bytes, senders: tuple[str, ...], *, verify: bool = True, gmail: bool = True
) -> MailOutcome:
    """Take one raw message (RFC 822) in: the trust rule, the company check, then the vault."""
    if len(raw) > MAX_MESSAGE_BYTES:
        return MailOutcome(Taken.TOO_LARGE)
    msg = email.message_from_bytes(raw)
    domain = sender_domain(msg)
    if not listed(domain, senders):
        return MailOutcome(Taken.UNLISTED, domain)
    if verify and not verified(msg, domain, gmail):
        return MailOutcome(Taken.UNVERIFIED, domain)
    fields = message_fields(msg)
    sha = sha256_of(raw)
    if is_business(fields["subject"]):
        with ws.db() as db:
            audit.record(db, Actor.SYSTEM, "document.business", sha, stage="mail")
        return MailOutcome(Taken.BUSINESS, domain)
    name = message_name(msg, domain)
    source = Source(SourceKind.EMAIL, name, name.removesuffix(".eml"), **fields)
    plan = intake.plan_documents(ws, [intake.Incoming(name, raw, source)])
    if any(c.verdict is intake.Verdict.BUSINESS for c in plan.items):
        for c in plan.items:  # a company document inside: the message is the company's too
            if c.verdict is intake.Verdict.STORE:
                c.verdict = intake.Verdict.BUSINESS
    applied = intake.apply(ws, plan, Actor.SYSTEM)
    message = plan.items[0]
    taken = {intake.Verdict.STORE: Taken.STORED, intake.Verdict.KNOWN: Taken.KNOWN}.get(message.verdict, Taken.BUSINESS)
    return MailOutcome(taken, domain, "" if taken is Taken.BUSINESS else sha, len(applied.stored))
