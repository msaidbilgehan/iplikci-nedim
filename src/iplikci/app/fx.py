"""Fetching the exchange rates and keeping them (F12, architecture §15, ADR-0009).

The settings ([fx] providers) name the providers the program may ask. TCMB's bulletin comes first; ECB's reference
rates, or Frankfurter's copy of them, fill the days TCMB leaves when it cannot be reached, and stand in its place when
the settings name no TCMB.

- The history is fetched once, for the days the data covers: from the oldest statement or row day to yesterday. TCMB
  is asked for every Monday to Friday it was not asked for yet, the newest first, one request a day with a pause
  between them; a day it published nothing for (a holiday: 404) is marked so and never asked again. A run asks at
  most RUN_LIMIT days, so the service's other jobs get their turn; the next run goes on where it stopped.
- Every day from 16:30 the day's bulletin is fetched, with the business days missed since the newest one. The day
  itself stays unrecorded until its bulletin comes: before 15:30, today.xml holds the day before's.
- When TCMB cannot be reached, the reference rates fill the days it left, once a run, kept under their own source;
  TCMB is asked again for its own days on a later run.

A provider's failure is recorded and logged at WARNING, shown on the System screen, never raised to one: everything
else works without the network, with the documents' own rates.
"""

import logging
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from datetime import time as clock
from typing import Any

from ..domain.codes import RateSource
from ..fx import ecb, frankfurter, tcmb
from ..fx.book import PREFERENCE, Quote
from ..fx.provider import ProviderError, Span, weekdays
from ..settings import config
from ..storage import feed_state, fx_rates, jobs
from ..storage.db import Database, now
from . import kinds
from .workspace import Workspace, file_lock

# What the API names from here: the use cases, their records and the codes they carry.
__all__ = [
    "Fetched",
    "Pace",
    "RateSource",
    "RatesStatus",
    "SourceDays",
    "describe",
    "fetch",
    "providers",
    "providers_of",
    "request",
    "request_missing",
    "status",
    "status_of",
]

FETCH_JOB = kinds.FX_RATES
DAILY_AT = clock(16, 30)  # local time: TCMB publishes at 15:30 Istanbul time
RUN_LIMIT = 400  # days a run asks TCMB for at most
PAUSE = 0.5  # seconds between two requests
# Business days in a row without a bulletin that make TCMB's answers suspect: no holiday of Turkey's is that long,
# so its files must have moved, and those days are left unrecorded instead of marked as holidays for good.
SILENCE = 10
# The new lira came on 1 January 2005: a rate before it is in the old one, a million times larger. The history is
# never asked for further back.
EARLIEST = date(2005, 1, 1)
STATE = "fx.fetch"  # feed_state: when the last run that asked anything was, and what went wrong in it
_LOCK_NAME = ".kurlar.kilit"
_BUSY = "kurlar şu an başka bir işlemde çekiliyor; biraz sonra yeniden deneyin"
_DAY = timedelta(days=1)
_RECENT = timedelta(days=7)  # what a reference provider is asked for when the program has none of its rates yet

log = logging.getLogger("iplikci.fx")


@dataclass(frozen=True, slots=True)
class Pace:
    """How politely a run asks: a pause between two requests, at most `limit` requests to TCMB. sleep is time.sleep
    outside the tests. The reference provider's few requests come on top of the limit."""

    pause: float = PAUSE
    limit: int = RUN_LIMIT
    sleep: Callable[[float], None] = time.sleep


POLITE = Pace()


@dataclass(frozen=True, slots=True)
class Fetched:
    """How a run went."""

    asked: int  # requests made
    stored: int  # days whose rates came
    missing: int  # business days of the history the first provider was still not asked for
    error: str  # what went wrong, in Turkish; "" when nothing did
    more: bool  # it stopped at its limit while TCMB answered: the next run goes on

    @property
    def message(self) -> str:
        """The run in a sentence or two, in Turkish."""
        if not self.asked:
            text = "Çekilecek kur yoktu."
        else:
            text = f"Kur sağlayıcılarına {self.asked} istek gitti; {self.stored} günün kurları geldi."
        if self.error:
            text += f" Hata: {self.error}."
        if self.missing:
            more = " Kalanlar bir sonraki çekimde istenecek." if self.more else ""
            text += f" Geçmişte {self.missing} iş günü eksik.{more}"
        return text


