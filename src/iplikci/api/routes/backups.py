"""The backups (F20): the list, and a backup on request, made by the service's worker."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...app import background, backup
from ..context import context_of
from ..guard import Principal
from ..models import BackupOut
from .deps import only

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])


class QueuedOut(BaseModel):
    queued: bool


@router.get("/api/backups")
def backups(request: Request) -> list[BackupOut]:
    """The whole backups, newest first."""
    return [
        BackupOut(
            name=b.name,
            created_at=b.created_at,
            reason=b.reason.value,
            app=b.app,
            documents=b.documents,
            annotations=b.annotations,
            size=b.size,
            damaged=len(b.damaged),
        )
        for b in backup.every(context_of(request).ws)
    ]


@router.post("/api/backups", status_code=202)
def back_up_now(request: Request) -> QueuedOut:
    """Ask for a backup now; the worker makes it within seconds and the System screen shows it."""
    background.request_backup(context_of(request).ws)
    return QueuedOut(queued=True)
