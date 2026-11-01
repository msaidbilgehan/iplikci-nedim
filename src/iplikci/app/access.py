"""Who may use the service (ADR-0007): one-time login keys that become browser sessions, and the API token of the
command line and the MCP bridge.

A login key lives two minutes in the service's memory and opens one session. The session token goes into an
HttpOnly cookie and the database keeps only its SHA-256. A session lasts 90 days; using it pushes that back, at most
once a day. The API token lives in the system keyring (architecture §20), or in IPLIKCI_API_TOKEN where there is
none.
"""

import hashlib
import hmac
import secrets
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import Enum

from ..settings import secrets as keychain
from ..storage import sessions
from ..storage.db import Database

SESSION_DAYS = 90
SESSION_SECONDS = SESSION_DAYS * 24 * 3600
LOGIN_KEY_SECONDS = 120
_RENEW_AFTER = timedelta(days=1)


class SessionState(Enum):
    NONE = "none"  # no such session, or it expired
    VALID = "valid"
    RENEWED = "renewed"  # valid, and its expiry was pushed back: the cookie is set again


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _iso(at: datetime) -> str:
    return at.astimezone(UTC).replace(microsecond=0).isoformat()


class LoginKeys:
    """One-time login keys in the service's memory: each opens one session within LOGIN_KEY_SECONDS."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._deadlines: dict[str, float] = {}  # key hash -> deadline
        self._lock = threading.Lock()
        self._clock = clock

    def issue(self) -> str:
        key = secrets.token_urlsafe(32)
        with self._lock:
            now = self._clock()
            self._deadlines = {h: d for h, d in self._deadlines.items() if d > now}
            self._deadlines[_hash(key)] = now + LOGIN_KEY_SECONDS
        return key

    def redeem(self, key: str) -> bool:
        """Whether key is a live login key; it is used up either way."""
        with self._lock:
            deadline = self._deadlines.pop(_hash(key), None)
        return deadline is not None and deadline > self._clock()


def open_session(db: Database, now: datetime | None = None) -> str:
    """A new session; its token, for the cookie."""
    token = secrets.token_urlsafe(32)
    at = now or datetime.now(UTC)
    sessions.add(db, _hash(token), _iso(at), _iso(at + timedelta(days=SESSION_DAYS)))
    return token


def check_session(db: Database, token: str, now: datetime | None = None) -> SessionState:
    if not token:
        return SessionState.NONE
    at = now or datetime.now(UTC)
    found = sessions.find(db, _hash(token))
    if found is None or datetime.fromisoformat(found.expires_at) <= at:
        return SessionState.NONE
    if at - datetime.fromisoformat(found.renewed_at) < _RENEW_AFTER:
        return SessionState.VALID
    sessions.renew(db, found.token_hash, _iso(at), _iso(at + timedelta(days=SESSION_DAYS)))
    return SessionState.RENEWED


def close_session(db: Database, token: str) -> None:
    sessions.remove(db, _hash(token))


def purge_sessions(db: Database, now: datetime | None = None) -> int:
    return sessions.purge(db, _iso(now or datetime.now(UTC)))


def api_token() -> str | None:
    """The token of the command line and the MCP bridge; None when none was made yet."""
    return keychain.load(keychain.API_TOKEN)


def ensure_api_token() -> str:
    """The API token, made at the service's first start and kept in the keyring. Where the system has no keyring and
    IPLIKCI_API_TOKEN is unset, the token lives only as long as this run of the service."""
    token = api_token()
    if token:
        return token
    token = secrets.token_urlsafe(32)
    keychain.store(keychain.API_TOKEN, token)
    return token


def same_token(given: str, expected: str) -> bool:
    return bool(given) and hmac.compare_digest(given.encode(), expected.encode())
