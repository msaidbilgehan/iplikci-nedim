"""Bank documents from e-mail: the statements and receipts banks send are fetched over IMAP.

    iplikci eposta                 fetch the new bank e-mails now
    iplikci eposta --kur           set the account up (asks for the address and an app password)
    iplikci eposta --durum         what is set up and what the last fetch did
    iplikci eposta --kaldir        forget the account

The only part of the program that uses the network, by the user's choice (2026-10-31). It connects to
the IMAP server over TLS (certificate and host name checked), opens the mailbox read-only and
downloads only the e-mails of the bank domains in `[eposta] gondericiler`; nothing in the mailbox is
flagged, moved or deleted. An e-mail counts only when the receiving server verified its sender (DMARC
pass for the From domain in its Authentication-Results), so one imitating a bank is ignored. The
attachments stay in memory and go through the organizer like any import: only new bank documents
(and unreadable ones, for a manual look) are copied into the inbox.

The password is kept in the system keyring (macOS Keychain, Windows Credential Manager, the Secret
Service on Linux) or, where there is none, given in the IPLIKCI_MAIL_PASSWORD environment
variable; never in a file, an argument or a log. The address, the start date and how far the
mailbox was read are in cikti/.eposta.json.
"""

import base64
import email
import hashlib
import imaplib
import itertools
import json
import os
import re
import socket
import ssl
import tempfile
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from . import duzenle
from .parsers import PARSER_VERSION
from .sources import _expand, attachments
from .workspace import Workspace, import_documents, output_lock

SERVICE = "iplikci"  # the keyring entry: this service, the address as the user name
PASSWORD_ENV = "IPLIKCI_MAIL_PASSWORD"
STATE_NAME = ".eposta.json"
GMAIL = "imap.gmail.com"
# The domains the banks' statement e-mails came from, and the base domains. The server's search
# narrows by them, then every sender is checked here again (a subdomain counts).
DEFAULT_SENDERS = ("garantibbva.com.tr", "isbank.com.tr", "ileti.isbank.com.tr", "qnb.com.tr", "email.qnb.com.tr",
                   "qnbfinansbank.com", "email.qnbfinansbank.com", "teb.com.tr", "vakifbank.com.tr")
SETUP_HINT = "e-posta hesabı kurulmadı; bir kez terminalde çalıştırın: uv run iplikci eposta --kur"
APP_PASSWORD_HELP = """\
Gmail, programların girişi için uygulama şifresi ister (normal Gmail şifresi çalışmaz):
  1. Google hesabınızda 2 Adımlı Doğrulama açık olmalı.
  2. https://myaccount.google.com/apppasswords sayfasında "iplikci" adıyla bir uygulama
     şifresi oluşturun ve gösterilen 16 harfi aşağıya yapıştırın.
Şifre bu bilgisayarın anahtar zincirinde saklanır; ayar dosyasına ya da kayıtlara yazılmaz.
E-posta kutusu salt okunur açılır: orada hiçbir şey okundu işaretlenmez, taşınmaz, silinmez."""
MAX_MESSAGES = 300  # per fetch; the next one continues where this one stopped
MAX_MESSAGE_BYTES = 40 << 20
_MAX_FETCH_BYTES = 512 << 20  # attachments held in memory by one fetch
_LOCK_NAME = ".eposta.kilit"
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")  # IMAP dates
_DOMAIN = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+")
_ADDRESS = re.compile(r"[^@\s\"\\]+@[a-z0-9.-]+\.[a-z]{2,}", re.IGNORECASE)
_LIST = re.compile(rb'\((?P<flags>[^)]*)\)\s+(?:"(?:[^"\\]|\\.)*"|NIL)\s+(?P<name>.+)', re.IGNORECASE)
_DMARC = re.compile(r'\bdmarc\s*=\s*pass\b[^;]*?\bheader\.from\s*=\s*"?([a-z0-9.-]+)', re.IGNORECASE)


