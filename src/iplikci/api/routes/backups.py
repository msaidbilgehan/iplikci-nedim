"""The backups (F20): the list, a backup on request, made by the service's worker, and a backup put back
(ADR-0017): checked now, put back as the service starts again, before anything opens the database."""

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Request
from pydantic import BaseModel

from ...app import background, backup, lifecycle
from ...app.lifecycle import Actor
from ..context import context_of
from ..guard import Principal
from ..models import BackupOut
from ..problems import Problem
from .deps import only

router = APIRouter(dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])
WRITE = [Depends(only(Principal.BROWSER))]


class RestoringOut(BaseModel):
    backup: str
    restarts: bool  # the service starts again with the backup put back; the page asks for a new login after it


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


@router.post("/api/backups/{name}/restore", status_code=202, dependencies=WRITE)
def restore(
    request: Request, later: BackgroundTasks, name: str = Path(min_length=1, max_length=200, pattern=r"^[^/\\]+$")
) -> RestoringOut:
    """Put a backup back: what there is now is backed up first, then the service starts again with the backup's
    database, settings and rules. A backup of the backups folder only, by its name."""
    context = context_of(request)
    if context.lifecycle is None:
        raise Problem(409, "service_unmanaged", "Bu servis buradan yeniden başlatılamaz.")
    try:
        lifecycle.must_be_registered(context.ws)
        chosen = lifecycle.request_restore(context.ws, name, Actor.USER)
    except lifecycle.LifecycleError as exc:
        raise Problem(409, "service_not_registered", str(exc)) from exc
    except backup.BackupError as exc:
        raise Problem(400, "backup_refused", str(exc)) from exc
    later.add_task(context.lifecycle.end, lifecycle.RESTART)
    return RestoringOut(backup=chosen.name, restarts=True)
