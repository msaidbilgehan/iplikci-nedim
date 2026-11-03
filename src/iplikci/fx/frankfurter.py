"""Frankfurter (api.frankfurter.dev): ECB's reference rates as JSON, for a span of days (architecture §15), asked in
place of ECB when the settings name it first. Only the span goes out (ADR-0009).

A span is asked a year at a time, each answer well within egress's 1 MB, and from a week before its first day: the
answer then holds a business day before the span, so a span that begins on a holiday is known to have had no rates
that day. The rates are ECB's, read as ecb.tl_rates reads them and stored as Frankfurter's own.
"""

import json
import re
from datetime import date, timedelta
from decimal import Decimal
from typing import cast

from .. import egress
from ..domain.codes import RateSource
from ..settings.config import Settings
from . import ecb, provider
from .provider import Day, ProviderError, Span

HOST = egress.FRANKFURTER
NAME = "Frankfurter"
YEAR = timedelta(days=365)  # a request covers at most a year and a day
LEAD = timedelta(days=7)  # asked before a span's first day
_CODE = re.compile(r"[A-Z]{3}")


def path(start: date, end: date) -> str:
    return f"/v1/{start.isoformat()}..{end.isoformat()}?base=EUR"


def spans(start: date, end: date) -> list[tuple[date, date]]:
    """start..end in the pieces asked one request each, the oldest first."""
    pieces: list[tuple[date, date]] = []
    while start <= end:
        pieces.append((start, min(end, start + YEAR)))
        start += YEAR + timedelta(days=1)
    return pieces


def _object(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProviderError(f"Frankfurter yanıtı beklenen biçimde değil ({what})")
    return {str(k): v for k, v in cast(dict[object, object], value).items()}


def parse(data: bytes) -> list[Day]:
    """An answer's days, the oldest first."""
    try:
        found = _object(json.loads(data, parse_float=Decimal, parse_int=Decimal), "yanıt")
    except (ValueError, RecursionError) as exc:  # a JSONDecodeError, a UnicodeDecodeError; too deep a nesting
        raise ProviderError("Frankfurter yanıtı okunamadı: JSON değil") from exc
    if found.get("base") != "EUR" or found.get("amount", Decimal(1)) != 1:
        raise ProviderError("Frankfurter yanıtı bir avronun kurlarını vermiyor")
    days: list[Day] = []
    for when, rates in _object(found.get("rates"), "rates").items():
        try:
            day = date.fromisoformat(when)
        except ValueError:
            raise ProviderError("Frankfurter yanıtında bir tarih okunamadı") from None
        per_euro = {
            code: rate
            for code, rate in _object(rates, when).items()
            if _CODE.fullmatch(code) and isinstance(rate, Decimal) and rate > 0
        }
        days.append(Day(day, ecb.tl_rates(day, per_euro, RateSource.FRANKFURTER)))
    return sorted(days, key=lambda d: d.day)


def fetch(start: date, end: date, settings: Settings) -> Span | None:
    """One piece of spans(): the days from start to end, as far as the answer covers them; None when it covers none."""
    return provider.span(parse(provider.body(HOST, path(start - LEAD, end), settings, NAME)), start, end)