class MailError(Exception):
    """The mailbox could not be read; the message says why and what to do (Turkish)."""


class NotConfigured(MailError):
    pass


@dataclass(frozen=True)
class Account:
    address: str
    start: date  # e-mails received on or after this day
    server: str = GMAIL
    port: int = 993
    senders: tuple[str, ...] = DEFAULT_SENDERS
    folder: str | None = None  # None: Gmail's All Mail (found by its \All flag), INBOX elsewhere
    verify: bool = True  # only e-mails whose sender the receiving server verified (DMARC)

    @property
    def is_gmail(self) -> bool:
        return self.server.lower() in (GMAIL, "imap.googlemail.com")

    def scan_key(self) -> list:
        """Changes when what is searched changes: the mailbox is then read again from the start. So do
        the readers: attachments an older reader could not use get another chance once."""
        return [self.server, self.address.lower(), self.folder, sorted(self.senders), self.start.isoformat(),
                PARSER_VERSION]


# --- settings and state -----------------------------------------------------------------------------

def _settings(ws: Workspace) -> dict:
    s = ws.settings.get("eposta", {})
    if not isinstance(s, dict):
        raise MailError(f"{ws.base / 'ayarlar.toml'}: [eposta] bir tablo olmalı")
    return s


def _account(ws: Workspace, address: str, start: date) -> Account:
    """The account with ayarlar.toml's [eposta] settings, checked: they end up in IMAP commands."""
    s = _settings(ws)
    where = f"{ws.base / 'ayarlar.toml'} [eposta]"
    senders = s.get("gondericiler", list(DEFAULT_SENDERS))
    if not isinstance(senders, list) or not senders:
        raise MailError(f"{where}: gondericiler alan adlarının listesi olmalı")
    cleaned = []
    for sender in senders:
        domain = sender.strip().lower().lstrip("@") if isinstance(sender, str) else ""
        if not _DOMAIN.fullmatch(domain):
            raise MailError(f"{where}: gondericiler içinde geçersiz alan adı {sender!r} (örnek: banka.com.tr)")
        cleaned.append(domain)
    server, port, folder = s.get("sunucu", GMAIL), s.get("port", 993), s.get("klasor")
    if not isinstance(server, str) or not _DOMAIN.fullmatch(server.strip().lower()):
        raise MailError(f"{where}: sunucu bir alan adı olmalı (örnek: imap.gmail.com)")
    if not isinstance(port, int) or isinstance(port, bool) or not 0 < port < 65536:
        raise MailError(f"{where}: port bir sayı olmalı (IMAP TLS için 993)")
    if folder is not None and (not isinstance(folder, str) or not folder.strip() or re.search(r"[\x00-\x1f]", folder)):
        raise MailError(f"{where}: klasor bir klasör adı olmalı")
    verify = s.get("gonderen_dogrulama", True)
    if not isinstance(verify, bool):
        raise MailError(f"{where}: gonderen_dogrulama true ya da false olmalı")
    return Account(address, start, server.strip().lower(), port, tuple(dict.fromkeys(cleaned)),
                   folder.strip() if folder else None, verify)


def _state_path(ws: Workspace) -> Path:
    return ws.output / STATE_NAME


def _state(ws: Workspace) -> dict:
    try:
        value = json.loads(_state_path(ws).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):  # damaged: as if never set up; `eposta --kur` writes it again
        return {}
    return value if isinstance(value, dict) else {}


def _save_state(ws: Workspace, state: dict) -> None:
    ws.output.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".eposta-", dir=ws.output)  # 0600: it holds the address
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1, default=str)
        os.replace(tmp, _state_path(ws))
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def default_start(today: date | None = None) -> date:
    today = today or date.today()
    return date(today.year - 2, 1, 1)


