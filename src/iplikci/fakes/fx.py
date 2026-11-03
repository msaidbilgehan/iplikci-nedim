"""Fake answers of the exchange rate providers (architecture §15), laid out as the providers write them: TCMB's daily
bulletin as XML, ECB's reference rates as XML and as the zip of their history, Frankfurter's JSON for the days and
rates given, and EVDS's JSON of a monthly series such as TÜFE. The figures are made up. The tests and the demo data
folder read them through the providers' own readers (iplikci.fx), so nothing here needs the network.
"""

import io
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from xml.sax.saxutils import escape, quoteattr

# Names a bulletin gives the currencies the fakes use, in Turkish and in English.
_NAMES = {
    "USD": ("ABD DOLARI", "US DOLLAR"),
    "EUR": ("EURO", "EURO"),
    "GBP": ("İNGİLİZ STERLİNİ", "POUND STERLING"),
    "JPY": ("JAPON YENİ", "JAPENESE YEN"),
    "CHF": ("İSVİÇRE FRANGI", "SWISS FRANK"),
    "XDR": ("ÖZEL ÇEKME HAKKI (SDR)", "SPECIAL DRAWING RIGHT (SDR)"),
}


@dataclass(frozen=True)
class TcmbRate:
    """A currency on a TCMB bulletin as the bulletin writes it: its rates for `unit` units. A rate left None is an
    empty element, as TCMB leaves the rates it does not give."""

    code: str
    buying: str | None  # ForexBuying, e.g. "49.8827"
    selling: str | None  # ForexSelling
    unit: int = 1


def _element(name: str, text: str | None) -> str:
    return f"<{name}>{escape(text)}</{name}>" if text else f"<{name}/>"


def tcmb_xml(day: date, rates: Sequence[TcmbRate], number: int = 1) -> bytes:
    """A bulletin of day, as /kurlar/today.xml and the day's own file give it."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?xml-stylesheet type="text/xsl" href="isokur.xsl"?>',
        f'<Tarih_Date Tarih="{day:%d.%m.%Y}" Date="{day:%m/%d/%Y}" Bulten_No="{day.year}/{number}" >',
    ]
    for order, rate in enumerate(rates):
        turkish, english = _NAMES.get(rate.code, (rate.code, rate.code))
        code = quoteattr(rate.code)
        lines += [
            f"\t<Currency CrossOrder={quoteattr(str(order))} Kod={code} CurrencyCode={code}>",
            f"\t\t\t<Unit>{rate.unit}</Unit>",
            f"\t\t\t<Isim>{escape(turkish)}</Isim>",
            f"\t\t\t<CurrencyName>{escape(english)}</CurrencyName>",
            f"\t\t\t{_element('ForexBuying', rate.buying)}",
            f"\t\t\t{_element('ForexSelling', rate.selling)}",
            f"\t\t\t{_element('BanknoteBuying', rate.buying)}",
            f"\t\t\t{_element('BanknoteSelling', rate.selling)}",
            "\t\t\t\t<CrossRateUSD/>",
            "\t\t\t\t<CrossRateOther/>",
            "\t</Currency>",
        ]
    lines.append("</Tarih_Date>")
    return "\n".join(lines).encode("utf-8")


def ecb_xml(days: Mapping[date, Mapping[str, str]]) -> bytes:
    """A reference rate file (the daily one holds one day, the 90-day one three months): each day's rates for a euro,
    TRY among them, the newest day first."""
    cubes = "".join(
        f"\t\t<Cube time='{day.isoformat()}'>\n"
        + "".join(f"\t\t\t<Cube currency='{code}' rate='{rate}'/>\n" for code, rate in rates.items())
        + "\t\t</Cube>\n"
        for day, rates in sorted(days.items(), reverse=True)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" '
        'xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">\n'
        "\t<gesmes:subject>Reference rates</gesmes:subject>\n"
        "\t<gesmes:Sender>\n\t\t<gesmes:name>European Central Bank</gesmes:name>\n\t</gesmes:Sender>\n"
        f"\t<Cube>\n{cubes}\t</Cube>\n"
        "</gesmes:Envelope>\n"
    ).encode()


def ecb_zip(days: Mapping[date, Mapping[str, str]]) -> bytes:
    """The history's zip: eurofxref-hist.csv, a column per currency, "N/A" where a day has no rate, the newest day
    first and every line ending with a comma, as ECB writes it."""
    codes = sorted({code for rates in days.values() for code in rates})
    lines = ["Date," + "".join(f"{code}," for code in codes)]
    lines += [
        f"{day.isoformat()}," + "".join(f"{rates.get(code, 'N/A')}," for code in codes)
        for day, rates in sorted(days.items(), reverse=True)
    ]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        member = zipfile.ZipInfo("eurofxref-hist.csv", date_time=(2026, 1, 1, 0, 0, 0))
        archive.writestr(member, "\n".join(lines) + "\n", compress_type=zipfile.ZIP_DEFLATED)
    return out.getvalue()


def frankfurter_json(days: Mapping[date, Mapping[str, str]]) -> bytes:
    """Frankfurter's answer for a span: each day's rates for a euro, the numbers written as given."""
    ordered = sorted(days.items())
    rates = ",".join(
        f'"{day.isoformat()}":{{' + ",".join(f'"{code}":{rate}' for code, rate in day_rates.items()) + "}"
        for day, day_rates in ordered
    )
    first, last = (ordered[0][0].isoformat(), ordered[-1][0].isoformat()) if ordered else ("", "")
    return f'{{"amount":1.0,"base":"EUR","start_date":"{first}","end_date":"{last}","rates":{{{rates}}}}}'.encode()


def evds_json(months: Mapping[str, str | None], series: str = "TP.FG.J0") -> bytes:
    """EVDS's answer for a monthly series: each YYYY-MM written "YYYY-M" as EVDS writes it, its value as text, or null
    for a month not published yet; the series' dots as underscores."""
    column = series.replace(".", "_")
    items: list[str] = []
    for month, value in sorted(months.items()):
        year, number = month.split("-")
        written = "null" if value is None else f'"{value}"'
        items.append(f'{{"Tarih":"{year}-{int(number)}","{column}":{written},"UNIXTIME":{{"$numberLong":"0"}}}}')
    return f'{{"totalCount":{len(items)},"items":[{",".join(items)}]}}'.encode()


