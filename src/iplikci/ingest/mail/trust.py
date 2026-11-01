"""The trust rule (ADR-0015): a message counts only when its sender's domain is on one of the sender lists (a
subdomain counts) and the topmost Authentication-Results, the one the receiving server added (on Gmail from
mx.google.com), shows DMARC pass for that domain: for the domain itself, or for the listed domain whose policy covers
it. Each server adds its own header on top and drops copies forged with its name, so headers further down prove
nothing.

The header is read as RFC 8601 writes it: its result clauses are separated by semicolons, and comments and quoted
strings may hold anything a sender typed, such as an envelope address that reads "dmarc=pass header.from=bank".
So the comments go, a semicolon inside quotes splits nothing, and only the clause that begins with dmarc= counts."""

import re
from email.message import Message

from ..archives import sent_at

MAX_MESSAGE_BYTES = 40 << 20
GMAIL_SERVER = "mx.google.com"
# Raised when the rule changes: the messages it refused before are asked for again. 2: a subdomain passing DMARC under
# its organizational domain's policy counts.
RULE_VERSION = 2
_DMARC = re.compile(r"dmarc\s*=\s*(\w+)", re.IGNORECASE)
_HEADER_FROM = re.compile(r'(?:^|\s)header\.from\s*=\s*"?([a-z0-9.-]+)', re.IGNORECASE)
_NAME = re.compile(r"[^a-z0-9.-]")


def listed(domain: str, senders: tuple[str, ...]) -> bool:
    return bool(domain) and any(domain == s or domain.endswith(f".{s}") for s in senders)


def verified(msg: Message, domain: str, senders: tuple[str, ...], gmail: bool = True) -> bool:
    """Whether the receiving server verified the sender: DMARC passed for the From domain."""
    return not trust_problem(msg, domain, senders, gmail)


def trust_problem(msg: Message, domain: str, senders: tuple[str, ...], gmail: bool = True) -> str:
    """Why the receiving server did not verify the sender; "" when DMARC passed for the From domain. The reason says
    what the topmost Authentication-Results showed, never an address: no-results, server:<name>, no-dmarc,
    dmarc:<result> (fail, none, temperror, …) or header-from:<domain> (DMARC passed for another domain)."""
    results = msg.get_all("Authentication-Results") or []
    if not results:
        return "no-results"
    server, *clauses = _clauses(" ".join(str(results[0]).split()))
    if gmail and server.lower() != GMAIL_SERVER:
        return f"server:{_NAME.sub('', server.lower())[:60]}"
    problem = "no-dmarc"
    for clause in clauses:
        result = _DMARC.match(clause)
        if result is None:
            continue
        if result[1].lower() != "pass":
            problem = f"dmarc:{result[1].lower()[:20]}"
            continue
        found = _HEADER_FROM.search(clause)
        checked = found[1].lower() if found else ""
        if checked and _covers(checked, domain, senders):
            return ""
        problem = f"header-from:{checked[:60]}"
    return problem


def _covers(checked: str, domain: str, senders: tuple[str, ...]) -> bool:
    """Whether DMARC passing for the domain the header names is DMARC passing for the From domain: the same domain, or
    a listed one above it. A subdomain without a DMARC record of its own falls under its organizational domain's
    policy (RFC 7489 §6.6.3), and Gmail then names that domain: mail from bilgi.bank.example passes as bank.example.
    The named domain must itself be listed, so a public suffix never covers a sender."""
    return checked == domain or (domain.endswith(f".{checked}") and listed(checked, senders))


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
