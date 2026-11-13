"""Claude's memory (F16, K30, ADR-0023): the notes Claude keeps across conversations, for the Claude bağlantısı screen to
list. Claude writes them through MCP; the user reads them here and removes the ones they do not want kept."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi import Path as FastPath
from pydantic import BaseModel

from ...app import memory
from ...app.memory import Actor, Memory, MemoryKind
from ...app.workspace import Workspace
from ..context import context_of
from ..guard import Principal
from ..problems import Problem
from .deps import only

router = APIRouter()
READ = [Depends(only(Principal.BROWSER, Principal.CLIENT))]
WRITE = [Depends(only(Principal.BROWSER))]

MemoryName = Annotated[str, FastPath(min_length=1, max_length=memory.NAME_LONGEST, pattern=f"^{memory.NAME.pattern}$")]


class MemoryOut(BaseModel):
    name: str  # its handle: kira-odemesi
    kind: MemoryKind
    description: str  # one line: what the note is about
    body: str  # the note itself
    created_at: str  # UTC, ISO 8601
    updated_at: str
    by: Literal["mcp", "user"]  # who wrote it last: Claude through the MCP server, or the user


class MemoriesOut(BaseModel):
    memories: list[MemoryOut]  # by kind (who the user is first), then by name
    most: int  # the notes kept at most


def _note(m: Memory) -> MemoryOut:
    return MemoryOut(
        name=m.name,
        kind=m.kind,
        description=m.description,
        body=m.body,
        created_at=m.created_at,
        updated_at=m.updated_at,
        by="user" if m.actor is Actor.USER else "mcp",
    )


def _out(ws: Workspace) -> MemoriesOut:
    return MemoriesOut(memories=[_note(m) for m in memory.notes(ws)], most=memory.MOST)


@router.get("/api/memory", dependencies=READ)
def memory_list(request: Request) -> MemoriesOut:
    """Every note Claude keeps, in full."""
    return _out(context_of(request).ws)


@router.delete("/api/memory/{name}", dependencies=WRITE)
def memory_remove(request: Request, name: MemoryName) -> MemoriesOut:
    """Take a note away: no conversation reads it again. The notes kept after it."""
    ws = context_of(request).ws
    try:
        memory.remove(ws, name, Actor.USER)
    except memory.NotFound as exc:
        raise Problem(404, "memory_not_found", "Bu adla bir not yok; başka bir yerden silinmiş olabilir.") from exc
    return _out(ws)
