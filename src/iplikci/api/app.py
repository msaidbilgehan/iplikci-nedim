"""The FastAPI application: its routes behind the guard (ADR-0007)."""

from fastapi import FastAPI

from .. import __version__
from . import pages, problems
from .context import Context
from .guard import Guard
from .routes import auth, events, system


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
    for router in (auth.router, system.router, events.router, pages.router):
        app.include_router(router)
    app.add_middleware(Guard, context=context)
    return app
