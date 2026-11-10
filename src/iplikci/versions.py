"""Versions compared as numbers: "0.10.0" is newer than "0.9.16"."""

import re

_NUMBERS = re.compile(r"\d+(?:\.\d+)*")


def version_key(text: str) -> tuple[int, ...] | None:
    """A version's numbers, compared as numbers ("0.10.0" after "0.9.1"), the zeros at its end left out ("1.0" is
    "1.0.0"); None for what is no version. What follows the numbers (a pre-release, ".yeni") does not count."""
    found = _NUMBERS.match(text)
    if found is None:
        return None
    numbers = [int(part) for part in found.group().split(".")]
    while len(numbers) > 1 and numbers[-1] == 0:
        numbers.pop()
    return tuple(numbers)


def newer(version: str, than: str) -> bool:
    """Whether version is newer than `than`; never when either is no version."""
    mine, theirs = version_key(version), version_key(than)
    return mine is not None and theirs is not None and mine > theirs
