"""The only way out (ADR-0009). Every connection the program opens to another computer is made here, to a host on
the allowlist: the mail servers the user set up, the Telegram Bot API, the exchange rate providers, TCMB's EVDS for
the consumer price index, and GitHub, where the program's own releases are (ADR-0022). A connection anywhere else is
refused before it leaves. 127.0.0.1 is no egress: the command line and the browser extension talk to the service
there."""

import hashlib
import http.client
import imaplib
import smtplib
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import BinaryIO

from .settings.config import Settings

# The user's own bot: the notifications (ADR-0010), and the documents its paired chat sends it (ADR-0021).
TELEGRAM = "api.telegram.org"
# The exchange rates (architecture §15): asked with a day only, by GET (ADR-0009, its note for Phase 8).
TCMB = "www.tcmb.gov.tr"  # the Central Bank of Turkey's daily bulletin
ECB = "www.ecb.europa.eu"  # the euro reference rates, when TCMB cannot be reached
FRANKFURTER = "api.frankfurter.dev"  # the same reference rates as JSON
# TÜFE for the spending in real terms, asked only with the user's own EVDS key (ADR-0009; evds2 redirects here).
EVDS = "evds3.tcmb.gov.tr"
# The program's releases (ADR-0022): the signed manifest and the update files, by GET only. github.com answers a
# release's file with a redirect to its file servers, and only a download follows one, to these.
GITHUB = "github.com"
GITHUB_FILES: frozenset[str] = frozenset({"release-assets.githubusercontent.com", "objects.githubusercontent.com"})
# ADR-0009's fixed hosts.
FIXED_HOSTS: frozenset[str] = frozenset({TELEGRAM, TCMB, ECB, FRANKFURTER, EVDS, GITHUB, *GITHUB_FILES})
# An answer larger than this is cut: the services asked answer in a few kilobytes, ECB's whole history in 642 KB.
# A caller that fetches a file (a document sent to the Telegram bot) names its own limit.
ANSWER_LIMIT = 1 << 20
REDIRECTS = 5  # a download follows at most this many redirects (GitHub: the latest release, then its file server)
_CHUNK = 1 << 16


class Refused(Exception):
    """A connection to a host the allowlist does not name."""


class Unreachable(Exception):
    """The host could not be reached or did not answer. The message names the host only: a path may hold a secret
    (the Telegram bot's token)."""


class TooLarge(Exception):
    """A download's answer was larger than its caller allowed; what came was not kept whole."""


@dataclass(frozen=True, slots=True)
class Downloaded:
    status: int  # the last answer's status; only a 200's body was written
    size: int  # the bytes written
    sha256: str  # their SHA-256, in hex; "" when nothing was written


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
    request = urllib.request.Request(_url(host, path), data=urllib.parse.urlencode(form).encode(), method="POST")
    return _send(host, request, timeout, ANSWER_LIMIT)


def https_get(
    host: str,
    path: str,
    settings: Settings,
    headers: Mapping[str, str] | None = None,
    timeout: float = 30.0,
    limit: int = ANSWER_LIMIT,
) -> tuple[int, bytes]:
    """A GET over HTTPS to an allowed host (certificate and host name checked, no redirect followed); the answer's
    status and body, an error status too, its body cut after limit bytes. Unreachable when no answer came."""
    check(host, settings)
    request = urllib.request.Request(_url(host, path), headers=dict(headers or {}), method="GET")
    return _send(host, request, timeout, limit)


def https_download(
    host: str,
    path: str,
    settings: Settings,
    into: BinaryIO,
    *,
    follow: frozenset[str],
    limit: int,
    timeout: float = 60.0,
) -> Downloaded:
    """A GET over HTTPS to an allowed host whose answer's body goes into `into` as it comes, with its size and
    SHA-256. A redirect is followed only to a host of `follow` that the allowlist also names, over HTTPS, at most
    REDIRECTS times; one anywhere else is Refused. An answer other than 200 writes nothing. TooLarge when the body is
    longer than limit; Unreachable when no answer came or it broke off. An OSError of `into` is the caller's."""
    check(host, settings)
    url = _url(host, path)
    for _ in range(REDIRECTS + 1):
        request = urllib.request.Request(url, method="GET")
        try:
            answer = _opener().open(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            with exc:
                if exc.code not in (301, 302, 303, 307, 308):
                    return Downloaded(int(exc.code), 0, "")
                url, host = _redirect(host, exc.headers.get("Location", ""), follow, settings)
            continue
        except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
            raise Unreachable(f"{host} adresine ulaşılamadı ({type(exc).__name__})") from None
        with answer:
            return _stream(host, answer, into, limit)
    raise Unreachable(f"{host} adresine ulaşılamadı (yönlendirme çok uzun)")


def _redirect(host: str, location: str, follow: frozenset[str], settings: Settings) -> tuple[str, str]:
    """Where a redirect from host leads, and its host: an https address of a followed, allowed host without a user
    name or another port, or a path on the same host. Refused otherwise."""
    if location.startswith("/") and not location.startswith("//"):
        location = f"https://{host}{location}"
    parts = urllib.parse.urlsplit(location)
    target = (parts.hostname or "").lower()
    if parts.scheme != "https" or parts.username is not None or parts.port not in (None, 443):
        raise Refused(f"{host} yönlendirmesi izlenmedi: güvenli olmayan ya da beklenmeyen bir adres")
    if target not in follow and target != host:
        raise Refused(f"{target or '?'} izin listesinde değil; yönlendirme izlenmedi")
    check(target, settings)
    return urllib.parse.urlunsplit(("https", target, parts.path or "/", parts.query, "")), target


def _stream(host: str, answer: http.client.HTTPResponse, into: BinaryIO, limit: int) -> Downloaded:
    digest = hashlib.sha256()
    size = 0
    while True:
        try:
            chunk = answer.read(_CHUNK)
        except (OSError, http.client.HTTPException) as exc:
            raise Unreachable(f"{host} adresinden gelen yanıt yarıda kesildi ({type(exc).__name__})") from None
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise TooLarge(f"{host} adresinden gelen yanıt {limit} baytı aşıyor")
        digest.update(chunk)
        into.write(chunk)
    return Downloaded(int(answer.status), size, digest.hexdigest())


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context()), _NoRedirect)


def _url(host: str, path: str) -> str:
    """The address of path on host. A path must begin with a slash: "@other.example/" after the host would make the
    host a user name and send the request to the other one."""
    if not path.startswith("/"):
        raise ValueError(f"yol / ile başlamalı: {path[:40]!r}")
    return f"https://{host}{path}"


def _send(host: str, request: urllib.request.Request, timeout: float, limit: int) -> tuple[int, bytes]:
    try:
        with _opener().open(request, timeout=timeout) as answer:
            return int(answer.status), answer.read(limit)
    except urllib.error.HTTPError as exc:
        with exc:
            return int(exc.code), exc.read(ANSWER_LIMIT)
    except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
        raise Unreachable(f"{host} adresine ulaşılamadı ({type(exc).__name__})") from None
