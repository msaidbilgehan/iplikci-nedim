"""`iplikci mcp` over stdin and stdout: the transport of a client that starts the server itself (Claude Desktop).

Each message goes to the service while it runs and is answered from the database opened only to read while it is
down, decided anew for every message (`bridge`): the service may start after the client, or stop for an update.
"""

import anyio

from ..app.workspace import Workspace
from . import bridge


def serve(ws: Workspace) -> int:
    """Answer the client on stdio until it closes stdin."""
    anyio.run(bridge.relay, ws)
    return 0
