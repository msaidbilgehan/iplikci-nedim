"""What a search box's text asks for (F04): the rows that have every term of any one of its parts.

A comma separates the parts and a row needs only one of them: "market, kira" finds the rows of either. The spaces
inside a part separate its words and a row needs all of them: "migros kadıköy" finds the rows with both, as the box
always did. A quoted term is kept as written, commas and spaces included ("ornek, kadikoy"), so a name with a comma
is searched whole. A comma between two digits is a decimal comma ("1,50"), never a separator. Every term is compared
in its folded form (domain.text.fold) anywhere in the row's text: "kira" finds "KİRA ÖDEMESİ".

The interface reads a search the same way (web/src/lib/search.ts) where it narrows something on the screen itself."""

import functools
import re
from dataclasses import dataclass

from .text import fold

_QUOTES = '"“”„'  # a straight quote and the curly ones a keyboard or a paste may give
_QUOTE = re.compile(f"[{_QUOTES}]")
_DIGITS = frozenset("0123456789")


@dataclass(frozen=True, slots=True)
class Part:
    """One of a search's parts: a row is found by it when it has every one of its terms."""

    text: str  # as written, its terms one space apart and a quoted one in straight quotes: what the screen names
    terms: tuple[str, ...]  # folded

    def found_in(self, folded: str) -> bool:
        return all(term in folded for term in self.terms)


@dataclass(frozen=True, slots=True)
class Search:
    """A search's parts in the order written, each once; a row is found by any one of them. No part finds every row."""

    parts: tuple[Part, ...] = ()

    def found_in(self, folded: str) -> bool:
        """Whether a text, folded, has every term of one of the parts."""
        return not self.parts or any(part.found_in(folded) for part in self.parts)


def _decimal_comma(text: str, at: int) -> bool:
    return 0 < at < len(text) - 1 and text[at - 1] in _DIGITS and text[at + 1] in _DIGITS


def _pieces(text: str) -> list[list[tuple[str, bool]]]:
    """text's parts, each its terms as written with whether the term was quoted."""
    parts: list[list[tuple[str, bool]]] = [[]]
    word = ""
    phrase: str | None = None  # inside quotes: the term so far
    for at, c in enumerate(text):
        if phrase is not None:
            if c in _QUOTES:
                parts[-1].append((phrase, True))
                phrase = None
            else:
                phrase += c
            continue
        if c in _QUOTES or c.isspace() or (c == "," and not _decimal_comma(text, at)):
            if word:
                parts[-1].append((word, False))
                word = ""
            if c in _QUOTES:
                phrase = ""
            elif c == ",":
                parts.append([])
            continue
        word += c
    if phrase is not None:  # a quote left open runs to the end
        parts[-1].append((phrase, True))
    elif word:
        parts[-1].append((word, False))
    return parts


@functools.lru_cache(maxsize=128)  # a list's filter asks once for every row
def parse(text: str) -> Search:
    """A search box's text read into its parts: a comma outside quotes ends a part, a space a word, and a quote opens
    or closes a term kept as written; a quote left open runs to the end. Empty parts and terms are left out, and a
    part written twice is kept once."""
    parts: dict[tuple[str, ...], Part] = {}
    for piece in _pieces(text):
        kept = [(" ".join(written.split()), quoted) for written, quoted in piece if fold(written)]
        terms = tuple(fold(written) for written, _ in kept)
        if terms and terms not in parts:
            parts[terms] = Part(" ".join(f'"{w}"' if quoted else w for w, quoted in kept), terms)
    return Search(tuple(parts.values()))


def exactly(text: str) -> str:
    """A search that finds text as written: text itself when it reads as one part of its own words, else its pieces
    between quote marks, each in quotes. A link that searches for a name (a merchant's, a description) gives it so: a
    comma in the name never splits it into parts."""
    found = parse(text).parts
    words = tuple(fold(w) for w in text.split() if fold(w))
    if len(found) == 1 and found[0].terms == words:
        return text
    return " ".join(f'"{" ".join(piece.split())}"' for piece in _QUOTE.split(text) if piece.strip())
