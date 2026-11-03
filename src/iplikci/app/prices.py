"""TÜFE from TCMB's EVDS, for the spending trend in real terms (F12's V1+ part; inflation.py; ADR-0009).

Only with the user's own EVDS key. The user types it on the Settings screen; it is tried once with EVDS and, when EVDS
takes it, kept in the keyring (settings.secrets.EVDS) — never in a file, an argument or the log — and the settings
say so (`[fx] evds = true`): a data folder without that never reads the keyring for it. From then on the index is
fetched every day at 10:30 (TÜFE comes out on the third of the month at 10:00), from January of the year before the
data's first day: one request, a few kilobytes. Without a key nothing goes out, and the trend stays in TL of its own
time. A failure is recorded for the Settings screen and logged at WARNING, never raised to the job.

The index is not part of the analysis: the Değerlendirme screen reads it beside it (index), so a new month needs no
new analysis, and the rebuild does not carry it — the key fetches it again.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from datetime import time as clock
from decimal import Decimal
from typing import Any

from ..domain.codes import Actor
from ..fx import evds
from ..fx.provider import ProviderError
from ..settings import config, secrets
from ..storage import audit, feed_state, jobs, prices
from ..storage.db import Database, now
from . import fx, kinds
from .workspace import Workspace

__all__ = [
    "DAILY_AT",
    "FETCH_JOB",
    "PricesError",
    "PricesStatus",
    "fetch",
    "index",
    "remove_key",
    "request",
    "set_key",
    "status",
]

FETCH_JOB = kinds.PRICES
DAILY_AT = clock(10, 30)  # local time
SERIES = evds.TUFE
STATE = "prices.fetch"  # feed_state: when the last fetch ran, and what went wrong in it
KEY_SET = "evds.key_set"
KEY_REMOVED = "evds.key_removed"
# What EVDS's keys look like: letters and digits, ten of them as EVDS gives them today; room for a longer one, and
# nothing that could break a header.
_KEY = re.compile(r"[A-Za-z0-9_-]{6,128}")

log = logging.getLogger("iplikci.prices")

Fetch = Callable[[str, date, date, config.Settings], dict[str, Decimal]]


class PricesError(Exception):
    """The key was refused, could not be tried or kept; the message says why, in Turkish, and never holds the key."""


@dataclass(frozen=True, slots=True)
class PricesStatus:
    """Where TÜFE stands, for the Settings screen."""

    has_key: bool  # a key was kept for this data folder (the settings say so; the keyring is not read for it)
    months: int  # months of the index kept
    first: str | None  # YYYY-MM; None with none
    newest: str | None
    last_run: str  # when the last fetch ran (UTC, ISO 8601); "" if none yet
    last_error: str  # what went wrong in it, in Turkish; ""


def _enabled(ws: Workspace) -> bool:
    """Whether the user kept a key for this data folder (the settings as the file says now)."""
    return config.load(ws.layout.settings).fx.evds


def _key() -> str | None:
    """The kept key; None without one, or when the keyring cannot be read (the log says why)."""
    try:
        return secrets.load(secrets.EVDS)
    except secrets.SecretError as exc:
        log.warning("EVDS anahtarı okunamadı: %s", exc)
        return None


def _span(db: Database, today: date) -> tuple[date, date]:
    """From January of the year before the data's first day (the trend's months and a year before them), or of last
    year without data, to today."""
    first = fx.first_day(db) or today
    return date(first.year - 1, 1, 1), today


def _save(db: Database, error: str) -> None:
    feed_state.save(db, STATE, {"at": now(), "error": error})


def status(ws: Workspace) -> PricesStatus:
    with ws.db() as db:
        kept = prices.every(db, SERIES)
        state: dict[str, Any] = feed_state.load(db, STATE) or {}
    months = list(kept)
    return PricesStatus(
        has_key=_enabled(ws),
        months=len(months),
        first=months[0] if months else None,
        newest=months[-1] if months else None,
        last_run=str(state.get("at", "")),
        last_error=str(state.get("error", "")),
    )


def index(ws: Workspace) -> dict[str, Decimal]:
    """TÜFE as kept, by YYYY-MM; empty without a key's fetch."""
    with ws.db() as db:
        return prices.every(db, SERIES)


def set_key(ws: Workspace, key: str, actor: Actor, get: Fetch | None = None, today: date | None = None) -> PricesStatus:
    """Try key with EVDS and, when EVDS takes it, keep it in the keyring with the months that came. PricesError when
    it is no key, EVDS refused it or could not be reached (then nothing is kept), or the keyring could not keep it."""
    key = key.strip()
    if not _KEY.fullmatch(key):
        raise PricesError("Bu bir EVDS anahtarı değil: EVDS'deki profil sayfanızdaki 'API Key Kopyala' ile alınır.")
    settings = config.load(ws.layout.settings)
    with ws.db() as db:
        start, end = _span(db, today or date.today())
    try:
        found = (get or evds.fetch)(key, start, end, settings)
    except evds.KeyRefused as exc:
        raise PricesError(str(exc)) from None
    except ProviderError as exc:
        raise PricesError(f"Anahtar denenemedi, saklanmadı: {exc}") from None
    try:
        in_keyring = secrets.store(secrets.EVDS, key)
    except secrets.SecretError as exc:
        raise PricesError(str(exc)) from exc
    if not in_keyring:
        raise PricesError(
            f"Bu bilgisayarda anahtar zinciri yok: anahtar saklanamadı. {secrets.EVDS.env} ortam değişkeniyle verin."
        )
    config.update(ws.layout.settings, "fx", {"evds": True})
    with ws.db() as db:
        prices.put(db, SERIES, found)
        _save(db, "")
        audit.record(db, actor, KEY_SET, "evds", months=len(found))
    return status(ws)


def remove_key(ws: Workspace, actor: Actor) -> None:
    """Forget the key; the months kept stay (they are TCMB's public figures) and are no longer fetched."""
    try:
        secrets.delete(secrets.EVDS)
    except secrets.SecretError as exc:
        raise PricesError(str(exc)) from exc
    config.update(ws.layout.settings, "fx", {"evds": False})
    with ws.db() as db:
        audit.record(db, actor, KEY_REMOVED, "evds")


def fetch(ws: Workspace, get: Fetch | None = None, today: date | None = None) -> int:
    """Fetch TÜFE with the kept key; how many months were new or changed. Without a key nothing goes out. A failure is
    recorded and logged, never raised: the next day's run tries again."""
    if not _enabled(ws):
        return 0
    key = _key()
    settings = config.load(ws.layout.settings)
    with ws.db() as db:
        if key is None:
            _save(db, "EVDS anahtarı anahtar zincirinde bulunamadı: Ayarlar'dan yeniden girin")
            return 0
        start, end = _span(db, today or date.today())
        try:
            found = (get or evds.fetch)(key, start, end, settings)
        except ProviderError as exc:
            log.warning("TÜFE çekilemedi: %s", exc)
            _save(db, str(exc))
            return 0
        stored = prices.put(db, SERIES, found)
        _save(db, "")
    return stored


def request(ws: Workspace) -> None:
    """Ask the service for a fetch now; asked twice before it starts, it fetches once."""
    with ws.db() as db:
        jobs.add(db, FETCH_JOB)
