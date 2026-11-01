"""The archive's list for the Documents screen (F03), a page at a time; the codes' labels for the interface."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, RootModel

from ...app import documents, labels
from ..context import context_of
from ..guard import Principal
from ..problems import Problem
from .deps import only

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])


class DocumentOut(BaseModel):
    sha256: str
    name: str
    file: str
    kind: str
    parser: str
    reader: str
    status: Literal["processed", "unprocessed", "unreadable"]  # a removed document is in the Trash, not listed
    reason: str
    verified: bool | None
    period_start: str
    period_end: str
    sources: list[str]
    added_at: str
    size: int


class DocumentPageOut(BaseModel):
    items: list[DocumentOut]
    next: str


class LabelsOut(RootModel[dict[str, dict[str, str]]]):
    """The Turkish label of every code, by code type (DocumentStatus, JobKind, …)."""


@router.get("/api/documents")
def document_page(
    request: Request,
    status: Annotated[list[str] | None, Query()] = None,
    cursor: Annotated[str, Query(max_length=200)] = "",
    limit: Annotated[int, Query(ge=1, le=documents.MAX_PAGE)] = 50,
) -> DocumentPageOut:
    """The kept documents, newest first; status narrows them (processed, unprocessed, unreadable)."""
    try:
        found = documents.page(context_of(request).ws, status or (), cursor, limit)
    except documents.BadCursor as exc:
        raise Problem(400, "cursor_invalid", str(exc)) from exc
    except ValueError as exc:  # a status that is no DocumentStatus
        raise Problem(400, "status_invalid", "Bilinmeyen belge durumu.") from exc
    return DocumentPageOut(
        items=[DocumentOut.model_validate(d, from_attributes=True) for d in found.items], next=found.next
    )


@router.get("/api/labels")
def code_labels() -> LabelsOut:
    return LabelsOut(labels.tables())
