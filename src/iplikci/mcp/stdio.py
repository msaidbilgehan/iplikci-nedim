"""`iplikci mcp` over stdin and stdout: the transport of a client that starts the server itself (Claude Desktop).

While the service runs, the bridge passes every message to its /mcp (`bridge`): one analysis, one set of plans, the
same answers as the screens. While it is down, the server answers here from the database opened only to read: the
tools that only read work, those that would change something say why they cannot (ADR-0011).

The SDK's stdio transport owns the process's standard streams while it serves: anything else printed (by a library
or a child process) goes to stderr, never into the messages.
"""

import io
import logging
import sys
from dataclasses import replace

import anyio
from mcp.server.stdio import stdio_server

from ..app import access
from ..app.workspace import Workspace
from ..service.client import healthy
from . import bridge
from .server import build
from .tools import Session

_log = logging.getLogger(__name__)


def serve(ws: Workspace) -> int:
    """Answer the client on stdio until it closes stdin: through the service when it runs, else from the database."""
    if healthy(ws.port):
        if access.api_token():
            stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace")
            return bridge.forward(ws, stdin, bridge.claim_stdout())
        _log.warning("the service runs but the API token could not be read: answering from the database")
    return serve_offline(ws)


def serve_offline(ws: Workspace) -> int:
    """The server on the database alone, opened only to read: what would change something is refused."""
    server = build(Session(replace(ws, offline=True), offline=True))

    async def main() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    anyio.run(main)
    return 0