# --- made-up rates that move a little from day to day -----------------------------------------------------------

ORIGIN = date(2026, 1, 1)
# TL for one unit on ORIGIN and its rise a day; a day before ORIGIN has ORIGIN's rate (all made up).
_DRIFT = {
    "EUR": (Decimal("50.3000"), Decimal("0.0190")),
    "USD": (Decimal("42.9500"), Decimal("0.0230")),
    "GBP": (Decimal("57.6000"), Decimal("0.0210")),
}
_WOBBLE = (Decimal("0.0000"), Decimal("0.0412"), Decimal("-0.0175"), Decimal("0.0236"), Decimal("-0.0318"))
_MARGIN = Decimal("1.0018")  # the selling rate over the buying one
_PLACES = Decimal("0.0001")


def tcmb_rates(day: date) -> list[TcmbRate]:
    """A made-up bulletin's EUR, USD and GBP rates on day, as TCMB writes them."""
    n = max(0, (day - ORIGIN).days)
    rates: list[TcmbRate] = []
    for code, (start, rise) in _DRIFT.items():
        buying = (start + rise * n + _WOBBLE[day.weekday() % 5]).quantize(_PLACES)
        rates.append(TcmbRate(code, str(buying), str((buying * _MARGIN).quantize(_PLACES))))
    return rates


def reference_rates(day: date) -> dict[str, str]:
    """Made-up reference rates for a euro on day, in line with tcmb_rates: TRY, USD and GBP."""
    tl = {rate.code: Decimal(rate.buying or "0") for rate in tcmb_rates(day)}
    lira = tl["EUR"]
    return {
        "USD": str((lira / tl["USD"]).quantize(_PLACES)),
        "GBP": str((lira / tl["GBP"]).quantize(_PLACES)),
        "TRY": str(lira),
    }
