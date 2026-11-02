"""`iplikci mcp` over stdin and stdout: the transport of a client that starts the server itself (Claude Desktop).

The SDK's stdio transport owns the process's standard streams while it serves: anything else printed (by a library
or a child process) goes to stderr, never into the messages.
"""

import anyio
from mcp.server.stdio import stdio_server

from ..app.workspace import Workspace
from .server import build
from .tools import Session


def serve(ws: Workspace) -> int:
    """Answer the client on stdio until it closes stdin."""
    server = build(Session(ws))

    async def main() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    anyio.run(main)
    return 0
