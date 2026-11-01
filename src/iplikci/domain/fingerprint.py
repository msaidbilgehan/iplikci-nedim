"""A transaction's fingerprint: the identity the user's notes and corrections are bound to (architecture §8).

A row's id in the database changes whenever its document is read again; its fingerprint does not. It is made of
the account, the day, the amount in the smallest unit, the currency, the description reduced to its letters and
digits, and the row's place among the rows identical in all of these (two coffees on one day are two rows, both
real). A reader that tidies a description's spacing or punctuation keeps the fingerprint; one that reads other
words makes a new one, and the note on the old one becomes an orphan the user is shown.
"""

import hashlib
import re
from collections import Counter
from datetime import date

from .text import fold

# The MVP's models write the lira as "TL"; the fingerprint always uses the ISO code, so moving the models to ISO
# codes keeps every fingerprint.
_ISO = {"TL": "TRY"}
_WORDS = re.compile(r"[0-9A-Z]+")
LENGTH = 20  # hex digits: 80 bits, far from a collision among a lifetime of rows


def simplified(description: str) -> str:
    """The description as the fingerprint sees it: folded, letters and digits only, one space apart."""
    return " ".join(_WORDS.findall(fold(description)))


def fingerprint(account: str, day: date, minor: int, currency: str, description: str, ordinal: int) -> str:
    text = "\x1f".join(
        (account, day.isoformat(), str(minor), _ISO.get(currency, currency), simplified(description), str(ordinal))
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:LENGTH]


class Fingerprints:
    """Fingerprints for rows given in their order: identical rows are numbered as they come."""

    def __init__(self) -> None:
        self._seen: Counter[tuple[str, date, int, str, str]] = Counter()

    def next(self, account: str, day: date, minor: int, currency: str, description: str) -> str:
        key = (account, day, minor, _ISO.get(currency, currency), simplified(description))
        ordinal = self._seen[key]
        self._seen[key] += 1
        return fingerprint(account, day, minor, currency, description, ordinal)