def account(ws: Workspace) -> Account | None:
    """The account set up with `eposta --kur`, None if there is none."""
    state = _state(ws)
    if not state.get("address"):
        return None
    try:
        start = date.fromisoformat(state.get("start", ""))
    except ValueError:
        start = default_start()
    return _account(ws, state["address"], start)


def configured(ws: Workspace) -> bool:
    return bool(_state(ws).get("address"))


def due(ws: Workspace, every: float) -> bool:
    """Whether the last attempt, successful or not, is older than every seconds (the automatic
    run's pace: an inbox change starts it too)."""
    last = _state(ws).get("last_attempt")
    try:
        return last is None or (datetime.now() - datetime.fromisoformat(last)).total_seconds() >= every
    except (TypeError, ValueError):
        return True


def last_error(ws: Workspace) -> str | None:
    error = _state(ws).get("last_error")
    return error.get("message") if isinstance(error, dict) else None


def status(ws: Workspace) -> dict:
    """What is set up and what the last fetch did; reads no password."""
    state = _state(ws)
    if not state.get("address"):
        return {"configured": False, "hint": SETUP_HINT}
    out = {"configured": True, "address": state["address"], "start": state.get("start"),
           "folder": state.get("folder"), "lastRun": state.get("last_run"), "lastResult": state.get("last_result"),
           "lastError": state.get("last_error")}
    try:
        acc = account(ws)
    except MailError as exc:
        return out | {"settingsError": str(exc)}
    return out | {"server": acc.server, "senders": list(acc.senders), "verifySender": acc.verify}


# --- the password -------------------------------------------------------------------------------------

def _keyring():
    import keyring  # only when e-mail is used: it picks a backend on import

    return keyring


def load_password(address: str) -> str:
    secret = os.environ.get(PASSWORD_ENV)
    if secret:
        return secret
    keyring = _keyring()
    try:
        secret = keyring.get_password(SERVICE, address)
    except keyring.errors.KeyringError as exc:
        raise MailError(f"e-posta şifresi anahtar zincirinden okunamadı ({exc}); anahtar zinciri olmayan "
                        f"sistemlerde şifreyi {PASSWORD_ENV} ortam değişkeniyle verin") from exc
    if not secret:
        raise MailError(f"{address} için kayıtlı şifre yok; yeniden kurun: uv run iplikci eposta --kur")
    return secret


def store_password(address: str, secret: str) -> bool:
    """Keep the password in the system keyring; False where the system has none."""
    keyring = _keyring()
    try:
        keyring.set_password(SERVICE, address, secret)
    except keyring.errors.NoKeyringError:
        return False
    except keyring.errors.KeyringError as exc:
        raise MailError(f"şifre anahtar zincirine yazılamadı: {exc}") from exc
    return True


def delete_password(address: str) -> None:
    keyring = _keyring()
    try:
        keyring.delete_password(SERVICE, address)
    except keyring.errors.KeyringError:  # PasswordDeleteError when there was none
        pass


def _clean_secret(acc: Account, secret: str) -> str:
    if re.search(r"[\x00-\x1f\x7f]", secret):
        raise MailError("şifrede satır sonu ya da denetim karakteri olamaz")
    if acc.is_gmail:
        secret = secret.replace(" ", "")  # Google shows app passwords in groups of four
    if not secret:
        raise MailError("şifre boş")
    return secret


# --- IMAP -----------------------------------------------------------------------------------------------

