"""E-mail (ADR-0015, ADR-0016): taking one message in, whichever connector fetched it, and the IMAP connector's use
cases (setup, fetch, status, removal).

The trust rule first (ingest.mail.trust): a message that fails it is counted and dropped, nothing of it is kept, so
a mail imitating a bank leaves no trace. Then the company check: a message whose subject marks a company, or one of
whose attachments is a company document, is not kept at all. Every other message is kept whole as .eml, and each
attachment, zip members included, as a document of its own with the message as its parent.

The address lives in settings.toml, the app password only in the keyring (`iplikci` service). A refused login stops
the connector and is told once (mail.auth_failed); nothing tries again until the user sets it up again.
"""

import email
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from .. import egress
from ..domain.codes import Actor, SourceKind
from ..ingest.archives import message_fields, sender_domain
from ..ingest.mail.idle import WatchTarget
from ..ingest.mail.imap import (
    Account,
    Connect,
    LoginRefused,
    MailError,
    body,
    clean_password,
    new_uids,
    session,
    sizes,
)
from ..ingest.mail.trust import MAX_MESSAGE_BYTES, listed, message_name, trust_problem
from ..parsers.common import is_business
from ..settings import config, secrets
from ..storage import audit, events, jobs
from ..storage import mail as mail_store
from ..storage.db import now
from ..storage.documents import Source
from ..vault.store import sha256_of
from . import intake, kinds
from .workspace import Workspace, file_lock

FETCH_JOB = kinds.MAIL_FETCH


class Taken(StrEnum):
    """What became of one message."""

    STORED = "stored"  # kept, with its attachments
    KNOWN = "known"  # the vault had it already
    UNLISTED = "unlisted"  # its sender is on no list
    UNVERIFIED = "unverified"  # from a listed domain, but the receiving server did not verify the sender
    BUSINESS = "business"  # carries company content: not kept
    TOO_LARGE = "too_large"


_DMARC_RESULTS = {
    "fail": "DMARC denetiminden geçmedi",
    "none": "gönderenin alan adında DMARC kaydı yok",
    "bestguesspass": "gönderenin alan adında DMARC kaydı yok (Gmail yalnızca tahmin etti)",
    "temperror": "DMARC denetimi geçici bir hata verdi",
    "permerror": "gönderenin DMARC kaydı bozuk",
}


def refusal_label(taken: str, reason: str) -> str:
    """Why a delivered message was not kept, in Turkish, for the System screen."""
    if taken == Taken.UNLISTED:
        return "gönderen hiçbir listede değil"
    if taken == Taken.BUSINESS:
        return "şirket iletisi"
    kind, _, detail = reason.partition(":")
    match kind:
        case "no-results":
            return "iletide doğrulama başlığı yok"
        case "server":
            return f"en üstteki doğrulama başlığını Gmail eklememiş ({detail})"
        case "no-dmarc":
            return "doğrulama başlığında DMARC sonucu yok"
        case "dmarc":
            return _DMARC_RESULTS.get(detail, f"DMARC sonucu: {detail}")
        case "header-from":
            return f"DMARC başka bir alan adı için geçti ({detail})"
        case _:
            return "gönderen doğrulanamadı"


@dataclass(frozen=True)
class MailOutcome:
    taken: Taken
    domain: str = ""
    sha256: str = ""  # the message's, when it was kept or known
    documents: int = 0  # new documents kept: the message and its attachments
    reason: str = ""  # why an unverified message was not verified (ingest.mail.trust.trust_problem)


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
    if verify and (problem := trust_problem(msg, domain, senders, gmail)):
        return MailOutcome(Taken.UNVERIFIED, domain, reason=problem)
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


# --- the IMAP connector ------------------------------------------------------------------------------------

IMAP, BRIDGE = "imap", "browser_bridge"
AUTH_FAILED = "mail.auth_failed"
NOT_SET_UP = "E-posta bağlantısı kurulmadı."
MAX_MESSAGES = 300  # per fetch; the next one continues where this one stopped
_LOCK_NAME = ".eposta.kilit"
_ADDRESS = re.compile(r"[^@\s\"\\]+@[a-z0-9.-]+\.[a-z]{2,}", re.IGNORECASE)


class NotConfigured(MailError):
    pass


def _settings(ws: Workspace) -> config.Settings:
    """The settings as the file says now: the setup may have changed it while the service runs."""
    return config.load(ws.layout.settings)


def default_start(today: date | None = None) -> date:
    today = today or date.today()
    return date(today.year - 2, 1, 1)


def senders(settings: config.Settings) -> tuple[str, ...]:
    return settings.mail.bank_senders + settings.mail.other_senders


