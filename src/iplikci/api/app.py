"""The FastAPI application: its routes behind the guard (ADR-0007)."""

from fastapi import FastAPI

from .. import __version__
from . import pages, problems
from .context import Context
from .guard import Guard
from .routes import auth, backups, bridge, documents, events, mail, system, uploads


def create_app(context: Context) -> FastAPI:
    app = FastAPI(
        title="İplikçi Nedim",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.context = context
    problems.install(app)
    # The interface's pages last: any address no route above takes is a page of the single-page app.
    routers = (auth, system, events, bridge, uploads, backups, mail, documents, pages)
    for module in routers:
        app.include_router(module.router)
    app.add_middleware(Guard, context=context)
    return app
