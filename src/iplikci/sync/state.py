"""The shared data as pieces with stamps, how two versions of a piece are merged, and the state file every computer
writes into its part of the sync folder (ADR-0025).

A piece is one value of the primary data, named by its kind and its key: an annotation by its fingerprint, a
document by its sha256, a setting by its section and name. Each carries the stamp of its last change and the value that
change gave it, or none when it was taken away. Merging keeps, of two versions, the one whose stamp is later; a
document taken away stays away whatever comes after (a removal is never undone, ADR-0003). Merging is the same whatever
order the versions come in and however often one comes: every computer that has seen the same versions holds the same
pieces.

A computer's state file holds every piece it knows, its own and those it merged, so any one file carries the whole
set of data, and a computer whose folder went missing is no loss.
"""

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, cast

from .clock import Stamp, StampError

FORMAT = "iplikci-esitleme-durumu"
VERSION = 1


class Kind(StrEnum):
    """The kinds of shared pieces."""

    ANNOTATION = "annotation"  # an annotation, by the fingerprint of its row
    ALIAS = "alias"  # the name the user gave an account, by the account's id
    CLOSURE = "closure"  # an account the user closed, with the day, by the account's id
    MEMORY = "memory"  # one of Claude's notes, by its name
    DOCUMENT = "document"  # a document kept or removed, by its sha256 (the bytes travel beside the state)
    SOURCE = "source"  # one arrival of a document
    SETTING = "setting"  # a setting every computer shares, by "section.name"
    FILE = "file"  # a rule file, by its place in the data folder ("rules/personal.yaml")
    SENDER = "sender"  # which computer sends a channel's notifications, by the channel


class StateError(ValueError):
    """A state file this program does not read; the message says why (Turkish)."""


class Newer(StateError):
    """A state file a newer version of the program wrote: this computer needs the update."""


@dataclass(frozen=True, slots=True)
class Entry:
    kind: str
    key: str
    stamp: Stamp
    value: str | None  # canonical JSON; None: taken away

    @property
    def id(self) -> tuple[str, str]:
        return self.kind, self.key


def canonical(value: Any) -> str:
    """The one text of a value: two computers holding the same value hold the same text."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(text: str | None) -> str:
    """What a value is compared by; "" for none."""
    return "" if text is None else hashlib.sha256(text.encode("utf-8")).hexdigest()


def removed_document(value: str | None) -> bool:
    """Whether a document's value says it was removed."""
    if value is None:
        return False
    try:
        found: Any = json.loads(value)
    except ValueError:
        return False
    return isinstance(found, dict) and bool(cast(dict[str, Any], found).get("removed"))


def _rank(entry: Entry) -> tuple[bool, Stamp]:
    if entry.kind == Kind.DOCUMENT:
        # A computer's data from before it joined (stamped zero) holds no removal over what the others keep.
        return removed_document(entry.value) and entry.stamp.ms > 0, entry.stamp
    return False, entry.stamp


def wins(current: Entry | None, incoming: Entry) -> bool:
    """Whether incoming takes the place of current: the later change, except that a document's removal beats every
    version that keeps it (one made since the computers share their data)."""
    return current is None or _rank(incoming) > _rank(current)


def merge(versions: Iterable[Entry]) -> dict[tuple[str, str], Entry]:
    """The winning version of every piece among versions, by kind and key."""
    found: dict[tuple[str, str], Entry] = {}
    for entry in versions:
        if wins(found.get(entry.id), entry):
            found[entry.id] = entry
    return found


# --- the state file ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Published:
    """A computer's state file."""

    library: str  # the set of data it belongs to
    device: str  # the computer that wrote it
    app: str  # the program's version that wrote it
    written_at: str  # UTC, ISO 8601
    entries: tuple[Entry, ...]
    dropped: int = 0  # pieces left out on reading: not of the shape their kind has (a damaged or forged file)


def encode(p: Published) -> bytes:
    rows = [
        [e.kind, e.key, e.stamp.text, None if e.value is None else json.loads(e.value)]
        for e in sorted(p.entries, key=lambda e: (e.kind, e.key))
    ]
    value = {
        "format": FORMAT,
        "version": VERSION,
        "library": p.library,
        "device": p.device,
        "app": p.app,
        "written_at": p.written_at,
        "entries": rows,
    }
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def entries_digest(entries: Iterable[Entry]) -> str:
    """What changes when any piece changes: a state file is written again only then."""
    h = hashlib.sha256()
    for e in sorted(entries, key=lambda e: (e.kind, e.key)):
        h.update(canonical([e.kind, e.key, e.stamp.text, e.value]).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def decode(data: bytes, valid: Callable[[Entry], bool] = lambda _entry: True) -> Published:
    """A state file read back; StateError when it is not one this program reads (Newer when a newer version wrote it).
    A piece valid refuses is left out and counted. Pieces of kinds this version does not know are kept as they are: a
    newer computer's pieces pass through."""
    try:
        value: Any = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise StateError("durum dosyası okunamadı (yarım inmiş olabilir)") from exc
    if not isinstance(value, dict):
        raise StateError("bir İplikçi Nedim durum dosyası değil")
    fields = cast(Mapping[str, Any], value)
    if fields.get("format") != FORMAT:
        raise StateError("bir İplikçi Nedim durum dosyası değil")
    version = fields.get("version")
    if not isinstance(version, int) or version > VERSION:
        raise Newer(f"durum dosyasını İplikçi Nedim'in daha yeni bir sürümü yazmış ({fields.get('app', '?')})")
    try:
        rows = cast(list[Any], fields["entries"])
        library, device = str(fields["library"]), str(fields["device"])
        app, written_at = str(fields["app"]), str(fields["written_at"])
    except (KeyError, TypeError) as exc:
        raise StateError(f"durum dosyası bozuk: {exc}") from exc
    if not isinstance(rows, list):
        raise StateError("durum dosyası bozuk: kayıtlar bir liste değil")
    entries: list[Entry] = []
    dropped = 0
    for row in rows:
        try:
            entry = _entry(row)
        except (TypeError, ValueError, StampError):
            dropped += 1
            continue
        if valid(entry):
            entries.append(entry)
        else:
            dropped += 1
    return Published(library, device, app, written_at, tuple(entries), dropped)


def _entry(row: Any) -> Entry:
    if not isinstance(row, list):
        raise TypeError("bir kayıt bir liste olmalı")
    items = cast(list[Any], row)
    if len(items) != 4:
        raise ValueError("bir kayıt dört öğeli olmalı")
    kind, key, stamp, value = items
    if not isinstance(kind, str) or not isinstance(key, str) or not isinstance(stamp, str):
        raise TypeError("kaydın türü, anahtarı ve damgası metin olmalı")
    return Entry(kind, key, Stamp.parse(stamp), None if value is None else canonical(value))
