"""The exports (F20): what the analysis wrote, a download of each, and a request to make them again now. A download
is always an attachment: the report runs its own script, which must never run in the interface's origin."""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from ...app import background, exports
from ...app.exports import ExportKind
from ..context import context_of
from ..guard import Principal
from ..problems import Problem
from .deps import only

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])


class ExportOut(BaseModel):
    kind: ExportKind
    name: str  # the name it downloads under, with the day it was made
    size: int  # bytes; the month-end pages: their files together, before zipping
    made_at: str  # when the analysis wrote it, ISO in UTC


class ExportsQueuedOut(BaseModel):
    queued: bool  # false: an analysis was already waiting, and it writes them too


@router.get("/api/exports")
def export_list(request: Request) -> list[ExportOut]:
    """The exports the last analysis wrote: the report, the rows as CSV and Excel, the month-end pages."""
    return [
        ExportOut(kind=e.kind, name=e.name, size=e.size, made_at=e.made_at)
        for e in exports.every(context_of(request).ws)
    ]


@router.get("/api/exports/{kind}", response_class=Response)
def export_download(request: Request, kind: ExportKind) -> Response:
    """One export as a file to save."""
    try:
        found = exports.download(context_of(request).ws, kind)
    except exports.Missing as exc:
        raise Problem(
            404, "export_missing", "Bu dışa aktarım henüz yazılmadı; servis ilk analizi yapınca yazar."
        ) from exc
    return Response(
        found.content,
        media_type=found.media_type,
        headers={"Content-Disposition": f'attachment; filename="{found.name}"', "Cache-Control": "no-store"},
    )


@router.post("/api/exports", status_code=202)
def export_again(request: Request) -> ExportsQueuedOut:
    """Make the analysis and its exports again now; the worker does it within moments and the stream tells."""
    return ExportsQueuedOut(queued=background.request_refresh(context_of(request).ws) is not None)
