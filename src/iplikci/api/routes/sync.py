"""The sync folder (ADR-0025, F22): where it stands, the places it can go on this computer (Google Drive's folder
first), what turning it on in a folder would do, turning it on and off, this computer's name, sending the
notifications that leave the computer from here, and a round now. The rounds themselves are the service's."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ...app import notify, sync
from ...app.sync import Actor, DeviceView, Place, Status, SyncError
from ..context import context_of
from ..guard import Principal
from ..problems import Problem
from .deps import only

router = APIRouter()
READ = [Depends(only(Principal.BROWSER, Principal.CLIENT))]
WRITE = [Depends(only(Principal.BROWSER))]


class SyncDeviceOut(BaseModel):
    id: str
    name: str
    app: str  # the program's version it runs
    system: str
    seen_at: str  # when it last said it is there (UTC)
    channels: list[str]  # the channels leaving the computer it could send on
    left: bool  # its user turned the sync off there
    me: bool  # this computer


class SyncOut(BaseModel):
    on: bool
    folder: str
    service: str  # "Google Drive", "iCloud Drive", …; "" for a folder no known sync service mirrors
    device: str
    name: str
    devices: list[SyncDeviceOut]
    senders: dict[str, str]  # channel → the id of the computer sending its notifications
    ready: list[str]  # the channels this computer could send on now
    last_at: str
    ok_at: str
    problem: str
    since: str
    waiting_down: int
    waiting_up: int
    documents: int


class SyncPlaceOut(BaseModel):
    service: str
    account: str
    folder: str
    exists: bool  # a set of data is there: turning the sync on joins it
    devices: list[SyncDeviceOut]
    usable: bool
    problem: str


class FolderIn(BaseModel):
    folder: str = Field(min_length=1, max_length=1000)


class TurnOnIn(BaseModel):
    folder: str = Field(min_length=1, max_length=1000)
    name: str = Field(default="", max_length=60)


class NameIn(BaseModel):
    name: str = Field(max_length=60)


class SendersIn(BaseModel):
    channels: list[str] = Field(default_factory=list[str], max_length=2)


class RoundOut(BaseModel):
    asked: bool


def _device(d: DeviceView) -> SyncDeviceOut:
    return SyncDeviceOut(
        id=d.id,
        name=d.name,
        app=d.app,
        system=d.system,
        seen_at=d.seen_at,
        channels=list(d.channels),
        left=d.left,
        me=d.me,
    )


def sync_out(found: Status, ready: tuple[str, ...]) -> SyncOut:
    return SyncOut(
        on=found.on,
        folder=found.folder,
        service=found.service,
        device=found.device,
        name=found.name,
        devices=[_device(d) for d in found.devices],
        senders=found.senders,
        ready=list(ready),
        last_at=found.last_at,
        ok_at=found.ok_at,
        problem=found.problem,
        since=found.since,
        waiting_down=found.waiting_down,
        waiting_up=found.waiting_up,
        documents=found.documents,
    )


def place_out(p: Place) -> SyncPlaceOut:
    return SyncPlaceOut(
        service=p.service,
        account=p.account,
        folder=p.folder,
        exists=p.exists,
        devices=[_device(d) for d in p.devices],
        usable=p.usable,
        problem=p.problem,
    )


@router.get("/api/sync", dependencies=READ)
def where_it_stands(request: Request) -> SyncOut:
    """Whether the sync is on, where, the computers in it, who sends which channel and how the last round went."""
    ws = context_of(request).ws
    return sync_out(sync.status(ws), notify.external_ready(ws))


@router.get("/api/sync/places", dependencies=READ)
def places(request: Request) -> list[SyncPlaceOut]:
    """The sync services' folders on this computer (Google Drive's first), each with the sync folder in it."""
    return [place_out(p) for p in sync.places(context_of(request).ws)]


@router.post("/api/sync/inspect", dependencies=WRITE)
def inspect(body: FolderIn) -> SyncPlaceOut:
    """What turning the sync on in a folder the user typed would do: begin a set of data there, or join one."""
    return place_out(sync.inspect(body.folder))


@router.put("/api/sync", dependencies=WRITE)
def turn_on(request: Request, body: TurnOnIn) -> SyncOut:
    """Share this computer's data through the folder: begin a set of data there or join the one there. The first
    round follows at once; the originals go into the folder over the next minutes."""
    ws = context_of(request).ws
    ready = notify.external_ready(ws)
    try:
        found = sync.turn_on(ws, body.folder, body.name, Actor.USER, ready)
    except SyncError as exc:
        raise Problem(400, "sync_refused", str(exc)) from exc
    return sync_out(found, ready)


@router.delete("/api/sync", dependencies=WRITE)
def turn_off(request: Request) -> SyncOut:
    """Stop sharing: the folder stays as it is, and this computer's data too."""
    ws = context_of(request).ws
    return sync_out(sync.turn_off(ws, Actor.USER), notify.external_ready(ws))


@router.put("/api/sync/name", dependencies=WRITE)
def rename(request: Request, body: NameIn) -> SyncOut:
    """This computer's name as the others show it; empty: the computer's own."""
    ws = context_of(request).ws
    return sync_out(sync.rename(ws, body.name, Actor.USER), notify.external_ready(ws))


@router.put("/api/sync/senders", dependencies=WRITE)
def send_from_here(request: Request, body: SendersIn) -> SyncOut:
    """This computer sends the given channels' notifications from now on (none given: every one it can send on)."""
    ws = context_of(request).ws
    ready = notify.external_ready(ws)
    wanted = [c for c in (body.channels or ready) if c in ready]
    try:
        found = sync.claim(ws, wanted, Actor.USER)
    except SyncError as exc:
        raise Problem(409, "sync_sender_refused", str(exc)) from exc
    return sync_out(found, ready)


@router.post("/api/sync/round", status_code=202, dependencies=READ)
def round_now() -> RoundOut:
    """Ask the service for a round now; /api/sync tells how it went within seconds."""
    sync.wake()
    return RoundOut(asked=True)
