"""The service in the foreground: the API on 127.0.0.1 at the configured port (ADR-0012: never another address)."""

from collections.abc import Callable

import uvicorn

from ..api.app import create_app
from ..api.context import Context
from ..app import access
from ..app.workspace import Workspace

HOST = "127.0.0.1"


def _say(text: str) -> None:
    print(text, flush=True)  # at once, also when the output goes to a file


def context(ws: Workspace) -> Context:
    """The service's context: the API token made or found, and the expired sessions forgotten."""
    with ws.db() as db:
        access.purge_sessions(db)
    return Context(ws=ws, token=access.ensure_api_token())


def run(ws: Workspace, announce: Callable[[str], None] = _say) -> None:
    """Serve until interrupted. The login link printed at start opens the interface once, within two minutes."""
    ctx = context(ws)
    app = create_app(ctx)
    announce(f"İplikçi Nedim servisi http://{HOST}:{ws.port} adresinde çalışıyor (durdurmak için Ctrl+C).")
    announce(f"Arayüz için tek kullanımlık giriş bağlantısı: {ctx.login_url(ctx.keys.issue())}")
    # No access log: a login link's key would land in it.
    config = uvicorn.Config(app, host=HOST, port=ws.port, access_log=False, log_level="warning", server_header=False)
    uvicorn.Server(config).run()
