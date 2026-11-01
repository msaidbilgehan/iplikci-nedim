"""The trust rule (ADR-0015): a message counts only when its sender's domain is on one of the sender lists (a
subdomain counts) and the topmost Authentication-Results, the one the receiving server added (on Gmail from
mx.google.com), shows DMARC pass for that domain. Each server adds its own header on top and drops copies forged
with its name, so headers further down prove nothing.

The header is read as RFC 8601 writes it: its result clauses are separated by semicolons, and comments and quoted
strings may hold anything a sender typed, such as an envelope address that reads "dmarc=pass header.from=bank".
So the comments go, a semicolon inside quotes splits nothing, and only the clause that begins with dmarc= counts."""

import re
from email.message import Message

from ..archives import sent_at

MAX_MESSAGE_BYTES = 40 << 20
GMAIL_SERVER = "mx.google.com"
_DMARC_PASS = re.compile(r"dmarc\s*=\s*pass\b", re.IGNORECASE)
_HEADER_FROM = re.compile(r'(?:^|\s)header\.from\s*=\s*"?([a-z0-9.-]+)', re.IGNORECASE)


def listed(domain: str, senders: tuple[str, ...]) -> bool:
    return bool(domain) and any(domain == s or domain.endswith(f".{s}") for s in senders)


def verified(msg: Message, domain: str, gmail: bool = True) -> bool:
    """Whether the receiving server verified the sender: DMARC passed for the From domain."""
    results = msg.get_all("Authentication-Results") or []
    if not results:
        return False
    server, *clauses = _clauses(" ".join(str(results[0]).split()))
    if gmail and server.lower() != GMAIL_SERVER:
        return False
    for clause in clauses:
        if _DMARC_PASS.match(clause) and (found := _HEADER_FROM.search(clause)) and found[1].lower() == domain:
            return True
    return False


def _clauses(header: str) -> list[str]:
    """The header's parts between semicolons, its comments taken out (nested ones too); inside a quoted string a
    semicolon or a parenthesis is only text. The first part names the server that added the header."""
    clauses: list[str] = []
    part: list[str] = []
    depth, quoted, escaped = 0, False, False
    for char in header:
        if escaped:  # the character after a backslash, in a comment or a quoted string
            escaped = False
            if not depth:
                part.append(char)
        elif char == "\\" and (depth or quoted):
            escaped = True
            if not depth:
                part.append(char)
        elif depth:
            depth += {"(": 1, ")": -1}.get(char, 0)
        elif quoted:
            part.append(char)
            quoted = char != '"'
        elif char == "(":
            depth = 1
        elif char == ";":
            clauses.append("".join(part).strip())
            part = []
        else:
            part.append(char)
            quoted = char == '"'
    clauses.append("".join(part).strip())
    return clauses


def message_name(msg: Message, domain: str) -> str:
    """The name a kept message gets: its date and its sender's domain."""
    sent = sent_at(msg)
    return f"E-posta {sent:%Y-%m-%d} {domain}.eml" if sent else f"E-posta {domain}.eml"