def connect(acc: Account) -> imaplib.IMAP4:
    """A TLS connection; the server's certificate and host name are checked."""
    return imaplib.IMAP4_SSL(acc.server, acc.port, ssl_context=ssl.create_default_context(), timeout=60)


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _unquote(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return re.sub(r"\\(.)", r"\1", text[1:-1])
    return text


def utf7_encode(name: str) -> str:
    """A folder name in IMAP's modified UTF-7 (RFC 3501 5.1.3): "Tüm Postalar" -> "T&APw-m Postalar"."""
    out, run = [], []

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
    def part(m: re.Match) -> str:
        coded = m[1].replace(",", "/")
        return base64.b64decode(coded + "=" * (-len(coded) % 4)).decode("utf-16-be") if coded else "&"

    try:
        return re.sub(r"&([A-Za-z0-9+,]*)-", part, name)
    except (ValueError, UnicodeDecodeError):  # not valid modified UTF-7: show it as the server sent it
        return name


def _shown(mailbox: str) -> str:
    return utf7_decode(_unquote(mailbox))


def _text(data) -> str:
    parts = [d.decode(errors="replace") if isinstance(d, bytes) else str(d) for d in (data or []) if d]
    return " ".join(parts)[:300]


def _all_mail(imap: imaplib.IMAP4) -> str | None:
    """Gmail's "All Mail" as the server names it (the name follows the account's language), found
    by its \\All flag (RFC 6154): every label and the archive, without Spam and Trash."""
    typ, data = imap.list()
    if typ != "OK":
        return None
    for line in data or []:
        if isinstance(line, tuple):  # a name sent as a literal
            line = line[0].rsplit(b"{", 1)[0] + _quote(line[1].decode("utf-8", errors="replace")).encode()
        m = _LIST.match(line or b"")
        if m and b"\\all" in m["flags"].lower().split():
            return m["name"].decode("utf-8", errors="replace").strip()
    return None


@dataclass
class _Box:
    imap: imaplib.IMAP4
    name: str  # as sent to SELECT (quoted, modified UTF-7)
    uidvalidity: int
    gmail: bool  # Gmail's extensions are there (X-GM-RAW search)


def _login_refused(acc: Account, exc: Exception) -> str:
    text = str(exc)
    if acc.is_gmail and re.search(r"AUTHENTICATIONFAILED|Invalid credentials|Application-specific password",
                                  text, re.IGNORECASE):
        return ("Gmail girişi reddetti: adres ya da uygulama şifresi yanlış. Normal Gmail şifresi çalışmaz; "
                "2 Adımlı Doğrulamayı açıp https://myaccount.google.com/apppasswords sayfasında bir uygulama "
                "şifresi oluşturun ve yeniden kurun: uv run iplikci eposta --kur")
    return f"{acc.server} girişi reddetti: {text}"


def _network_trouble(exc: BaseException) -> str:
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
def _session(acc: Account, secret: str) -> Iterator[_Box]:
    """Logged in, with the mailbox open read-only (EXAMINE): nothing there can change."""
    try:
        imap = connect(acc)
    except (OSError, ssl.SSLError, imaplib.IMAP4.error) as exc:
        raise MailError(f"{acc.server} sunucusuna bağlanılamadı: {_network_trouble(exc)}") from exc
    try:
        try:
            imap.login(acc.address, secret)
        except imaplib.IMAP4.error as exc:
            raise MailError(_login_refused(acc, exc)) from exc
        except UnicodeEncodeError as exc:  # imaplib sends LOGIN in ASCII
            raise MailError("adres ve şifre yalnızca ASCII karakterler içerebilir") from exc
        gmail = "X-GM-EXT-1" in imap.capabilities
        if acc.folder:
            name = _quote(utf7_encode(acc.folder))
        else:
            name = (_all_mail(imap) if gmail else None) or "INBOX"
        typ, data = imap.select(name, readonly=True)
        if typ != "OK":
            raise MailError(f"'{_shown(name)}' klasörü açılamadı: {_text(data)}")
        validity = imap.response("UIDVALIDITY")[1]
        yield _Box(imap, name, int(validity[0]) if validity and validity[0] else 0, gmail)
    except imaplib.IMAP4.error as exc:  # abort too: the connection broke off
        raise MailError(f"{acc.server} ile bağlantı kesildi ya da komut reddedildi: {exc}") from exc
    except (OSError, ssl.SSLError) as exc:
        raise MailError(f"{acc.server} ile bağlantı kesildi: {_network_trouble(exc)}") from exc
    finally:
        try:
            imap.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


def _any_from(senders: tuple[str, ...]) -> str:
    """IMAP's OR takes two keys: OR FROM "a" OR FROM "b" FROM "c"."""
    key = f"FROM {_quote(senders[-1])}"
    for sender in reversed(senders[:-1]):
        key = f"OR FROM {_quote(sender)} {key}"
    return key


def search_criteria(acc: Account, after_uid: int, gmail: bool) -> list[str]:
    since = acc.start
    keys = [f"UID {after_uid + 1}:*", f"SINCE {since.day}-{_MONTHS[since.month - 1]}-{since.year}",
            _any_from(acc.senders)]
    if gmail:
        keys.append('X-GM-RAW "has:attachment"')  # the server leaves out the banks' campaign e-mails
    return keys


def _search(box: _Box, acc: Account, after_uid: int) -> list[int]:
    typ, data = box.imap.uid("SEARCH", *search_criteria(acc, after_uid, box.gmail))
    if typ != "OK":
        raise MailError(f"e-postalar aranamadı: {_text(data)}")
    found = {int(x) for line in data or [] if isinstance(line, bytes) for x in line.split() if x.isdigit()}
    return sorted(u for u in found if u > after_uid)  # "n:*" always holds the newest message


def _sizes(imap: imaplib.IMAP4, uids: list[int]) -> dict[int, int]:
    sizes: dict[int, int] = {}
    for chunk in itertools.batched(uids, 200):
        typ, data = imap.uid("FETCH", ",".join(map(str, chunk)), "(RFC822.SIZE)")
        if typ != "OK":
            raise MailError(f"e-posta boyutları alınamadı: {_text(data)}")
        for line in data or []:
            head = line[0] if isinstance(line, tuple) else line
            uid, size = re.search(rb"\bUID (\d+)", head or b""), re.search(rb"RFC822\.SIZE (\d+)", head or b"")
            if uid and size:
                sizes[int(uid[1])] = int(size[1])
    return sizes


def _body(imap: imaplib.IMAP4, uid: int) -> bytes | None:
    # BODY.PEEK: reading does not mark the e-mail as read (the mailbox is read-only anyway).
    typ, data = imap.uid("FETCH", str(uid), "(BODY.PEEK[])")
    if typ != "OK":
        raise MailError(f"e-posta indirilemedi: {_text(data)}")
    for part in data or []:
        if isinstance(part, tuple) and b"BODY[]" in part[0]:
            return part[1]
    return None


# --- one e-mail -----------------------------------------------------------------------------------------

def sender_domain(msg: Message) -> str:
    return parseaddr(str(msg.get("From", "")))[1].rpartition("@")[2].strip().lower()


def wanted(domain: str, senders: tuple[str, ...]) -> bool:
    return any(domain == s or domain.endswith("." + s) for s in senders)


def verified(msg: Message, domain: str, gmail: bool) -> bool:
    """Whether the receiving server verified the sender: DMARC passed for the From domain. Its
    Authentication-Results header is the topmost one (each server adds its own on top and drops
    copies forged with its name); on Gmail it must come from mx.google.com."""
    results = msg.get_all("Authentication-Results") or []
    if not results:
        return False
    top = " ".join(str(results[0]).split())
    if gmail and top.split(";", 1)[0].strip().lower() != "mx.google.com":
        return False
    m = _DMARC.search(top)
    return bool(m) and m[1].lower() == domain


def _documents(msg: Message, domain: str) -> list[duzenle.Item]:
    try:
        when = f" {parsedate_to_datetime(str(msg['Date'])):%Y-%m-%d}"
    except (TypeError, ValueError, IndexError):
        when = ""
    origin = Path(f"E-posta{when} {domain}")
    items = []
    for name, data in attachments(msg):
        for member, _, blob in _expand(name, str(origin), data):  # zips opened in memory
            items.append(duzenle.Item(member, hashlib.sha256(blob).hexdigest(), archive=origin, data=blob))
    return items


# --- fetching ---------------------------------------------------------------------------------------------

_SKIPPED = {duzenle.DUPLICATE: "zaten vardı", duzenle.BUSINESS: "şirket belgesi", duzenle.KEEP: "zaten gelen kutusunda",
            duzenle.FAILED: "zaten gelen kutusunda"}


@dataclass
class Fetched:
    scanned: int = 0  # new e-mails from the bank domains
    again: bool = False  # the mailbox was read from the start (new readers, other settings)
    with_documents: int = 0  # verified ones that carried documents
    unverified: int = 0  # from a bank domain, but the receiving server did not verify the sender: ignored
    too_large: int = 0
    more: bool = False  # stopped at the per-fetch limit; the next fetch continues
    folder: str = ""
    found: list[duzenle.Item] = field(default_factory=list)  # the attachments, with the organizer's verdict
    copied: list[tuple[duzenle.Item, Path]] = field(default_factory=list)  # new ones, with their inbox copy

    @property
    def message(self) -> str:
        if not self.scanned:
            return "yeni banka e-postası yok"
        parts = [f"{self.scanned} banka e-postası baştan okundu" if self.again else
                 f"{self.scanned} yeni banka e-postası okundu"]
        if self.copied:
            kinds = Counter(_kind(it) for it, _ in self.copied)
            detail = ", ".join(f"{n} {k}" for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]))
            parts.append(f"{len(self.copied)} yeni belge gelen kutusuna kopyalandı ({detail})")
        else:
            parts.append("yeni belge yok")
        copied = {id(it) for it, _ in self.copied}
        # What an unused attachment is: "sigorta poliçesi/bilgilendirmesi", "talimat formu", ...
        skipped = Counter(_SKIPPED.get(it.action) or it.reason or "kullanılmıyor"
                          for it in self.found if id(it) not in copied)
        if skipped:
            parts.append("ekler: " + ", ".join(f"{n} {why}" for why, n in skipped.most_common()))
        if self.unverified:
            parts.append(f"{self.unverified} e-postanın göndereni doğrulanamadı, alınmadı")
        if self.too_large:
            parts.append(f"{self.too_large} e-posta {MAX_MESSAGE_BYTES >> 20} MB sınırından büyük olduğu için alınmadı")
        if self.more:
            parts.append("daha fazla e-posta var, sonraki alımda sürecek")
        return "; ".join(parts)

    def as_dict(self, ws: Workspace) -> dict:
        return {"message": self.message, "scanned": self.scanned, "withDocuments": self.with_documents,
                "unverified": self.unverified, "tooLarge": self.too_large, "more": self.more, "folder": self.folder,
                "copied": [str(p.relative_to(ws.inbox)) for _, p in self.copied]}


