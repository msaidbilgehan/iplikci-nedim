"""Amounts and dates as Turkish bank documents print them, shared by every reader."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ..domain.money import round_half_up
from ..domain.text import fold


def squash(s: str) -> str:
    """fold() without any whitespace, for PDFs that drop the spaces between words."""
    return fold(s).replace(" ", "")


# Turkish number format as printed on statements: "1.234,56", "-12.345,67",
# "+123,45", "1.234,00+" (Garanti credit), "TL.1.500,-" / "-TL.2.345,-" (TEB).
_TR_AMOUNT = re.compile(
    r"^(?P<lead>[+-])?(?:TL\.?)?(?P<int>\d{1,3}(?:\.\d{3})+|\d+),(?P<frac>\d{1,2}|-)(?P<trail>[+-])?$"
)


def parse_tr_amount(text: str) -> Decimal | None:
    """Parse a Turkish-format amount. A leading '-' or a trailing '+'/'-' makes it negative."""
    m = _TR_AMOUNT.match(text.replace(" ", ""))
    if not m:
        return None
    frac = m["frac"]
    cents = 0 if frac == "-" else int(frac.ljust(2, "0"))
    value = Decimal(int(m["int"].replace(".", "")) * 100 + cents).scaleb(-2)
    return -value if m["lead"] == "-" or m["trail"] in ("+", "-") else value


def is_tr_amount(text: str) -> bool:
    return parse_tr_amount(text) is not None


_US_AMOUNT = re.compile(r"^\d{1,3}(?:,\d{3})*(?:\.\d+)?$|^\d+(?:\.\d+)?$")


def parse_us_amount(text: str) -> Decimal | None:
    """Parse '2,345.67' / '12.34' / '4,321.0' (QNB receipts, interest breakdowns), to two decimals."""
    text = text.strip()
    if not _US_AMOUNT.match(text):
        return None
    try:
        return round_half_up(Decimal(text.replace(",", "")))
    except InvalidOperation:
        return None


TR_MONTHS = {
    "OCAK": 1,
    "SUBAT": 2,
    "MART": 3,
    "NISAN": 4,
    "MAYIS": 5,
    "HAZIRAN": 6,
    "TEMMUZ": 7,
    "AGUSTOS": 8,
    "EYLUL": 9,
    "EKIM": 10,
    "KASIM": 11,
    "ARALIK": 12,
}


def parse_dmy(text: str) -> date | None:
    m = re.match(r"^(\d{1,2})[./](\d{1,2})[./](\d{4})", text.strip())
    if not m:
        return None
    try:
        return date(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None


def parse_tr_words_date(day: str, month: str, year: str) -> date | None:
    """'27', 'Haziran', '2025' -> date(2025, 6, 27)."""
    mon = TR_MONTHS.get(fold(month))
    if not mon or not day.isdigit() or not year.isdigit():
        return None
    try:
        return date(int(year), mon, int(day))
    except ValueError:
        return None
