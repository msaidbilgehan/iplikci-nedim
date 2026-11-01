"""The non-bank senders (F14): the domains whose bills, receipts and order mails are taken in beside the banks'.

A message from them counts as a bank's does (ingest.mail.trust): its sender's domain is on the list and the receiving
server's DMARC check passed for it. The list lives in settings.toml (mail.other_senders). When it changes, both
connectors read the history again for it: the IMAP connector's scan key and the browser extension's history key name
the senders. A bank's domain belongs to mail.bank_senders, never here. Nothing of the list is logged; the audit log
keeps only how many domains it has.
"""

from collections.abc import Sequence

from ..domain.codes import Actor
from ..ingest.mail.trust import listed
from ..settings import config
from ..settings.config import SettingsError
from ..storage import audit
from .workspace import Workspace

# What the API names from here: SettingsError is settings.toml itself refusing to be read or written.
__all__ = ["CHANGED", "SenderRefused", "SettingsError", "other_senders", "set_other_senders"]

CHANGED = "settings.changed"  # the audit log's action; its target names the setting, its detail only counts
_TARGET = "mail.other_senders"
_EXAMPLE = "ornekcell.example"


class SenderRefused(ValueError):
    """A domain the list does not take; the message says which and why, in Turkish."""


def other_senders(ws: Workspace) -> tuple[str, ...]:
    """The non-bank senders as settings.toml holds them now: the file may change while the service runs."""
    return config.load(ws.layout.settings).mail.other_senders


def set_other_senders(ws: Workspace, domains: Sequence[str]) -> tuple[str, ...]:
    """Make domains the non-bank senders, each checked as settings.toml checks it. A bank's domain, one under or
    above it, or a domain named twice is refused, and then nothing is written. Returns the list as saved."""
    settings = config.load(ws.layout.settings)
    # The shipped banks too: a bank the user took off the bank list is still a bank.
    banks = tuple(dict.fromkeys((*settings.mail.bank_senders, *config.BANK_SENDERS)))
    found: list[str] = []
    for item in domains:
        domain = _domain(item)
        if domain in found:
            raise SenderRefused(f"{domain} listede zaten var.")
        if listed(domain, banks):
            raise SenderRefused(f"{domain} bir bankanın alan adı; bankaların e-postaları zaten alınıyor.")
        if any(listed(bank, (domain,)) for bank in banks):
            # Above a bank's domain (com.tr): it would take in every sender under it, banks and strangers alike.
            raise SenderRefused(f"{domain} bankaların alan adlarını da kapsıyor; göndericinin kendi alan adını yazın.")
        found.append(domain)
    if tuple(found) == settings.mail.other_senders:
        return settings.mail.other_senders
    saved = config.update(ws.layout.settings, "mail", {"other_senders": found})
    with ws.db() as db:
        audit.record(db, Actor.USER, CHANGED, _TARGET, count=len(found))
    return saved.mail.other_senders


def _domain(item: str) -> str:
    """item as the list keeps it (lower case, no leading @); refused when it is no domain."""
    try:
        (domain,) = config.sender_domains("Banka dışı göndericiler", [item])
    except SettingsError as exc:
        shown = " ".join(item.split())[:80]
        raise SenderRefused(
            f"“{shown}” bir alan adı değil; gönderenin adresinde @ işaretinden sonra gelen kısmı yazın "
            f"(ör. {_EXAMPLE})."
        ) from exc
    return domain
