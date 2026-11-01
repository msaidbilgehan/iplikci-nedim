"""Adding documents by hand (F02, ADR-0007): uploads land in a batch in vault/staging, the plan shows what would
happen to each file, and only the plan the user confirmed is applied. The inbox folder can be planned the same way;
on its own the service takes it in without a plan once it has been quiet."""

from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from ...app import intake, uploads
from ...app.workspace import Busy, StalePlan
from ..context import Context, context_of
from ..problems import Problem

router = APIRouter()


class UploadOut(BaseModel):
    batch: str
    status: uploads.UploadStatus
    name: str
    reason: str


class PlanIn(BaseModel):
    upload: str = ""  # an upload batch; none: the inbox folder


class PlanDocumentOut(BaseModel):
    """The document a plan item would add: a statement, an account statement or a receipt, and its check."""

    kind: str  # ekstre, hesap, dekont
    account: str
    start: str | None
    end: str
    rows: int
    verified: bool | None
    check: str


class PlanItemOut(BaseModel):
    """One file of a plan (intake.describe): what it is and what happens to it. The MCP client reads the same keys,
    so two keep their camelCase names."""

    model_config = ConfigDict(serialize_by_alias=True, validate_by_alias=True)

    action: str
    label: str
    name: str
    source: str
    reason: str
    copy_of: str | None = Field(alias="copyOf")  # the kept document holding the same statement or receipt
    target: str | None
    from_inbox: bool = Field(alias="fromInbox")
    document: PlanDocumentOut | None = None


class PlanOut(BaseModel):
    plan_id: str
    changes: int
    by_action: dict[str, int]
    items: list[PlanItemOut]


class ApplyIn(BaseModel):
    plan_id: str


class AppliedOut(BaseModel):
    stored: int
    counts: dict[str, int]
    trash: str | None


@router.post("/api/uploads")
async def upload(request: Request, batch: str = Query("", max_length=16)) -> UploadOut:
    """One file in the body; its name, percent-encoded UTF-8, in X-Filename. A new batch unless one is named."""
    context = context_of(request)
    try:
        batch_id, folder = await run_in_threadpool(uploads.batch_folder, context.ws, batch)
    except ValueError as exc:
        raise Problem(400, "upload_batch_invalid", str(exc)) from exc
    name = unquote(request.headers.get("x-filename", ""))
    partial = await run_in_threadpool(uploads.partial_file, folder)
    try:
        size = await _receive(request, partial)
    except BaseException:
        await run_in_threadpool(partial.unlink, True)  # our own partial file, never a document
        raise
    result = await run_in_threadpool(uploads.finish_upload, folder, name, partial, size)
    return UploadOut(batch=batch_id, status=result.status, name=result.name, reason=result.reason)


async def _receive(request: Request, partial: Path) -> int:
    """Write the body into partial, without blocking the event loop; how many bytes came. Past the size limit the
    rest is not stored: finishing refuses the file."""
    size = 0
    out = await run_in_threadpool(partial.open, "wb")
    try:
        async for chunk in request.stream():
            size += len(chunk)
            if size > uploads.MAX_UPLOAD_BYTES:
                break
            await run_in_threadpool(out.write, chunk)
    finally:
        await run_in_threadpool(out.close)
    return size


@router.post("/api/inbox/plan")
def plan(request: Request, body: PlanIn) -> PlanOut:
    """What applying would do, touching nothing."""
    context = context_of(request)
    try:
        if body.upload:
            _, folder = uploads.batch_folder(context.ws, body.upload)
            found = intake.plan_upload(context.ws, folder)
        else:
            found = intake.plan_inbox(context.ws)
    except ValueError as exc:
        raise Problem(400, "plan_invalid", str(exc)) from exc
    context.keep(found)
    changes = found.changes
    by_action: dict[str, int] = {}
    for c in changes:
        label = intake.ACTION_LABELS.get(c.action, c.action)
        by_action[label] = by_action.get(label, 0) + 1
    return PlanOut(
        plan_id=found.id,
        changes=len(changes),
        by_action=by_action,
        items=[PlanItemOut.model_validate(intake.describe(c, context.ws)) for c in changes[:500]],
    )


@router.post("/api/inbox/apply")
def apply(request: Request, body: ApplyIn) -> AppliedOut:
    """Carry out exactly the plan that was shown; a file that changed since makes the user plan again."""
    context: Context = context_of(request)
    found = context.plan(body.plan_id)
    if found is None:
        raise Problem(404, "plan_unknown", "Bu plan artık yok; planı yeniden alın.")
    try:
        done = intake.apply(context.ws, found)
    except StalePlan as exc:
        raise Problem(409, "plan_stale", str(exc)) from exc
    except Busy as exc:
        raise Problem(409, "busy", str(exc)) from exc
    context.forget(body.plan_id)
    return AppliedOut(stored=len(done.stored), counts=dict(done.counts), trash=str(done.trash) if done.trash else None)
