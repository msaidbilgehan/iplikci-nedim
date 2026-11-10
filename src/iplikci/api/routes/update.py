"""The program's own updates (ADR-0022, F21): where they stand, a check or an install now, and whether the program
installs a new version by itself, only tells, or never asks. The worker does the work; these only ask for it."""

from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ...app import update
from ...app.update import Actor, UpdateError, UpdateState
from ..context import context_of
from ..guard import Principal
from ..problems import Problem
from .deps import only

router = APIRouter()

Mode = Literal["auto", "ask", "off"]


class AvailableOut(BaseModel):
    version: str
    tag: str
    date: str
    notes: str  # the changelog's section, Markdown
    size: int  # this system's update file in bytes; 0: none for this system
    page: str  # the release's page


class OutcomeOut(BaseModel):
    from_version: str
    to_version: str
    at: str
    ok: bool
    error: str
    tries: int


class UpdateOut(BaseModel):
    version: str  # the running one
    mode: Mode
    installation: Literal["macos_app", "linux_copy", "windows_setup", "manual"]
    automatic: bool  # this copy installs a new version of itself
    platform: str
    checked_at: str  # "" before any check
    check_error: str
    available: AvailableOut | None
    installing: str  # the version being put in place now; ""
    last: OutcomeOut | None
    page: str  # where the releases are


class ModeIn(BaseModel):
    mode: Mode


class UpdateQueuedOut(BaseModel):
    queued: bool
    version: str = ""  # the version an install was asked for


def update_out(found: UpdateState) -> UpdateOut:
    return UpdateOut.model_validate(
        {
            "version": found.version,
            "mode": found.mode,
            "installation": found.installation,
            "automatic": found.automatic,
            "platform": found.platform,
            "checked_at": found.checked_at,
            "check_error": found.check_error,
            "available": None if found.available is None else asdict(found.available),
            "installing": found.installing,
            "last": None if found.last is None else asdict(found.last),
            "page": found.page,
        }
    )


@router.get("/api/update", dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])
def where_it_stands(request: Request) -> UpdateOut:
    """The running version, the mode, the last check and what it found, and the last install."""
    return update_out(update.state(context_of(request).ws))


@router.post("/api/update/check", status_code=202, dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])
def check_now(request: Request) -> UpdateQueuedOut:
    """Ask the worker to check now, whatever the mode says; /api/update tells what it found within seconds."""
    update.request_check(context_of(request).ws)
    return UpdateQueuedOut(queued=True)


@router.post("/api/update/install", status_code=202, dependencies=[Depends(only(Principal.BROWSER, Principal.CLIENT))])
def install_now(request: Request) -> UpdateQueuedOut:
    """Ask the worker to install the newer version the last check found. A backup comes first; then the service
    starts again with the new version, and the interface finds it back within a minute."""
    try:
        version = update.request_install(context_of(request).ws, Actor.USER)
    except UpdateError as exc:
        raise Problem(409, "update_unavailable", str(exc)) from exc
    return UpdateQueuedOut(queued=True, version=version)


@router.put("/api/update/mode", dependencies=[Depends(only(Principal.BROWSER))])
def set_mode(request: Request, body: ModeIn) -> UpdateOut:
    """Install a new version by itself (auto), only tell (ask), or never ask GitHub (off)."""
    try:
        return update_out(update.set_mode(context_of(request).ws, body.mode, Actor.USER))
    except UpdateError as exc:
        raise Problem(400, "update_mode_invalid", str(exc)) from exc
