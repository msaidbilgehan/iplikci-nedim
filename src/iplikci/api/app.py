"""The FastAPI application: its routes behind the guard (ADR-0007)."""

from typing import Any

from fastapi import FastAPI

from .. import __version__
from . import pages, problems
from .context import Context
from .guard import Guard
from .routes import (
    accounts,
    auth,
    backups,
    bridge,
    dashboard,
    documents,
    events,
    exports,
    feed,
    holdings,
    insights,
    invoices,
    mail,
    month_end,
    notify,
    outlook,
    rules,
    service,
    settings,
    spending,
    system,
    todos,
    transactions,
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
    settings,
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


def _routes() -> FastAPI:
    app = FastAPI(
        title="İplikçi Nedim",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    problems.install(app)
    for module in ROUTERS:
        app.include_router(module.router)
    return app


def create_app(context: Context) -> FastAPI:
    app = _routes()
    app.state.context = context
    app.add_middleware(Guard, context=context)
    return app


def openapi_document() -> dict[str, Any]:
    """The API's OpenAPI document, without a service or a data folder: the interface's types come from it."""
    return _routes().openapi()
