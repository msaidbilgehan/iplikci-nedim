"""What the rate providers share (ADR-0009): one GET through egress, an answer read as the untrusted input it is,
and what a provider published for a day.

An answer comes from the network: XML that declares a document type or an entity is refused before it is parsed, so
the parser never expands or fetches anything, and every answer stays within egress's 1 MB.
"""

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .. import egress
from ..settings.config import Settings
from .book import Quote

_DECLARATION = re.compile(rb"<!\s*(?:DOCTYPE|ENTITY)", re.IGNORECASE)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


class ProviderError(Exception):
    """A provider could not be reached, or its answer could not be read; the message says which and why, in Turkish,
    and names no path."""


@dataclass(frozen=True, slots=True)
class Day:
    """A provider's rates of one day, in TL for one unit; none when it published nothing that day."""

    day: date
    quotes: tuple[Quote, ...]


@dataclass(frozen=True, slots=True)
class Span:
    """A reference provider's answer for a span of days: the days it gave, and the days it covers, first to last. A
    business day between them that it gave no rates for had none published (a TARGET holiday); a day outside them
    the answer does not tell of."""

    days: tuple[Day, ...]
    first: date
    last: date


def span(days: list[Day], start: date, end: date) -> Span | None:
    """days, an answer holding days of its own from the oldest to the newest, cut to start..end; None when the answer
    covers none of those days."""
    if not days:
        return None
    first, last = max(start, days[0].day), min(end, days[-1].day)
    if first > last:
        return None
    return Span(tuple(d for d in days if first <= d.day <= last), first, last)


def get(host: str, path: str, settings: Settings, name: str) -> tuple[int, bytes]:
    """path asked of host: the answer's status and body. ProviderError when no answer came."""
    try:
        return egress.https_get(host, path, settings)
    except (egress.Unreachable, egress.Refused) as exc:  # their messages name the host only
        raise ProviderError(f"{name}: {exc}") from exc


def body(host: str, path: str, settings: Settings, name: str) -> bytes:
    """What path on host holds; ProviderError unless the answer is a 200."""
    status, data = get(host, path, settings, name)
    if status != 200:
        raise ProviderError(f"{name} {status} yanıtı verdi")
    return data


def xml(data: bytes, name: str) -> ET.Element:
    """data read as XML, once it is UTF-8 and declares no document type and no entity."""
    text = data.removeprefix(b"\xef\xbb\xbf")
    if b"\x00" in text:  # UTF-16 or UTF-32: a declaration in it would slip past the check below
        raise ProviderError(f"{name} yanıtı okunamadı: UTF-8 değil")
    if _DECLARATION.search(text):
        raise ProviderError(f"{name} yanıtı bir DOCTYPE ya da ENTITY bildiriyor; okunmadı")
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise ProviderError(f"{name} yanıtı okunamadı: XML değil") from exc


def local(tag: str) -> str:
    """An XML tag without its namespace: ECB's elements carry one."""
    return tag.rpartition("}")[2]


def number(text: str | None) -> Decimal | None:
    """A positive decimal number as the providers write it ("49.8827"), exactly; None for an empty or another
    value."""
    written = (text or "").strip()
    if not _NUMBER.fullmatch(written):
        return None
    value = Decimal(written)
    return value if value > 0 else None


def weekdays(start: date, end: date) -> Iterator[date]:
    """Monday to Friday from start to end, both included: the days a provider may publish on."""
    day = start
    while day <= end:
        if day.weekday() < 5:
            yield day
        day += timedelta(days=1)
