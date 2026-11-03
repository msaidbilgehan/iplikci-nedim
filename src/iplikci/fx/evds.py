"""TCMB's EVDS (Elektronik Veri Dağıtım Sistemi): the monthly consumer price index TÜFE (TP.FG.J0, 2003=100), for the
spending trend in real terms (F12's V1+ part; inflation.py). Only with the user's own key, which EVDS gives a
registered user on their profile page; nothing else goes out but the series' code and the span (ADR-0009).

A request is a GET with the parameters in the path and no "?":

    /igmevdsms-dis/series=TP.FG.J0&startDate=01-01-2025&endDate=31-12-2026&type=json

and the key in its `key` header (EVDS refuses a key in the address since 2024-04-05). The answer is JSON:

    {"totalCount": 22, "items": [{"Tarih": "2025-1", "TP_FG_J0": "3021.45", "UNIXTIME": {...}}, ...]}

the series' dots turned into underscores, a month written "YYYY-M", and a month TÜFE is not out for yet null. An
answer holds at most 1000 observations: 83 years of months. A refused key is answered 401 or 403.
"""

import json
import re
from datetime import date
from decimal import Decimal
from typing import cast

from .. import egress
from ..settings.config import Settings
from . import provider
from .provider import ProviderError

HOST = egress.EVDS
NAME = "EVDS"
TUFE = "TP.FG.J0"  # the consumer price index (2003=100), monthly
REFUSED = frozenset({401, 403})
_MONTH = re.compile(r"([0-9]{4})-([0-9]{1,2})")


class KeyRefused(ProviderError):
    """EVDS did not take the key: it was mistyped, or EVDS no longer knows it."""


def path(series: str, start: date, end: date) -> str:
    return f"/igmevdsms-dis/series={series}&startDate={start:%d-%m-%Y}&endDate={end:%d-%m-%Y}&type=json"


def month(when: str) -> str | None:
    """A monthly series' date as EVDS writes it ("2025-1") as YYYY-MM; None for any other."""
    found = _MONTH.fullmatch(when)
    if found is None or not 1 <= int(found[2]) <= 12:
        return None
    return f"{found[1]}-{int(found[2]):02d}"


def parse(data: bytes, series: str = TUFE) -> dict[str, Decimal]:
    """An answer's months and their values, by YYYY-MM; a month without a value yet is left out."""
    try:
        found: object = json.loads(data, parse_float=Decimal, parse_int=Decimal)  # a number exactly as written
    except (ValueError, RecursionError) as exc:  # a JSONDecodeError, a UnicodeDecodeError; too deep a nesting
        raise ProviderError("EVDS yanıtı okunamadı: JSON değil") from exc
    if not isinstance(found, dict):
        raise ProviderError("EVDS yanıtı beklenen biçimde değil")
    items = cast(dict[str, object], found).get("items")
    if not isinstance(items, list):
        raise ProviderError("EVDS yanıtında gözlem listesi yok")
    column = series.replace(".", "_")
    months: dict[str, Decimal] = {}
    for item in cast(list[object], items):
        if not isinstance(item, dict):
            raise ProviderError("EVDS yanıtında bir gözlem okunamadı")
        fields = cast(dict[str, object], item)
        when, value = fields.get("Tarih"), fields.get(column)
        written = month(when) if isinstance(when, str) else None
        if written is None:
            raise ProviderError("EVDS yanıtında aylık bir tarih okunamadı")
        if value is None or value == "":
            continue  # not published yet
        number = provider.number(value if isinstance(value, str) else str(value))
        if number is None:
            raise ProviderError(f"EVDS yanıtında {written} değeri okunamadı")
        months[written] = number
    return months


def fetch(key: str, start: date, end: date, settings: Settings, series: str = TUFE) -> dict[str, Decimal]:
    """The series' months from start to end, by YYYY-MM. KeyRefused when EVDS did not take the key, ProviderError
    when it could not be reached or its answer could not be read; neither message holds the key."""
    try:
        status, data = egress.https_get(HOST, path(series, start, end), settings, headers={"key": key})
    except (egress.Unreachable, egress.Refused) as exc:  # their messages name the host only
        raise ProviderError(f"{NAME}: {exc}") from exc
    if status in REFUSED:
        raise KeyRefused("EVDS anahtarı kabul etmedi: anahtarı EVDS'deki profil sayfanızdan yeniden kopyalayın")
    if status != 200:
        raise ProviderError(f"{NAME} {status} yanıtı verdi")
    return parse(data, series)
