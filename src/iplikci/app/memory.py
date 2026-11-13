"""What Claude keeps across conversations (F16, K30, ADR-0023): notes any agent connected over MCP reads and writes,
from whichever folder or application it connects, and the user reads and removes on the Claude bağlantısı screen.

A note is named by a short handle (`kira-odemesi`) and says what it is about (MemoryKind), what it is in one line and
the note itself. The index (`notes`) lists every note with its line but not its text: a conversation reads it first,
then the notes it needs, as Claude Code reads its MEMORY.md. A note tells what was true when it was written; what the
user says now comes first, and a note never asks for a change the user has not approved (the server's instructions).

The notes stay within what can be read at the start of every conversation: MOST notes, each a line of at most
DESCRIPTION_LONGEST characters and a text of at most BODY_LONGEST.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from ..domain import search as searching
from ..domain.codes import Actor, MemoryKind
from ..domain.text import fold
from ..storage import memories
from ..storage.memories import Memory
from .workspace import Workspace

__all__ = [
    "Actor",
    "Memory",
    "MemoryKind",
    "NotFound",
    "Refused",
    "Written",
    "count",
    "notes",
    "read",
    "remove",
    "search",
    "write",
]

NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
NAME_LONGEST = 64
DESCRIPTION_LONGEST = 200
BODY_LONGEST = 4000
MOST = 200  # notes kept at most: the index is read at the start of every conversation

BAD_NAME = (
    f"Notun adı küçük harf, rakam ve tirelerden oluşur, Türkçe karakter ve boşluk içermez (ör. kira-odemesi); en çok "
    f"{NAME_LONGEST} karakter."
)
FULL = (
    "Hafızada en çok {most} not tutulur: yenisini yazmadan önce aynı konudaki notları birleştirin ya da eskiyenleri "
    "silin."
)
NOTHING_TO_CHANGE = "Neyin değişeceğini verin: kind, description ya da body."
NO_TERMS = "Aranacak bir kelime verin."
_ORDER = {kind: i for i, kind in enumerate(MemoryKind)}

type Saved = Literal["created", "updated", "unchanged"]


class NotFound(Exception):
    """No note has the name."""


class Refused(Exception):
    """The note cannot be kept as given; the message says why (Turkish)."""


@dataclass(frozen=True, slots=True)
class Written:
    memory: Memory  # as kept now
    saved: Saved
    count: int  # the notes kept now


def notes(ws: Workspace) -> list[Memory]:
    """Every note: by kind in MemoryKind's order (who the user is first), then by name."""
    with ws.db() as db:
        found = memories.every(db)
    return sorted(found, key=lambda m: (_ORDER[m.kind], m.name))


def count(ws: Workspace) -> int:
    with ws.db() as db:
        return memories.count(db)


def read(ws: Workspace, names: Sequence[str]) -> tuple[list[Memory], list[str]]:
    """The notes the names give, in their order and each once, and the names no note has."""
    wanted = list(dict.fromkeys(names))
    with ws.db() as db:
        found = {name: memories.get(db, name) for name in wanted}
    return [m for m in found.values() if m is not None], [name for name, m in found.items() if m is None]


def search(ws: Workspace, text: str) -> list[Memory]:
    """The notes whose name, line or text has every term of one of the search's parts (domain.search: a comma
    separates the parts), the newest first."""
    asked = searching.parse(text)
    if not asked.parts:
        raise Refused(NO_TERMS)
    found = [m for m in notes(ws) if asked.found_in(fold(" ".join((m.name.replace("-", " "), m.description, m.body))))]
    return sorted(found, key=lambda m: m.updated_at, reverse=True)


def write(
    ws: Workspace,
    name: str,
    actor: Actor,
    *,
    kind: MemoryKind | None = None,
    description: str | None = None,
    body: str | None = None,
) -> Written:
    """Keep a note under name: a new one needs its kind, its line and its text; one already kept takes what is given
    and keeps the rest. Refused when the note would not be kept as asked: a name not a handle, a line or a text empty
    or too long, MOST notes kept already."""
    if len(name) > NAME_LONGEST or not NAME.fullmatch(name):
        raise Refused(BAD_NAME)
    with ws.db() as db, db.transaction():  # the count and the new note in one transaction: two writers queue
        old = memories.get(db, name)
        if old is None:
            if kind is None or description is None or body is None:
                given = {"kind": kind, "description": description, "body": body}
                missing = ", ".join(field for field, value in given.items() if value is None)
                raise Refused(f"Bu adla bir not yok; yeni bir not için şunlar da gerekir: {missing}.")
            if memories.count(db) >= MOST:
                raise Refused(FULL.format(most=MOST))
            kept = memories.write(db, name, kind, _line(description), _text(body), actor)
        else:
            if kind is None and description is None and body is None:
                raise Refused(NOTHING_TO_CHANGE)
            kept = memories.write(
                db,
                name,
                old.kind if kind is None else kind,
                old.description if description is None else _line(description),
                old.body if body is None else _text(body),
                actor,
            )
        now = memories.count(db)
    saved: Saved = "created" if old is None else "unchanged" if kept == old else "updated"
    return Written(kept, saved, now)


def remove(ws: Workspace, name: str, actor: Actor) -> Memory:
    """Take the note away; the note as it was. NotFound when no note has the name."""
    with ws.db() as db:
        gone = memories.remove(db, name, actor)
    if gone is None:
        raise NotFound(name)
    return gone


def _line(description: str) -> str:
    """The note's line as the index shows it: one line, its spaces made single."""
    line = " ".join(description.split())
    if not line:
        raise Refused("description boş olamaz: notun ne olduğunu tek satırda söyleyin.")
    if len(line) > DESCRIPTION_LONGEST:
        raise Refused(f"description en çok {DESCRIPTION_LONGEST} karakter olabilir.")
    return line


def _text(body: str) -> str:
    text = body.strip()
    if not text:
        raise Refused("body boş olamaz.")
    if len(text) > BODY_LONGEST:
        raise Refused(f"body en çok {BODY_LONGEST} karakter olabilir: notu kısaltın ya da ikiye bölün.")
    return text
