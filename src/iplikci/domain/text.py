"""Turkish text folding: the form names and descriptions are compared and searched in."""

import re
import unicodedata

_TR_FOLD = str.maketrans(
    {
        "ı": "i",
        "İ": "I",
        "ş": "s",
        "Ş": "S",
        "ğ": "g",
        "Ğ": "G",
        "ü": "u",
        "Ü": "U",
        "ö": "o",
        "Ö": "O",
        "ç": "c",
        "Ç": "C",
        "â": "a",
        "Â": "A",
        "î": "i",
        "Î": "I",
        "û": "u",
        "Û": "U",
    }
)
_SPACES = re.compile(r"\s+")


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def fold(s: str) -> str:
    """Uppercase ASCII form used for matching: 'Migros Örnek Şube' -> 'MIGROS ORNEK SUBE'."""
    s = nfc(s).translate(_TR_FOLD)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return _SPACES.sub(" ", s.upper()).strip()