def _account(settings: config.Settings, address: str, start: date | None) -> Account:
    m = settings.mail
    folder = None if m.folder == "auto" else m.folder
    return Account(
        address, start or default_start(), m.imap_host, m.imap_port, senders(settings), folder, m.verify_sender
    )


def account(ws: Workspace) -> Account | None:
    """The IMAP account set up; None when there is none (or the connector is the browser extension)."""
    settings = _settings(ws)
    if settings.mail.connector != IMAP or not settings.mail.address:
        return None
    return _account(settings, settings.mail.address, settings.mail.start_day)


def _connect(settings: config.Settings) -> Connect:
    return lambda host, port: egress.imap(host, port, settings)


def load_password(address: str) -> str:
    try:
        secret = secrets.load(secrets.mail(address))
    except secrets.SecretError as exc:
        raise MailError(f"e-posta şifresi okunamadı: {exc}") from exc
    if not secret:
        raise MailError("kayıtlı e-posta şifresi yok; e-posta kurulumunda şifreyi yeniden girin")
    return secret


@dataclass
class Fetched:
    scanned: int = 0  # messages from the listed senders that were read
    again: bool = False  # the mailbox was read from the start (other settings, a renumbered folder)
    stored: int = 0  # messages kept
    documents: int = 0  # new documents: the messages and their attachments
    known: int = 0
    unverified: int = 0  # from a listed sender, but the receiving server did not verify it: not kept
    business: int = 0
    too_large: int = 0
    more: bool = False  # stopped at the limit; the next fetch continues
    folder: str = ""

    def add(self, outcome: MailOutcome) -> None:
        if outcome.taken is Taken.UNLISTED:
            return  # the server's search matches more loosely than the lists
        self.scanned += 1
        self.documents += outcome.documents
        match outcome.taken:
            case Taken.STORED:
                self.stored += 1
            case Taken.KNOWN:
                self.known += 1
            case Taken.UNVERIFIED:
                self.unverified += 1
            case Taken.BUSINESS:
                self.business += 1
            case _:
                self.too_large += 1

    @property
    def message(self) -> str:
        if not self.scanned:
            return "yeni e-posta yok"
        parts = [f"{self.scanned} e-posta baştan okundu" if self.again else f"{self.scanned} yeni e-posta okundu"]
        parts.append(
            f"{self.stored} ileti arşive alındı ({self.documents} yeni belge)" if self.stored else "yeni belge yok"
        )
        if self.known:
            parts.append(f"{self.known} zaten vardı")
        if self.unverified:
            parts.append(f"{self.unverified} e-postanın göndereni doğrulanamadı, alınmadı")
        if self.business:
            parts.append(f"{self.business} şirket iletisi alınmadı")
        if self.too_large:
            parts.append(f"{self.too_large} e-posta {MAX_MESSAGE_BYTES >> 20} MB sınırından büyük olduğu için alınmadı")
        if self.more:
            parts.append("daha fazla e-posta var, sonraki alımda sürecek")
        return "; ".join(parts)

    def as_dict(self) -> dict[str, object]:
        found: dict[str, object] = {"message": self.message}
        found.update(vars(self))
        return found


def fetch(ws: Workspace, wait: float = 120.0, progress: Callable[[int, int], None] | None = None) -> Fetched:
    """Take in the messages that arrived since the last fetch, at most MAX_MESSAGES (Fetched.more says there are
    more). A connector stopped by a refused login does not try again until it is set up again."""
    settings = _settings(ws)
    acc = account(ws)
    if acc is None:
        raise NotConfigured(NOT_SET_UP)
    with file_lock(ws.run, _LOCK_NAME, wait, "e-postalar şu anda başka bir işlemce alınıyor"):
        with ws.db() as db:
            state = mail_store.load(db, IMAP)
        if state.stopped:
            raise MailError(
                state.last_error or "e-posta girişi reddedilmişti; e-posta kurulumunda şifreyi yeniden girin"
            )
        try:
            password = clean_password(acc, load_password(acc.address))
            out = _download(ws, acc, password, state, _connect(settings), progress)
        except LoginRefused as exc:
            refused(ws, str(exc))
            raise
        except MailError as exc:
            state.last_error = str(exc)
            with ws.db() as db:
                mail_store.save(db, state)
            raise
        state.last_run, state.last_error = now(), ""
        for name in ("stored", "known", "unverified", "business", "too_large"):
            state.count(name, getattr(out, name))
        with ws.db() as db:
            mail_store.save(db, state)
    return out


