"""The service's health: `/healthz` for a process watcher, `/api/system` for the System screen (architecture §22)."""

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, Response

from ...app import system
from ..context import context_of
from ..models import BackupHealthOut, DiskOut, MailOut, QueueOut, ReaderHealthOut, ServiceOut, SystemOut

router = APIRouter()


@router.get("/healthz", include_in_schema=False)
async def healthz(request: Request) -> JSONResponse:
    """Whether the process and its database answer; nothing else, so it needs no session."""
    healthy = await run_in_threadpool(system.healthy, context_of(request).ws)
    return JSONResponse({"status": "ok" if healthy else "unavailable"}, status_code=200 if healthy else 503)


@router.get("/api/system")
def system_status(request: Request) -> SystemOut:
    context = context_of(request)
    found = system.status(context.ws)
    return SystemOut(
        service=ServiceOut(version=found.version, started_at=context.started_at, pid=context.pid, home=found.home),
        documents=found.documents,
        readers=[ReaderHealthOut.model_validate(r, from_attributes=True) for r in found.readers],
        disk=DiskOut.model_validate(found.disk, from_attributes=True),
        queue=QueueOut.model_validate(found.queue, from_attributes=True),
        mail=MailOut.model_validate(found.mail, from_attributes=True),
        backup=BackupHealthOut.model_validate(found.backup, from_attributes=True),
    )


@router.get("/api/system/log", response_class=Response)
def system_log(request: Request) -> Response:
    """The service's log to send on when something goes wrong, without the paths, addresses and numbers that could
    be personal."""
    context = context_of(request)
    name = f"iplikci-gunluk-{context.today().isoformat()}.log"
    return Response(
        system.log_text(context.ws).encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
