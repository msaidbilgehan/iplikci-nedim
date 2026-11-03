"""Masking what the tools tell (ADR-0011; settings `[privacy] mcp_masking`): with it on, no account number, IBAN or,
on its second level, person's name reaches the model.

- `accounts`: every account's number, wherever it stands (an account's name carries it: "Vadesiz TL 123456789", a
  card's last digits "•1234"), becomes `•••` and a letter that tells the accounts apart (`•••A`, `•••B` in the order
  of their ids). An IBAN becomes `[IBAN]`; a run of ten or more digits standing alone (an account number a bank's
  description prints) becomes `[numara]`.
- `accounts_and_names`: also the names of people, as the ledger knows them: the user's own names (settings), the
  other side of a transfer to or from a person, of an own transfer and of an income from a person (a company's name,
  told by its marks, stays), and the payee a person's transfer is named after when the bank prints no other side.
  Each becomes `Kişi 1`, `Kişi 2`… in the order of their names, wherever it stands ("Veli Örneksoy Kira Ödemesi"
  becomes "Kişi 1 Kira Ödemesi") and whatever the letters' case.

Only text is masked, never a number: amounts and counts stay exact. Nor is the program's own identifier in the field
that holds one: a row's fingerprint, a document's id, a plan's id are hex digits, all of them digits now and then (a
fingerprint about once in 12 000 rows), and the tools must still find what they name. The masks follow the data each
time: a new account or person gets its own.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast

from ..analysis import Dataset
from ..domain.codes import TransactionKind
from ..domain.text import fold

OFF, ACCOUNTS, NAMES = "off", "accounts", "accounts_and_names"
IBAN = "[IBAN]"
NUMBER = "[numara]"

_IBAN = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){3,7}(?:[ ]?[A-Z0-9]{1,4})?(?![A-Za-z0-9])")
_LONG_NUMBER = re.compile(r"(?<![0-9A-Za-z])\d{10,}(?![0-9A-Za-z])")
_DIGITS = re.compile(r"\d{3,}")
# The fields that hold the program's own identifiers, and what such an identifier is: a plan's id (16 hex digits), a
# row's fingerprint (20), a document's sha256 (64) or the resource address made of one.
_IDENTIFIER_KEYS = frozenset({"fingerprint", "fingerprints", "splitOf", "row", "document", "id", "plan_id", "resource"})
_IDENTIFIER = re.compile(r"[0-9a-f]{16}|[0-9a-f]{20}|[0-9a-f]{64}|iplikci://documents/[0-9a-f]{64}(?:/pages/\d+)?")
# The kinds whose other side may be a person: transfers to and from people, own transfers, income.
_PEOPLE = frozenset({TransactionKind.P2P_TRANSFER, TransactionKind.OWN_TRANSFER, TransactionKind.INCOME})
# A company's name is no person's: its legal form or trade says so.
_COMPANY = re.compile(
    r"\b(a\.?\s?s\.?|ltd|sti|tic|san|anonim|limited|sirket|holding|bank|bankasi|vakif|dernek|kooperatif|"
    r"belediye|universite|ajans|group|grup|inc|gmbh|llc|bv|b\.v)\b",
    re.IGNORECASE,  # fold gives ASCII capitals
)
# The letters Turkish cases apart from what Python's case folding knows: i İ ı I are one letter for a name.
_I = "[iİıI]"


def _name_pattern(name: str) -> str:
    parts = [_I if ch in "iİıI" else re.escape(ch) for ch in name]
    return r"(?<!\w)" + "".join(parts).replace(r"\ ", r"\s+") + r"(?!\w)"


@dataclass(frozen=True)
class Mask:
    """What one level of masking hides in a dataset, and how."""

    level: str
    replacements: tuple[tuple[re.Pattern[str], str], ...] = ()

    @property
    def on(self) -> bool:
        return self.level != OFF

    def text(self, value: str) -> str:
        if not self.on:
            return value
        for pattern, by in self.replacements:
            value = pattern.sub(by, value)
        value = _IBAN.sub(IBAN, value)
        return _LONG_NUMBER.sub(NUMBER, value)

    def apply(self, value: Any, key: str = "") -> Any:
        """value with its text masked: the JSON a tool returns, keys, numbers and identifiers untouched. key: the field
        value stands in (a list's items stand in its field)."""
        if not self.on:
            return value
        if isinstance(value, str):
            return value if key in _IDENTIFIER_KEYS and _IDENTIFIER.fullmatch(value) else self.text(value)
        if isinstance(value, dict):
            return {k: self.apply(v, k) for k, v in cast(dict[str, Any], value).items()}
        if isinstance(value, (list, tuple)):
            return [self.apply(v, key) for v in cast(Iterable[Any], value)]
        return value


def mask_for(level: str, ds: Dataset, own_names: Iterable[str] = ()) -> Mask:
    """The mask of a level over ds: its accounts' numbers and, on the second level, its people's names."""
    if level not in (ACCOUNTS, NAMES):
        return Mask(OFF)
    replacements: list[tuple[re.Pattern[str], str]] = []
    for i, account in enumerate(sorted(ds.accounts.values(), key=lambda a: a.id)):
        code = f"•••{_letters(i)}"
        numbers = {account.number, *_DIGITS.findall(account.label)} - {""}
        # The longest first: a card's last digits are a part of its whole number.
        for number in sorted(numbers, key=len, reverse=True):
            # Never inside an identifier: a fingerprint's or a document's hex digits are no account number.
            digits = r"[\s-]?".join(re.escape(part) for part in re.split(r"[\s-]", number))
            replacements.append((re.compile(r"(?<![0-9A-Za-z])[•*…]*" + digits + r"(?![0-9A-Za-z])"), code))
    if level == NAMES:
        names = sorted(_people(ds, own_names), key=lambda n: (fold(n), n))
        # The longest first: "Veli Örneksoy" before "Veli".
        for i, name in sorted(enumerate(names, 1), key=lambda pair: -len(pair[1])):
            replacements.append((re.compile(_name_pattern(name), re.IGNORECASE), f"Kişi {i}"))
    return Mask(level, tuple(replacements))


def _people(ds: Dataset, own_names: Iterable[str]) -> set[str]:
    """The people's names the ledger knows, one spelling each (the first seen, whatever its case)."""
    found: dict[str, str] = {}

    def keep(name: str) -> None:
        name = " ".join(name.split())
        key = fold(name)
        if len(key) >= 3 and not _COMPANY.search(key) and key not in found:
            found[key] = name

    for name in own_names:
        keep(name)
    for t in ds.transactions:
        if t.kind not in _PEOPLE:
            continue
        if t.counterparty:
            keep(t.counterparty)
        elif t.kind is TransactionKind.P2P_TRANSFER and t.merchant:  # a person's transfer named after them
            keep(t.merchant)
    return set(found.values())


def _letters(i: int) -> str:
    """A, B, … Z, AA, AB, …: a short code for the i-th account."""
    code = ""
    i += 1
    while i:
        i, rest = divmod(i - 1, 26)
        code = chr(ord("A") + rest) + code
    return code