@dataclass(frozen=True, slots=True)
class SourceDays:
    """What a provider gave: the newest day of its rates, and how many days of them are kept."""

    source: RateSource
    newest: date
    days: int


@dataclass(frozen=True, slots=True)
class RatesStatus:
    """Where the rates stand, for the System screen and `iplikci kur durum`."""

    providers: tuple[RateSource, ...]  # the providers the settings let the program ask, in that order; () none
    sources: tuple[SourceDays, ...]  # those whose rates are kept, TCMB first
    days: int  # days with any provider's rates
    start: date | None  # the history's first day: the oldest the data covers; None without documents
    missing: int  # business days from start to yesterday the first provider was not asked for yet
    last_run: str  # when the last fetch that asked anything ran (UTC, ISO 8601); "" if none yet
    last_error: str  # what went wrong in it, in Turkish; ""
    summary: str  # all of it in a line, in Turkish


def providers(settings: config.Settings) -> tuple[RateSource, ...]:
    """The providers the settings let the program ask, in the order it asks them: TCMB when the settings name it,
    then the first of ECB and Frankfurter they name."""
    names = settings.fx.providers
    asked = [RateSource.TCMB] if "tcmb" in names else []
    asked += [RateSource(name) for name in names if name in ("ecb", "frankfurter")][:1]
    return tuple(asked)


def providers_of(ws: Workspace) -> tuple[RateSource, ...]:
    """providers() of ws's settings as the file says now."""
    return providers(config.load(ws.layout.settings))


def first_day(db: Database) -> date | None:
    """The oldest day the data covers, of a statement's period or a row's, a receipt's too; None without any. Only a
    document read has rows."""
    value = db.scalar(
        "SELECT min(day) FROM ("
        "SELECT min(date) AS day FROM transactions UNION ALL SELECT min(date) FROM evidence "
        "UNION ALL SELECT min(nullif(start, '')) FROM statements UNION ALL SELECT min(cut_date) FROM statements "
        "UNION ALL SELECT min(nullif(period_start, '')) FROM documents WHERE status = 'processed')"
    )
    return date.fromisoformat(str(value)) if value else None


def history_start(db: Database) -> date | None:
    """Where the history begins: the data's oldest day, no further back than EARLIEST."""
    found = first_day(db)
    return None if found is None else max(found, EARLIEST)


# --- a run ----------------------------------------------------------------------------------------------------


@dataclass
class _Run:
    db: Database
    settings: config.Settings
    today: date
    pace: Pace
    progress: Callable[[int, int], None] | None
    asked: int = 0
    stored: int = 0
    more: bool = False
    errors: list[str] = field(default_factory=list[str])

    def request(self) -> None:
        """Before a request: a pause after the run's first."""
        if self.asked:
            self.pace.sleep(self.pace.pause)
        self.asked += 1

    def keep(self, day: date, source: RateSource, quotes: Iterable[Quote]) -> None:
        """A provider's answer for day: its rates, or none (it published nothing that day)."""
        if fx_rates.put(self.db, day, source, quotes):
            self.stored += 1

    def failed(self, source: RateSource, exc: ProviderError) -> None:
        self.errors.append(str(exc))
        log.warning("exchange rates: %s failed after %d requests: %s", source.value, self.asked, exc)