def _kind(it: duzenle.Item) -> str:
    if it.action == duzenle.FAILED:
        return "okunamayan belge"
    if it.result and it.result.statements:
        return "hesap dökümü" if it.result.statements[0].is_account else "kart ekstresi"
    return "dekont"


def fetch(ws: Workspace, wait: float = 120.0, progress: Callable[[int, int, str], None] | None = None) -> Fetched:
    """Download the bank e-mails that arrived since the last fetch and copy their new documents into
    the inbox. At most MAX_MESSAGES e-mails at a time (Fetched.more says there are more)."""
    if not configured(ws):
        raise NotConfigured(SETUP_HINT)
    with output_lock(ws.output, wait, name=_LOCK_NAME, busy="e-postalar şu anda başka bir işlemce alınıyor"):
        state = _state(ws)
        state["last_attempt"] = _now()
        try:
            acc = account(ws)
            if acc is None:
                raise NotConfigured(SETUP_HINT)
            secret = _clean_secret(acc, load_password(acc.address))
            out, last, box = _download(acc, secret, state, progress)
        except MailError as exc:  # kept, so the automatic run tells the user about a new problem only once
            state["last_error"] = {"at": _now(), "message": str(exc)}
            _save_state(ws, state)
            raise
        if out.found:
            out.copied = import_documents(ws, out.found)
        # Only now that the documents are safe in the inbox does the mailbox count as read this far.
        state.update(uidvalidity=box.uidvalidity, last_uid=last, scan=acc.scan_key(), folder=out.folder,
                     last_run=_now(), last_error=None,
                     last_result={"scanned": out.scanned, "copied": len(out.copied), "unverified": out.unverified,
                                  "more": out.more})
        _save_state(ws, state)
    return out


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _download(acc: Account, secret: str, state: dict, progress) -> tuple[Fetched, int, _Box]:
    out = Fetched()
    with _session(acc, secret) as box:
        out.folder = _shown(box.name)
        same = state.get("uidvalidity") == box.uidvalidity and state.get("scan") == acc.scan_key()
        after = int(state.get("last_uid") or 0) if same else 0
        out.again = not same and bool(state.get("last_uid"))
        uids = _search(box, acc, after)
        todo = uids[:MAX_MESSAGES]
        out.more = len(uids) > len(todo)
        sizes = _sizes(box.imap, todo)
        last, held = after, 0
        for i, uid in enumerate(todo, 1):
            if held > _MAX_FETCH_BYTES:
                out.more = True
                break
            if progress:
                progress(i, len(todo), "")
            last = uid
            if sizes.get(uid, 0) > MAX_MESSAGE_BYTES:
                out.too_large += 1
                continue
            raw = _body(box.imap, uid)
            if not raw:
                continue
            msg = email.message_from_bytes(raw)
            domain = sender_domain(msg)
            if not wanted(domain, acc.senders):  # the server's search matches more loosely
                continue
            out.scanned += 1
            if acc.verify and not verified(msg, domain, box.gmail):
                out.unverified += 1
                continue
            docs = _documents(msg, domain)
            if docs:
                out.with_documents += 1
                out.found += docs
                held += sum(len(d.data) for d in docs)
    return out, last, box


