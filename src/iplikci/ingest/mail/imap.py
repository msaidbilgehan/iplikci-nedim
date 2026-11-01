"""The IMAP connector (ADR-0015). The mailbox opens read-only (EXAMINE) and messages come with BODY.PEEK[], so nothing
there is flagged, moved or deleted. On Gmail the folder read is All Mail, found by its \\All flag whatever the
account's language; elsewhere INBOX, unless the settings name a folder. The search asks for the listed senders'
messages since the start day, after the last UID read; the trust rule checks every sender again, as servers match
loosely. IDLE tells about new mail at once; Python 3.13's imaplib has no idle(), so the exchange is written here.

A refused login is never tried again by the program: repeated failed logins can lock a Google account. The user
enters the password again in the e-mail setup.
"""

import base64
import imaplib
import itertools
import json
import re
import select
import socket
import ssl
import threading
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import date
from typing import cast

GMAIL = "imap.gmail.com"
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")  # IMAP dates
_LIST = re.compile(rb'\((?P<flags>[^)]*)\)\s+(?:"(?:[^"\\]|\\.)*"|NIL)\s+(?P<name>.+)', re.IGNORECASE)
_IDLE_TAG = b"IPLKIDLE"

type Connect = Callable[[str, int], imaplib.IMAP4]


class MailError(Exception):
    """The mailbox could not be read; the message says why and what to do (Turkish)."""


class LoginRefused(MailError):
    """The server refused the address or the password: never tried again by the program."""


@dataclass(frozen=True)
class Account:
    address: str
    start: date  # messages received on or after this day
    server: str = GMAIL
    port: int = 993
    senders: tuple[str, ...] = ()
    folder: str | None = None  # None: Gmail's All Mail, INBOX elsewhere
    verify: bool = True  # only messages whose sender the receiving server verified (DMARC)

    @property
    def is_gmail(self) -> bool:
        return self.server.lower() in (GMAIL, "imap.googlemail.com")

    def scan_key(self) -> str:
        """Changes when what is searched changes: the mailbox is then read again from the start. New readers do not
        change it (ADR-0005): the archive keeps every message, and that is what they read again."""
        return json.dumps(
            [self.server.lower(), self.address.lower(), self.folder, sorted(self.senders), str(self.start)]
        )


