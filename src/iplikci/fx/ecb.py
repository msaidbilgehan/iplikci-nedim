"""ECB's euro reference rates (architecture §15): one rate a currency and TARGET business day, for a euro, published
around 16:00 CET. They come in when TCMB cannot be reached, or when the settings name no TCMB. Nothing but the
address goes out (ADR-0009).

A currency's rate in TL is TRY per euro divided by the currency's own rate per euro; the euro's is TRY per euro
itself. A reference rate is one rate, so both sides of the quote take it. The euro's rate is kept as published;
another's quotient is rounded to six decimals, finer than ECB writes any rate, halves away from zero.

The 90-day file holds the last three months, newest first. The whole history since 1999 comes as a zip with one CSV
in it, opened within limits: a CSV that unpacks to more than CSV_LIMIT is refused, as a zip bomb would be.
"""

import csv
import io
import re
import zipfile
import zlib
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation

from .. import egress
from ..domain.codes import RateSource
from ..domain.money import round_half_up
from ..settings.config import Settings
from . import provider
from .book import Quote
from .provider import Day, ProviderError, Span

HOST = egress.ECB
NAME = "ECB"
RECENT = "/stats/eurofxref/eurofxref-hist-90d.xml"
HISTORY = "/stats/eurofxref/eurofxref-hist.zip"
RECENT_DAYS = 85  # a span that begins fewer days back than this is in the 90-day file
DIGITS = 6
CSV_LIMIT = 16 << 20  # the history's CSV unpacks to about 2 MB
LIRA = "TRY"
_CODE = re.compile(r"[A-Z]{3}")


def tl_rates(day: date, per_euro: Mapping[str, Decimal], source: RateSource) -> tuple[Quote, ...]:
    """A day's TL rates from its rates per euro; none without the lira's own (ECB has it from 2005 on). A rate so
    far off that its quotient has no six decimals within Decimal's precision makes the answer unreadable."""
    lira = per_euro.get(LIRA)
    if lira is None:
        return ()
    quotes = [Quote(day, "EUR", lira, lira, source)]
    for code, rate in sorted(per_euro.items()):
        if code not in (LIRA, "EUR"):
            try:
                value = round_half_up(lira / rate, DIGITS)
            except InvalidOperation:
                raise ProviderError(f"{source.value} yanıtında okunamayan bir kur var ({code})") from None
            quotes.append(Quote(day, code, value, value, source))
    return tuple(quotes)


def parse_xml(data: bytes) -> list[Day]:
    """The days of a reference rate file (the daily or the 90-day one), the oldest first."""
    root = provider.xml(data, NAME)
    days: list[Day] = []
    for cube in root.iter():
        when = cube.get("time")
        if provider.local(cube.tag) != "Cube" or when is None:
            continue
        try:
            day = date.fromisoformat(when)
        except ValueError:
            raise ProviderError("ECB kurlarının tarihi okunamadı") from None
        per_euro: dict[str, Decimal] = {}
        for child in cube:
            code, rate = (child.get("currency") or "").strip().upper(), provider.number(child.get("rate"))
            if _CODE.fullmatch(code) and rate is not None:
                per_euro[code] = rate
        days.append(Day(day, tl_rates(day, per_euro, RateSource.ECB)))
    if not any(d.quotes for d in days):  # a changed layout must not pass for days without rates
        raise ProviderError("ECB yanıtında TL kuru yok")
    return sorted(days, key=lambda d: d.day)


def parse_zip(data: bytes, start: date, end: date) -> Span | None:
    """The history's days from start to end (both included), and the part of that span the history covers; None
    when it covers none of it. Only those days' rates are worked out: the history holds every day since 1999."""
    try:
        rows = iter(list(csv.reader(io.StringIO(_history_text(data)))))
    except csv.Error as exc:  # a NUL, a field longer than the csv module takes
        raise ProviderError("ECB geçmişi okunamadı") from exc
    header = next(rows, None)
    if not header or header[0].strip() != "Date":
        raise ProviderError("ECB geçmişi beklenen biçimde değil")
    codes = [h.strip().upper() for h in header[1:]]
    if LIRA not in codes:  # a changed layout must not pass for days without rates
        raise ProviderError("ECB geçmişinde TL kuru yok")
    days: list[Day] = []
    seen: list[date] = []
    for row in rows:
        if not row or not row[0].strip():
            continue
        try:
            day = date.fromisoformat(row[0].strip())
        except ValueError:
            raise ProviderError("ECB geçmişinde bir tarih okunamadı") from None
        seen.append(day)
        if not start <= day <= end:
            continue
        per_euro: dict[str, Decimal] = {}
        for code, written in zip(codes, row[1:], strict=False):  # the header ends with an empty column
            rate = provider.number(written)
            if _CODE.fullmatch(code) and rate is not None:
                per_euro[code] = rate
        days.append(Day(day, tl_rates(day, per_euro, RateSource.ECB)))
    if not seen:
        raise ProviderError("ECB geçmişinde kur yok")
    first, last = max(start, min(seen)), min(end, max(seen))
    if first > last:
        return None
    return Span(tuple(sorted(days, key=lambda d: d.day)), first, last)


def _history_text(data: bytes) -> str:
    """The CSV in the history's zip, read no further than CSV_LIMIT."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [m for m in archive.infolist() if m.filename.lower().endswith(".csv")]
            if len(members) != 1:
                raise ProviderError("ECB geçmişi beklenen biçimde değil")
            if members[0].file_size > CSV_LIMIT:
                raise ProviderError("ECB geçmişi beklenenden büyük; açılmadı")
            with archive.open(members[0]) as member:
                raw = member.read(CSV_LIMIT + 1)  # the size the zip states may lie
    except (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, EOFError, RuntimeError, NotImplementedError) as exc:
        raise ProviderError("ECB geçmişi açılamadı") from exc
    if len(raw) > CSV_LIMIT:
        raise ProviderError("ECB geçmişi beklenenden büyük; açılmadı")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ProviderError("ECB geçmişi okunamadı") from None


def fetch(start: date, end: date, today: date, settings: Settings) -> Span | None:
    """The days from start to end, from the smaller file that holds them: the 90-day one for a span that begins in
    the last RECENT_DAYS days, else the whole history. None when the answer covers none of them."""
    if (today - start).days < RECENT_DAYS:
        return provider.span(parse_xml(provider.body(HOST, RECENT, settings, NAME)), start, end)
    return parse_zip(provider.body(HOST, HISTORY, settings, NAME), start, end)
