"""The event log for the feed: a page of events, and the live stream (SSE, F05). A stream opened afresh starts after
the newest event, as what happened before is in what the page loads; its first message, the named `start` event,
carries that event's id, so the browser resumes after it. A stream that breaks off resumes from the last event it
delivered: the browser sends its id back in Last-Event-ID. Beside the events the stream tells, as a named
`notifications` event without an id, that a notification was made or settled: the notifications follow the events by
a moment (ADR-0010), so the event alone would leave the box behind."""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import APIRouter, Query, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from ...app import events, notify
from ..context import Context, context_of
from ..models import EventOut

router = APIRouter()

_HEARTBEAT = 15.0  # seconds between comments that keep an idle stream open
_RETRY_MS = 3000


@router.get("/api/events")
def recent(request: Request, after: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)) -> list[EventOut]:
    return [EventOut(**asdict(e)) for e in events.since(context_of(request).ws, after, limit)]


@router.get("/api/events/stream", response_class=StreamingResponse)
def stream(request: Request, after: int | None = Query(None, ge=0)) -> StreamingResponse:
    resume = request.headers.get("last-event-id", "")
    start = int(resume) if resume.isdigit() else after
    return StreamingResponse(
        _events(context_of(request), start),
        media_type="text/event-stream",
        headers={"x-accel-buffering": "no"},
    )


async def _events(context: Context, after: int | None) -> AsyncIterator[str]:
    yield f"retry: {_RETRY_MS}\n\n"
    if after is None:
        after = await run_in_threadpool(events.newest, context.ws)
        yield f"event: start\nid: {after}\ndata: {after}\n\n"
    deadline = time.monotonic() + context.stream_limit
    quiet_since = time.monotonic()
    told = await run_in_threadpool(notify.version, context.ws)  # the page reads the notifications when it opens
    while True:
        found = await run_in_threadpool(events.since, context.ws, after, 100)
        for event in found:
            after = event.id
            data = json.dumps(asdict(event), ensure_ascii=False, separators=(",", ":"))
            yield f"id: {event.id}\ndata: {data}\n\n"
            quiet_since = time.monotonic()
        version = await run_in_threadpool(notify.version, context.ws)
        if version != told:
            told = version
            yield f"event: notifications\ndata: {version}\n\n"
            quiet_since = time.monotonic()
        now = time.monotonic()
        if now >= deadline:
            return
        if now - quiet_since >= _HEARTBEAT:
            yield ": canlı\n\n"
            quiet_since = now
        if not found or len(found) < 100:
            await asyncio.sleep(min(context.poll, max(0.0, deadline - now)))
