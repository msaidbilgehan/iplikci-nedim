"""The FastAPI application: its routes behind the guard (ADR-0007), MCP at `/mcp` among them (ADR-0011)."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from starlette.routing import Route

from .. import __version__
from ..mcp import http as mcp_http
from ..mcp.tools import Session
from . import pages, problems
from .context import Context
from .guard import Guard
from .routes import (
    accounts,
    auth,
    backups,
    bridge,
    claude,
    dashboard,
    documents,
    events,
    exports,
    feed,
    holdings,
    insights,
    invoices,
    mail,
    memory,
    month_end,
    notify,
    outlook,
    rates,
    rules,
    service,
    settings,
    spending,
    sync,
    system,
    todos,
    transactions,
    update,
    uploads,
)

# The interface's pages last: any address no route before them takes is a page of the single-page app.
ROUTERS = (
    auth,
    system,
    service,
    events,
    bridge,
    uploads,
    backups,
    exports,
    mail,
    rates,
    update,
    sync,
    settings,
    claude,
    memory,
    documents,
    feed,
    dashboard,
    accounts,
    month_end,
    holdings,
    outlook,
    insights,
    spending,
    invoices,
    notify,
    rules,
    todos,
    transactions,
    pages,
)


def _routes(mcp: mcp_http.Transport | None = None) -> FastAPI:
    """The API's routes; with mcp, its endpoint before the interface's pages (they take every other address) and its
    session manager running for as long as the app does."""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        if mcp is None:
            yield
            return
        async with mcp.running():
            yield

    app = FastAPI(
        title="İplikçi Nedim",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    problems.install(app)
    for module in ROUTERS:
        if module is pages and mcp is not None:
            app.router.routes.append(Route(mcp_http.PATH, mcp.endpoint, methods=["GET", "POST", "DELETE"]))
        app.include_router(module.router)
    return app


def create_app(context: Context) -> FastAPI:
    """The service's app. Its MCP tools read the analysis the screens read: the same question gets the same answer."""
    session = Session(context.ws, context.analysis)
    session.today = context.today
    app = _routes(mcp_http.Transport(session))
    app.state.context = context
    app.add_middleware(Guard, context=context)
    return app


def openapi_document() -> dict[str, Any]:
    """The API's OpenAPI document, without a service or a data folder: the interface's types come from it."""
    return _routes().openapi()
