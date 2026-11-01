"""The browser extension's side of the service (ADR-0016): pairing, the bridge's token, and taking the raw messages
it delivers.

Pairing: the setup page asks for a pairing code (a signed-in browser session); the page hands it to the extension,
or the user types it there. The extension confirms in its own window and trades the code for a token that opens the
mail intake and nothing else. A code is single-use and lives ten minutes; five wrong codes drop every open one.

Before it delivers anything, the extension makes the service prove it is the one it paired with: it sends a nonce,
and the service answers with an HMAC of it keyed with the token's SHA-256, which only the paired service holds. A
process listening on 127.0.0.1:8643 in the service's place cannot answer, so it receives no message.
"""

import hashlib
import hmac
import json
import secrets
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ..domain.codes import Actor
from ..settings import config
from ..storage import audit, bridges, events
from ..storage import mail as mail_store
from ..storage.db import now
from . import mail
from .workspace import Workspace

MAX_MESSAGE_BYTES = mail.MAX_MESSAGE_BYTES  # what the intake takes at most
CODE_SECONDS = 600
CODE_LENGTH = 8
MAX_WRONG_CODES = 5
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I: the user may type it
_SEEN_EVERY = timedelta(minutes=1)
PAIRED, REVOKED = "bridge.paired", "bridge.revoked"  # in the audit log, and as events for the pairing page
ALARM = "mail.bridge_alarm"  # a layer of the extension met a Gmail page it does not know and stopped (ADR-0016)
SILENT = "mail.bridge_silent"  # no paired extension was seen for a day: the browser stayed closed
SILENCE = timedelta(days=1)
LAYERS = {1: "gelen kutusu akışı", 2: "tam tarama", 3: "ham ileti"}  # the extension's three ways of reading Gmail


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class PairingCodes:
    """The open pairing codes, in the service's memory."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._deadlines: dict[str, float] = {}
        self._wrong = 0
        self._lock = threading.Lock()
        self._clock = clock

    def issue(self) -> tuple[str, float]:
        """A new code and how many seconds it lives."""
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        with self._lock:
            now_ = self._clock()
            self._deadlines = {c: d for c, d in self._deadlines.items() if d > now_}
            self._deadlines[code] = now_ + CODE_SECONDS
            self._wrong = 0
        return code, CODE_SECONDS

    def redeem(self, code: str) -> bool:
        """Whether code is open; it is used up either way. Too many wrong codes close them all."""
        typed = code.strip().upper().replace("-", "").replace(" ", "")
        with self._lock:
            deadline = self._deadlines.pop(typed, None)
            if deadline is not None and deadline > self._clock():
                return True
            self._wrong += 1
            if self._wrong >= MAX_WRONG_CODES:
                self._deadlines.clear()
            return False


@dataclass(frozen=True)
class Paired:
    id: str
    token: str  # shown once, to the extension


def pair(ws: Workspace, name: str) -> Paired:
    """Make a bridge for an extension whose code was redeemed, and make the browser extension the mail connector."""
    token = secrets.token_urlsafe(32)
    bridge_id = secrets.token_hex(6)
    with ws.db() as db, db.transaction():
        bridges.add(db, bridge_id, _hash(token), name.strip()[:80])
        audit.record(db, Actor.USER, PAIRED, bridge_id)
        events.record(db, PAIRED, bridge_id)  # the pairing page sees it at once
    settings = config.load(ws.layout.settings)
    config.update(
        ws.layout.settings,
        "mail",
        {"connector": mail.BRIDGE, "start_day": settings.mail.start_day or mail.default_start()},
    )
    return Paired(bridge_id, token)


def identify(ws: Workspace, token: str) -> str | None:
    """The id of the active bridge holding token; None for any other token. Notes when the bridge was last seen."""
    if not token:
        return None
    with ws.db() as db:
        found = bridges.by_token(db, _hash(token))
        if found is None or not found.active:
            return None
        at = datetime.now(UTC)
        if not found.last_seen or at - datetime.fromisoformat(found.last_seen) >= _SEEN_EVERY:
            bridges.seen(db, found.id, at.replace(microsecond=0).isoformat())
    return found.id


def proof(ws: Workspace, bridge_id: str, nonce: str) -> str | None:
    """The answer to an extension's nonce: HMAC-SHA256 keyed with its token's hash; None for an unknown or revoked
    bridge."""
    with ws.db() as db:
        found = bridges.get(db, bridge_id)
    if found is None or not found.active:
        return None
    return hmac.new(found.token_hash.encode(), nonce.encode(), hashlib.sha256).hexdigest()


def every(ws: Workspace) -> list[bridges.Bridge]:
    with ws.db() as db:
        return bridges.every(db)


def revoke(ws: Workspace, bridge_id: str) -> bool:
    with ws.db() as db, db.transaction():
        if not bridges.revoke(db, bridge_id):
            return False
        audit.record(db, Actor.USER, REVOKED, bridge_id)
        events.record(db, REVOKED, bridge_id)
    return True


@dataclass(frozen=True)
class Cursor:
    last_id: str  # Gmail's id of the newest message delivered
    last_date: str
    start_day: str  # where the history begins
    senders: tuple[str, ...]  # whose messages to deliver
    history_due: bool  # no finished scan of Gmail searched this start day and these senders


def history_key(start_day: str, senders: Iterable[str]) -> str:
    """What a scan of Gmail searched. The bridge's state keeps the key of the last finished scan, as the IMAP
    connector keeps what it read from the start; another key means the history needs a scan again."""
    return json.dumps([start_day, sorted({s.lower() for s in senders})])


def history_due(settings: config.Settings, state: mail_store.MailState) -> bool:
    """Whether no finished scan of Gmail searched the start day and the senders the settings ask for now."""
    start = settings.mail.start_day or mail.default_start()
    return state.scan_key != history_key(start.isoformat(), mail.senders(settings))


def cursor(ws: Workspace) -> Cursor:
    settings = config.load(ws.layout.settings)
    with ws.db() as db:
        state = mail_store.load(db, mail.BRIDGE)
    start = settings.mail.start_day or mail.default_start()
    return Cursor(
        state.last_id, state.last_date, start.isoformat(), mail.senders(settings), history_due(settings, state)
    )


def missing(ws: Workspace, gmail_ids: list[str]) -> list[str]:
    """Which of the Gmail ids a scan of Gmail found the service does not hold yet."""
    with ws.db() as db:
        return bridges.missing(db, gmail_ids)


def scanned(ws: Workspace, start_day: str, senders: Iterable[str]) -> bool:
    """A scan of Gmail finished: it searched the senders' messages from start_day on, as the cursor said when it
    began. Whether the history still needs a scan: the settings may have changed while it ran."""
    settings = config.load(ws.layout.settings)
    with ws.db() as db:
        state = mail_store.load(db, mail.BRIDGE)
        state.scan_key = history_key(start_day, senders)
        mail_store.save(db, state)
    return history_due(settings, state)


def alarm(ws: Workspace, layer: int, version: str, page: dict[str, object] | None = None) -> bool:
    """A layer of the extension stopped on a Gmail page it does not know; told once per layer and extension version
    (the fix comes with an update of the extension). page: what a "Show original" page showed, without its text, for
    whoever fixes the extension. Whether it was news."""
    if layer not in LAYERS:
        raise ValueError(f"bilinmeyen katman: {layer}")
    shown: dict[str, object] = {} if page is None else {"page": page}
    with ws.db() as db:
        added = events.record(db, ALARM, f"katman-{layer}", version=version, **shown)
        state = mail_store.load(db, mail.BRIDGE)
        state.last_error = f"eklentinin {LAYERS[layer]} katmanı durdu: Gmail'in sayfası tanınmadı"
        mail_store.save(db, state)
    return added


def check_silence(ws: Workspace, at: datetime | None = None) -> list[str]:
    """Tell once (mail.bridge_silent) about each paired extension not seen for a day; the ids told now. A bridge
    that comes back and falls silent again is told again."""
    at = at or datetime.now(UTC)
    with ws.db() as db:
        quiet = [b for b in bridges.every(db) if b.active and at - datetime.fromisoformat(b.last_seen) >= SILENCE]
        told = [b.id for b in quiet if events.record(db, SILENT, b.id, since=b.last_seen)]
    return told


def deliver(ws: Workspace, raw: bytes, gmail_id: str = "", gmail_date: str = "") -> mail.MailOutcome:
    """Take a raw message the extension delivers through the same pipeline as every connector. A message the service
    holds afterwards is remembered by Gmail's id; the cursor moves on when the message is the newest so far. A message
    from a scan of Gmail comes without a date and leaves the cursor where it is: the feed's newest moves it."""
    settings = config.load(ws.layout.settings)
    outcome = mail.take(ws, raw, mail.senders(settings), verify=settings.mail.verify_sender, gmail=True)
    with ws.db() as db:
        if gmail_id and outcome.sha256:
            bridges.remember(db, gmail_id, outcome.sha256)
        state = mail_store.load(db, mail.BRIDGE)
        state.count(str(outcome.taken))
        if gmail_id and gmail_date and gmail_date >= state.last_date:
            state.last_id, state.last_date = gmail_id, gmail_date
        state.last_run, state.last_error = now(), ""
        mail_store.save(db, state)
    return outcome