def _download(
    ws: Workspace,
    acc: Account,
    password: str,
    state: mail_store.MailState,
    connect: Connect,
    progress: Callable[[int, int], None] | None,
) -> Fetched:
    out = Fetched()
    with session(acc, password, connect) as box:
        out.folder = box.shown
        same = state.uidvalidity == box.uidvalidity and state.scan_key == acc.scan_key()
        after = state.last_uid if same else 0
        out.again = not same and state.last_uid > 0
        state.uidvalidity, state.scan_key, state.last_uid = box.uidvalidity, acc.scan_key(), after
        uids = new_uids(box, acc, after)
        todo = uids[:MAX_MESSAGES]
        out.more = len(uids) > len(todo)
        lengths = sizes(box.imap, todo)
        for i, uid in enumerate(todo, 1):
            if progress:
                progress(i, len(todo))
            if lengths.get(uid, 0) > MAX_MESSAGE_BYTES:
                out.add(MailOutcome(Taken.TOO_LARGE))
            elif raw := body(box.imap, uid):
                out.add(take(ws, raw, acc.senders, verify=acc.verify, gmail=box.gmail))
            state.last_uid = uid  # the message is safe in the vault (or was not to be kept)
            if i % 25 == 0:
                with ws.db() as db:
                    mail_store.save(db, state)
    return out


def refused(ws: Workspace, message: str) -> None:
    """A refused login stops the connector (no automatic attempt) and tells the user once."""
    with ws.db() as db:
        state = mail_store.load(db, IMAP)
        if state.stopped:
            return
        state.stopped, state.last_error = True, message
        mail_store.save(db, state)
        events.append(db, AUTH_FAILED, IMAP, reason=message)


def watch_target(ws: Workspace) -> WatchTarget | None:
    """What the IDLE watcher logs in with; None while there is nothing it may try."""
    acc = account(ws)
    if acc is None:
        return None
    with ws.db() as db:
        if mail_store.load(db, IMAP).stopped:
            return None
    try:
        password = clean_password(acc, load_password(acc.address))
    except MailError:
        return None
    return WatchTarget(acc, password, _connect(_settings(ws)))


def request_fetch(ws: Workspace) -> None:
    """Ask the service to fetch the new messages; asked twice before it starts, it fetches once."""
    with ws.db() as db:
        jobs.add(db, FETCH_JOB)


def setup_imap(ws: Workspace, address: str, password: str, start: date | None = None) -> tuple[Account, bool, str]:
    """Log in once to check the address and the password, then keep them: the password in the keyring, the address
    and the start day in settings.toml. Returns the account, whether the keyring took the password, and the folder
    that will be read. A refused login keeps nothing."""
    address = address.strip()
    if not _ADDRESS.fullmatch(address):
        raise MailError("geçerli bir e-posta adresi yazın")
    settings = _settings(ws)
    acc = _account(settings, address, start)
    secret = clean_password(acc, password)
    with session(acc, secret, _connect(settings)) as box:
        folder = box.shown
    try:
        stored = secrets.store(secrets.mail(address), secret)
    except secrets.SecretError as exc:
        raise MailError(f"şifre saklanamadı: {exc}") from exc
    old = settings.mail.address
    if old and old.lower() != address.lower():
        secrets.delete(secrets.mail(old))
    config.update(ws.layout.settings, "mail", {"connector": IMAP, "address": address, "start_day": acc.start})
    with ws.db() as db:
        mail_store.forget(db, IMAP)  # a fresh start: a stopped connector runs again
        jobs.add(db, FETCH_JOB)
    return acc, stored, folder


def set_start(ws: Workspace, start: date) -> None:
    """Read the mailbox from another day on; the next fetch reads it again from that day."""
    if account(ws) is None:
        raise NotConfigured(NOT_SET_UP)
    config.update(ws.layout.settings, "mail", {"start_day": start})


def remove(ws: Workspace) -> bool:
    """Forget the IMAP account: its password, its address and where it stood. False when none was set up."""
    settings = _settings(ws)
    if settings.mail.connector != IMAP or not settings.mail.address:
        return False
    secrets.delete(secrets.mail(settings.mail.address))
    config.update(ws.layout.settings, "mail", {"address": None, "start_day": None, "connector": None})
    with ws.db() as db:
        mail_store.forget(db, IMAP)
    return True


def status(ws: Workspace) -> dict[str, object]:
    """What is set up and how the last runs went; never the address (ADR-0015)."""
    settings = _settings(ws)
    connector = settings.mail.connector
    configured = bool(settings.mail.address) if connector == IMAP else False
    with ws.db() as db:
        state = mail_store.load(db, connector)
    return {
        "connector": connector,
        "configured": configured,
        "start": (settings.mail.start_day or default_start()).isoformat() if configured else None,
        "server": settings.mail.imap_host if connector == IMAP else None,
        "lastRun": state.last_run or None,
        "lastError": state.last_error or None,
        "stopped": state.stopped,
        "totals": state.totals,
    }