@dataclass
class Box:
    imap: imaplib.IMAP4
    name: str  # as sent to SELECT: quoted, in modified UTF-7
    uidvalidity: int
    gmail: bool  # Gmail's extensions are there

    @property
    def shown(self) -> str:
        return utf7_decode(_unquote(self.name))


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _unquote(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return re.sub(r"\\(.)", r"\1", text[1:-1])
    return text


def utf7_encode(name: str) -> str:
    """A folder name in IMAP's modified UTF-7 (RFC 3501 5.1.3): "Tüm Postalar" -> "T&APw-m Postalar"."""
    out: list[str] = []
    run: list[str] = []

    def flush() -> None:
        if run:
            coded = base64.b64encode("".join(run).encode("utf-16-be")).decode("ascii").rstrip("=")
            out.append("&" + coded.replace("/", ",") + "-")
            run.clear()

    for ch in name:
        if 0x20 <= ord(ch) <= 0x7E:
            flush()
            out.append("&-" if ch == "&" else ch)
        else:
            run.append(ch)
    flush()
    return "".join(out)


def utf7_decode(name: str) -> str:
    def part(match: re.Match[str]) -> str:
        coded = match[1].replace(",", "/")
        return base64.b64decode(coded + "=" * (-len(coded) % 4)).decode("utf-16-be") if coded else "&"

    try:
        return re.sub(r"&([A-Za-z0-9+,]*)-", part, name)
    except (ValueError, UnicodeDecodeError):  # not valid modified UTF-7: shown as the server sent it
        return name


def _text(data: object) -> str:
    """A server's answer for a message: imaplib gives a list of bytes, tuples or None."""
    items = cast(list[object], data) if isinstance(data, list) else [data]
    parts = [d.decode(errors="replace") if isinstance(d, bytes) else str(d) for d in items if d]
    return " ".join(parts)[:300]


def _all_mail(imap: imaplib.IMAP4) -> str | None:
    """Gmail's All Mail as the server names it (the name follows the account's language), found by its \\All flag
    (RFC 6154): every label and the archive, without Spam and Trash."""
    typ, data = imap.list()
    if typ != "OK":
        return None
    for item in data or []:
        line = item
        if isinstance(item, tuple):  # a name sent as a literal
            head, literal = item[0], item[1]
            line = head.rsplit(b"{", 1)[0] + _quote(literal.decode("utf-8", errors="replace")).encode()
        match = _LIST.match(line if isinstance(line, bytes) else b"")
        if match and b"\\all" in match["flags"].lower().split():
            return match["name"].decode("utf-8", errors="replace").strip()
    return None


def clean_password(account: Account, secret: str) -> str:
    if re.search(r"[\x00-\x1f\x7f]", secret):
        raise MailError("şifrede satır sonu ya da denetim karakteri olamaz")
    if account.is_gmail:
        secret = secret.replace(" ", "")  # Google shows app passwords in groups of four
    if not secret:
        raise MailError("şifre boş")
    return secret


def _refused(account: Account, exc: Exception) -> str:
    text = str(exc)
    if account.is_gmail and re.search(
        r"AUTHENTICATIONFAILED|Invalid credentials|Application-specific password", text, re.IGNORECASE
    ):
        return (
            "Gmail girişi reddetti: adres ya da uygulama şifresi yanlış. Normal Gmail şifresi çalışmaz; Google "
            "hesabınızın uygulama şifreleri sayfasında bir uygulama şifresi oluşturup e-posta kurulumunda yeniden "
            "girin. Gelişmiş Koruma'daki hesaplarda uygulama şifresi yoktur; onlar için tarayıcı eklentisi var."
        )
    return f"{account.server} girişi reddetti: {text}"


def network_trouble(exc: BaseException) -> str:
    """What went wrong on the way to the server, in the user's words."""
    if isinstance(exc, socket.gaierror):
        return "sunucu adı bulunamadı; internet bağlantısı yok ya da sunucu adı yanlış"
    if isinstance(exc, ssl.SSLCertVerificationError):
        return f"sunucunun sertifikası doğrulanamadı ({exc.verify_message}); bağlantı güvenli değil, kesildi"
    if isinstance(exc, TimeoutError):
        return "sunucu zamanında yanıt vermedi; internet bağlantısını denetleyin"
    if isinstance(exc, ConnectionRefusedError):
        return "sunucu bağlantıyı reddetti; sunucu adı ya da port yanlış olabilir"
    return f"{exc} ({type(exc).__name__}); internet bağlantısını denetleyin"


@contextmanager
def session(account: Account, password: str, connect: Connect) -> Generator[Box]:
    """Logged in, with the folder open read-only (EXAMINE): nothing there can change."""
    try:
        imap = connect(account.server, account.port)
    except (OSError, ssl.SSLError, imaplib.IMAP4.error) as exc:
        raise MailError(f"{account.server} sunucusuna bağlanılamadı: {network_trouble(exc)}") from exc
    try:
        try:
            imap.login(account.address, password)
        except imaplib.IMAP4.error as exc:
            raise LoginRefused(_refused(account, exc)) from exc
        except UnicodeEncodeError as exc:  # imaplib sends LOGIN in ASCII
            raise MailError("adres ve şifre yalnızca ASCII karakterler içerebilir") from exc
        gmail = "X-GM-EXT-1" in imap.capabilities
        if account.folder:
            name = _quote(utf7_encode(account.folder))
        else:
            name = (_all_mail(imap) if gmail else None) or "INBOX"
        typ, data = imap.select(name, readonly=True)
        if typ != "OK":
            raise MailError(f"'{utf7_decode(_unquote(name))}' klasörü açılamadı: {_text(data)}")
        validity = imap.response("UIDVALIDITY")[1]
        first = validity[0] if validity else None
        text = first.decode(errors="replace") if isinstance(first, bytes) else str(first or "")
        yield Box(imap, name, int(text) if text.isdigit() else 0, gmail)
    except imaplib.IMAP4.error as exc:  # abort too: the connection broke off
        raise MailError(f"{account.server} ile bağlantı kesildi ya da komut reddedildi: {exc}") from exc
    except (OSError, ssl.SSLError) as exc:
        raise MailError(f"{account.server} ile bağlantı kesildi: {network_trouble(exc)}") from exc
    finally:
        with suppress(imaplib.IMAP4.error, OSError):
            imap.logout()


def _any_from(senders: tuple[str, ...]) -> str:
    """IMAP's OR takes two keys: OR FROM "a" OR FROM "b" FROM "c"."""
    key = f"FROM {_quote(senders[-1])}"
    for sender in reversed(senders[:-1]):
        key = f"OR FROM {_quote(sender)} {key}"
    return key


def search_criteria(account: Account, after_uid: int) -> list[str]:
    since = account.start
    return [
        f"UID {after_uid + 1}:*",
        f"SINCE {since.day}-{_MONTHS[since.month - 1]}-{since.year}",
        _any_from(account.senders),
    ]


def new_uids(box: Box, account: Account, after: int) -> list[int]:
    typ, data = box.imap.uid("SEARCH", *search_criteria(account, after))
    if typ != "OK":
        raise MailError(f"e-postalar aranamadı: {_text(data)}")
    found = {int(x) for line in data or [] if isinstance(line, bytes) for x in line.split() if x.isdigit()}
    return sorted(u for u in found if u > after)  # "n:*" always holds the newest message


def sizes(imap: imaplib.IMAP4, uids: list[int]) -> dict[int, int]:
    found: dict[int, int] = {}
    for chunk in itertools.batched(uids, 200):
        typ, data = imap.uid("FETCH", ",".join(map(str, chunk)), "(RFC822.SIZE)")
        if typ != "OK":
            raise MailError(f"e-posta boyutları alınamadı: {_text(data)}")
        for line in cast(list[object], data or []):
            first = cast(tuple[object, ...], line)[0] if isinstance(line, tuple) else line
            head = first if isinstance(first, bytes) else b""
            uid, size = re.search(rb"\bUID (\d+)", head), re.search(rb"RFC822\.SIZE (\d+)", head)
            if uid and size:
                found[int(uid[1])] = int(size[1])
    return found


def body(imap: imaplib.IMAP4, uid: int) -> bytes | None:
    # BODY.PEEK: reading does not mark the message as read (and the folder is open read-only anyway).
    typ, data = imap.uid("FETCH", str(uid), "(BODY.PEEK[])")
    if typ != "OK":
        raise MailError(f"e-posta indirilemedi: {_text(data)}")
    for part in cast(list[object], data or []):
        if isinstance(part, tuple):
            head, blob = cast(tuple[object, object], part)[:2]
            if isinstance(head, bytes) and b"BODY[]" in head and isinstance(blob, bytes):
                return blob
    return None


def wait_for_news(imap: imaplib.IMAP4, seconds: float, stop: threading.Event) -> bool:
    """Wait in IDLE (RFC 2177) up to seconds, or until stop is set; whether the server announced a change."""
    imap.send(_IDLE_TAG + b" IDLE\r\n")
    answer = imap.readline()
    if not answer.startswith(b"+"):
        raise MailError(f"sunucu IDLE'ı kabul etmedi: {answer[:80]!r}")
    news = False
    waited = 0.0
    sock = imap.socket()
    while waited < seconds and not stop.is_set() and not news:
        pending = isinstance(sock, ssl.SSLSocket) and sock.pending() > 0
        if pending or select.select([sock], [], [], 1.0)[0]:
            line = imap.readline()
            if not line:
                raise MailError("sunucu bağlantıyı kapattı")
            news = b"EXISTS" in line or b"RECENT" in line
        waited += 1.0
    imap.send(b"DONE\r\n")
    while True:  # the rest up to the answer to our IDLE
        line = imap.readline()
        if not line:
            raise MailError("sunucu bağlantıyı kapattı")
        if line.startswith(_IDLE_TAG):
            return news
        news = news or b"EXISTS" in line
