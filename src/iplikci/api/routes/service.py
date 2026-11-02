"""The service's own life from the interface (ADR-0017): whether the computer starts it, and stopping, restarting and
removing it. Each step answers first and ends the service after the answer is sent; only the service's own pages may
ask (a client with the token may read)."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel

from ... import __version__
from ...app import lifecycle
from ...app.lifecycle import Actor
from ..context import Context, context_of
from ..guard import Principal
from ..problems import Problem
from .deps import only

router = APIRouter()

READ = [Depends(only(Principal.BROWSER, Principal.CLIENT))]
WRITE = [Depends(only(Principal.BROWSER))]


class RestoreOutcomeOut(BaseModel):
    """How the last restore went, as the start that tried it wrote it."""

    backup: str
    ok: bool
    error: str  # why it could not be done; "" when it was. Its data stayed as it was before
    at: str


class ServiceStateOut(BaseModel):
    version: str
    started_at: str
    registered: bool  # the computer starts this data folder's service at login; a restart needs it
    manager: str  # launchd, systemd, Görev Zamanlayıcı; "" on a system with none this program knows
    can_end: bool  # this service can end itself here (false only where the API runs without the service)
    restore: RestoreOutcomeOut | None  # the last restore's outcome; null before any


class ServiceEndingOut(BaseModel):
    ending: bool  # the service ends within moments of this answer
    restarts: bool  # and the service manager starts it again


class ServiceRemoveIn(BaseModel):
    data_to_trash: bool = False  # also move the data folder to the Trash once the service has ended


def _life(context: Context) -> lifecycle.Lifecycle:
    if context.lifecycle is None:
        raise Problem(409, "service_unmanaged", "Bu servis buradan durdurulamaz.")
    return context.lifecycle


@router.get("/api/service", dependencies=READ)
def service_state(request: Request) -> ServiceStateOut:
    context = context_of(request)
    found = lifecycle.registration(context.ws)
    restored = lifecycle.last_restore(context.ws)
    return ServiceStateOut(
        version=__version__,
        started_at=context.started_at,
        registered=found.registered,
        manager=found.manager,
        can_end=context.lifecycle is not None,
        restore=None
        if restored is None
        else RestoreOutcomeOut(backup=restored.backup, ok=restored.ok, error=restored.error, at=restored.at),
    )


@router.post("/api/service/stop", status_code=202, dependencies=WRITE)
def service_stop(request: Request, later: BackgroundTasks) -> ServiceEndingOut:
    """Stop the service until the next login or until the app is opened again."""
    life = _life(context_of(request))
    later.add_task(life.end, lifecycle.STOP)
    return ServiceEndingOut(ending=True, restarts=False)


@router.post("/api/service/restart", status_code=202, dependencies=WRITE)
def service_restart(request: Request, later: BackgroundTasks) -> ServiceEndingOut:
    """End the service so that the computer's service manager starts it again, within a minute at most."""
    context = context_of(request)
    life = _life(context)
    try:
        lifecycle.must_be_registered(context.ws)
    except lifecycle.LifecycleError as exc:
        raise Problem(409, "service_not_registered", str(exc)) from exc
    later.add_task(life.end, lifecycle.RESTART)
    return ServiceEndingOut(ending=True, restarts=True)


@router.post("/api/service/remove", status_code=202, dependencies=WRITE)
def service_remove(request: Request, body: ServiceRemoveIn, later: BackgroundTasks) -> ServiceEndingOut:
    """Take the service off the computer and end it; the data folder goes to the Trash when asked, never deleted.
    The app itself is removed as the system removes apps."""
    context = context_of(request)
    life = _life(context)
    try:
        lifecycle.remove(context.ws, body.data_to_trash, Actor.USER)
    except lifecycle.NotRegistered as exc:
        raise Problem(409, "service_not_registered", str(exc)) from exc
    except lifecycle.LifecycleError as exc:
        raise Problem(409, "service_remove_failed", str(exc)) from exc
    later.add_task(life.end, lifecycle.STOP)
    return ServiceEndingOut(ending=True, restarts=False)
