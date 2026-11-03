"""TCMB's daily bulletin (architecture §15): the Central Bank's indicative rates, published on business days at 15:30
Istanbul time, in TL for a unit of each currency. Only the day goes out (ADR-0009).

`today.xml` holds the newest bulletin: before the day's is published, and on a weekend or a holiday, that is an
earlier day's, so a bulletin's day is the one it names (Tarih), never the day asked. Every day has a file of its own,
/kurlar/YYYYMM/DDMMYYYY.xml; for a day without a bulletin the answer is 404.

A currency's rates are its forex buying and selling rates (ForexBuying, ForexSelling) divided by its unit: the yen is
quoted for 100. A currency the bulletin gives no forex rate for is left out: the SDR has none to sell.
"""

import re
from datetime import date, datetime

from .. import egress
from ..domain.codes import RateSource
from ..settings.config import Settings
from . import provider
from .book import Quote
from .provider import Day, ProviderError

HOST = egress.TCMB
NAME = "TCMB"
TODAY = "/kurlar/today.xml"
_CODE = re.compile(r"[A-Z]{3}")


def day_path(day: date) -> str:
    """Where the bulletin of day is: 2 November 2026's is /kurlar/202611/02112026.xml."""
    return f"/kurlar/{day:%Y%m}/{day:%d%m%Y}.xml"


def parse(data: bytes) -> Day:
    """A bulletin's day and its rates. ProviderError for anything but a bulletin with at least one rate: a page of
    another kind, or a bulletin whose layout changed, must not pass for a day without rates."""
    root = provider.xml(data, NAME)
    if root.tag != "Tarih_Date":
        raise ProviderError("TCMB yanıtı bir kur bülteni değil")
    try:
        day = datetime.strptime(root.get("Tarih", ""), "%d.%m.%Y").date()
    except ValueError:
        raise ProviderError("TCMB bülteninin tarihi okunamadı") from None
    quotes: list[Quote] = []
    for currency in root.findall("Currency"):
        code = (currency.get("CurrencyCode") or currency.get("Kod") or "").strip().upper()
        unit = provider.number(currency.findtext("Unit"))
        buying = provider.number(currency.findtext("ForexBuying"))
        selling = provider.number(currency.findtext("ForexSelling"))
        if not _CODE.fullmatch(code) or unit is None or buying is None or selling is None:
            continue
        quotes.append(Quote(day, code, buying / unit, selling / unit, RateSource.TCMB))
    if not quotes:
        raise ProviderError(f"TCMB bülteninde kur yok ({day:%d.%m.%Y})")
    return Day(day, tuple(quotes))


def fetch_today(settings: Settings) -> Day:
    """The newest bulletin: today's once it is published, else an earlier day's."""
    return parse(provider.body(HOST, TODAY, settings, NAME))


def fetch_day(day: date, settings: Settings) -> Day | None:
    """The bulletin of day; None when TCMB published none that day (a weekend, a holiday)."""
    status, data = provider.get(HOST, day_path(day), settings, NAME)
    if status == 404:
        return None
    if status != 200:
        raise ProviderError(f"TCMB {status} yanıtı verdi")
    return parse(data)
