"""The trust rule (ADR-0015): a message counts only when its sender's domain is on one of the sender lists (a
subdomain counts) and the topmost Authentication-Results, the one the receiving server added (on Gmail from
mx.google.com), shows DMARC pass for that domain. Each server adds its own header on top and drops copies forged
with its name, so headers further down prove nothing."""

import re
from email.message import Message

from ..archives import sent_at

MAX_MESSAGE_BYTES = 40 << 20
GMAIL_SERVER = "mx.google.com"
_DMARC = re.compile(r'\bdmarc\s*=\s*pass\b[^;]*?\bheader\.from\s*=\s*"?([a-z0-9.-]+)', re.IGNORECASE)


def listed(domain: str, senders: tuple[str, ...]) -> bool:
    return bool(domain) and any(domain == s or domain.endswith(f".{s}") for s in senders)


def verified(msg: Message, domain: str, gmail: bool = True) -> bool:
    """Whether the receiving server verified the sender: DMARC passed for the From domain."""
    results = msg.get_all("Authentication-Results") or []
    if not results:
        return False
    top = " ".join(str(results[0]).split())
    if gmail and top.split(";", 1)[0].strip().lower() != GMAIL_SERVER:
        return False
    found = _DMARC.search(top)
    return found is not None and found[1].lower() == domain


def message_name(msg: Message, domain: str) -> str:
    """The name a kept message gets: its date and its sender's domain."""
    sent = sent_at(msg)
    return f"E-posta {sent:%Y-%m-%d} {domain}.eml" if sent else f"E-posta {domain}.eml"
