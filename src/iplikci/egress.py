"""The only way out (ADR-0009). Every connection the program opens to another computer is made here, to a host on
the allowlist: the mail servers the user set up, the Telegram Bot API, and the services the ADR names as their
features arrive (the exchange rates, EVDS). A connection anywhere else is refused before it leaves. 127.0.0.1 is no
egress: the command line and the browser extension talk to the service there."""

import http.client
import imaplib
import smtplib
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping

from .settings.config import Settings

TELEGRAM = "api.telegram.org"  # the notifications' Telegram channel (ADR-0010)
# ADR-0009's fixed hosts; the exchange rates and EVDS join with their features.
FIXED_HOSTS: frozenset[str] = frozenset({TELEGRAM})
_ANSWER_LIMIT = 1 << 20  # an answer larger than this is cut: the services asked answer in a few kilobytes


class Refused(Exception):
    """A connection to a host the allowlist does not name."""


class Unreachable(Exception):
    """The host could not be reached or did not answer. The message names the host only: a path may hold a secret
    (the Telegram bot's token)."""


def allowed_hosts(settings: Settings) -> frozenset[str]:
    return FIXED_HOSTS | {settings.mail.imap_host.lower(), settings.mail.smtp_host.lower()}


def check(host: str, settings: Settings) -> None:
    if host.lower() not in allowed_hosts(settings):
        raise Refused(f"{host} izin listesinde değil; yeni bir dış bağlantı yeni bir karar (ADR) ister")


def imap(host: str, port: int, settings: Settings, timeout: float = 60.0) -> imaplib.IMAP4:
    """A TLS connection to the mail server; its certificate and host name are checked."""
    check(host, settings)
    return imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=timeout)


def smtp(host: str, port: int, settings: Settings, timeout: float = 30.0) -> smtplib.SMTP:
    """A TLS connection to the mail server that sends: the notifications to the user's own address (ADR-0010)."""
    check(host, settings)
    return smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=timeout)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would lead past the allowlist: it is answered as it came, never followed."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def https_post(
    host: str, path: str, form: Mapping[str, str], settings: Settings, timeout: float = 30.0
) -> tuple[int, bytes]:
    """A form POSTed over HTTPS to an allowed host (certificate and host name checked, no redirect followed); the
    answer's status and body, an error status too. Unreachable when no answer came."""
    check(host, settings)
    request = urllib.request.Request(f"https://{host}{path}", data=urllib.parse.urlencode(form).encode(), method="POST")
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context()), _NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as answer:
            return int(answer.status), answer.read(_ANSWER_LIMIT)
    except urllib.error.HTTPError as exc:
        with exc:
            return int(exc.code), exc.read(_ANSWER_LIMIT)
    except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
        raise Unreachable(f"{host} adresine ulaşılamadı ({type(exc).__name__})") from None
