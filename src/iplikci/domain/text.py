"""Turkish text folding, the form names and descriptions are compared and searched in, and title case."""

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


_TR_LOWER = str.maketrans({"İ": "i", "I": "i"})
_ABBREVIATION = re.compile(r"^(?:\w\.)+\w?\.?$")  # V.D., A.Ş., T.C.


def title_tr(s: str) -> str:
    """Readable title case for bank descriptions ('ORNEK KAHVE' -> 'Ornek Kahve').

    Banks ASCII-fold most names, so a plain 'I' is lowered to 'i' rather than
    the Turkish dotless 'ı'. Dotted abbreviations stay upper case.
    """
    words: list[str] = []
    for w in s.split():
        if _ABBREVIATION.match(w):
            words.append(w)
            continue
        low = w.translate(_TR_LOWER).lower()
        words.append(low[:1].upper() + low[1:] if low[:1] != "i" else "İ" + low[1:])
    return " ".join(words)


# What a spreadsheet takes for the start of a formula: a cell from a document (a transfer's description, which its
# sender writes) could run as one when the export is opened.
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def spreadsheet_text(value: str) -> str:
    """value as a spreadsheet shows it, never as a formula: one that starts like a formula gets an apostrophe."""
    return f"'{value}" if value.startswith(_FORMULA_START) else value