# --- setting up -------------------------------------------------------------------------------------------

def setup(ws: Workspace, address: str, secret: str, start: date | None = None) -> tuple[Account, bool, str]:
    """Log in once to check the address and the password, then keep them. Returns the account,
    whether the system keyring took the password, and the folder that will be read."""
    address = address.strip()
    if not _ADDRESS.fullmatch(address):
        raise MailError(f"geçerli bir e-posta adresi yazın ({address!r} değil)")
    acc = _account(ws, address, start or default_start())
    secret = _clean_secret(acc, secret)
    with _session(acc, secret) as box:
        folder = _shown(box.name)
    stored = store_password(address, secret)
    with output_lock(ws.output, 30, name=_LOCK_NAME, busy="e-postalar şu anda alınıyor; biraz sonra yeniden kurun"):
        old = _state(ws).get("address")
        if old and old.lower() != address.lower():
            delete_password(old)
        _save_state(ws, {"address": address, "start": acc.start.isoformat(), "folder": folder})
    return acc, stored, folder


def set_start(ws: Workspace, start: date) -> None:
    """Read the mailbox from another day on; the next fetch reads it again from that day."""
    with output_lock(ws.output, 30, name=_LOCK_NAME, busy="e-postalar şu anda alınıyor; biraz sonra yeniden deneyin"):
        state = _state(ws)
        if not state.get("address"):
            raise NotConfigured(SETUP_HINT)
        state["start"] = start.isoformat()
        _save_state(ws, state)


def forget(ws: Workspace) -> bool:
    """Remove the password from the keyring and the account from the state; False if none was set up."""
    state = _state(ws)
    if not state.get("address"):
        return False
    delete_password(state["address"])
    _state_path(ws).unlink(missing_ok=True)  # the program's own state file, not a document
    return True
