"""The only way out (ADR-0009). Every connection the program opens to another computer is made here, to a host on
the allowlist: the mail server the user set up, and the services the ADR names as their features arrive (Telegram,
the exchange rates, EVDS). A connection anywhere else is refused before it leaves. 127.0.0.1 is no egress: the
command line and the browser extension talk to the service there."""

import imaplib
import ssl

from .settings.config import Settings

# ADR-0009's fixed hosts join with the features that use them (exchange rates in Phase 4, Telegram in Phase 5).
FIXED_HOSTS: frozenset[str] = frozenset()


class Refused(Exception):
    """A connection to a host the allowlist does not name."""


def allowed_hosts(settings: Settings) -> frozenset[str]:
    return FIXED_HOSTS | {settings.mail.imap_host.lower()}


def check(host: str, settings: Settings) -> None:
    if host.lower() not in allowed_hosts(settings):
        raise Refused(f"{host} izin listesinde değil; yeni bir dış bağlantı yeni bir karar (ADR) ister")


def imap(host: str, port: int, settings: Settings, timeout: float = 60.0) -> imaplib.IMAP4:
    """A TLS connection to the mail server; its certificate and host name are checked."""
    check(host, settings)
    return imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=timeout)
