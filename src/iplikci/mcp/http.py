"""MCP over Streamable HTTP at the service's `/mcp` (ADR-0011), behind the gate every request passes (ADR-0007).

Stateless, with JSON answers: each request stands alone, so a client's session outlives a restart of the service (an
update restarts it) and nothing waits on an open stream. The tools need nothing from the client, so a GET (the stream
a server would send its own requests on) is refused with 405, as the protocol lets a server do; the SDK would keep it
open. The gate checks the Host header and the API token before a request reaches this; the SDK's own checks would
repeat them.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from mcp.server.streamable_http_manager import StreamableHTTPASGIApp, StreamableHTTPSessionManager
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from .server import build
from .tools import Session

PATH = "/mcp"


class _Endpoint:
    """MCP's endpoint as an ASGI app (a route calls a bound method with a request instead): the SDK's for POST and
    DELETE, 405 for GET."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["method"] == "GET":
            await Response(status_code=405, headers={"Allow": "POST, DELETE"})(scope, receive, send)
            return
        await self.app(scope, receive, send)


class Transport:
    """The `/mcp` endpoint and the session manager its requests need running (`running`, in the app's lifespan)."""

    def __init__(self, session: Session) -> None:
        self.manager = StreamableHTTPSessionManager(app=build(session), json_response=True, stateless=True)
        self.endpoint = _Endpoint(StreamableHTTPASGIApp(self.manager))

    @asynccontextmanager
    async def running(self) -> AsyncGenerator[None]:
        async with self.manager.run():
            yield
