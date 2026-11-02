"""The FastAPI application: its routes behind the guard (ADR-0007)."""

from typing import Any

from fastapi import FastAPI

from .. import __version__
from . import pages, problems
from .context import Context
from .guard import Guard
from .routes import (
    auth,
    backups,
    bridge,
    dashboard,
    documents,
    events,
    exports,
    feed,
    insights,
    invoices,
    mail,
    notify,
    outlook,
    rules,
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