def fetch(
    ws: Workspace,
    history: bool = False,
    *,
    today: date | None = None,
    pace: Pace | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> Fetched:
    """Fetch the rates: today's bulletin and the business days missed since the newest one; with history, every day
    of the history not asked for yet. A provider that fails stops this run's requests to it; its error is recorded,
    never raised. pace: POLITE's when None. Busy while another process fetches."""
    day = today or date.today()
    settings = config.load(ws.layout.settings)  # as the file says now: the Settings screen may have changed it
    asked = providers(settings)
    with file_lock(ws.run, _LOCK_NAME, timeout=5.0, busy=_BUSY), ws.db() as db:
        run = _Run(db, settings, day, pace or POLITE, progress)
        start = history_start(db) if history else None
        reference = next((s for s in asked if s is not RateSource.TCMB), None)
        if RateSource.TCMB in asked:
            left = _from_tcmb(run, start, history)
            if left and reference is not None:
                _from_reference(run, reference, left)  # once a run, for what TCMB left
        elif reference is not None:
            _from_reference(run, reference, _reference_days(db, reference, start, day))
        if run.asked:
            feed_state.save(db, STATE, {"at": now(), "error": "; ".join(run.errors), "asked": run.asked})
        found = _missing(db, asked[0], history_start(db), day) if asked else 0
    return Fetched(run.asked, run.stored, found, "; ".join(run.errors), run.more and not run.errors)


@dataclass
class _Tcmb:
    """A run's requests to TCMB: the days it was asked for before, the days answered in this run, and the days in a
    row that answered 404, recorded once a bulletin breaks the row."""

    run: _Run
    asked: dict[date, fx_rates.Asked]
    total: int  # requests this run means to make, for the progress
    done: set[date] = field(default_factory=set[date])
    silent: list[date] = field(default_factory=list[date])

    def keep(self, day: date, quotes: Iterable[Quote]) -> None:
        if day not in self.asked and day not in self.done:
            self.run.keep(day, RateSource.TCMB, quotes)
            self.done.add(day)

    def today(self) -> None:
        """Today's bulletin: before 15:30, and on a holiday, an earlier day's, which leaves today for a later run."""
        self.run.request()
        bulletin = tcmb.fetch_today(self.run.settings)
        self.keep(bulletin.day, bulletin.quotes)
        self.tell()

    def day(self, day: date) -> None:
        """The bulletin of day; a 404 marks day as one without a bulletin, unless SILENCE days answer so in a row."""
        self.run.request()
        bulletin = tcmb.fetch_day(day, self.run.settings)
        self.tell()
        if bulletin is None:
            self.silent.append(day)
            if len(self.silent) >= SILENCE:
                raise ProviderError(f"TCMB {SILENCE} iş günü üst üste bülten vermedi; adresi değişmiş olabilir")
            return
        self.settle()
        self.keep(bulletin.day, bulletin.quotes)
        self.keep(day, ())  # a file holding another day's bulletin: nothing of day's own

    def settle(self) -> None:
        """The days of the row of 404s: none of them had a bulletin."""
        for day in self.silent:
            self.keep(day, ())
        self.silent.clear()

    def tell(self) -> None:
        if self.run.progress is not None:
            self.run.progress(self.run.asked, self.total)


def _from_tcmb(run: _Run, start: date | None, history: bool) -> list[date]:
    """Ask TCMB for today's bulletin and the days it was not asked for: from start with history, else from the
    newest bulletin on. The days it left unanswered because it could not be reached: the reference fills them."""
    asked = fx_rates.asked(run.db, RateSource.TCMB)
    newest = max((d for d, a in asked.items() if a.published), default=None)
    first = start if history else newest + _DAY if newest is not None else None
    due = sorted((d for d in weekdays(first, run.today - _DAY) if d not in asked), reverse=True) if first else []
    wanted = [run.today] if run.today.weekday() < 5 and run.today not in asked else []
    ask = _Tcmb(run, asked, min(len(wanted) + len(due), run.pace.limit))
    try:
        if wanted:
            ask.today()
        for day in (d for d in due if d not in ask.done):
            if run.asked >= run.pace.limit:
                run.more = True
                break
            ask.day(day)
        ask.settle()
    except ProviderError as exc:
        run.failed(RateSource.TCMB, exc)
        return [d for d in [*wanted, *due] if d not in ask.done]
    return []


def _reference_days(db: Database, source: RateSource, start: date | None, today: date) -> list[date]:
    """The days to ask a reference provider for when it stands in TCMB's place: the history's from start, else the
    ones since its newest day (the last week when it gave none yet); today among them, in case it was published."""
    asked = fx_rates.asked(db, source)
    if start is None:
        newest = max((d for d, a in asked.items() if a.published), default=None)
        start = newest + _DAY if newest is not None else today - _RECENT
    return [d for d in weekdays(start, today) if d not in asked]


def _from_reference(run: _Run, source: RateSource, wanted: Sequence[date]) -> None:
    """The wanted days from a reference provider, in one answer (or one a year, Frankfurter's): the days it was not
    asked for yet. A business day its answer covers without rates had none published; a day after the newest it
    covers is left for a later run."""
    asked = fx_rates.asked(run.db, source)
    due = sorted(d for d in wanted if d not in asked)
    if not due:
        return
    try:
        for span in _reference_spans(run, source, due[0], due[-1]):  # each kept as it comes
            given = {d.day: d.quotes for d in span.days}
            for day in due:
                if span.first <= day <= span.last:
                    run.keep(day, source, given.get(day, ()))
    except ProviderError as exc:
        run.failed(source, exc)


def _reference_spans(run: _Run, source: RateSource, start: date, end: date) -> Iterator[Span]:
    if source is RateSource.ECB:
        run.request()
        found = ecb.fetch(start, end, run.today, run.settings)
        if found is not None:
            yield found
        return
    for first, last in frankfurter.spans(start, end):
        run.request()
        found = frankfurter.fetch(first, last, run.settings)
        if found is not None:
            yield found


def _missing(db: Database, source: RateSource, start: date | None, today: date) -> int:
    """The business days from start to yesterday the provider was not asked for yet."""
    if start is None or start >= today:
        return 0
    total = sum(1 for _ in weekdays(start, today - _DAY))
    done = db.scalar(
        "SELECT count(*) FROM fx_days WHERE source = ? AND day >= ? AND day < ? "
        "AND strftime('%w', day) NOT IN ('0', '6')",
        (source.value, start.isoformat(), today.isoformat()),
    )
    return max(0, total - int(done or 0))


# --- asking the service -----------------------------------------------------------------------------------------


def request(ws: Workspace, history: bool = False) -> None:
    """Ask the service for a fetch: today's bulletin and the days missed since the newest one; with history, every
    missing day of the history. Asked twice before it starts, it fetches once."""
    with ws.db() as db:
        jobs.add(db, FETCH_JOB, {"history": history})


def request_missing(ws: Workspace, today: date | None = None) -> bool:
    """At the service's start: queue the history's fetch when its first provider was not asked for a day of it yet;
    whether it was queued."""
    asked = providers(config.load(ws.layout.settings))
    with ws.db() as db:
        if not asked or not _missing(db, asked[0], history_start(db), today or date.today()):
            return False
        return jobs.add(db, FETCH_JOB, {"history": True}) is not None


# --- where the rates stand --------------------------------------------------------------------------------------

_NEWEST = {
    RateSource.TCMB: "TCMB'nin son bülteni",
    RateSource.ECB: "ECB'nin son kuru",
    RateSource.FRANKFURTER: "Frankfurter'in son kuru",
}


def status(ws: Workspace, today: date | None = None) -> RatesStatus:
    with ws.db() as db:
        return status_of(db, config.load(ws.layout.settings), today or date.today())


def status_of(db: Database, settings: config.Settings, today: date) -> RatesStatus:
    asked = providers(settings)
    kept = {
        RateSource(r["source"]): SourceDays(RateSource(r["source"]), date.fromisoformat(r["newest"]), int(r["days"]))
        for r in db.rows("SELECT source, max(day) AS newest, count(DISTINCT day) AS days FROM fx_rates GROUP BY 1")
    }
    sources = tuple(kept[s] for s in PREFERENCE if s in kept)
    days = int(db.scalar("SELECT count(DISTINCT day) FROM fx_rates") or 0)
    start = history_start(db)
    missing = _missing(db, asked[0], start, today) if asked else 0
    state: dict[str, Any] = feed_state.load(db, STATE) or {}
    found = RatesStatus(asked, sources, days, start, missing, str(state.get("at", "")), str(state.get("error", "")), "")
    return replace(found, summary=describe(found))


def describe(found: RatesStatus) -> str:
    """The status in a line: "TCMB'nin son bülteni 02.11.2026 · 214 günün kurları saklı · geçmiş tamam"."""
    if not found.providers and not found.sources:
        return "ağdan çekilmiyor (ayarlarda kur sağlayıcısı yok); belgelerdeki kurlar kullanılıyor"
    parts = [", ".join(f"{_NEWEST[s.source]} {s.newest:%d.%m.%Y}" for s in found.sources) or "henüz kur yok"]
    if found.days:
        parts.append(f"{found.days} günün kurları saklı")
    if not found.providers:
        parts.append("ağdan çekilmiyor (ayarlarda kur sağlayıcısı yok)")
    elif found.start is None:
        parts.append("geçmiş kurlar ilk belge gelince çekilir")
    else:
        parts.append(f"{found.missing} iş günü eksik" if found.missing else "geçmiş tamam")
    if found.last_error:
        parts.append(f"son hata: {found.last_error}")
    return " · ".join(parts)
